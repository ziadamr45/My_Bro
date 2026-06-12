# 🤖 ماي برو — My Bro | Dual-platform AI Assistant Bot

بوت ذكي شخصي يعمل على تيليجرام وواتساب في نفس الوقت — محادثة ذكية، أخبار يومية، تحميل فيديوهات، بحث صوتي، توليد صور، وتحليل ملفات PDF.

A dual-platform (Telegram + WhatsApp) AI assistant bot with smart chat, daily news, video/audio downloads, search, image generation, PDF analysis, and more.

## ✨ المميزات

| الميزة | الوصف |
|--------|-------|
| 💬 محادثة ذكية | دردشة AI مع ذاكرة محادثة وسياق شخصي |
| 📬 أخبار يومية | ملخص يومي لأهم أخبار AI — الوقت الافتراضي 12 الظهر |
| 📥 تحميل فيديو/صوت | YouTube, Dailymotion, SoundCloud, Twitter, TikTok, Instagram, Facebook, Threads, Reddit |
| 🔍 بحث صوت بالبحث | ابحث عن أغنية وحمّلها صوت أو فيديو |
| 🖼️ توليد وتعديل صور | AI image generation + image editing |
| 📄 تحليل PDF | رفع PDF والرد على أسئلتك عنه |
| 🎥 ملخص YouTube | تلخيص أي فيديو YouTube بالعربي |
| 🔍 بحث ويب | بحث مباشر في الإنترنت |
| 📚 تعلم وخرائط | خريطة تعلم لأي تقنية + شروحات مفصلة |
| 🏢 تقارير شركات | تحليل ذكي لأي شركة تقنية |
| 🌐 ثنائي اللغة | عربي وإنجليزي — مع اختيار تلقائي |
| ⭐ نظام Premium | خطط مجانية ومميزة مع حدود استخدام |
| 🛡️ أمان المحتوى | فلترة تلقائية للمحتوى غير الآمن |
| ☁️ رفع سحابي | Supabase Storage للملفات الكبيرة مع رابط تحميل 24 ساعة |

## 🛠️ التقنيات

| التقنية | الاستخدام |
|---------|-----------|
| Python 3.11 | اللغة الأساسية |
| python-telegram-bot v20 | Telegram Bot API |
| Flask | WhatsApp Cloud API Webhook |
| PostgreSQL / SQLite | قاعدة بيانات المستخدمين (عبر Supabase) |
| Google Gemini | AI chat, summarization, image generation |
| yt-dlp | تحميل الفيديوهات |
| FFmpeg | تحويل الكوديك وضغط الفيديو |
| Supabase Storage | رفع الملفات السحابي |
| Invidious / Piped APIs | تحميل YouTube بديل |
| Cobalt API | fallback لتحميل الفيديو |
| RapidAPI | تحليل Threads وخدمات إضافية |
| APScheduler | جدولة الأخبار اليومية |
| aiohttp | HTTP requests غير متزامن |
| Railway | الاستضافة والتشغيل |

## 📁 بنية المشروع

```
ai-news-bot/
├── main.py                      # نقطة تشغيل بوت التليجرام
├── whatsapp_webhook.py          # واب هوك بوت واتساب (7800+ سطر)
├── bot.py                       # جدولة الأخبار + APScheduler
├── config.py                    # إعدادات ومتغيرات البيئة
├── memory.py                    # قاعدة بيانات المستخدمين + العمليات
├── memory_context.py            # بناء سياق AI من الذاكرة
├── smart_chat.py                # محادثة AI الذكية
├── ai_engine.py                 # محرك AI (Gemini + fallbacks)
├── premium.py                   # نظام Premium والاشتراكات
├── content_safety.py            # فلترة أمان المحتوى
├── supabase_storage.py          # رفع ملفات Supabase السحابي
├── image_gen.py                 # توليد وتعديل الصور
├── news_fetcher.py              # جلب الأخبار من RSS
├── filters.py                   # فلترة الأخبار
├── scorer.py                    # ترتيب وتقييم الأخبار
├── summarizer.py                # تلخيص الأخبار بالAI
├── formatters.py                # تنسيق الرسائل
├── i18n.py                      # نظام ثنائي اللغة
├── dashboard.py                 # لوحة تحليلات وإحصائيات
├── invidious_api.py             # Invidious API integration
├── piped_api.py                 # Piped API integration
├── dailymotion_search.py        # بحث Dailymotion المباشر
├── youtube_search.py            # بحث YouTube
├── soundcloud_search.py         # بحث SoundCloud
├── image_search.py              # بحث صور (Unsplash)
├── cookie_rotator.py            # تدوير كوكيز YouTube
├── web_search.py                # بحث ويب
├── progress.py                  # شريط تقدم التليجرام
├── admin.py                     # لوحة تحكم الأدمن
├── handlers/
│   ├── download_handlers.py     # تحميل فيديو/صوت (YouTube, Threads, etc.)
│   ├── search_download_handlers.py  # بحث + تحميل صوت
│   ├── media_handlers.py        # معالجة ملفات الميديا
│   ├── ai_handlers.py           # أوامر AI
│   ├── image_handlers.py        # توليد وتعديل صور
│   ├── basic_handlers.py        # أوامر أساسية
│   ├── news_handlers.py         # أوامر الأخبار
│   ├── memory_handlers.py       # إعدادات المستخدم
│   ├── callbacks.py             # أزرار inline keyboard
│   ├── keyboards.py             # تصميم الكيبورد
│   ├── message_handler.py       # معالجة الرسائل
│   ├── dedup.py                 # منع تكرار الرسائل
│   └── error_monitor.py         # مراقبة الأخطاء
├── agents/
│   ├── pdf_agent.py             # تحليل PDF
│   ├── youtube_agent.py         # ملخص YouTube
│   ├── study_agent.py           # تعلم وشرح
│   └── voice_agent.py           # معالجة الصوت
├── download-service/            # خدمة تحميل منفصلة (VPS)
└── requirements.txt
```

## 🚀 التشغيل

### متغيرات البيئة المطلوبة

| المتغير | الوصف |
|---------|-------|
| `BOT_TOKEN` | توكن بوت التليجرام |
| `GEMINI_API_KEY` | مفتاح Google Gemini API |
| `WHATSAPP_ACCESS_TOKEN` | توكن واتساب Cloud API |
| `WHATSAPP_PHONE_NUMBER_ID` | معرف رقم واتساب |
| `WHATSAPP_VERIFY_TOKEN` | توكن التحقق من واب هوك واتساب |
| `SUPABASE_URL` | رابط Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | مفتاح Supabase Service Role |
| `DATABASE_URL` | رابط PostgreSQL |

### تشغيل محلي

```bash
pip install -r requirements.txt
python main.py
```

### تشغيل على Railway

البوت متصمم يشتغل على Railway مع auto-deploy من GitHub:
- بوت التليجرام + واتساب بيشتغلوا في نفس العملية
- الـ healthcheck على `/health`
- APScheduler بيشتغل داخل الـ event loop

## 📱 المنصات المدعومة للتحميل

| المنصة | فيديو | صوت | ملاحظات |
|--------|-------|------|---------|
| YouTube | ✅ | ✅ | Invidious/Piped + yt-dlp |
| Dailymotion | ✅ | ✅ | API مباشر + yt-dlp |
| SoundCloud | ✅ | ✅ | API مباشر |
| Twitter/X | ✅ | ✅ | yt-dlp |
| TikTok | ✅ | ✅ | yt-dlp |
| Instagram | ✅ | ✅ | yt-dlp |
| Facebook | ✅ | ✅ | yt-dlp |
| Threads | ✅ | ✅ | RapidAPI + data-sjs + GraphQL + Cobalt |
| Reddit | ✅ | ✅ | yt-dlp |

## ⭐ خطط الاشتراك

| الميزة | مجاني | Premium |
|--------|-------|---------|
| محادثة AI | 20 رسالة/يوم | غير محدود |
| تحميل فيديو | 5/يوم | غير محدود |
| أخبار يومية | ✅ | ✅ |
| توليد صور | 3/يوم | 20/يوم |
| تحليل PDF | ❌ | ✅ |
| ملخص YouTube | ❌ | ✅ |

## 📄 الترخيص

MIT License
