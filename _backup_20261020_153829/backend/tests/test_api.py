import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["GEMINI_API_KEY"] = ""
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["API_KEY"] = "k"
os.environ["AUTO_REFRESH"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app import services  # noqa: E402
from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Project  # noqa: E402
from app.parser import Detail, ListItem  # noqa: E402

H = {"X-API-Key": "k"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def seed():
    with Session(engine) as db:
        for i, (t, score) in enumerate([("بوت تيليجرام وأتمتة n8n", 90), ("تصميم لوجو", 20)], start=1):
            db.add(Project(mostaql_id=str(i), title=t, url=f"https://mostaql.com/project/{i}",
                           description=t, category="برمجة" if i == 1 else "تصميم",
                           budget_min=50, budget_max=200, ai_score=score))
        db.commit()


def test_auth_required(client):
    assert client.get("/api/projects").status_code == 401
    assert client.get("/health").status_code == 200


def test_filters_and_status(client):
    seed()
    assert len(client.get("/api/projects", headers=H).json()) == 2
    hi = client.get("/api/projects?min_score=70", headers=H).json()
    assert [p["title"] for p in hi] == ["بوت تيليجرام وأتمتة n8n"]
    assert len(client.get("/api/projects?q=لوجو", headers=H).json()) == 1
    assert client.get("/api/categories", headers=H).json() == ["برمجة", "تصميم"]
    pid = hi[0]["id"]
    assert client.get(f"/api/projects/{pid}", headers=H).json()["status"] == "seen"
    assert client.patch(f"/api/projects/{pid}", json={"status": "zzz"}, headers=H).status_code == 422


def test_proposal_lifecycle(client):
    pid = client.get("/api/projects?min_score=70", headers=H).json()[0]["id"]
    pr = client.post(f"/api/projects/{pid}/draft", headers=H).json()  # بدون Gemini: قالب احتياطي
    assert pr["status"] == "draft" and pr["draft_text"]
    r = client.patch(f"/api/proposals/{pr['id']}", json={"draft_text": "نص معدّل", "status": "sent"}, headers=H).json()
    assert r["status"] == "sent" and r["draft_text"] == "نص معدّل"
    assert client.get(f"/api/projects/{pid}", headers=H).json()["has_my_proposal"] is True
    rows = client.get("/api/proposals?status=sent", headers=H).json()
    assert rows and rows[0]["project_title"]
    assert client.get("/api/stats", headers=H).json()["projects"] == 2


def test_refresh_pipeline_with_fake_scraper(client, monkeypatch):
    sent = []
    monkeypatch.setattr("app.notify.send_message", lambda text, buttons=None, chat_id=None: sent.append(text))

    class Fake:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def list_projects(self):
            return [ListItem("100", "أتمتة وسحب بيانات بـ n8n و fastapi", "https://mostaql.com/project/100", 100, 300, 2)]
        def project_detail(self, url):
            return Detail(description="نحتاج scraping و أتمتة عبر n8n وبوت تيليجرام و api", category="برمجة")
        def my_proposal_ids(self): return None

    monkeypatch.setattr("app.scraper.Scraper", Fake)
    run_id = services.start_refresh()
    assert run_id
    import time
    for _ in range(50):
        st = client.get("/api/refresh/status", headers=H).json()
        if not st["running"]:
            break
        time.sleep(0.1)
    assert st["run"]["status"] == "done", st
    assert st["run"]["new_count"] == 1 and st["run"]["notified_count"] == 1
    assert len(sent) == 1 and "مشروع مناسب" in sent[0]
