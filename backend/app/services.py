"""منطق العمل: التحديث، التقييم، المسودات."""
import logging
import threading
from datetime import timedelta

from sqlmodel import Session, select

from . import ai, notify
from .config import get_settings
from .db import engine
from .models import Project, Proposal, RefreshRun, SeenProject, now
from .scraper import BlockedError

log = logging.getLogger("radar.services")
s = get_settings()
_lock = threading.Lock()


def is_running() -> bool:
    return _lock.locked()


def start_refresh() -> int | None:
    """يبدأ تحديثاً في خيط خلفي. يعيد None إن كان هناك تحديث جارٍ."""
    if _lock.locked():
        return None
    with Session(engine) as db:
        run = RefreshRun()
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id
    threading.Thread(target=_refresh_worker, args=(run_id,), daemon=True).start()
    return run_id


def _stage(db: Session, run: RefreshRun, stage: str) -> None:
    run.stage = stage
    db.add(run)
    db.commit()


def _pick_fresh(db: Session, items) -> list:
    """يفصل الجديد فعلاً عن المعروف. غير الجديد يُسجَّل «مرئياً» بصمت دون إشعار."""
    known = set(db.exec(select(SeenProject.mostaql_id)).all())
    known |= set(db.exec(select(Project.mostaql_id)).all())
    first_run = not known
    cutoff = now() - timedelta(minutes=s.fresh_window_min)
    fresh = []
    for it in items:
        if it.mostaql_id in known:
            continue
        at = getattr(it, "posted_at", None)
        is_fresh = (not first_run) if at is None else at >= cutoff
        if is_fresh:
            fresh.append(it)
        else:
            db.add(SeenProject(mostaql_id=it.mostaql_id))
    db.commit()
    fresh.sort(key=lambda i: getattr(i, "posted_at", None) or cutoff, reverse=True)
    return fresh[: s.max_detail_fetch]


def _process_item(db: Session, sc, it, notified_so_far: int) -> int:
    """مشروع جديد واحد: حفظ، تفاصيل، تقييم، ثم إشعار فوري. يعيد 1 إن أُرسل إشعار."""
    db.add(SeenProject(mostaql_id=it.mostaql_id))
    p = Project(
        mostaql_id=it.mostaql_id, title=it.title, url=it.url,
        budget_min=it.budget_min, budget_max=it.budget_max,
        proposals_count=it.proposals_count, posted_text=it.posted_text,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    try:
        d = sc.project_detail(p.url)
        p.description = d.description or p.description
        p.category = d.category or p.category
        p.budget_min = d.budget_min if d.budget_min is not None else p.budget_min
        p.budget_max = d.budget_max if d.budget_max is not None else p.budget_max
        p.detail_fetched = True
    except BlockedError:
        raise
    except Exception:  # noqa: BLE001
        log.exception("تعذّر جلب تفاصيل %s", p.url)
    try:
        r = ai.score_project(p)
    except Exception:  # noqa: BLE001
        log.exception("فشل التقييم، استخدام التقييم الاحتياطي")
        r = ai.fallback_score(p)
    p.ai_score = r["score"]
    p.ai_summary = r.get("summary", "")
    p.ai_reason = r.get("reason", "")
    p.category = p.category or r.get("category", "")
    db.add(p)
    db.commit()
    if p.ai_score >= s.notify_threshold and notified_so_far < s.max_notify_per_refresh:
        try:
            notify.notify_project(p)
            p.notified = True
            db.add(p)
            db.commit()
            return 1
        except Exception:  # noqa: BLE001
            log.exception("فشل إرسال الإشعار")
    return 0


def purge_old(db: Session) -> None:
    """حذف المشاريع الأقدم من keep_hours (إلا ما له مسودة عرض)، مع تذكّر أرقامها."""
    cut = now() - timedelta(hours=s.keep_hours)
    with_proposal = set(db.exec(select(Proposal.project_id)).all())
    seen = set(db.exec(select(SeenProject.mostaql_id)).all())
    for p in db.exec(select(Project).where(Project.first_seen_at < cut)).all():
        if p.id in with_proposal:
            continue
        if p.mostaql_id not in seen:
            db.add(SeenProject(mostaql_id=p.mostaql_id))
        db.delete(p)
    for x in db.exec(select(SeenProject).where(SeenProject.seen_at < now() - timedelta(days=7))).all():
        db.delete(x)
    db.commit()


def _refresh_worker(run_id: int) -> None:
    if not _lock.acquire(blocking=False):
        return
    try:
        from .scraper import Scraper

        with Session(engine) as db:
            run = db.get(RefreshRun, run_id)
            try:
                with Scraper() as sc:
                    _stage(db, run, "سحب قائمة المشاريع")
                    fresh = _pick_fresh(db, sc.list_projects())
                    run.new_count = len(fresh)
                    notified = 0
                    for i, it in enumerate(fresh, 1):
                        _stage(db, run, f"معالجة مشروع جديد ({i}/{len(fresh)})")
                        notified += _process_item(db, sc, it, notified)
                    run.notified_count = notified
                run.status, run.stage, run.finished_at = "done", "اكتمل", now()
            except Exception as e:  # noqa: BLE001
                log.exception("فشل التحديث")
                run.status, run.error, run.finished_at = "error", str(e)[:500], now()
            db.add(run)
            db.commit()
            try:
                purge_old(db)
            except Exception:  # noqa: BLE001
                log.exception("فشل التنظيف الدوري")
    finally:
        _lock.release()


def create_draft(db: Session, project: Project) -> Proposal:
    d = ai.draft_proposal(project)
    pr = Proposal(
        project_id=project.id, draft_text=d["text"],
        bid_amount=d.get("bid_amount"), duration_days=d.get("duration_days"),
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    return pr


def set_proposal_status(db: Session, pr: Proposal, status: str) -> Proposal:
    pr.status = status
    db.add(pr)
    if status == "sent":
        proj = db.get(Project, pr.project_id)
        if proj:
            proj.status, proj.has_my_proposal = "applied", True
            db.add(proj)
    db.commit()
    db.refresh(pr)
    return pr


def stats(db: Session) -> dict:
    projects = db.exec(select(Project)).all()
    scored = [p.ai_score for p in projects if p.ai_score is not None]
    budgets = [p.budget_max for p in projects if p.budget_max]
    props = db.exec(select(Proposal)).all()
    by_status: dict[str, int] = {}
    for pr in props:
        by_status[pr.status] = by_status.get(pr.status, 0) + 1
    cats: dict[str, int] = {}
    for p in projects:
        if p.category:
            cats[p.category] = cats.get(p.category, 0) + 1
    return {
        "projects": len(projects),
        "strong": sum(1 for x in scored if x >= s.notify_threshold),
        "avg_score": round(sum(scored) / len(scored), 1) if scored else None,
        "avg_budget": round(sum(budgets) / len(budgets), 1) if budgets else None,
        "proposals_by_status": by_status,
        "top_categories": sorted(cats.items(), key=lambda kv: -kv[1])[:5],
    }
