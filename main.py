"""Main entry point for the AI News Bot."""

import logging
import sys
import os
from datetime import datetime

from config import CAIRO_TZ, LOG_LEVEL, MAX_NEWS_ITEMS, MIN_NEWS_ITEMS
from news_fetcher import fetch_all_news
from filters import filter_articles
from scorer import score_and_rank
from summarizer import generate_summaries, format_message
from telegram_sender import send_message, send_no_news_message

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ai_news_bot")


def run():
    """Main execution flow."""
    logger.info("=" * 60)
    logger.info("🤖 AI News Bot started")
    now = datetime.now(CAIRO_TZ)
    logger.info(f"Current time (Cairo): {now.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # Step 1: Fetch news from all sources
    logger.info("📡 Step 1: Fetching news from RSS feeds...")
    try:
        all_articles = fetch_all_news()
    except Exception as e:
        logger.error(f"Failed to fetch news: {e}")
        all_articles = []

    if not all_articles:
        logger.warning("No articles fetched from any source")
        send_no_news_message()
        return

    logger.info(f"📊 Fetched {len(all_articles)} total articles")

    # Step 2: Filter for AI-related content
    logger.info("🔍 Step 2: Filtering AI-related articles...")
    try:
        filtered = filter_articles(all_articles)
    except Exception as e:
        logger.error(f"Failed to filter articles: {e}")
        filtered = all_articles  # Use unfiltered as fallback

    if not filtered:
        logger.warning("No AI-related articles found after filtering")
        send_no_news_message()
        return

    logger.info(f"✅ {len(filtered)} AI-related articles after filtering")

    # Step 3: Score and rank
    logger.info("📈 Step 3: Scoring and ranking articles...")
    try:
        top_articles = score_and_rank(filtered, max_items=MAX_NEWS_ITEMS)
    except Exception as e:
        logger.error(f"Failed to score articles: {e}")
        top_articles = filtered[:MAX_NEWS_ITEMS]

    if not top_articles:
        logger.warning("No articles scored above threshold")
        send_no_news_message()
        return

    logger.info(f"🏆 Selected top {len(top_articles)} articles")

    # Step 4: Generate Arabic summaries
    logger.info("🧠 Step 4: Generating Arabic summaries...")
    try:
        summaries, most_important = generate_summaries(top_articles)
    except Exception as e:
        logger.error(f"Failed to generate summaries: {e}")
        # Fallback: use original titles
        summaries = []
        most_important = 1
        for article in top_articles:
            summaries.append({
                "arabic_title": article["title"],
                "arabic_summary": article.get("summary", "")[:200],
                "url": article["url"],
                "source": article.get("source", ""),
                "score": article.get("score", 0),
            })

    if not summaries:
        logger.error("No summaries generated")
        send_no_news_message()
        return

    # Step 5: Format and send message
    logger.info("📱 Step 5: Formatting and sending message...")
    try:
        message = format_message(summaries, most_important)
    except Exception as e:
        logger.error(f"Failed to format message: {e}")
        return

    # Truncate message if too long for Telegram (4096 char limit)
    if len(message) > 4000:
        message = message[:3950] + "\n\n...(تم قطع الرسالة لتجاوز الحد)"
        logger.warning("Message truncated to fit Telegram limit")

    success = send_message(message)

    if success:
        logger.info("✅ Daily AI news report sent successfully!")
    else:
        logger.error("❌ Failed to send daily AI news report")

    logger.info("=" * 60)
    logger.info("🤖 AI News Bot finished")
    logger.info("=" * 60)


if __name__ == "__main__":
    # Check for test mode
    if "--test" in sys.argv:
        logging.basicConfig(level=logging.DEBUG)
        logger.info("Running in TEST mode")

    # Validate required environment variables
    missing = []
    if not os.environ.get("BOT_TOKEN"):
        missing.append("BOT_TOKEN")
    if not os.environ.get("CHAT_ID"):
        missing.append("CHAT_ID")
    if not os.environ.get("GEMINI_API_KEY"):
        missing.append("GEMINI_API_KEY")

    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        logger.error("Set them before running the bot")
        sys.exit(1)

    run()
