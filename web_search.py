"""
بحث الويب - Web Search Module
يستخدم DuckDuckGo (ddgs) للبحث مع تلخيص النتائج بالذكاء الاصطناعي
+ دعم المكالمات غير المتزامنة
+ دعم البحث العميق (Deep Search) باستخدام نماذج أقوى
+ استخدام Provider Manager مع تبديل تلقائي
"""

import asyncio
import logging
from typing import List, Dict, Optional

from config import REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


def _get_ddgs():
    """استيراد DDGS من الحزمة المناسبة"""
    try:
        from ddgs import DDGS
        return DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
            return DDGS
        except ImportError:
            logger.warning("Neither ddgs nor duckduckgo-search is installed")
            return None


def _search_web_sync(query: str, max_results: int = 5) -> List[Dict]:
    """البحث في الويب (متزامن)"""
    DDGS = _get_ddgs()
    if DDGS is None:
        return []

    try:
        results = []
        with DDGS() as ddgs:
            search_results = list(ddgs.text(query, max_results=max_results))

            for r in search_results:
                results.append({
                    "title": r.get("title", ""),
                    "link": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })

        logger.info(f"DuckDuckGo search for '{query}': found {len(results)} results")
        return results

    except Exception as e:
        logger.error(f"DuckDuckGo search error: {e}")
        return []


async def search_web(query: str, max_results: int = 5) -> List[Dict]:
    """البحث في الويب (غير متزامن)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: _search_web_sync(query, max_results)
    )


def _search_news_sync(query: str, max_results: int = 5) -> List[Dict]:
    """البحث عن أخبار (متزامن)"""
    DDGS = _get_ddgs()
    if DDGS is None:
        return []

    try:
        results = []
        with DDGS() as ddgs:
            search_results = list(ddgs.news(query, max_results=max_results))

            for r in search_results:
                results.append({
                    "title": r.get("title", ""),
                    "link": r.get("url", r.get("href", "")),
                    "snippet": r.get("body", ""),
                    "source": r.get("source", ""),
                    "date": r.get("date", ""),
                })

        logger.info(f"DuckDuckGo news search for '{query}': found {len(results)} results")
        return results

    except Exception as e:
        logger.error(f"DuckDuckGo news search error: {e}")
        return []


async def search_news_async(query: str, max_results: int = 5) -> List[Dict]:
    """البحث عن أخبار (غير متزامن)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: _search_news_sync(query, max_results)
    )


# Keep sync version for backward compatibility
def search_news(query: str, max_results: int = 5) -> List[Dict]:
    """البحث عن أخبار محددة في الويب (متزامن)"""
    return _search_news_sync(query, max_results)


# ═══════════════════════════════════════
# البحث العادي والتلخيص - Normal Search & Summarize
# ═══════════════════════════════════════

def _search_and_summarize_sync(query: str, language: str = "ar") -> str:
    """البحث والتلخيص (متزامن)"""
    from provider_manager import call_ai_sync

    results = _search_web_sync(query, max_results=5)

    if not results:
        if language == "ar":
            prompt = f"""أجب على السؤال التالي بأفضل ما تعرفه. إذا لم تكن متأكداً، اذكر ذلك.

السؤال: {query}

⚠️ ماتستخدمش Markdown (لا *, **, #, |). استخدم HTML فقط: <b>عريض</b> <i>مائل</i> <code>كود</code>"""
            system = "أنت مساعد ذكي تجيب بالعربية الفصحى. كن دقيقاً واستخدم إيموجي مناسبة. ماتستخدمش Markdown أبداً."
        else:
            prompt = f"""Answer the following question to the best of your knowledge. If unsure, say so.

Question: {query}

⚠️ NEVER use Markdown (no *, **, #, |). Use HTML only: <b>bold</b> <i>italic</i> <code>code</code>"""
            system = "You are a smart assistant. Be accurate and use appropriate emojis. NEVER use Markdown."

        response = call_ai_sync(prompt, system_prompt=system, task_type="chat", temperature=0.5, max_tokens=1500)
        from formatters import clean_ai_response
        if response:
            response = clean_ai_response(response)
        return response or ("لم أتمكن من العثور على معلومات. 🤖" if language == "ar" else "I couldn't find information. 🤖")

    # تجميع نتائج البحث
    search_text = ""
    for i, r in enumerate(results, 1):
        search_text += f"\n--- نتيجة {i} ---\n"
        search_text += f"العنوان: {r['title']}\n"
        search_text += f"المقتطف: {r['snippet']}\n"
        search_text += f"الرابط: {r['link']}\n"

    if language == "ar":
        prompt = f"""بناءً على نتائج البحث التالية، أجب على سؤال المستخدم بالعربية الفصحى.
أضف الروابط المفيدة في إجابتك باستخدام تنسيق HTML.

سؤال المستخدم: {query}

نتائج البحث:{search_text}

التنسيق المطلوب:
- إجابة واضحة ومفيدة
- استخدم إيموجي مناسبة
- أضف الروابط المفيدة: 🔗 <a href="الرابط">عنوان الرابط</a>
- كن مختصراً لكن شاملاً

⚠️ ماتستخدمش Markdown أبداً (لا *, **, #, |, ---). استخدم HTML فقط: <b>عريض</b> <i>مائل</i> <code>كود</code> • نقاط"""
        system = "أنت مساعد ذكي يجيب بالعربية الفصحى بناءً على نتائج بحث حقيقية. استخدم إيموجي وتنسيق HTML جميل. ماتستخدمش Markdown أبداً."
    else:
        prompt = f"""Based on the following search results, answer the user's question in English.
Include useful links in your answer using HTML format.

User's question: {query}

Search results:{search_text}

Format requirements:
- Clear and helpful answer
- Use appropriate emojis
- Include useful links: 🔗 <a href="link">Link title</a>
- Be concise but comprehensive

⚠️ NEVER use Markdown (no *, **, #, |, ---). Use HTML only: <b>bold</b> <i>italic</i> <code>code</code> • bullets"""
        system = "You are a smart assistant answering based on real search results. Use emojis and nice HTML formatting. NEVER use Markdown."

    response = call_ai_sync(prompt, system_prompt=system, task_type="chat", temperature=0.5, max_tokens=1500)
    from formatters import clean_ai_response
    if response:
        response = clean_ai_response(response)
    return response or ("لم أتمكن من معالجة نتائج البحث. 🤖" if language == "ar" else "I couldn't process search results. 🤖")


async def search_and_summarize_async(query: str, language: str = "ar") -> str:
    """البحث والتلخيص (غير متزامن)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: _search_and_summarize_sync(query, language)
    )


# Keep sync version for backward compatibility
def search_and_summarize(query: str, language: str = "ar") -> str:
    """البحث والتلخيص (متزامن - للتوافق مع الكود القديم)"""
    return _search_and_summarize_sync(query, language)


# ═══════════════════════════════════════
# البحث العميق - Deep Search
# ═══════════════════════════════════════

def _deep_search_and_summarize_sync(query: str, language: str = "ar") -> str:
    """
    البحث العميق - يستخدم نماذج أقوى وبحث أشمل
    يجمع نتائج من بحث الويب + بحث الأخبار
    ثم يلخص بنموذج Deep Search مخصص
    """
    from provider_manager import call_ai_sync

    # 1. بحث متعدد المصادر
    web_results = _search_web_sync(query, max_results=8)
    news_results = _search_news_sync(query, max_results=5)

    if not web_results and not news_results:
        # لو مفيش نتائج، نحاول بالإجابة المباشرة
        if language == "ar":
            prompt = f"""أجب على السؤال التالي بأفضل ما تعرفه بشكل مفصل وشامل.

السؤال: {query}

⚠️ ماتستخدمش Markdown (لا *, **, #, |). استخدم HTML فقط: <b>عريض</b> <i>مائل</i> <code>كود</code> • نقاط"""
            system = "أنت مساعد ذكي متخصص في البحث العميق. تجيب بالعربية الفصحى بشكل مفصل وشامل. ماتستخدمش Markdown أبداً."
        else:
            prompt = f"""Answer the following question comprehensively and in detail.

Question: {query}

⚠️ NEVER use Markdown (no *, **, #, |). Use HTML only: <b>bold</b> <i>italic</i> <code>code</code> • bullets"""
            system = "You are a smart assistant specialized in deep research. Answer comprehensively. NEVER use Markdown."

        response = call_ai_sync(prompt, system_prompt=system, task_type="deep_search", temperature=0.4, max_tokens=3000)
        from formatters import clean_ai_response
        if response:
            response = clean_ai_response(response)
        return response or ("لم أتمكن من العثور على معلومات كافية. 🤖" if language == "ar" else "I couldn't find enough information. 🤖")

    # 2. تجميع كل النتائج
    search_text = ""
    if web_results:
        search_text += "\n🌐 نتائج بحث الويب:\n" if language == "ar" else "\n🌐 Web Search Results:\n"
        for i, r in enumerate(web_results, 1):
            search_text += f"\n--- نتيجة ويب {i} ---\n"
            search_text += f"العنوان: {r['title']}\n"
            search_text += f"المقتطف: {r['snippet']}\n"
            search_text += f"الرابط: {r['link']}\n"

    if news_results:
        search_text += "\n📰 نتائج أخبار:\n" if language == "ar" else "\n📰 News Results:\n"
        for i, r in enumerate(news_results, 1):
            search_text += f"\n--- خبر {i} ---\n"
            search_text += f"العنوان: {r['title']}\n"
            search_text += f"المقتطف: {r['snippet']}\n"
            search_text += f"الرابط: {r['link']}\n"
            if r.get('source'):
                search_text += f"المصدر: {r['source']}\n"
            if r.get('date'):
                search_text += f"التاريخ: {r['date']}\n"

    # 3. تلخيص شامل باستخدام نموذج Deep Search
    if language == "ar":
        prompt = f"""🔬 <b>بحث عميق</b>

بناءً على نتائج البحث الشاملة التالية، قدّم إجابة مفصلة ومنظمة بالعربية الفصحى.

سؤال المستخدم: {query}

نتائج البحث الشاملة:{search_text}

المطلوب:
- إجابة شاملة ومفصلة
- تنظيم المعلومات بوضوح
- ذكر المصادر والروابط
- مقارنة بين الآراء إن وُجدت
- استنتاجات وتوقعات إن أمكن
- الروابط: 🔗 <a href="الرابط">عنوان الرابط</a>

⚠️ ماتستخدمش Markdown أبداً (لا *, **, #, |, ---). استخدم HTML فقط: <b>عريض</b> <i>مائل</i> <code>كود</code> • نقاط"""
        system = """أنت باحث متخصص في البحث العميق. تجيب بالعربية الفصحى بشكل شامل ومفصل.
تنظم المعلومات بشكل واضح مع ذكر المصادر.
ماتستخدمش Markdown أبداً. استخدم HTML فقط: <b>عريض</b> <i>مائل</i> <code>كود</code> • نقاط."""
    else:
        prompt = f"""🔬 <b>Deep Search</b>

Based on the following comprehensive search results, provide a detailed and organized answer in English.

User's question: {query}

Comprehensive search results:{search_text}

Requirements:
- Comprehensive and detailed answer
- Well-organized information
- Cite sources and links
- Compare different viewpoints if available
- Include conclusions and predictions if possible
- Links: 🔗 <a href="link">Link title</a>

⚠️ NEVER use Markdown (no *, **, #, |, ---). Use HTML only: <b>bold</b> <i>italic</i> <code>code</code> • bullets"""
        system = """You are a researcher specialized in deep search. Answer comprehensively and in detail.
Organize information clearly with source citations.
NEVER use Markdown. Use HTML only: <b>bold</b> <i>italic</i> <code>code</code> • bullets."""

    response = call_ai_sync(prompt, system_prompt=system, task_type="deep_search", temperature=0.4, max_tokens=3000)
    from formatters import clean_ai_response
    if response:
        response = clean_ai_response(response)
    return response or ("لم أتمكن من معالجة نتائج البحث العميق. 🤖" if language == "ar" else "I couldn't process deep search results. 🤖")


async def deep_search_and_summarize_async(query: str, language: str = "ar") -> str:
    """البحث العميق والتلخيص (غير متزامن)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: _deep_search_and_summarize_sync(query, language)
    )


def format_search_results(query: str, results: List[Dict], language: str = "ar") -> str:
    """تنسيق نتائج البحث كرسالة تيليجرام جميلة"""
    if not results:
        if language == "ar":
            return f"🔍 لم أجد نتائج لـ '{query}'"
        return f"🔍 No results found for '{query}'"

    if language == "ar":
        message = f"🔍 <b>نتائج البحث: {query}</b>\n━━━━━━━━━━━━━━━━━\n\n"
    else:
        message = f"🔍 <b>Search Results: {query}</b>\n━━━━━━━━━━━━━━━━━\n\n"

    for i, r in enumerate(results[:5], 1):
        title = r.get("title", "بدون عنوان" if language == "ar" else "No title")
        snippet = r.get("snippet", "")
        link = r.get("link", "")
        source = r.get("source", "")

        if language == "ar":
            message += f"{i}. 📄 <b>{title}</b>\n"
            if snippet:
                message += f"   {snippet[:200]}\n"
            if source:
                message += f"   📡 {source}\n"
            if link:
                message += f'   🔗 <a href="{link}">اقرأ المزيد</a>\n'
        else:
            message += f"{i}. 📄 <b>{title}</b>\n"
            if snippet:
                message += f"   {snippet[:200]}\n"
            if source:
                message += f"   📡 {source}\n"
            if link:
                message += f'   🔗 <a href="{link}">Read more</a>\n'
        message += "\n"

    message += "━━━━━━━━━━━━━━━━━\n🤖 <i>My Bro — بحث الويب</i>"
    return message
