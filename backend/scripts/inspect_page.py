"""يفحص صفحة من مستقل ويعرض ما استخرجه المحلل — لتعديل app/parser.py عند الحاجة.

التشغيل:
  python scripts/inspect_page.py list                 # قائمة المشاريع
  python scripts/inspect_page.py detail <رابط المشروع>
  python scripts/inspect_page.py mine                 # صفحة عروضي (يحتاج جلسة)
يحفظ HTML الخام في data/debug_<kind>.html لتفحصه.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import BACKEND, get_settings  # noqa: E402
from app.parser import parse_detail, parse_list, parse_my_proposals  # noqa: E402
from app.scraper import Scraper  # noqa: E402

s = get_settings()
kind = sys.argv[1] if len(sys.argv) > 1 else "list"
out = BACKEND / "data"
out.mkdir(exist_ok=True)

with Scraper() as sc:
    if kind == "list":
        html = sc._get(f"{s.list_path}?page=1")
        (out / "debug_list.html").write_text(html, encoding="utf-8")
        items = parse_list(html, s.mostaql_base)
        for it in items:
            print(it.mostaql_id, "|", it.title, "|", it.posted_text, "| عروض:", it.proposals_count)
        print(f"\nصفوف project-row في الصفحة: {html.count('project-row')} | المُستخرَج: {len(items)}")
    elif kind == "detail":
        html = sc._get(sys.argv[2])
        (out / "debug_detail.html").write_text(html, encoding="utf-8")
        print(parse_detail(html))
    elif kind == "mine":
        html = sc._get(s.my_proposals_path)
        (out / "debug_mine.html").write_text(html, encoding="utf-8")
        print(sorted(parse_my_proposals(html)))
print("تم. الملف الخام محفوظ في", out)