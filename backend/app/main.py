import logging
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session, select

from . import notify, scheduler, services, telegram_bot
from .config import get_settings
from .db import get_session, init_db
from .models import Project, Proposal, RefreshRun

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
s = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    telegram_bot.start()
    scheduler.start()
    yield
    scheduler.stop()
    telegram_bot.stop()


app = FastAPI(title="Mostaql Radar", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=[o.strip() for o in s.cors_origins.split(",")],
    allow_methods=["*"], allow_headers=["*"],
)


def check_key(x_api_key: str = Header(default="")):
    if s.api_key and x_api_key != s.api_key:
        raise HTTPException(401, "مفتاح API غير صحيح")


api = APIRouter(prefix="/api", dependencies=[Depends(check_key)])


class ProjectPatch(BaseModel):
    status: str


class ProposalPatch(BaseModel):
    draft_text: Optional[str] = None
    bid_amount: Optional[float] = None
    duration_days: Optional[int] = None
    status: Optional[str] = None


@app.get("/health")
def health():
    return {"ok": True, "gemini": bool(s.gemini_api_key), "telegram": bool(s.telegram_bot_token), "n8n": bool(s.n8n_webhook_url)}


@api.get("/projects")
def list_projects(
    q: str = "", category: str = "", min_score: int = 0, min_budget: float = 0,
    status: str = "", hide_applied: bool = False,
    limit: int = Query(50, le=200), offset: int = 0, db: Session = Depends(get_session),
):
    stmt = select(Project)
    if q:
        stmt = stmt.where(Project.title.contains(q) | Project.description.contains(q))
    if category:
        stmt = stmt.where(Project.category == category)
    if min_score:
        stmt = stmt.where(Project.ai_score >= min_score)
    if min_budget:
        stmt = stmt.where(Project.budget_max >= min_budget)
    if status:
        stmt = stmt.where(Project.status == status)
    if hide_applied:
        stmt = stmt.where(Project.has_my_proposal == False)  # noqa: E712
    rows = db.exec(stmt.order_by(Project.id.desc()).offset(offset).limit(limit)).all()
    return rows


@api.get("/recent")
def recent(db: Session = Depends(get_session)):
    """آخر المشاريع ضمن نافذة العرض فقط (الأحدث أولاً، حد أقصى max_recent)."""
    n = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = db.exec(
        select(Project)
        .where(Project.first_seen_at >= n - timedelta(minutes=s.show_minutes), Project.status != "ignored")
        .order_by(Project.first_seen_at.desc()).limit(s.max_recent)
    ).all()
    items = []
    for p in rows:
        born = p.first_seen_at.replace(tzinfo=None)
        left = int((born + timedelta(minutes=s.show_minutes) - n).total_seconds())
        items.append({
            "id": p.id, "mostaql_id": p.mostaql_id, "title": p.title, "url": p.url,
            "category": p.category, "budget_min": p.budget_min, "budget_max": p.budget_max,
            "proposals_count": p.proposals_count, "posted_text": p.posted_text,
            "ai_score": p.ai_score, "ai_summary": p.ai_summary,
            "seconds_left": max(left, 0), "total_seconds": s.show_minutes * 60,
        })
    return {
        "items": items, "show_minutes": s.show_minutes, "running": services.is_running(),
        "interval_min": max(s.min_interval_min, s.refresh_interval_min),
    }


@api.get("/categories")
def categories(db: Session = Depends(get_session)):
    return sorted({c for c in db.exec(select(Project.category)).all() if c})


@api.get("/projects/{pid}")
def get_project(pid: int, db: Session = Depends(get_session)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "غير موجود")
    if p.status == "new":
        p.status = "seen"
        db.add(p)
        db.commit()
        db.refresh(p)
    return p


@api.patch("/projects/{pid}")
def patch_project(pid: int, body: ProjectPatch, db: Session = Depends(get_session)):
    if body.status not in {"new", "seen", "applied", "ignored"}:
        raise HTTPException(422, "حالة غير صالحة")
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "غير موجود")
    p.status = body.status
    db.add(p)
    db.commit()
    return p


@api.post("/projects/{pid}/draft")
def draft(pid: int, db: Session = Depends(get_session)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "غير موجود")
    try:
        return services.create_draft(db, p)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"تعذّر توليد المسودة: {e}") from e


@api.get("/proposals")
def list_proposals(status: str = "", db: Session = Depends(get_session)):
    stmt = select(Proposal, Project).join(Project, Project.id == Proposal.project_id)
    if status:
        stmt = stmt.where(Proposal.status == status)
    out = []
    for pr, pj in db.exec(stmt.order_by(Proposal.id.desc())).all():
        out.append({**pr.model_dump(), "project_title": pj.title, "project_url": pj.url})
    return out


@api.patch("/proposals/{pid}")
def patch_proposal(pid: int, body: ProposalPatch, db: Session = Depends(get_session)):
    pr = db.get(Proposal, pid)
    if not pr:
        raise HTTPException(404, "غير موجود")
    if body.status and body.status not in {"draft", "approved", "sent", "rejected"}:
        raise HTTPException(422, "حالة غير صالحة")
    for field in ("draft_text", "bid_amount", "duration_days"):
        v = getattr(body, field)
        if v is not None:
            setattr(pr, field, v)
    db.add(pr)
    db.commit()
    if body.status:
        services.set_proposal_status(db, pr, body.status)
    db.refresh(pr)
    return pr


@api.post("/proposals/{pid}/telegram")
def proposal_to_telegram(pid: int, db: Session = Depends(get_session)):
    pr = db.get(Proposal, pid)
    if not pr:
        raise HTTPException(404, "غير موجود")
    notify.notify_proposal(db.get(Project, pr.project_id), pr)
    return {"ok": True}


@api.post("/refresh", status_code=202)
def refresh():
    run_id = services.start_refresh()
    if run_id is None:
        raise HTTPException(409, "هناك تحديث جارٍ بالفعل")
    return {"run_id": run_id}


@api.get("/refresh/status")
def refresh_status(db: Session = Depends(get_session)):
    run = db.exec(select(RefreshRun).order_by(RefreshRun.id.desc())).first()
    return {"running": services.is_running(), "run": run}


@api.get("/stats")
def get_stats(db: Session = Depends(get_session)):
    return services.stats(db)


app.include_router(api)
