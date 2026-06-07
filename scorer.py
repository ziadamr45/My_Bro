"""Score and rank news articles by importance."""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict

from config import (
    SOURCE_PRIORITIES,
    SOURCE_PRIORITY_WEIGHT,
    KEYWORD_RELEVANCE_WEIGHT,
    RECENCY_WEIGHT,
    TITLE_QUALITY_WEIGHT,
    CAIRO_TZ,
)

logger = logging.getLogger(__name__)


def _source_priority_score(article: Dict) -> float:
    """Score based on source credibility and priority."""
    domain = article.get("source_domain", "")

    # Check exact domain match
    if domain in SOURCE_PRIORITIES:
        return float(SOURCE_PRIORITIES[domain])

    # Check partial domain match
    for source_domain, priority in SOURCE_PRIORITIES.items():
        if source_domain in domain or domain.endswith(source_domain):
            return float(priority)

    # Unknown source — low score
    return 2.0


def _keyword_relevance_score(article: Dict) -> float:
    """Score based on number and quality of AI keyword matches."""
    keyword_count = article.get("ai_keyword_count", 0)
    matched = article.get("matched_keywords", [])

    if keyword_count == 0:
        return 0.0

    # High-value keywords that indicate major news
    high_value_keywords = {
        "openai", "chatgpt", "gpt-4", "gpt-5", "gemini",
        "deepmind", "anthropic", "claude ai", "agi",
        "ai regulation", "ai act", "ai safety",
        "ai funding", "ai investment",
    }

    high_value_count = sum(1 for k in matched if k.lower() in high_value_keywords)

    # Base score from keyword count (capped at 5)
    base_score = min(keyword_count, 5) / 5.0 * 7.0

    # Bonus for high-value keywords
    bonus = high_value_count * 1.5

    return min(base_score + bonus, 10.0)


def _recency_score(article: Dict) -> float:
    """Score based on how recent the article is."""
    published = article.get("published", "")
    if not published:
        return 5.0  # Middle score if we can't determine recency

    try:
        from dateutil import parser as date_parser
        dt = date_parser.parse(published)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        age_hours = (now - dt).total_seconds() / 3600

        if age_hours < 0:
            return 10.0  # Future article (clock skew) — give max score
        elif age_hours < 6:
            return 10.0
        elif age_hours < 12:
            return 8.0
        elif age_hours < 24:
            return 6.0
        elif age_hours < 48:
            return 3.0
        else:
            return 1.0
    except Exception:
        return 5.0


def _title_quality_score(article: Dict) -> float:
    """Score based on title quality indicators."""
    title = article.get("title", "")
    exclusion_count = article.get("exclusion_count", 0)

    score = 5.0  # Base score

    # Longer, more specific titles tend to be more important
    if len(title) > 50:
        score += 1.0
    if len(title) > 80:
        score += 0.5

    # Penalize exclusion keywords
    score -= exclusion_count * 2.0

    # Bonus for source domain being a known entity
    source = article.get("source", "")
    tier1_sources = ["OpenAI Blog", "Google AI Blog", "Microsoft AI Blog", "NVIDIA Blog", "Reuters"]
    if source in tier1_sources:
        score += 2.0

    return max(score, 0.0)


def score_article(article: Dict) -> float:
    """Calculate composite score for an article."""
    source_score = _source_priority_score(article) * SOURCE_PRIORITY_WEIGHT
    keyword_score = _keyword_relevance_score(article) * KEYWORD_RELEVANCE_WEIGHT
    recency_score = _recency_score(article) * RECENCY_WEIGHT
    title_score = _title_quality_score(article) * TITLE_QUALITY_WEIGHT

    total = source_score + keyword_score + recency_score + title_score

    return round(total, 2)


def score_and_rank(articles: List[Dict], max_items: int = 5) -> List[Dict]:
    """Score all articles and return top items."""
    if not articles:
        return []

    # Calculate scores
    for article in articles:
        article["score"] = score_article(article)

    # Sort by score (descending)
    ranked = sorted(articles, key=lambda x: x["score"], reverse=True)

    # Log top scores for debugging
    for i, article in enumerate(ranked[:10]):
        logger.info(
            f"  #{i+1} Score: {article['score']:.1f} | "
            f"Source: {article.get('source', 'unknown')} | "
            f"Title: {article['title'][:60]}..."
        )

    # Return top items
    top = ranked[:max_items]

    logger.info(f"Selected top {len(top)} articles (from {len(articles)} candidates)")
    return top
