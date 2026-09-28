-- ================================================================
-- ANIMEZONE — COMPLETE DATABASE SCHEMA
-- Content catalog with 18+ filtering, bookmarks, analytics
-- ================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============= USERS TABLE =============
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    language_code VARCHAR(10) DEFAULT 'en',

    show_nsfw BOOLEAN DEFAULT FALSE,
    theme VARCHAR(10) DEFAULT 'dark',
    notifications_enabled BOOLEAN DEFAULT TRUE,

    total_clicks INTEGER DEFAULT 0,
    total_joins INTEGER DEFAULT 0,
    total_shares INTEGER DEFAULT 0,
    total_bookmarks INTEGER DEFAULT 0,

    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_active TIMESTAMPTZ DEFAULT NOW(),
    last_app_open TIMESTAMPTZ,
    app_opens_count INTEGER DEFAULT 0,
    source VARCHAR(100) DEFAULT 'organic',
    referred_by BIGINT,

    is_banned BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_users_active ON users(last_active);
CREATE INDEX IF NOT EXISTS idx_users_banned ON users(is_banned);

-- ============= CATEGORIES TABLE =============
CREATE TABLE IF NOT EXISTS categories (
    category_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    emoji VARCHAR(10) DEFAULT '📂',
    slug VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_nsfw BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    title_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO categories (name, emoji, slug, sort_order, is_nsfw) VALUES
('Anime', '🎌', 'anime', 1, FALSE),
('Movies', '🎬', 'movies', 2, FALSE),
('Web Series', '📺', 'web-series', 3, FALSE)
ON CONFLICT (name) DO NOTHING;

-- ============= GENRES TABLE =============
CREATE TABLE IF NOT EXISTS genres (
    genre_id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    emoji VARCHAR(10) DEFAULT '🎭',
    slug VARCHAR(50) NOT NULL UNIQUE
);

INSERT INTO genres (name, emoji, slug) VALUES
('Action', '⚔️', 'action'),
('Adventure', '🏔️', 'adventure'),
('Comedy', '😂', 'comedy'),
('Drama', '🎭', 'drama'),
('Fantasy', '✨', 'fantasy'),
('Horror', '👻', 'horror'),
('Mystery', '🔍', 'mystery'),
('Psychological', '🧠', 'psychological'),
('Romance', '💕', 'romance'),
('Sci-Fi', '🚀', 'sci-fi'),
('Shonen', '⚡', 'shonen'),
('Slice of Life', '🌸', 'slice-of-life'),
('Sports', '🏋️', 'sports'),
('Supernatural', '👹', 'supernatural'),
('Thriller', '😱', 'thriller'),
('Isekai', '🌀', 'isekai'),
('Mecha', '🤖', 'mecha'),
('Ecchi', '🔥', 'ecchi'),
('Seinen', '🕶️', 'seinen'),
('Josei', '🌷', 'josei'),
('Shoujo', '🎀', 'shoujo'),
('Harem', '💗', 'harem'),
('Martial Arts', '🥋', 'martial-arts'),
('School', '🏫', 'school'),
('Military', '🎖️', 'military'),
('Magic', '🪄', 'magic'),
('Historical', '🏛️', 'historical'),
('Music', '🎵', 'music'),
('Demons', '😈', 'demons'),
('Vampire', '🧛', 'vampire'),
('Game', '🎮', 'game'),
('Parody', '🤡', 'parody'),
('Superhero', '🦸', 'superhero'),
('Gourmet', '🍜', 'gourmet'),
('Crime', '🔫', 'crime'),
('Cyberpunk', '🌆', 'cyberpunk'),
('Kids', '🧒', 'kids')
ON CONFLICT (name) DO NOTHING;

-- ============= TITLES TABLE =============
CREATE TABLE IF NOT EXISTS titles (
    title_id BIGSERIAL PRIMARY KEY,

    title VARCHAR(255) NOT NULL,
    title_alt VARCHAR(255),
    slug VARCHAR(255) NOT NULL UNIQUE,
    category_id INTEGER NOT NULL REFERENCES categories(category_id),
    description TEXT DEFAULT '',

    channel_link TEXT NOT NULL,
    channel_username VARCHAR(255),

    image_file_id TEXT,
    image_url TEXT,

    language VARCHAR(50) DEFAULT 'Hindi',
    status VARCHAR(20) DEFAULT 'Ongoing',
    episode_count INTEGER DEFAULT 0,
    quality VARCHAR(50) DEFAULT '720p + 1080p',
    release_year INTEGER,

    is_nsfw BOOLEAN DEFAULT FALSE,

    total_clicks INTEGER DEFAULT 0,
    total_joins INTEGER DEFAULT 0,
    total_bookmarks INTEGER DEFAULT 0,
    total_shares INTEGER DEFAULT 0,
    rating DECIMAL(2,1) DEFAULT 0.0,
    rating_count INTEGER DEFAULT 0,

    is_featured BOOLEAN DEFAULT FALSE,
    featured_order INTEGER DEFAULT 0,

    is_active BOOLEAN DEFAULT TRUE,
    is_approved BOOLEAN DEFAULT TRUE,
    deleted_at TIMESTAMPTZ,
    channel_alive BOOLEAN DEFAULT TRUE,
    last_checked_at TIMESTAMPTZ,

    added_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    added_by BIGINT
);

CREATE INDEX IF NOT EXISTS idx_titles_category ON titles(category_id);
CREATE INDEX IF NOT EXISTS idx_titles_featured ON titles(is_featured, featured_order) WHERE is_featured = TRUE;
CREATE INDEX IF NOT EXISTS idx_titles_active ON titles(is_active, channel_alive);
CREATE INDEX IF NOT EXISTS idx_titles_nsfw ON titles(is_nsfw);
CREATE INDEX IF NOT EXISTS idx_titles_clicks ON titles(total_clicks DESC);
CREATE INDEX IF NOT EXISTS idx_titles_added ON titles(added_at DESC);
CREATE INDEX IF NOT EXISTS idx_titles_slug ON titles(slug);
CREATE INDEX IF NOT EXISTS idx_titles_search ON titles USING gin(title gin_trgm_ops);

-- ============= TITLE GENRES (many-to-many) =============
CREATE TABLE IF NOT EXISTS title_genres (
    title_id BIGINT NOT NULL REFERENCES titles(title_id) ON DELETE CASCADE,
    genre_id INTEGER NOT NULL REFERENCES genres(genre_id) ON DELETE CASCADE,
    PRIMARY KEY (title_id, genre_id)
);

CREATE INDEX IF NOT EXISTS idx_tg_title ON title_genres(title_id);
CREATE INDEX IF NOT EXISTS idx_tg_genre ON title_genres(genre_id);

-- ============= TITLE TAGS =============
CREATE TABLE IF NOT EXISTS title_tags (
    tag_id SERIAL PRIMARY KEY,
    title_id BIGINT NOT NULL REFERENCES titles(title_id) ON DELETE CASCADE,
    tag VARCHAR(50) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tags_title ON title_tags(title_id);

-- ============= BOOKMARKS =============
CREATE TABLE IF NOT EXISTS bookmarks (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title_id BIGINT NOT NULL REFERENCES titles(title_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, title_id)
);

CREATE INDEX IF NOT EXISTS idx_bookmarks_user ON bookmarks(user_id);

-- ============= CLICK TRACKING =============
CREATE TABLE IF NOT EXISTS click_events (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    title_id BIGINT NOT NULL REFERENCES titles(title_id) ON DELETE CASCADE,
    event_type VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clicks_title ON click_events(title_id);
CREATE INDEX IF NOT EXISTS idx_clicks_time ON click_events(created_at);
CREATE INDEX IF NOT EXISTS idx_clicks_type ON click_events(event_type);

-- ============= RATINGS =============
CREATE TABLE IF NOT EXISTS ratings (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    title_id BIGINT NOT NULL REFERENCES titles(title_id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, title_id)
);

CREATE INDEX IF NOT EXISTS idx_ratings_title ON ratings(title_id);

-- ============= DAILY ANALYTICS =============
CREATE TABLE IF NOT EXISTS daily_analytics (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    total_app_opens INTEGER DEFAULT 0,
    total_clicks INTEGER DEFAULT 0,
    total_joins INTEGER DEFAULT 0,
    total_new_users INTEGER DEFAULT 0,
    total_bookmarks INTEGER DEFAULT 0,
    total_shares INTEGER DEFAULT 0,
    UNIQUE(date)
);

CREATE INDEX IF NOT EXISTS idx_da_date ON daily_analytics(date);

-- ============= TITLE DAILY STATS =============
CREATE TABLE IF NOT EXISTS title_daily_stats (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    title_id BIGINT NOT NULL REFERENCES titles(title_id) ON DELETE CASCADE,
    clicks INTEGER DEFAULT 0,
    joins INTEGER DEFAULT 0,
    bookmarks INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    UNIQUE(date, title_id)
);

CREATE INDEX IF NOT EXISTS idx_tds_date ON title_daily_stats(date);
CREATE INDEX IF NOT EXISTS idx_tds_title ON title_daily_stats(title_id);

-- ============= PLATFORM SETTINGS =============
CREATE TABLE IF NOT EXISTS platform_settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO platform_settings (key, value) VALUES
('app_name', 'AnimeZone'),
('app_tagline', 'Your Anime Universe'),
('max_featured', '5'),
('max_bookmarks_per_user', '100'),
('items_per_page', '20'),
('welcome_message', E'🎌 Welcome to AnimeZone!\n\nBrowse thousands of anime, movies, and web series — all in one place!\n\nTap the button below to start exploring!'),
('nsfw_warning_text', '⚠️ This section contains 18+ content. Are you sure you want to proceed?'),
('maintenance_mode', 'false'),
('maintenance_message', '🔧 We are updating. Back in 5 minutes!')
ON CONFLICT DO NOTHING;

-- ============= BROADCASTS =============
CREATE TABLE IF NOT EXISTS broadcasts (
    broadcast_id BIGSERIAL PRIMARY KEY,
    admin_id BIGINT NOT NULL,
    content_type VARCHAR(20) DEFAULT 'text',
    content TEXT,
    media_file_id TEXT,
    caption TEXT,
    buttons_json JSONB,
    total_targets INTEGER DEFAULT 0,
    sent_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    blocked_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- ============= CONTENT REQUESTS =============
CREATE TABLE IF NOT EXISTS content_requests (
    request_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    title_requested VARCHAR(255) NOT NULL,
    category VARCHAR(50),
    status VARCHAR(20) DEFAULT 'pending',
    admin_note TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cr_status ON content_requests(status);

-- ============= BOT ADMINS (panel-managed moderators) =============
CREATE TABLE IF NOT EXISTS bot_admins (
    user_id BIGINT PRIMARY KEY,
    role VARCHAR(20) DEFAULT 'moderator',
    first_name VARCHAR(255),
    username VARCHAR(255),
    added_by BIGINT,
    added_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============= CLONE BOTS (extra bot tokens on the same server/DB/Mini App) =============
CREATE TABLE IF NOT EXISTS bot_clones (
    bot_id BIGINT PRIMARY KEY,
    token VARCHAR(255) NOT NULL,
    username VARCHAR(255),
    name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_maintenance BOOLEAN DEFAULT FALSE,
    added_by BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bot_subscribers (
    bot_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    first_name VARCHAR(255),
    username VARCHAR(255),
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (bot_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_bot_subscribers_bot ON bot_subscribers(bot_id);
