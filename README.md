# 🤖 AI News Telegram Bot

بوت تليجرام تلقائي يبعث ملخص يومي بالعربي لأهم أخبار الذكاء الاصطناعي.

## المميزات

- ✅ تشغيل تلقائي يومياً الساعة 9:00 صباحاً بتوقيت القاهرة
- ✅ جمع الأخبار من مصادر موثوقة (RSS feeds)
- ✅ فلترة الأخبار للذكاء الاصطناعي فقط
- ✅ نظام تسجيل لتقييم أهمية الأخبار
- ✅ ملخصات عربية احترافية باستخدام Gemini API
- ✅ منع التكرار والأخبار المضللة
- ✅ أعلى 3-5 أخبار فقط يومياً
- ✅ نشر تلقائي عبر GitHub Actions

## الإعداد

### 1. المتطلبات

- Python 3.12+
- حساب GitHub
- Telegram Bot Token (من @BotFather)
- Gemini API Key (من Google AI Studio)

### 2. إعداد التليجرام

1. ابحث عن @BotFather في تليجرام
2. ابعث `/newbot` واتبع التعليمات
3. احفظ الـ Token
4. ابعت رسالة للبوت
5. استخدم الـ API لجلب الـ CHAT_ID

### 3. GitHub Secrets

في إعدادات المستودع (Settings > Secrets and variables > Actions):

| Secret | الوصف |
|--------|-------|
| `BOT_TOKEN` | Telegram Bot Token |
| `CHAT_ID` | Chat ID الخاص بك |
| `GEMINI_API_KEY` | Gemini API Key |

### 4. التشغيل المحلي

```bash
# نسخ ملف البيئة
cp .env.example .env

# تعبئة البيانات
# BOT_TOKEN=...
# CHAT_ID=...
# GEMINI_API_KEY=...

# تثبيت المتطلبات
pip install -r requirements.txt

# تشغيل البوت
python main.py

# تشغيل في وضع الاختبار
python main.py --test
```

## الهيكل

```
ai-news-bot/
├── main.py              # نقطة التشغيل الرئيسية
├── news_fetcher.py      # جلب الأخبار من RSS feeds
├── filters.py           # فلترة الأخبار المتعلقة بالذكاء الاصطناعي
├── scorer.py            # نظام تسجيل وترتيب الأخبار
├── summarizer.py        # توليد الملخصات العربية
├── telegram_sender.py   # إرسال الرسائل لتليجرام
├── config.py            # الإعدادات
├── requirements.txt     # متطلبات Python
├── .env.example         # نموذج متغيرات البيئة
├── .gitignore
├── README.md
└── .github/
    └── workflows/
        └── daily_news.yml  # جدول التشغيل اليومي
```

## المصادر

### الأولوية القصوى
- OpenAI Blog
- Google DeepMind Blog
- Anthropic News
- Microsoft AI Blog
- NVIDIA Blog
- Reuters

### أولوية ثانوية
- TechCrunch AI
- MIT Technology Review
- VentureBeat AI
- The Verge AI
- Hugging Face Blog

## الترخيص

MIT License
