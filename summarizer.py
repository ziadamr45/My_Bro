"""
تلخيص الأخبار - News Summarizer Module
يستخدم Provider Manager لتلخيص الأخبار بالعربية
+ دعم المكالمات غير المتزامنة
+ تبديل تلقائي بين المزودين
"""

import asyncio
import logging
import time as time_module
from typing import List, Dict, Optional

from provider_manager import get_provider_manager
from config import REQUEST_TIMEOUT

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


def _summarize_articles_sync(articles: List[Dict]) -> List[Dict]:
    """تلخيص الأخبار (متزامن - باستخدام Provider Manager)"""
    if not articles:
        return articles

    manager = get_provider_manager()

    # فحص هل في مزودين متاحين
    routes = manager.get_model_routes("summary")
    if not routes:
        logger.warning("No summary providers available, using original descriptions")
        for article in articles:
            article["arabic_summary"] = article.get("description", "")[:200]
        return articles

    logger.info(f"Summarizing {len(articles)} articles using Provider Manager...")

    prompt = create_summary_prompt(articles)
    system_prompt = "أنت مساعد عربي متخصص في أخبار الذكاء الاصطناعي. تجيب دائماً بالعربية الفصحى فقط."

    response = manager.call_with_system_prompt_sync(
        prompt=prompt,
        system_prompt=system_prompt,
        task_type="summary",
        temperature=0.3,
        max_tokens=2048,
    )

    if response:
        summaries = parse_summaries(response, len(articles))
        for i, article in enumerate(articles):
            if i < len(summaries):
                article["arabic_summary"] = summaries[i]
            else:
                article["arabic_summary"] = article.get("description", "")[:200]
        logger.info(f"Successfully summarized {len(summaries)} articles")
        return articles

    logger.warning("All summarization attempts failed. Using original descriptions.")
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
