"""محلل صفحات مستقل. اختُبر على صفحات حية بتاريخ 2026-10-20 (قائمة + تفاصيل).

بنية القائمة: tr.project-row > h2 a (العنوان) و ul.project__meta (الوقت + عدد العروض).
الميزانية غير معروضة في القائمة؛ تُقرأ من صفحة التفاصيل.
إن تغيّر تصميم الموقع استخدم scripts/inspect_page.py وعدّل هنا.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

PROJECT_HREF = re.compile(r"/project/(\d+)")
MONEY = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)")
PROPOSALS = re.compile(r"(?<![\d.])(\d+)\s*(?:عروض|عرض)")
CATEGORY_HREF = re.compile(r"/projects/([^/?#\s]+)")
CHROME_CLASSES = re.compile(r"sidebar|footer|list-links|navbar|menu|breadcrumb", re.I)
BLOCK_TAGS = ("tr", "li", "article")

DESC_SELECTORS = [
    "#project-brief-panel", ".project-post__body", ".text-wrapper-div",
    "[class*=project-brief]", "[class*=project__body]", "article",
]


@dataclass
class ListItem:
    mostaql_id: str
    title: str
    url: str
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    proposals_count: Optional[int] = None
    posted_text: str = ""
    posted_at: Optional[datetime] = None  # بتوقيت UTC (من وسم time)


@dataclass
class Detail:
    title: str = ""
    description: str = ""
    category: str = ""
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    proposals_count: Optional[int] = None
    extra: dict = field(default_factory=dict)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _budget(text: str):
    nums = [float(m.replace(",", "")) for m in MONEY.findall(text)]
    if not nums:
        return None, None
    if len(nums) == 1:
        return nums[0], nums[0]
    return min(nums[:2]), max(nums[:2])


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """وسم time في مستقل يحمل التوقيت بالـ UTC مثل 2026-10-20 06:21:05"""
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value.strip()[:19], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _relative_minutes(text: str) -> Optional[int]:
    """احتياطي إن غاب datetime: «منذ 6 دقائق» ← 6"""
    t = _clean(text)
    if not t.startswith("منذ"):
        return None
    if "ثانية" in t or "ثوان" in t:
        return 0
    n = re.search(r"\d+", t)
    num = int(n.group()) if n else None
    if "دقيقتين" in t:
        return 2
    if "دقيقة" in t or "دقائق" in t:
        return num or 1
    if "ساعتين" in t:
        return 120
    if "ساعة" in t or "ساعات" in t:
        return (num or 1) * 60
    if "يومين" in t:
        return 2880
    if "يوم" in t or "أيام" in t:
        return (num or 1) * 1440
    return None


def _posted_at(time_el) -> Optional[datetime]:
    if time_el is None:
        return None
    dt = _parse_dt(time_el.get("datetime"))
    if dt:
        return dt
    mins = _relative_minutes(time_el.get_text(" "))
    return datetime.now(timezone.utc) - timedelta(minutes=mins) if mins is not None else None


def _proposals(text: str) -> Optional[int]:
    m = PROPOSALS.search(MONEY.sub(" ", text))  # نزيل المبالغ كي لا تُقرأ كعدد عروض
    return int(m.group(1)) if m else None


def _container(anchor):
    node = anchor
    for _ in range(8):
        node = node.parent
        if node is None:
            break
        if node.name in BLOCK_TAGS:
            return node
        cls = " ".join(node.get("class", [])) if node.name == "div" else ""
        if "project" in cls and PROJECT_HREF.search(str(node)):
            return node
    return anchor.parent


def _parse_list_by_rows(soup: BeautifulSoup, base: str) -> list[ListItem]:
    items: dict[str, ListItem] = {}
    for row in soup.select("tr.project-row"):
        a = row.select_one("h2 a[href]") or row.find("a", href=PROJECT_HREF)
        if not a:
            continue
        m = PROJECT_HREF.search(a["href"])
        title = _clean(a.get_text())
        if not m or len(title) < 2 or m.group(1) in items:
            continue
        meta = row.select_one("ul.project__meta")
        meta_text = _clean(meta.get_text(" ")) if meta else ""
        time_el = row.find("time")
        bmin, bmax = _budget(meta_text)
        items[m.group(1)] = ListItem(
            mostaql_id=m.group(1),
            title=title,
            url=urljoin(base, a["href"].split("?")[0]),
            budget_min=bmin,
            budget_max=bmax,
            proposals_count=_proposals(meta_text),
            posted_text=_clean(time_el.get_text(" ")) if time_el else "",
            posted_at=_posted_at(time_el),
        )
    return list(items.values())


def _parse_list_by_links(soup: BeautifulSoup, base: str) -> list[ListItem]:
    """احتياطي إن تغيّرت بنية الصفوف: يعتمد على روابط /project/<id> فقط."""
    seen: dict[str, ListItem] = {}
    for a in soup.find_all("a", href=PROJECT_HREF):
        pid = PROJECT_HREF.search(a["href"]).group(1)
        title = _clean(a.get_text())
        if pid in seen or len(title) < 4:
            continue
        box = _container(a)
        text = _clean(box.get_text(" ")) if box else ""
        time_el = box.find("time") if box else None
        bmin, bmax = _budget(text)
        seen[pid] = ListItem(
            mostaql_id=pid, title=title, url=urljoin(base, a["href"].split("?")[0]),
            budget_min=bmin, budget_max=bmax, proposals_count=_proposals(text),
            posted_text=_clean(time_el.get_text(" ")) if time_el else "",
            posted_at=_posted_at(time_el),
        )
    return list(seen.values())


def parse_list(html: str, base: str) -> list[ListItem]:
    soup = BeautifulSoup(html, "lxml")
    return _parse_list_by_rows(soup, base) or _parse_list_by_links(soup, base)


def _category(soup: BeautifulSoup) -> str:
    # 1) نص «التصنيف» ثم أقرب رابط قسم بعده
    for label in soup.find_all(string=re.compile(r"^\s*التصنيف\s*:?\s*$")):
        a = label.find_parent().find_next("a", href=CATEGORY_HREF)
        if a and _clean(a.get_text()):
            return _clean(a.get_text())
    # 2) أول رابط قسم خارج القوائم الجانبية والتذييل والقوائم العامة
    for a in soup.find_all("a", href=CATEGORY_HREF):
        if a.find_parent(["footer", "nav", "header"]) or a.find_parent(class_=CHROME_CLASSES):
            continue
        if a.get("class") and any(CHROME_CLASSES.search(c) for c in a["class"]):
            continue
        if _clean(a.get_text()):
            return _clean(a.get_text())
    return ""


def parse_detail(html: str) -> Detail:
    soup = BeautifulSoup(html, "lxml")
    d = Detail()
    h1 = soup.find("h1")
    d.title = _clean(h1.get_text()) if h1 else ""
    for sel in DESC_SELECTORS:
        el = soup.select_one(sel)
        if el and len(_clean(el.get_text())) > 40:
            d.description = _clean(el.get_text(" "))
            break
    if not d.description:
        meta = soup.find("meta", attrs={"property": "og:description"}) or soup.find(
            "meta", attrs={"name": "description"}
        )
        d.description = _clean(meta["content"]) if meta and meta.get("content") else ""
    d.category = _category(soup)
    d.budget_min, d.budget_max = _budget(_clean(soup.get_text(" "))[:3000])
    return d


def parse_my_proposals(html: str) -> set[str]:
    """معرّفات المشاريع التي قدّمت عليها (أي رابط /project/<id> في صفحة عروضي)."""
    return set(PROJECT_HREF.findall(html))


def looks_blocked(html: str) -> bool:
    low = html.lower()
    return any(s in low for s in ("just a moment", "cf-challenge", "captcha", "attention required"))


def looks_logged_out(html: str) -> bool:
    low = html.lower()
    return 'href="/login"' in low and "logout" not in low and "تسجيل الخروج" not in html