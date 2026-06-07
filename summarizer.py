"""
تلخيص الأخبار - News Summarizer Module
يستخدم OpenRouter API لتلخيص الأخبار بالعربية
+ دعم المكالمات غير المتزامنة
"""

import asyncio
import logging
import time as time_module
from typing import List, Dict, Optional

import requests

from config import (
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL,
    OPENROUTER_FALLBACK_MODELS, FAST_MODEL, MAX_RETRIES, RETRY_DELAY,
    REQUEST_TIMEOUT, FAST_TIMEOUT
)

logger = logging.getLogger(__name__)


def create_summary_prompt(articles: List[Dict]) -> str:
    articles_text = ""
    for i, article in enumerate(articles, 1):
        articles_text += f"\n--- الخبر {i} ---\n"
        articles_text += f"العنوان: {article.get('title', '')}\n"
        articles_text += f"الوصف: {article.get('description', '')}\n"
        articles_text += f"المصدر: {article.get('source', '')}\n"
        articles_text += f"الرابط: {article.get('link', '')}\n"

    prompt = f"""أنت خبير في أخبار الذكاء الاصطناعي. قم بتلخيص الأخبار التالية باللغة العربية.

المطلوب:
1. تلخيص كل خبر في 2-3 جمل بالعربية الفصحى
2. التركيز على الجوهر والأهمية
3. استخدام لغة واضحة ومباشرة
4. ذكر اسم الشركة أو المنتج إن وُجد
5. عدم إضافة معلومات غير موجودة في الخبر الأصلي
6. التلخيص يجب أن يكون مفيد للقارئ العربي المهتم بالذكاء الاصطناعي
7. التلخيص يجب أن يكون بالعربية فقط

الأخبار:{articles_text}

قم بإرجاع التلخيصات في الصيغة التالية لكل خبر:
SUMMARY_START
[التلخيص بالعربية]
SUMMARY_END"""

    return prompt


def parse_summaries(response_text: str, num_articles: int) -> List[str]:
    summaries = []

    parts = response_text.split("SUMMARY_START")
    for part in parts[1:]:
        end_idx = part.find("SUMMARY_END")
        if end_idx != -1:
            summary = part[:end_idx].strip()
            if summary:
                summaries.append(summary)

    if len(summaries) != num_articles:
        summaries = []
        lines = response_text.strip().split("\n")
        current_summary = []

        for line in lines:
            line = line.strip()
            if not line:
                if current_summary:
                    summary_text = " ".join(current_summary).strip()
                    if summary_text and len(summary_text) > 10:
                        summaries.append(summary_text)
                    current_summary = []
                continue
            current_summary.append(line)

        if current_summary:
            summary_text = " ".join(current_summary).strip()
            if summary_text and len(summary_text) > 10:
                summaries.append(summary_text)

    if len(summaries) < num_articles:
        while len(summaries) < num_articles:
            summaries.append("تفاصيل الخبر متاحة عبر الرابط المرفق.")

    summaries = summaries[:num_articles]
    return summaries


def _call_openrouter_sync(prompt: str, model: str) -> Optional[str]:
    """استدعاء OpenRouter API (متزامن)"""
    url = f"{OPENROUTER_BASE_URL}/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/ziadamr45/ai-news-bot",
        "X-Title": "AI News Telegram Bot",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "أنت مساعد عربي متخصص في أخبار الذكاء الاصطناعي. تجيب دائماً بالعربية الفصحى فقط."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 2048,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        if "choices" in data and len(data["choices"]) > 0:
            content = data["choices"][0].get("message", {}).get("content", "")
            if content:
                return content

        if "error" in data:
            logger.warning(f"OpenRouter API error for {model}: {data['error']}")

    except requests.exceptions.Timeout:
        logger.warning(f"Timeout calling OpenRouter with model {model}")
    except requests.exceptions.RequestException as e:
        logger.warning(f"Request error for model {model}: {str(e)[:150]}")
    except Exception as e:
        logger.warning(f"Unexpected error for model {model}: {str(e)[:150]}")

    return None


async def _call_openrouter(prompt: str, model: str) -> Optional[str]:
    """استدعاء OpenRouter API (غير متزامن)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: _call_openrouter_sync(prompt, model)
    )


def _summarize_articles_sync(articles: List[Dict]) -> List[Dict]:
    """تلخيص الأخبار (متزامن - للتوافق مع main.py)"""
    if not articles:
        return articles

    if not OPENROUTER_API_KEY:
        for article in articles:
            article["arabic_summary"] = article.get("description", "")[:200]
        return articles

    logger.info(f"Summarizing {len(articles)} articles using OpenRouter API...")

    prompt = create_summary_prompt(articles)

    if FAST_MODEL:
        models_to_try = [FAST_MODEL, OPENROUTER_MODEL] + OPENROUTER_FALLBACK_MODELS
    else:
        models_to_try = [OPENROUTER_MODEL] + OPENROUTER_FALLBACK_MODELS

    for attempt in range(MAX_RETRIES):
        for model in models_to_try:
            logger.info(f"Trying model: {model} (attempt {attempt + 1})")
            result = _call_openrouter_sync(prompt, model)

            if result:
                summaries = parse_summaries(result, len(articles))
                for i, article in enumerate(articles):
                    if i < len(summaries):
                        article["arabic_summary"] = summaries[i]
                    else:
                        article["arabic_summary"] = article.get("description", "")[:200]

                logger.info(f"Successfully summarized {len(summaries)} articles using {model}")
                return articles

        if attempt < MAX_RETRIES - 1:
            logger.info(f"Waiting {RETRY_DELAY}s before retry...")
            time_module.sleep(RETRY_DELAY)

    logger.warning("All OpenRouter attempts failed. Using original descriptions.")
    for article in articles:
        desc = article.get("description", "")
        article["arabic_summary"] = desc[:200] if desc else "تفاصيل الخبر متاحة عبر الرابط المرفق."

    return articles


async def summarize_articles(articles: List[Dict]) -> List[Dict]:
    """تلخيص الأخبار (غير متزامن)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: _summarize_articles_sync(articles)
    )
