# 📡 رادار مستقل (Mostaql Radar)

أداة شخصية: تسحب مشاريع مستقل بزر، تقيّمها بـ Gemini، تنبّهك على تيليجرام، وتكتب مسودات عروض تعتمدها أو ترفضها بزر.

```
React (5173) ──REST──► FastAPI (8000) ──Playwright──► mostaql.com
                          │  ├─ SQLite  ├─ Gemini
   تيليجرام ◄─polling─────┘  └─webhook─► n8n (Docker 5678) ──► تيليجرام (رسائل + أزرار)
```

| المجلد | المحتوى |
|---|---|
| `docs/01-analysis.md` | التحليل، القرارات، المعمارية، المخاطر |
| `docs/02-ux-ui.md` | تدفق المستخدم، الشاشات، نظام التصميم |
| `backend/` | FastAPI + SQLite + Playwright + Gemini + بوت تيليجرام |
| `frontend/` | React (Vite) عربي RTL |
| `n8n/workflow.json` | Workflow استقبال Webhook وإرسال رسائل تيليجرام |
| `docker-compose.yml` | n8n فقط |

## المتطلبات
Windows + Python 3.11+ + Node 20+ + Docker Desktop + مفتاح Gemini (aistudio.google.com) + بوت تيليجرام.

## التشغيل خطوة بخطوة

**1) الإعدادات**
```
copy .env.example .env
```
املأ `GEMINI_API_KEY` و`TELEGRAM_BOT_TOKEN` و`TELEGRAM_CHAT_ID`، وضع في `N8N_SHARED_SECRET` نصاً عشوائياً طويلاً.
عدّل `backend/profile.json` بمهاراتك الحقيقية (يُستخدم للتقييم وكتابة العروض).

**2) n8n**
```
docker compose up -d
```
افتح http://localhost:5678 وأنشئ حساب المالك، ثم: *Workflows ← Import from file* واختر `n8n/workflow.json`، وفعّل المفتاح **Active** (أعلى اليمين). رابط الإنتاج الذي يستدعيه FastAPI:
`http://localhost:5678/webhook/mostaql-notify` (موجود مسبقاً في `.env.example`).

**3) الباك اند**
```
run_backend.bat
```
تحقق: http://127.0.0.1:8000/health ثم http://127.0.0.1:8000/docs

**4) جلسة مستقل (لصفحات حسابك)**
```
cd backend
.venv\Scripts\activate
python scripts\save_session.py
```
تظهر نافذة متصفح: سجّل الدخول يدوياً ثم اضغط Enter في الطرفية. تُحفظ الكوكيز فقط في `backend/data/` (لا كلمة مرور). بدونها يعمل السحب على الصفحات العامة فقط.

**5) فحص المحلل (مهم عند أول تشغيل)**
```
python scripts\inspect_page.py list
python scripts\inspect_page.py detail https://mostaql.com/project/<رقم>
python scripts\inspect_page.py mine
```
إن خرجت قوائم فارغة أو حقول ناقصة، افتح ملفات `backend/data/debug_*.html` وعدّل `backend/app/parser.py`. ولو كان رابط «عروضي» مختلفاً عدّل `MY_PROPOSALS_PATH` في `.env`.

**6) الواجهة**
```
run_frontend.bat
```
افتح http://localhost:5173 واضغط **تحديث الآن**.

## البوت
`/refresh` تحديث · `/latest` آخر المشاريع · `/top` الأعلى درجة · `/search كلمة` · `/stats` · `/draft رقم`
وأزرار الرسائل: ✍️ اكتب عرضاً · 🙈 تجاهل · ✅ موافقة · ❌ رفض · 🔄 إعادة · 📨 تم الإرسال.
البوت يتجاهل أي دردشة غير `TELEGRAM_CHAT_ID`.

## سلوك مهم
- **«موافقة» لا ترسل شيئاً لمستقل.** تحصل على النص والرابط وتقدّم أنت يدوياً (تجنباً لحظر الحساب ومخالفة الشروط).
- إن تعطل n8n يرسل FastAPI لتيليجرام مباشرة؛ وإن تعطل Gemini يعمل مقيّم احتياطي بالكلمات المفتاحية.
- عند حاجز Cloudflare/CAPTCHA يتوقف التحديث برسالة واضحة؛ افتح الموقع يدوياً وأعد `save_session.py`.
- السحب بطيء عمداً (3–7 ثوانٍ بين الصفحات). لا ترفع `MAX_LIST_PAGES` كثيراً. راجع شروط استخدام مستقل وتحمّل مسؤولية السحب من حسابك.

## الاختبارات
```
cd backend
.venv\Scripts\activate
pytest -q
```

## ما تم التحقق منه وما لم يتم (صراحةً)
| البند | الحالة |
|---|---|
| اختبارات محلل HTML (4 اختبارات) | ✅ نجحت (وكشفت وأصلحت خللاً في عدّ العروض) |
| تجميع كل ملفات بايثون | ✅ |
| صياغة ملفات JSX (esbuild) | ✅ |
| `docker compose config` وبنية workflow JSON | ✅ |
| اختبارات API وخط التحديث (`tests/test_api.py`) | ⚠️ مكتوبة **لكن لم تُشغَّل** (بيئة البناء لا تصل إلى PyPI) — شغّلها عندك بـ `pytest` |
| بناء الواجهة `npm run build` | ⚠️ **لم يُجرَّب** (لا وصول إلى npm) |
| المحلل على صفحات مستقل الحية | ⚠️ **لم يُجرَّب** — استخدم `inspect_page.py` |
| استيراد workflow في n8n وإرسال تيليجرام فعلي | ⚠️ لم يُجرَّب |
| اسم نموذج Gemini الافتراضي | ⚠️ قابل للتغيير عبر `GEMINI_MODEL` |

## تطوير لاحق
صفحة إعدادات للملف الشخصي، لوحة تحليل السوق، جدولة، إرسال شبه تلقائي اختياري.
