"""
Определение SQL-схем таблиц базы данных.
Используется при инициализации БД для создания таблиц.
"""

USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id     INTEGER UNIQUE NOT NULL,
    username        TEXT,
    first_name      TEXT,
    role            TEXT,
    goal            TEXT,
    branch_id       TEXT,
    current_screen_id       TEXT,
    last_completed_screen_id TEXT,
    nurture_stage   INTEGER DEFAULT 0,
    nurture_branch_id       TEXT,
    clicked_trial_cta       INTEGER DEFAULT 0,
    clicked_manager_cta     INTEGER DEFAULT 0,
    cta_shown_at    TEXT,
    is_admin        INTEGER DEFAULT 0,
    is_active       INTEGER DEFAULT 1,
    is_blocked      INTEGER DEFAULT 0,
    segment         TEXT,
    source          TEXT,
    campaign_tag    TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    last_activity_at TEXT NOT NULL
);
"""

ANALYTICS_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS analytics_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    screen_id   TEXT,
    event_type  TEXT NOT NULL,
    event_data  TEXT,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
);
"""

NURTURE_QUEUE_TABLE = """
CREATE TABLE IF NOT EXISTS nurture_queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    branch_id   TEXT NOT NULL,
    next_step   INTEGER NOT NULL DEFAULT 1,
    next_send_at TEXT NOT NULL,
    is_active   INTEGER DEFAULT 1,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
);
"""

BROADCASTS_TABLE = """
CREATE TABLE IF NOT EXISTS broadcasts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_by      INTEGER NOT NULL,
    text            TEXT NOT NULL,
    media_type      TEXT,
    media_file_id   TEXT,
    segment_filter  TEXT,
    status          TEXT NOT NULL DEFAULT 'draft',
    scheduled_at    TEXT,
    sent_at         TEXT,
    created_at      TEXT NOT NULL
);
"""

BROADCAST_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS broadcast_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    broadcast_id    INTEGER NOT NULL,
    user_id         INTEGER NOT NULL,
    status          TEXT NOT NULL,
    error           TEXT,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (broadcast_id) REFERENCES broadcasts(id)
);
"""

ALL_TABLES = [
    USERS_TABLE,
    ANALYTICS_EVENTS_TABLE,
    NURTURE_QUEUE_TABLE,
    BROADCASTS_TABLE,
    BROADCAST_LOGS_TABLE,
]
