"""Generate Arabic summaries using Gemini API."""

import logging
from typing import List, Dict, Optional
import requests
import json

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_MAX_TOKENS,
    GEMINI_TEMPERATURE,
    MAX_RETRIES,
    RETRY_DELAY_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    CAIRO_TZ,
)

logger = logging.getLogger(__name__)


def _call_gemini_api(prompt: str) -> Optional[str]:
    """Call Gemini API with retries."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": GEMINI_MAX_TOKENS,
            "temperature": GEMINI_TEMPERATURE,
        },
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            data = response.json()
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")

            if text:
                return text.strip()
            else:
                logger.warning(f"Gemini returned empty response (attempt {attempt + 1})")

        except requests.exceptions.RequestException as e:
            logger.warning(f"Gemini API attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                import time
                time.sleep(RETRY_DELAY_SECONDS)

    return None


def _build_summary_prompt(articles: List[Dict]) -> str:
    """Build the prompt for Gemini to generate Arabic summaries."""
    articles_text = ""
    for i, article in enumerate(articles, 1):
        articles_text += f"""
---
خبر رقم {i}:
العنوان: {article['title']}
الملخص المتاح: {article.get('summary', 'لا يوجد ملخص')}
المصدر: {article.get('source', 'غير محدد')}
الرابط: {article['url']}
الدرجة: {article.get('score', 0)}
---
"""

    prompt = f"""أنت محرر أخبار ذكاء اصطناعي محترف. مهمتك هي كتابة ملخصات عربية مختصرة ومهنية لأهم أخبار الذكاء الاصطناعي.

القواعد:
1. اكتب ملخص عربي مختصر (3-4 جمل فقط) لكل خبر
2. استخدم عربية فصحى مبسطة مناسبة للقارئ المصري
3. لا تترجم حرفياً — اكتب بأسلوب طبيعي ومهني
4. ركز على الأهمية والتأثير العملي للخبر
5. لا تخترع معلومات غير موجودة في النص الأصلي
6. إذا كان الملخص المتاح فارغاً، اكتب ملخصاً بناءً على العنوان فقط
7. حدد أهم خبر في اليوم

الأخبار:
{articles_text}

المطلوب:
لكل خبر، اكتب:
- عنوان عربي مختصر وواضح (سطر واحد)
- ملخص عربي مختصر (3-4 جمل)
- أهم خبر اليوم (رقم الخبر الأهم مع سبب قصير)

أجب بهذا التنسيق بالضبط:

خبر1:
العنوان: ...
الملخص: ...

خبر2:
العنوان: ...
الملخص: ...

(وهكذا لكل الأخبار)

أهم خبر اليوم: رقم X - السبب: ...
"""

    return prompt


def _parse_gemini_response(response_text: str, articles: List[Dict]) -> List[Dict]:
    """Parse Gemini's response and map summaries to articles."""
    summaries = []

    for i, article in enumerate(articles, 1):
        # Try to extract the summary for this article number
        arabic_title = article["title"]  # Default to original title
        arabic_summary = ""  # Will be filled from Gemini response

        # Pattern matching for Arabic response
        import re

        # Match news block (خبر1, خبر 1, etc.)
        news_pattern = rf"خبر\s*{i}\s*:\s*(.*?)(?=خبر\s*{i+1}\s*:|أهم خبر اليوم|$)"
        news_match = re.search(news_pattern, response_text, re.DOTALL)

        if news_match:
            news_block = news_match.group(1)

            # Extract Arabic title
            title_match = re.search(r"العنوان\s*:\s*(.+?)(?:\n|$)", news_block)
            if title_match:
                arabic_title = title_match.group(1).strip()

            # Extract Arabic summary
            summary_match = re.search(r"الملخص\s*:\s*(.+?)(?=\n\n|\nخبر|$)", news_block, re.DOTALL)
            if summary_match:
                arabic_summary = summary_match.group(1).strip()

        # Fallback: if we couldn't parse, use the original title
        if not arabic_summary:
            arabic_summary = article.get("summary", article["title"])[:200]

        summaries.append({
            "arabic_title": arabic_title,
            "arabic_summary": arabic_summary,
            "url": article["url"],
            "source": article.get("source", ""),
            "score": article.get("score", 0),
        })

    # Extract the most important news
    most_important = 1  # Default to first (highest scored)
    import_match = re.search(r"أهم خبر اليوم\s*:\s*رقم\s*(\d+)", response_text)
    if import_match:
        try:
            most_important = int(import_match.group(1))
        except ValueError:
            pass

    return summaries, most_important


def generate_summaries(articles: List[Dict]) -> tuple:
    """Generate Arabic summaries for articles using Gemini API."""
    if not articles:
        return [], 0

    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set — cannot generate summaries")
        return [], 0

    logger.info(f"Generating Arabic summaries for {len(articles)} articles...")

    prompt = _build_summary_prompt(articles)
    response = _call_gemini_api(prompt)

    if not response:
        logger.error("Failed to get response from Gemini API")
        # Fallback: use original titles
        summaries = []
        for article in articles:
            summaries.append({
                "arabic_title": article["title"],
                "arabic_summary": article.get("summary", "")[:200],
                "url": article["url"],
                "source": article.get("source", ""),
                "score": article.get("score", 0),
            })
        return summaries, 1

    summaries, most_important = _parse_gemini_response(response, articles)
    logger.info(f"Generated {len(summaries)} Arabic summaries")
    return summaries, most_important


def format_message(summaries: List[Dict], most_important: int) -> str:
    """Format the final Telegram message in Arabic."""
    from datetime import datetime

    now = datetime.now(CAIRO_TZ)
    date_str = now.strftime("%d/%m/%Y")

    number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

    message = f"🧠 أهم أخبار الذكاء الاصطناعي اليوم\n\n📅 {date_str}\n\n"

    for i, item in enumerate(summaries):
        emoji = number_emojis[i] if i < len(number_emojis) else f"{i+1}."
        message += f"{emoji} {item['arabic_title']}\n\n"
        message += f"الملخص:\n{item['arabic_summary']}\n\n"
        message += f"المصدر:\n{item['url']}\n\n"
        message += "━━━━━━━━━━━━\n\n"

    # Most important news
    if summaries and 1 <= most_important <= len(summaries):
        best = summaries[most_important - 1]
        message += f"🎯 أهم خبر اليوم:\n{best['arabic_title']}"

    return message.strip()
