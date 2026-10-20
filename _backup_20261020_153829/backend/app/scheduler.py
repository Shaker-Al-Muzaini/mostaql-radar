"""تحديث تلقائي دوري: يشغّل دورة التحديث كل N دقيقة دون أي ضغط زر.
بعد كل دورة يُرسَل الجديد إلى n8n (انظر services._refresh_worker) ومنه إلى تيليجرام."""
import logging
import random
import threading

from . import services
from .config import get_settings

log = logging.getLogger("radar.scheduler")
s = get_settings()
_stop = threading.Event()


def _loop() -> None:
    _stop.wait(10)  # مهلة قصيرة بعد تشغيل الخادم
    while not _stop.is_set():
        try:
            if services.start_refresh() is None:
                log.info("تحديث سابق ما زال جارياً، تخطي هذه الدورة")
            else:
                log.info("بدأ التحديث التلقائي")
        except Exception:  # noqa: BLE001
            log.exception("فشل بدء التحديث التلقائي")
        minutes = max(5, s.refresh_interval_min)  # حد أدنى 5 دقائق لتجنب الحظر
        _stop.wait(minutes * 60 * random.uniform(0.9, 1.2))


def start() -> None:
    if not s.auto_refresh:
        log.info("التحديث التلقائي معطّل (AUTO_REFRESH=false)")
        return
    threading.Thread(target=_loop, daemon=True, name="auto-refresh").start()
    log.info("التحديث التلقائي يعمل كل %s دقيقة", max(5, s.refresh_interval_min))


def stop() -> None:
    _stop.set()