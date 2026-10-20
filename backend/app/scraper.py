"""سحب مهذّب عبر Playwright (متزامن، يُشغَّل داخل خيط منفصل)."""
import random
import time
from pathlib import Path

from .config import get_settings
from .parser import ListItem, looks_blocked, parse_detail, parse_list, parse_my_proposals, Detail

s = get_settings()


class BlockedError(RuntimeError):
    pass


class Scraper:
    def __init__(self):
        self._pw = None
        self._browser = None
        self.ctx = None
        self.has_session = Path(s.session_file).exists()

    def __enter__(self):
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=s.headless)
        kwargs = {"locale": "ar", "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")}
        if self.has_session:
            kwargs["storage_state"] = s.session_file
        self.ctx = self._browser.new_context(**kwargs)
        return self

    def __exit__(self, *exc):
        for obj in (self.ctx, self._browser):
            try:
                obj and obj.close()
            except Exception:
                pass
        if self._pw:
            self._pw.stop()

    def _pause(self):
        time.sleep(random.uniform(s.delay_min, s.delay_max))

    def _get(self, path_or_url: str) -> str:
        url = path_or_url if path_or_url.startswith("http") else s.mostaql_base + path_or_url
        page = self.ctx.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(1200)
            html = page.content()
        finally:
            page.close()
        if looks_blocked(html):
            raise BlockedError(f"واجهنا حاجز حماية (Cloudflare/CAPTCHA) عند {url}. افتح الموقع يدوياً وأعد حفظ الجلسة.")
        return html

    def list_projects(self) -> list[ListItem]:
        items: dict[str, ListItem] = {}
        for page_no in range(1, s.max_list_pages + 1):
            sep = "&" if "?" in s.list_path else "?"
            html = self._get(f"{s.list_path}{sep}page={page_no}")
            for it in parse_list(html, s.mostaql_base):
                items.setdefault(it.mostaql_id, it)
            self._pause()
        return list(items.values())

    def project_detail(self, url: str) -> Detail:
        html = self._get(url)
        self._pause()
        return parse_detail(html)

    def my_proposal_ids(self) -> set[str] | None:
        """None = لا توجد جلسة دخول (تُتخطى هذه الخطوة)."""
        if not self.has_session:
            return None
        html = self._get(s.my_proposals_path)
        self._pause()
        return parse_my_proposals(html)
