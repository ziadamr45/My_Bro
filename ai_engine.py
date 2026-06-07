"""
محرك الذكاء الاصطناعي - AI Engine
يتعامل مع OpenRouter API لجميع وظائف الذكاء الاصطناعي
"""

import logging
from typing import Optional, List

import requests

from config import (
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL,
    OPENROUTER_FALLBACK_MODELS, MAX_RETRIES, RETRY_DELAY, REQUEST_TIMEOUT
)

logger = logging.getLogger(__name__)


def call_ai(
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.7,
    max_tokens: int = 2048,
    prefer_arabic: bool = False,
) -> Optional[str]:
    """
    استدعاء OpenRouter API مع دعم تعدد الموديلات
    """
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY not set")
        return None

    if prefer_arabic and not system_prompt:
        system_prompt = "أنت مساعد ذكي تجيب بالعربية الفصحى دائماً. استخدم تنسيق جميل مع إيموجي."

    url = f"{OPENROUTER_BASE_URL}/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/ziadamr45/ai-news-bot",
        "X-Title": "My Bro AI Bot",
    }

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    # تجربة الموديل الرئيسي ثم البدائل
    models_to_try = [OPENROUTER_MODEL] + OPENROUTER_FALLBACK_MODELS

    for attempt in range(MAX_RETRIES):
        for model in models_to_try:
            payload["model"] = model
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()

                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0].get("message", {}).get("content", "")
                    if content:
                        logger.info(f"AI response from {model} (attempt {attempt+1})")
                        return content

                if "error" in data:
                    logger.warning(f"API error for {model}: {data['error']}")
                    continue

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout for model {model}")
            except requests.exceptions.RequestException as e:
                if "403" in str(e) or "401" in str(e):
                    logger.warning(f"Auth/region error for {model}, trying next")
                    continue
                logger.warning(f"Request error for {model}: {str(e)[:100]}")
            except Exception as e:
                logger.warning(f"Error for {model}: {str(e)[:100]}")

        if attempt < MAX_RETRIES - 1:
            import time
            time.sleep(RETRY_DELAY)

    logger.error("All AI model attempts failed")
    return None


def smart_chat(user_message: str, language: str = "ar") -> str:
    """
    المحادثة الذكية - يفهم القصد تلقائياً ويرد بذكاء
    """
    if language == "ar":
        system = """أنت "My Bro" - مساعد ذكاء اصطناعي شخصي. تجيب دائماً بالعربية الفصحى.

قواعد:
- فهم قصد المستخدم تلقائياً
- أجب بذكاء ووضوح
- استخدم إيموجي مناسبة
- استخدم تنسيق جميل (عناوين، نقاط، فواصل)
- إذا سأل عن أخبار AI، اذكر أحدث ما تعرفه
- إذا سأل سؤال تقني، اشرح ببساطة
- كن ودود ومفيد"""
    else:
        system = """You are "My Bro" - a personal AI assistant. Always respond in English.

Rules:
- Understand user intent automatically
- Answer intelligently and clearly
- Use appropriate emojis
- Use beautiful formatting (headings, bullets, separators)
- If asked about AI news, share what you know
- If asked technical questions, explain simply
- Be friendly and helpful"""

    response = call_ai(user_message, system_prompt=system, temperature=0.7, max_tokens=2048)
    return response or ("عذراً، لم أتمكن من معالجة طلبك. حاول مرة أخرى. 🤖" if language == "ar" else "Sorry, I couldn't process your request. Please try again. 🤖")


def ask_question(question: str, language: str = "ar") -> str:
    """
    /ask - سؤال مباشر مع إجابة مفصلة
    """
    if language == "ar":
        system = """أنت خبير ذكاء اصطناعي. أجب على الأسئلة بالعربية الفصحى بشكل مفصل ومorganized.
استخدم:
- 📌 عنوان للإجابة
- شرح واضح مع أمثلة
- نقاط رئيسية
- روابط أو مراجع إن أمكن"""
    else:
        system = """You are an AI expert. Answer questions in English in detail and organized format.
Use:
- 📌 Title for the answer
- Clear explanation with examples
- Key points
- Links or references if possible"""

    response = call_ai(question, system_prompt=system, temperature=0.5, max_tokens=2048)
    return response or ("لم أتمكن من الإجابة. 🤖" if language == "ar" else "I couldn't answer that. 🤖")


def explain_topic(topic: str, language: str = "ar") -> str:
    """
    /learn - شرح تعليمي لموضوع
    """
    if language == "ar":
        prompt = f"""اشرح "{topic}" بشكل تعليمي ومبسط بالعربية.

التنسيق المطلوب:
📚 <b>ما هو {topic}؟</b>
→ تعريف بسيط وواضح

🔑 <b>المفاهيم الأساسية</b>
→ أهم المفاهيم المرتبطة

💡 <b>أمثلة عملية</b>
→ تطبيقات في الواقع

🚀 <b>الاستخدامات</b>
→ كيف يُستخدم اليوم

📖 <b>مصادر للتعلم</b>
→ أين يمكن التعمق أكثر"""
    else:
        prompt = f"""Explain "{topic}" in an educational and simple way in English.

Format:
📚 <b>What is {topic}?</b>
→ Simple clear definition

🔑 <b>Core Concepts</b>
→ Key related concepts

💡 <b>Practical Examples</b>
→ Real-world applications

🚀 <b>Use Cases</b>
→ How it's used today

📖 <b>Learning Resources</b>
→ Where to learn more"""

    response = call_ai(prompt, temperature=0.5, max_tokens=2048, prefer_arabic=True)
    return response or ("لم أتمكن من شرح الموضوع. 🤖" if language == "ar" else "I couldn't explain this topic. 🤖")


def generate_roadmap(topic: str, language: str = "ar") -> str:
    """
    /roadmap - خارطة طريق تعليمية
    """
    from config import ROADMAPS

    topic_lower = topic.lower().strip()

    # البحث في القوالب الجاهزة
    for key, roadmap in ROADMAPS.items():
        if key in topic_lower or topic_lower in key:
            if language == "ar":
                text = f"🗺️ <b>{roadmap['title_ar']}</b>\n\n"
                text += "🟢 <b>مبتدئ</b>\n"
                for i, item in enumerate(roadmap["beginner"], 1):
                    text += f"  {i}. {item}\n"
                text += "\n🟡 <b>متوسط</b>\n"
                for i, item in enumerate(roadmap["intermediate"], 1):
                    text += f"  {i}. {item}\n"
                text += "\n🔴 <b>متقدم</b>\n"
                for i, item in enumerate(roadmap["advanced"], 1):
                    text += f"  {i}. {item}\n"
                return text
            else:
                text = f"🗺️ <b>{roadmap['title_en']}</b>\n\n"
                text += "🟢 <b>Beginner</b>\n"
                for i, item in enumerate(roadmap["beginner"], 1):
                    text += f"  {i}. {item}\n"
                text += "\n🟡 <b>Intermediate</b>\n"
                for i, item in enumerate(roadmap["intermediate"], 1):
                    text += f"  {i}. {item}\n"
                text += "\n🔴 <b>Advanced</b>\n"
                for i, item in enumerate(roadmap["advanced"], 1):
                    text += f"  {i}. {item}\n"
                return text

    # لو مش لقي خارطة جاهزة، يولد واحدة بالـ AI
    if language == "ar":
        prompt = f"""أنشئ خارطة طريق تعليمية لـ "{topic}" بالعربية.

التنسيق:
🗺️ <b>خارطة طريق {topic}</b>

🟢 <b>مبتدئ</b>
1. ...
2. ...
3. ...

🟡 <b>متوسط</b>
1. ...
2. ...
3. ...

🔴 <b>متقدم</b>
1. ...
2. ...
3. ..."""
    else:
        prompt = f"""Create a learning roadmap for "{topic}" in English.

Format:
🗺️ <b>{topic} Roadmap</b>

🟢 <b>Beginner</b>
1. ...
2. ...
3. ...

🟡 <b>Intermediate</b>
1. ...
2. ...
3. ...

🔴 <b>Advanced</b>
1. ...
2. ...
3. ..."""

    response = call_ai(prompt, temperature=0.5, max_tokens=2048, prefer_arabic=True)
    return response or ("لم أتمكن من إنشاء خارطة طريق. 🤖" if language == "ar" else "I couldn't generate a roadmap. 🤖")


def generate_company_report(company_key: str, language: str = "ar") -> str:
    """
    /company - تقرير عن شركة
    """
    from config import COMPANY_DATA

    company_key = company_key.lower().strip()
    company = None
    for key, data in COMPANY_DATA.items():
        if key == company_key or company_key in data["keywords"] or company_key in data["name"].lower():
            company = data
            break

    if not company:
        if language == "ar":
            return f"❌ لم أجد شركة باسم '{company_key}'.\n\nالشركات المتاحة: " + "، ".join(COMPANY_DATA.keys())
        else:
            return f"❌ Company '{company_key}' not found.\n\nAvailable: " + ", ".join(COMPANY_DATA.keys())

    if language == "ar":
        prompt = f"""أنشئ تقرير ذكاء شركة عن {company['name']} ({company['name_ar']}) بالعربية.

معلومات عن الشركة:
- الوصف: {company['description_ar']}
- المنتجات: {', '.join(company['products'])}

التنسيق:
🏢 <b>تقرير {company['name_ar']}</b>
━━━━━━━━━━━━━━━━━

📋 <b>نبذة عن الشركة</b>
→ وصف مختصر

🚀 <b>المنتجات الرئيسية</b>
→ قائمة بالمنتجات

📰 <b>أحدث التطورات</b>
→ أهم الأخبار الأخيرة

💡 <b>نقاط القوة</b>
→ أبرز المزايا

⚠️ <b>التحديات</b>
→ التحديات الحالية

🔮 <b>التوقعات</b>
→ ما نتوقعه مستقبلاً"""
    else:
        prompt = f"""Create a company intelligence report for {company['name']} in English.

Company info:
- Description: {company['description']}
- Products: {', '.join(company['products'])}

Format:
🏢 <b>{company['name']} Report</b>
━━━━━━━━━━━━━━━━━

📋 <b>Overview</b>
→ Brief description

🚀 <b>Key Products</b>
→ Product list

📰 <b>Latest Developments</b>
→ Recent important news

💡 <b>Strengths</b>
→ Key advantages

⚠️ <b>Challenges</b>
→ Current challenges

🔮 <b>Outlook</b>
→ Future expectations"""

    response = call_ai(prompt, temperature=0.5, max_tokens=2048, prefer_arabic=True)
    return response or ("لم أتمكن من إنشاء التقرير. 🤖" if language == "ar" else "I couldn't generate the report. 🤖")
