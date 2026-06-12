"""
Migration: 001_initial_schema
Description: Create all initial database tables
Created: 2025-06-13

Consolidates CREATE TABLE statements from:
- memory.py: user_profiles, conversations, learning_progress, favorites, user_memories, banned_users
- premium.py: premium_users, usage_tracking, workspace_items, smart_alerts, premium_history
- admin.py: admin_users
- dashboard.py: bot_stats
- news_editor.py: sent_articles

Also includes all ALTER TABLE ADD COLUMN migrations and CREATE INDEX statements.
All statements use IF NOT EXISTS for idempotent safety on existing databases.
"""

MIGRATION_ID = "001_initial_schema"

# ─────────────────────────────────────────────────────────
# PostgreSQL
# ─────────────────────────────────────────────────────────
UP_PG = """
-- ═══ memory.py tables ═══

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id BIGINT PRIMARY KEY,
    name TEXT DEFAULT '',
    language TEXT DEFAULT 'ar',
    news_time TEXT DEFAULT '12:00',
    sources TEXT DEFAULT '[]',
    subscribed INTEGER DEFAULT 0,
    response_length TEXT DEFAULT 'medium',
    notification_enabled INTEGER DEFAULT 1,
    interests TEXT DEFAULT '[]',
    favorite_companies TEXT DEFAULT '[]',
    created_at TEXT,
    last_interaction TEXT,
    commands_used INTEGER DEFAULT 0,
    chat_count INTEGER DEFAULT 0,
    last_news_delivery TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TEXT DEFAULT (NOW() AT TIME ZONE 'UTC'::text),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS learning_progress (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    topic TEXT NOT NULL,
    level TEXT DEFAULT 'explored',
    learned_at TEXT DEFAULT (NOW() AT TIME ZONE 'UTC'::text),
    UNIQUE(user_id, topic),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS favorites (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT DEFAULT '',
    url TEXT DEFAULT '',
    saved_at TEXT DEFAULT (NOW() AT TIME ZONE 'UTC'::text),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_memories (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    created_at TEXT DEFAULT (NOW() AT TIME ZONE 'UTC'::text),
    UNIQUE(user_id, key),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS banned_users (
    user_id BIGINT PRIMARY KEY,
    reason TEXT DEFAULT '',
    banned_at TEXT DEFAULT (NOW() AT TIME ZONE 'UTC'::text),
    banned_by TEXT DEFAULT '',
    warning_count INTEGER DEFAULT 0
);

-- ═══ memory.py indexes ═══

CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_learning_user ON learning_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id, category);
CREATE INDEX IF NOT EXISTS idx_memories_user ON user_memories(user_id, category);
CREATE INDEX IF NOT EXISTS idx_user_profiles_wa_phone ON user_profiles(wa_phone);

-- ═══ memory.py ALTER TABLE migrations (columns added post-initial CREATE) ═══

ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS last_news_delivery TEXT DEFAULT NULL;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS platform TEXT DEFAULT 'telegram';
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS wa_phone TEXT DEFAULT '';
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS profile_name TEXT DEFAULT '';

-- ═══ premium.py tables ═══

CREATE TABLE IF NOT EXISTS premium_users (
    user_id BIGINT PRIMARY KEY,
    plan TEXT DEFAULT 'free',
    premium_since TEXT DEFAULT NULL,
    premium_expires TEXT DEFAULT NULL,
    granted_by TEXT DEFAULT NULL,
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS usage_tracking (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    date TEXT NOT NULL,
    ai_messages INTEGER DEFAULT 0,
    pdf_analyses INTEGER DEFAULT 0,
    image_analyses INTEGER DEFAULT 0,
    youtube_summaries INTEGER DEFAULT 0,
    searches INTEGER DEFAULT 0,
    deep_searches INTEGER DEFAULT 0,
    UNIQUE(user_id, date),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workspace_items (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    item_type TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT DEFAULT '',
    url TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (NOW() AT TIME ZONE 'UTC'::text),
    updated_at TEXT DEFAULT (NOW() AT TIME ZONE 'UTC'::text),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS smart_alerts (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    topic TEXT NOT NULL,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (NOW() AT TIME ZONE 'UTC'::text),
    last_notified TEXT DEFAULT NULL,
    UNIQUE(user_id, topic),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS premium_history (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    action TEXT NOT NULL,
    plan_before TEXT DEFAULT 'free',
    plan_after TEXT DEFAULT 'free',
    granted_by TEXT DEFAULT NULL,
    expires TEXT DEFAULT NULL,
    created_at TEXT DEFAULT (NOW() AT TIME ZONE 'UTC'::text),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE
);

-- ═══ premium.py indexes ═══

CREATE INDEX IF NOT EXISTS idx_usage_user_date ON usage_tracking(user_id, date);
CREATE INDEX IF NOT EXISTS idx_workspace_user ON workspace_items(user_id, item_type);
CREATE INDEX IF NOT EXISTS idx_alerts_user ON smart_alerts(user_id, active);
CREATE INDEX IF NOT EXISTS idx_premium_history_user ON premium_history(user_id, created_at DESC);

-- ═══ premium.py ALTER TABLE migrations ═══

ALTER TABLE usage_tracking ADD COLUMN IF NOT EXISTS image_generations INTEGER DEFAULT 0;
ALTER TABLE usage_tracking ADD COLUMN IF NOT EXISTS image_edits INTEGER DEFAULT 0;
ALTER TABLE usage_tracking ADD COLUMN IF NOT EXISTS deep_searches INTEGER DEFAULT 0;

-- ═══ admin.py tables ═══

CREATE TABLE IF NOT EXISTS admin_users (
    user_id BIGINT PRIMARY KEY,
    username TEXT DEFAULT '',
    role TEXT DEFAULT 'admin',
    added_at TEXT DEFAULT (NOW() AT TIME ZONE 'UTC'::text),
    added_by TEXT DEFAULT 'system'
);

-- ═══ dashboard.py tables ═══

CREATE TABLE IF NOT EXISTS bot_stats (
    id SERIAL PRIMARY KEY,
    date TEXT NOT NULL,
    platform TEXT DEFAULT 'telegram',
    total_messages INTEGER DEFAULT 0,
    total_commands INTEGER DEFAULT 0,
    total_errors INTEGER DEFAULT 0,
    new_users INTEGER DEFAULT 0,
    active_users INTEGER DEFAULT 0,
    premium_users INTEGER DEFAULT 0,
    ai_requests INTEGER DEFAULT 0,
    search_requests INTEGER DEFAULT 0,
    pdf_analyses INTEGER DEFAULT 0,
    image_analyses INTEGER DEFAULT 0,
    voice_messages INTEGER DEFAULT 0,
    youtube_summaries INTEGER DEFAULT 0,
    UNIQUE(date, platform)
);

ALTER TABLE bot_stats ADD COLUMN IF NOT EXISTS platform TEXT DEFAULT 'telegram';

-- ═══ news_editor.py tables ═══

CREATE TABLE IF NOT EXISTS sent_articles (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    title_hash TEXT NOT NULL,
    source TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    published_date TEXT DEFAULT NULL,
    sent_date TEXT NOT NULL,
    score REAL DEFAULT 0,
    is_top_story INTEGER DEFAULT 0,
    UNIQUE(url, sent_date)
);

-- ═══ news_editor.py indexes ═══

CREATE INDEX IF NOT EXISTS idx_sent_url ON sent_articles(url);
CREATE INDEX IF NOT EXISTS idx_sent_title_hash ON sent_articles(title_hash);
CREATE INDEX IF NOT EXISTS idx_sent_date ON sent_articles(sent_date);
"""

# ─────────────────────────────────────────────────────────
# SQLite
# ─────────────────────────────────────────────────────────
UP_SQLITE = """
-- ═══ memory.py tables ═══

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id INTEGER PRIMARY KEY,
    name TEXT DEFAULT '',
    language TEXT DEFAULT 'ar',
    news_time TEXT DEFAULT '12:00',
    sources TEXT DEFAULT '[]',
    subscribed INTEGER DEFAULT 0,
    response_length TEXT DEFAULT 'medium',
    notification_enabled INTEGER DEFAULT 1,
    interests TEXT DEFAULT '[]',
    favorite_companies TEXT DEFAULT '[]',
    created_at TEXT,
    last_interaction TEXT,
    commands_used INTEGER DEFAULT 0,
    chat_count INTEGER DEFAULT 0,
    last_news_delivery TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
);

CREATE TABLE IF NOT EXISTS learning_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    topic TEXT NOT NULL,
    level TEXT DEFAULT 'explored',
    learned_at TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, topic),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
);

CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT DEFAULT '',
    url TEXT DEFAULT '',
    saved_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
);

CREATE TABLE IF NOT EXISTS user_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, key),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
);

CREATE TABLE IF NOT EXISTS banned_users (
    user_id INTEGER PRIMARY KEY,
    reason TEXT DEFAULT '',
    banned_at TEXT DEFAULT (datetime('now')),
    banned_by TEXT DEFAULT '',
    warning_count INTEGER DEFAULT 0
);

-- ═══ memory.py indexes ═══

CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_learning_user ON learning_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id, category);
CREATE INDEX IF NOT EXISTS idx_memories_user ON user_memories(user_id, category);

-- ═══ memory.py ALTER TABLE migrations ═══
-- Note: SQLite doesn't support IF NOT EXISTS on ALTER TABLE ADD COLUMN.
-- The migration runner handles errors gracefully for these statements.

ALTER TABLE user_profiles ADD COLUMN last_news_delivery TEXT DEFAULT NULL;
ALTER TABLE user_profiles ADD COLUMN platform TEXT DEFAULT 'telegram';
ALTER TABLE user_profiles ADD COLUMN wa_phone TEXT DEFAULT '';
ALTER TABLE user_profiles ADD COLUMN profile_name TEXT DEFAULT '';

-- ═══ premium.py tables ═══

CREATE TABLE IF NOT EXISTS premium_users (
    user_id INTEGER PRIMARY KEY,
    plan TEXT DEFAULT 'free',
    premium_since TEXT DEFAULT NULL,
    premium_expires TEXT DEFAULT NULL,
    granted_by TEXT DEFAULT NULL,
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
);

CREATE TABLE IF NOT EXISTS usage_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    ai_messages INTEGER DEFAULT 0,
    pdf_analyses INTEGER DEFAULT 0,
    image_analyses INTEGER DEFAULT 0,
    youtube_summaries INTEGER DEFAULT 0,
    searches INTEGER DEFAULT 0,
    deep_searches INTEGER DEFAULT 0,
    UNIQUE(user_id, date),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
);

CREATE TABLE IF NOT EXISTS workspace_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    item_type TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT DEFAULT '',
    url TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
);

CREATE TABLE IF NOT EXISTS smart_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    topic TEXT NOT NULL,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    last_notified TEXT DEFAULT NULL,
    UNIQUE(user_id, topic),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
);

CREATE TABLE IF NOT EXISTS premium_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    plan_before TEXT DEFAULT 'free',
    plan_after TEXT DEFAULT 'free',
    granted_by TEXT DEFAULT NULL,
    expires TEXT DEFAULT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
);

-- ═══ premium.py indexes ═══

CREATE INDEX IF NOT EXISTS idx_usage_user_date ON usage_tracking(user_id, date);
CREATE INDEX IF NOT EXISTS idx_workspace_user ON workspace_items(user_id, item_type);
CREATE INDEX IF NOT EXISTS idx_alerts_user ON smart_alerts(user_id, active);
CREATE INDEX IF NOT EXISTS idx_premium_history_user ON premium_history(user_id, created_at DESC);

-- ═══ premium.py ALTER TABLE migrations ═══

ALTER TABLE usage_tracking ADD COLUMN image_generations INTEGER DEFAULT 0;
ALTER TABLE usage_tracking ADD COLUMN image_edits INTEGER DEFAULT 0;
ALTER TABLE usage_tracking ADD COLUMN deep_searches INTEGER DEFAULT 0;

-- ═══ admin.py tables ═══

CREATE TABLE IF NOT EXISTS admin_users (
    user_id BIGINT PRIMARY KEY,
    username TEXT DEFAULT '',
    role TEXT DEFAULT 'admin',
    added_at TEXT DEFAULT (datetime('now')),
    added_by TEXT DEFAULT 'system'
);

-- ═══ dashboard.py tables ═══

CREATE TABLE IF NOT EXISTS bot_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    platform TEXT DEFAULT 'telegram',
    total_messages INTEGER DEFAULT 0,
    total_commands INTEGER DEFAULT 0,
    total_errors INTEGER DEFAULT 0,
    new_users INTEGER DEFAULT 0,
    active_users INTEGER DEFAULT 0,
    premium_users INTEGER DEFAULT 0,
    ai_requests INTEGER DEFAULT 0,
    search_requests INTEGER DEFAULT 0,
    pdf_analyses INTEGER DEFAULT 0,
    image_analyses INTEGER DEFAULT 0,
    voice_messages INTEGER DEFAULT 0,
    youtube_summaries INTEGER DEFAULT 0,
    UNIQUE(date, platform)
);

-- ═══ news_editor.py tables ═══

CREATE TABLE IF NOT EXISTS sent_articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    title_hash TEXT NOT NULL,
    source TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    published_date TEXT DEFAULT NULL,
    sent_date TEXT NOT NULL,
    score REAL DEFAULT 0,
    is_top_story INTEGER DEFAULT 0,
    UNIQUE(url, sent_date)
);

-- ═══ news_editor.py indexes ═══

CREATE INDEX IF NOT EXISTS idx_sent_url ON sent_articles(url);
CREATE INDEX IF NOT EXISTS idx_sent_title_hash ON sent_articles(title_hash);
CREATE INDEX IF NOT EXISTS idx_sent_date ON sent_articles(sent_date);
"""

DOWN = """
-- Not implementing down migrations for safety
-- Tables use IF NOT EXISTS so re-running is safe
"""
