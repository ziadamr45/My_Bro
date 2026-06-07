"""Fetch AI news from RSS feeds and web sources."""

import logging
import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
import feedparser
import requests

from config import (
    RSS_FEEDS,
    NEWS_LOOKBACK_HOURS,
    CAIRO_TZ,
    REQUEST_TIMEOUT_SECONDS,
    MAX_RETRIES,
    RETRY_DELAY_SECONDS,
)

logger = logging.getLogger(__name__)


def _make_request_with_retry(url: str) -> Optional[str]:
    """Make HTTP request with retries."""
    for attempt in range(MAX_RETRIES):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; AINewsBot/1.0; +https://github.com/ziadamr45)"
            }
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.warning(f"Attempt {attempt + 1}/{MAX_RETRIES} failed for {url}: {e}")
            if attempt < MAX_RETRIES - 1:
                import time
                time.sleep(RETRY_DELAY_SECONDS)
    return None


def _is_recent(published_date: str, lookback_hours: int = NEWS_LOOKBACK_HOURS) -> bool:
    """Check if an article was published within the lookback window."""
    try:
        # feedparser can parse most date formats
        from time import mktime
        parsed_time = feedparser._parse_date(published_date)
        if parsed_time is None:
            # Try direct parsing
            try:
                dt = datetime.fromisoformat(published_date.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return True  # If we can't parse the date, include it
        else:
            dt = datetime.fromtimestamp(mktime(parsed_time), tz=timezone.utc)

        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        return dt >= cutoff
    except Exception:
        # If date parsing fails, include the article (better safe than sorry)
        return True


def _content_hash(title: str, url: str) -> str:
    """Generate a hash for deduplication."""
    normalized = (title.strip().lower() + url.strip().lower()).encode("utf-8")
    return hashlib.md5(normalized).hexdigest()


def fetch_rss_feed(feed_name: str, feed_url: str) -> List[Dict]:
    """Fetch and parse a single RSS feed."""
    articles = []
    try:
        logger.info(f"Fetching RSS feed: {feed_name} ({feed_url})")

        # Try fetching with requests first for better control
        xml_content = _make_request_with_retry(feed_url)
        if xml_content:
            feed = feedparser.parse(xml_content)
        else:
            # Fallback to direct feedparser
            feed = feedparser.parse(feed_url)

        if feed.bozo and not feed.entries:
            logger.warning(f"RSS feed {feed_name} returned malformed data: {feed.bozo_exception}")
            return articles

        for entry in feed.entries:
            try:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                published = entry.get("published", entry.get("updated", ""))

                # Remove HTML tags from summary
                if summary:
                    import re
                    summary = re.sub(r"<[^>]+>", "", summary)
                    summary = re.sub(r"\s+", " ", summary).strip()

                if not title or not link:
                    continue

                # Check recency
                if published and not _is_recent(published):
                    continue

                articles.append({
                    "title": title,
                    "url": link,
                    "summary": summary[:500] if summary else "",
                    "published": published,
                    "source": feed_name,
                    "source_domain": _extract_domain(link),
                    "content_hash": _content_hash(title, link),
                })

            except Exception as e:
                logger.warning(f"Error parsing entry from {feed_name}: {e}")
                continue

        logger.info(f"Fetched {len(articles)} articles from {feed_name}")

    except Exception as e:
        logger.error(f"Error fetching RSS feed {feed_name}: {e}")

    return articles


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        return domain
    except Exception:
        return ""


def fetch_all_news() -> List[Dict]:
    """Fetch news from all configured RSS sources."""
    all_articles = []
    seen_hashes = set()

    for feed_name, feed_url in RSS_FEEDS.items():
        articles = fetch_rss_feed(feed_name, feed_url)
        for article in articles:
            # Deduplicate by content hash
            if article["content_hash"] not in seen_hashes:
                seen_hashes.add(article["content_hash"])
                all_articles.append(article)

    logger.info(f"Total unique articles fetched: {len(all_articles)}")
    return all_articles
