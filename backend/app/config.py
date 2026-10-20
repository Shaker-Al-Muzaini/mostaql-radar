from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]  # مجلد المشروع
BACKEND = ROOT / "backend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    # عام
    api_key: str = ""  # إن وُضع، تُطلب الترويسة X-API-Key في كل طلب /api
    database_url: str = f"sqlite:///{BACKEND / 'data' / 'radar.db'}"
    cors_origins: str = "http://localhost:5173"

    # مستقل / السحب
    mostaql_base: str = "https://mostaql.com"
    list_path: str = "/projects?category=development,ai-machine-learning&sort=latest"
    my_proposals_path: str = "/dashboard/bids"  # عدّله إن اختلف عندك
    session_file: str = str(BACKEND / "data" / "mostaql_session.json")
    max_list_pages: int = 1
    max_detail_fetch: int = 15
    delay_min: float = 3.0
    delay_max: float = 7.0
    headless: bool = True
    auto_refresh: bool = True
    refresh_interval_min: int = 3  # فترة الفحص بالدقائق
    min_interval_min: int = 2  # حد أدنى لحماية الحساب من الحظر
    show_minutes: int = 10  # مدة بقاء المشروع في الصفحة
    keep_hours: int = 24  # بعدها يُحذف من القاعدة (تبقى أزرار تيليجرام صالحة حتى ذلك الحين)
    max_recent: int = 5  # أقصى عدد مشاريع في الصفحة
    fresh_window_min: int = 45  # المشروع المنشور قبل أكثر من هذا لا يُعدّ «جديداً»

    # الذكاء الاصطناعي
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    max_ai_per_refresh: int = 20
    notify_threshold: int = 70
    max_notify_per_refresh: int = 8

    # تيليجرام + n8n
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    n8n_webhook_url: str = ""  # مثال: http://localhost:5678/webhook/mostaql-notify
    n8n_shared_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
