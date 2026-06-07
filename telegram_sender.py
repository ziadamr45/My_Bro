"""Send messages to Telegram."""

import logging
from typing import Optional

import requests

from config import BOT_TOKEN, CHAT_ID, MAX_RETRIES, RETRY_DELAY_SECONDS, REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


def send_message(text: str, chat_id: Optional[str] = None) -> bool:
    """Send a text message to Telegram."""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set")
        return False

    target_chat_id = chat_id or CHAT_ID
    if not target_chat_id:
        logger.error("CHAT_ID not set")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": target_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()

            result = response.json()
            if result.get("ok"):
                logger.info("Message sent successfully to Telegram")
                return True
            else:
                logger.error(f"Telegram API error: {result.get('description', 'Unknown error')}")
                return False

        except requests.exceptions.RequestException as e:
            logger.warning(f"Telegram send attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                import time
                time.sleep(RETRY_DELAY_SECONDS)

    logger.error("Failed to send message after all retries")
    return False


def send_no_news_message() -> bool:
    """Send the 'no important news' message."""
    message = "لا توجد اليوم أخبار كبيرة في مجال الذكاء الاصطناعي تستحق التنبيه."
    return send_message(message)


def test_connection() -> bool:
    """Test the Telegram bot connection."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"

    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        result = response.json()
        if result.get("ok"):
            bot_info = result.get("result", {})
            logger.info(f"Bot connected: @{bot_info.get('username', 'unknown')}")
            return True
        else:
            logger.error(f"Bot connection failed: {result.get('description', 'Unknown')}")
            return False
    except Exception as e:
        logger.error(f"Bot connection error: {e}")
        return False
