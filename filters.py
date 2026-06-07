"""Filter news articles to keep only AI-related content."""

import logging
import re
from typing import List, Dict

from config import AI_KEYWORDS, EXCLUSION_KEYWORDS

logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    """Normalize text for keyword matching."""
    return re.sub(r"\s+", " ", text.lower().strip())


def is_ai_related(article: Dict) -> bool:
    """Check if an article is related to AI based on title and summary."""
    title = _normalize_text(article.get("title", ""))
    summary = _normalize_text(article.get("summary", ""))
    combined_text = f"{title} {summary}"

    # Check for AI keywords
    ai_keyword_count = 0
    matched_keywords = []
    for keyword in AI_KEYWORDS:
        if keyword.lower() in combined_text:
            ai_keyword_count += 1
            matched_keywords.append(keyword)

    article["ai_keyword_count"] = ai_keyword_count
    article["matched_keywords"] = matched_keywords

    # Must have at least 1 AI keyword to be considered
    return ai_keyword_count >= 1


def has_exclusion_keywords(article: Dict) -> bool:
    """Check if article contains exclusion keywords (non-AI content)."""
    title = _normalize_text(article.get("title", ""))
    summary = _normalize_text(article.get("summary", ""))
    combined_text = f"{title} {summary}"

    exclusion_count = 0
    for keyword in EXCLUSION_KEYWORDS:
        if keyword.lower() in combined_text:
            exclusion_count += 1

    article["exclusion_count"] = exclusion_count
    return exclusion_count > 0


def is_clickbait(title: str) -> bool:
    """Detect clickbait-style titles."""
    clickbait_patterns = [
        r"you won't believe",
        r"shocking",
        r"mind.?blowing",
        r"this one trick",
        r"what happens next",
        r"\bclick\b",
        r"must see",
        r"gone wrong",
        r"revealed:\s",
        r"exposed:\s",
        r"\d+ things?\s+you",
        r"before you (watch|read|buy)",
    ]
    title_lower = title.lower()
    for pattern in clickbait_patterns:
        if re.search(pattern, title_lower):
            return True
    return False


def filter_articles(articles: List[Dict]) -> List[Dict]:
    """Filter articles to keep only relevant AI news."""
    filtered = []

    for article in articles:
        title = article.get("title", "")

        # Skip clickbait
        if is_clickbait(title):
            logger.debug(f"Filtered clickbait: {title}")
            continue

        # Must be AI-related
        if not is_ai_related(article):
            logger.debug(f"Filtered non-AI: {title}")
            continue

        # Penalize articles with exclusion keywords (don't remove entirely,
        # just mark them — scorer will handle the rest)
        has_exclusion_keywords(article)

        filtered.append(article)

    logger.info(f"Filtered: {len(articles)} -> {len(filtered)} AI-related articles")
    return filtered
