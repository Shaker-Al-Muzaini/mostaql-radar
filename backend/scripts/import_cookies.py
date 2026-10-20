"""يحوّل كوكيز مصدّرة من متصفحك العادي (إضافة Cookie-Editor، صيغة JSON) إلى ملف جلسة للمشروع.

الاستخدام:
  python scripts/import_cookies.py cookies.json
ثم احذف cookies.json بعدها. الكوكيز تعادل كلمة مرورك، لا تشاركها مع أحد.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402

SAMESITE = {"no_restriction": "None", "none": "None", "lax": "Lax", "strict": "Strict"}


def convert(cookies: list[dict]) -> dict:
    out = []
    for c in cookies:
        if not c.get("name") or "domain" not in c:
            continue
        exp = c.get("expirationDate", c.get("expires", -1))
        out.append({
            "name": c["name"],
            "value": c.get("value", ""),
            "domain": c["domain"],
            "path": c.get("path", "/"),
            "expires": float(exp) if exp not in (None, "", -1) and not c.get("session") else -1,
            "httpOnly": bool(c.get("httpOnly", False)),
            "secure": bool(c.get("secure", False)),
            "sameSite": SAMESITE.get(str(c.get("sameSite", "")).lower(), "Lax"),
        })
    return {"cookies": out, "origins": []}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("الاستخدام: python scripts/import_cookies.py cookies.json")
    raw = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    state = convert(raw)
    if not state["cookies"]:
        sys.exit("لم أجد كوكيز صالحة في الملف.")
    s = get_settings()
    Path(s.session_file).parent.mkdir(parents=True, exist_ok=True)
    Path(s.session_file).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    now = time.time()
    live = [c for c in state["cookies"] if c["expires"] == -1 or c["expires"] > now]
    print(f"تم حفظ {len(state['cookies'])} كوكي ({len(live)} صالح) في: {s.session_file}")
    print("الدومينات:", sorted({c["domain"] for c in state["cookies"]}))