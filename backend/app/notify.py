"""إرسال الرسائل: عبر n8n (Webhook) وإن تعطّل فمباشرة إلى تيليجرام."""
import html
import logging

import httpx

from .config import get_settings
from .models import Project, Proposal

log = logging.getLogger("radar.notify")
s = get_settings()
TG = "https://api.telegram.org/bot{token}/{method}"


def tg_call(method: str, **payload) -> dict:
    r = httpx.post(TG.format(token=s.telegram_bot_token, method=method), json=payload, timeout=40)
    r.raise_for_status()
    return r.json()


def send_message(text: str, buttons: list[list[dict]] | None = None, chat_id: str | None = None) -> None:
    """buttons: [[{"text": "...", "callback_data": "..."} | {"text": "...", "url": "..."}]]"""
    chat = chat_id or s.telegram_chat_id
    if not (s.telegram_bot_token and chat):
        log.info("تيليجرام غير مُعدّ، تخطي الإرسال")
        return
    payload = {
        "chat_id": chat, "text": text[:4000], "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}
    if s.n8n_webhook_url:
        try:
            r = httpx.post(
                s.n8n_webhook_url,
                json={"secret": s.n8n_shared_secret, "telegram": payload},
                timeout=20,
            )
            r.raise_for_status()
            return
        except Exception as e:  # noqa: BLE001
            log.warning("n8n غير متاح (%s) — إرسال مباشر", e)
    tg_call("sendMessage", **payload)


def money(p: Project) -> str:
    if p.budget_min is None:
        return "غير محددة"
    if p.budget_min == p.budget_max:
        return f"{p.budget_min:g}$"
    return f"{p.budget_min:g}–{p.budget_max:g}$"


def project_message(p: Project):
    e = html.escape
    score = p.ai_score if p.ai_score is not None else "—"
    text = (
        f"🎯 <b>مشروع مناسب ({score}/100)</b>\n{e(p.title)}\n"
        f"💰 {money(p)} · 📩 {p.proposals_count if p.proposals_count is not None else '—'} عروض"
        f"{' · 🏷 ' + e(p.category) if p.category else ''}\n\n{e(p.ai_summary)}"
    )
    buttons = [[
        {"text": "✍️ اكتب عرضاً", "callback_data": f"draft:{p.id}"},
        {"text": "🔗 افتح", "url": p.url},
        {"text": "🙈 تجاهل", "callback_data": f"ignore:{p.id}"},
    ]]
    return text, buttons


def notify_project(p: Project) -> None:
    send_message(*project_message(p))


def notify_proposal(p: Project, pr: Proposal) -> None:
    e = html.escape
    text = (
        f"📝 <b>مسودة عرض</b> — {e(p.title)}\n"
        f"💵 {pr.bid_amount if pr.bid_amount else '—'}$ · ⏱ {pr.duration_days or '—'} يوم\n\n{e(pr.draft_text)}"
    )
    buttons = [[
        {"text": "✅ موافقة", "callback_data": f"approve:{pr.id}"},
        {"text": "❌ رفض", "callback_data": f"reject:{pr.id}"},
        {"text": "🔄 إعادة", "callback_data": f"draft:{p.id}"},
    ], [{"text": "🔗 افتح المشروع", "url": p.url}]]
    send_message(text, buttons)
