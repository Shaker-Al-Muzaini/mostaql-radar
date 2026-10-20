"""يفتح نافذة متصفح لتسجّل دخولك يدوياً في مستقل، ثم يحفظ الجلسة (cookies) محلياً.
لا تُخزَّن كلمة المرور في أي مكان.

التشغيل:  python scripts/save_session.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright  # noqa: E402

from app.config import get_settings  # noqa: E402

s = get_settings()
Path(s.session_file).parent.mkdir(parents=True, exist_ok=True)

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=False)
    ctx = browser.new_context(locale="ar")
    page = ctx.new_page()
    page.goto(s.mostaql_base + "/login")
    input("سجّل الدخول في النافذة (وحل أي تحقق). عند ظهور حسابك اضغط Enter هنا… ")
    ctx.storage_state(path=s.session_file)
    browser.close()
print("تم حفظ الجلسة في:", s.session_file)
