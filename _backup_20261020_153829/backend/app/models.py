from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now(timezone.utc)


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    mostaql_id: str = Field(index=True, unique=True)
    title: str
    url: str
    description: str = ""
    category: str = ""
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    proposals_count: Optional[int] = None
    posted_text: str = ""
    status: str = "new"  # new | seen | applied | ignored
    has_my_proposal: bool = False
    detail_fetched: bool = False
    ai_score: Optional[int] = Field(default=None, index=True)
    ai_summary: str = ""
    ai_reason: str = ""
    notified: bool = False
    first_seen_at: datetime = Field(default_factory=now)


class Proposal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    draft_text: str = ""
    status: str = "draft"  # draft | approved | sent | rejected
    bid_amount: Optional[float] = None
    duration_days: Optional[int] = None
    created_at: datetime = Field(default_factory=now)


class RefreshRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    status: str = "running"  # running | done | error
    stage: str = ""
    new_count: int = 0
    notified_count: int = 0
    error: str = ""
    started_at: datetime = Field(default_factory=now)
    finished_at: Optional[datetime] = None
