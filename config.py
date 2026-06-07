"""Configuration constants for the AI News Bot."""

import os
from datetime import datetime, timezone, timedelta

# Cairo timezone
CAIRO_TZ = timezone(timedelta(hours=2))

# Environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# News settings
MAX_NEWS_ITEMS = 5
MIN_NEWS_ITEMS = 1
NEWS_LOOKBACK_HOURS = 24

# Scoring weights
SOURCE_PRIORITY_WEIGHT = 4.0
KEYWORD_RELEVANCE_WEIGHT = 3.0
RECENCY_WEIGHT = 1.5
TITLE_QUALITY_WEIGHT = 1.0

# Source priority levels (10 = highest)
SOURCE_PRIORITIES = {
    # Highest priority (Tier 1)
    "reuters.com": 10,
    "openai.com": 10,
    "deepmind.google": 10,
    "deepmind.com": 10,
    "anthropic.com": 10,
    "blogs.microsoft.com": 9,
    "microsoft.com": 9,
    "blogs.nvidia.com": 9,
    "nvidia.com": 9,
    # Secondary priority (Tier 2)
    "techcrunch.com": 7,
    "technologyreview.com": 7,
    "venturebeat.com": 6,
    "theverge.com": 6,
    "huggingface.co": 6,
    # Additional sources
    "arstechnica.com": 5,
    "wired.com": 5,
    "zdnet.com": 4,
    "engadget.com": 4,
    "blog.google": 7,
    "ai.google": 8,
}

# AI-related keywords for filtering (case-insensitive)
AI_KEYWORDS = [
    "openai", "chatgpt", "gpt-4", "gpt-5", "gpt model", "o1", "o3",
    "google ai", "gemini", "deepmind", "alphafold",
    "anthropic", "claude ai",
    "xai", "grok",
    "meta ai", "llama",
    "microsoft ai", "copilot ai", "phi-",
    "nvidia ai", "nvidia chip", "gpu ai",
    "ai agent", "ai agents", "autonomous ai",
    "foundation model", "large language model", "llm",
    "ai research", "ai paper", "neurips", "icml", "iclr",
    "ai funding", "ai investment", "ai valuation",
    "ai regulation", "ai law", "ai policy", "ai act",
    "ai product", "ai launch", "ai release",
    "artificial intelligence", "machine learning",
    "generative ai", "diffusion model",
    "ai safety", "ai alignment", "ai risk",
    "transformer model", "multimodal ai",
    "ai chip", "ai hardware", "ai infrastructure",
    "sora", "dall-e", "midjourney",
    "agi", "artificial general intelligence",
]

# Exclusion keywords (if found, reduce score significantly)
EXCLUSION_KEYWORDS = [
    "smartphone", "iphone", "android phone", "samsung galaxy",
    "laptop review", "gaming laptop", "macbook",
    "gaming", "game release", "esports", "playstation", "xbox",
    "crypto", "bitcoin", "ethereum", "nft",
    "stock market", "share price",
    "software update", "ios update", "android update",
    "rumor", "leaked", "unconfirmed",
    "discount", "deal", "sale",
]

# RSS Feed URLs
RSS_FEEDS = {
    # Tier 1 sources
    "OpenAI Blog": "https://openai.com/blog/rss.xml",
    "Google AI Blog": "https://blog.google/technology/ai/rss/",
    "Microsoft AI Blog": "https://blogs.microsoft.com/ai/feed/",
    "NVIDIA Blog": "https://blogs.nvidia.com/feed/",
    # Tier 2 sources
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    "MIT Tech Review": "https://www.technologyreview.com/feed/",
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",
    "Ars Technica AI": "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "Wired AI": "https://www.wired.com/feed/tag/ai/latest/rss",
}

# Gemini API settings
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_MAX_TOKENS = 2048
GEMINI_TEMPERATURE = 0.3

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
REQUEST_TIMEOUT_SECONDS = 30

# Logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
