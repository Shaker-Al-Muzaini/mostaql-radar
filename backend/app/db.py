from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings

_settings = get_settings()
if _settings.database_url.startswith("sqlite:///"):
    Path(_settings.database_url.replace("sqlite:///", "", 1)).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    _settings.database_url,
    connect_args={"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {},
)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
