"""بوت تيليجرام عبر long polling (لا يحتاج رابطاً عاماً). يتجاهل أي دردشة غير المصرّح بها."""
import html
import logging
import threading
import time

import httpx
from sqlmodel import Session, select

from . import notify, services
from .config import get_settings
from .db import engine
from .models import Project, Proposal

log = logging.getLogger("radar.bot")
s = get_settings()
_stop = threading.Event()


def _reply(text: str, buttons=None) -> None:
    notify.send_message(text, buttons)


def _line(p: Project) -> str:
    return f"• <b>{p.ai_score if p.ai_score is not None else '—'}</b> — <a href=\"{p.url}\">{html.escape(p.title)}</a> ({notify.money(p)})"


def handle_command(text: str) -> None:
    cmd, _, arg = text.strip().partition(" ")
    cmd = cmd.split("@")[0].lower()
    with Session(engine) as db:
        if cmd in ("/start", "/help"):
            _reply("الأوامر:\n/refresh — تحديث الآن\n/latest — آخر المشاريع\n/top — الأعلى درجة\n"
                   "/search كلمة — بحث\n/stats — إحصاءات\n/draft رقم — مسودة عرض لمشروع")
        elif cmd == "/refresh":
            run = services.start_refresh()
            _reply("⏳ بدأ التحديث… سأرسل لك المشاريع المناسبة." if run else "⚠️ هناك تحديث جارٍ بالفعل.")
        elif cmd == "/latest":
            rows = db.exec(select(Project).order_by(Project.id.desc()).limit(8)).all()
            _reply("\n".join(_line(p) for p in rows) or "لا مشاريع بعد. أرسل /refresh")
        elif cmd == "/top":
            rows = db.exec(select(Project).where(Project.ai_score != None, Project.has_my_proposal == False)  # noqa: E711,E712
                           .order_by(Project.ai_score.desc()).limit(8)).all()
            _reply("\n".join(_line(p) for p in rows) or "لا مشاريع مقيّمة بعد.")
        elif cmd == "/search":
            if not arg:
                return _reply("اكتب: /search كلمة")
            rows = db.exec(select(Project).where(Project.title.contains(arg) | Project.description.contains(arg))
                           .order_by(Project.id.desc()).limit(8)).all()
            _reply("\n".join(_line(p) for p in rows) or "لا نتائج.")
        elif cmd == "/stats":
            st = services.stats(db)
            cats = "، ".join(f"{c} ({n})" for c, n in st["top_categories"]) or "—"
            _reply(f"📊 المشاريع: {st['projects']}\n🎯 قوية (≥{s.notify_threshold}): {st['strong']}\n"
                   f"⭐ متوسط الدرجة: {st['avg_score']}\n💰 متوسط الميزانية: {st['avg_budget']}$\n"
                   f"📝 العروض: {st['proposals_by_status'] or '—'}\n🏷 أكثر التصنيفات: {cats}")
        elif cmd == "/draft":
            if not arg.strip().isdigit():
                return _reply("اكتب: /draft رقم_المشروع")
            _do_draft(db, int(arg))
        else:
            _reply("أمر غير معروف. جرّب /help")


def _do_draft(db: Session, project_id: int) -> None:
    p = db.get(Project, project_id)
    if not p:
        return _reply("المشروع غير موجود.")
    _reply("✍️ جارٍ كتابة المسودة…")
    try:
        pr = services.create_draft(db, p)
        notify.notify_proposal(p, pr)
    except Exception as e:  # noqa: BLE001
        log.exception("فشل توليد المسودة")
        _reply(f"تعذّر توليد المسودة: {html.escape(str(e))[:200]}")


def handle_callback(data: str) -> str:
    action, _, raw = data.partition(":")
    if not raw.isdigit():
        return "؟"
    obj_id = int(raw)
    with Session(engine) as db:
        if action == "draft":
            _do_draft(db, obj_id)
            return "تم"
        if action == "ignore":
            p = db.get(Project, obj_id)
            if p:
                p.status = "ignored"
                db.add(p)
                db.commit()
            return "تم التجاهل"
        pr = db.get(Proposal, obj_id)
        if not pr:
            return "غير موجود"
        if action == "approve":
            services.set_proposal_status(db, pr, "approved")
            p = db.get(Project, pr.project_id)
            _reply(f"✅ اعتُمد. انسخ النص أعلاه وقدّمه يدوياً:\n{p.url}",
                   [[{"text": "📨 تم الإرسال", "callback_data": f"sent:{pr.id}"}]])
            return "تمت الموافقة"
        if action == "reject":
            services.set_proposal_status(db, pr, "rejected")
            return "تم الرفض"
        if action == "sent":
            services.set_proposal_status(db, pr, "sent")
            return "سُجّل كمُرسَل"
    return "؟"


def _answer_callback(cb_id: str, text: str) -> None:
    try:
        notify.tg_call("answerCallbackQuery", callback_query_id=cb_id, text=text)
    except Exception:  # noqa: BLE001
        pass


def _process(update: dict) -> None:
    allowed = str(s.telegram_chat_id)
    if cb := update.get("callback_query"):
        if str(cb["message"]["chat"]["id"]) != allowed:
            return
        _answer_callback(cb["id"], handle_callback(cb.get("data", "")))
    elif msg := update.get("message"):
        if str(msg["chat"]["id"]) != allowed:
            return
        text = msg.get("text", "")
        if text.startswith("/"):
            handle_command(text)


def _loop() -> None:
    offset = None
    while not _stop.is_set():
        try:
            r = httpx.post(
                notify.TG.format(token=s.telegram_bot_token, method="getUpdates"),
                json={"timeout": 30, "offset": offset, "allowed_updates": ["message", "callback_query"]},
                timeout=40,
            )
            for upd in r.json().get("result", []):
                offset = upd["update_id"] + 1
                try:
                    _process(upd)
                except Exception:  # noqa: BLE001
                    log.exception("خطأ في معالجة التحديث")
        except Exception as e:  # noqa: BLE001
            log.warning("polling: %s", e)
            time.sleep(5)


def start() -> None:
    if not (s.telegram_bot_token and s.telegram_chat_id):
        log.info("بوت تيليجرام غير مُعدّ")
        return
    threading.Thread(target=_loop, daemon=True, name="telegram-poll").start()
    log.info("بوت تيليجرام يعمل")


def stop() -> None:
    _stop.set()
