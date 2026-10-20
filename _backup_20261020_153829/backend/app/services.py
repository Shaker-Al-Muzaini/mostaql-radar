"""منطق العمل: التحديث، التقييم، المسودات."""
import logging
import threading

from sqlmodel import Session, select

from . import ai, notify
from .config import get_settings
from .db import engine
from .models import Project, Proposal, RefreshRun, now

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
                    items = sc.list_projects()
                    known = set(db.exec(select(Project.mostaql_id)).all())
                    fresh = [i for i in items if i.mostaql_id not in known]
                    run.new_count = len(fresh)
                    for it in fresh:
                        db.add(Project(
                            mostaql_id=it.mostaql_id, title=it.title, url=it.url,
                            budget_min=it.budget_min, budget_max=it.budget_max,
                            proposals_count=it.proposals_count, posted_text=it.posted_text,
                        ))
                    db.commit()

                    new_projects = db.exec(
                        select(Project).where(Project.detail_fetched == False)  # noqa: E712
                        .order_by(Project.id.desc()).limit(s.max_detail_fetch)
                    ).all()
                    for i, p in enumerate(new_projects, 1):
                        _stage(db, run, f"تفاصيل المشاريع ({i}/{len(new_projects)})")
                        d = sc.project_detail(p.url)
                        p.description = d.description or p.description
                        p.category = d.category or p.category
                        p.budget_min = d.budget_min if d.budget_min is not None else p.budget_min
                        p.budget_max = d.budget_max if d.budget_max is not None else p.budget_max
                        p.detail_fetched = True
                        db.add(p)
                        db.commit()

                    _stage(db, run, "مزامنة عروضي")
                    mine = sc.my_proposal_ids()
                    if mine:
                        for p in db.exec(select(Project).where(Project.mostaql_id.in_(mine))).all():
                            p.has_my_proposal = True
                            p.status = "applied"
                            db.add(p)
                        db.commit()

                _stage(db, run, "التقييم بالذكاء الاصطناعي")
                to_score = db.exec(
                    select(Project).where(Project.ai_score == None, Project.has_my_proposal == False)  # noqa: E711,E712
                    .order_by(Project.id.desc()).limit(s.max_ai_per_refresh)
                ).all()
                for p in to_score:
                    r = ai.score_project(p)
                    p.ai_score = r["score"]
                    p.ai_summary = r.get("summary", "")
                    p.ai_reason = r.get("reason", "")
                    p.category = p.category or r.get("category", "")
                    db.add(p)
                db.commit()

                _stage(db, run, "إرسال الإشعارات")
                hot = db.exec(
                    select(Project).where(
                        Project.notified == False, Project.ai_score >= s.notify_threshold,  # noqa: E712
                        Project.has_my_proposal == False,
                    ).order_by(Project.ai_score.desc()).limit(s.max_notify_per_refresh)
                ).all()
                for p in hot:
                    notify.notify_project(p)
                    p.notified = True
                    db.add(p)
                run.notified_count = len(hot)
                run.status, run.stage, run.finished_at = "done", "اكتمل", now()
            except Exception as e:  # noqa: BLE001
                log.exception("فشل التحديث")
                run.status, run.error, run.finished_at = "error", str(e)[:500], now()
            db.add(run)
            db.commit()
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
