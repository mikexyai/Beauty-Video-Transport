CREATE SCHEMA IF NOT EXISTS beauty;

CREATE TABLE IF NOT EXISTS beauty.ai_beauty_sources (
    id BIGSERIAL PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_value TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT true,
    priority INTEGER NOT NULL DEFAULT 0,
    last_checked_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_type, source_value)
);

CREATE TABLE IF NOT EXISTS beauty.ai_beauty_candidates (
    id BIGSERIAL PRIMARY KEY,
    source_platform TEXT NOT NULL DEFAULT 'Douyin',
    source_type TEXT NOT NULL,
    source_value TEXT,
    aweme_id TEXT UNIQUE NOT NULL,
    douyin_url TEXT,
    author_id TEXT,
    author_name TEXT,
    caption TEXT,
    hashtags TEXT[],
    duration_seconds NUMERIC,
    width INTEGER,
    height INTEGER,
    source_stats JSONB,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ,
    candidate_status TEXT NOT NULL DEFAULT 'new',
    priority_score NUMERIC DEFAULT 0,
    collection_run_id TEXT,
    local_video_path TEXT,
    analysis_dir TEXT,
    last_error TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS beauty.ai_beauty_screenings (
    id BIGSERIAL PRIMARY KEY,
    aweme_id TEXT NOT NULL REFERENCES beauty.ai_beauty_candidates(aweme_id),
    screened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    model_name TEXT,
    contact_sheet_path TEXT,
    is_beauty_content BOOLEAN,
    suitable_for_ai_beauty BOOLEAN,
    visible_minor_risk BOOLEAN,
    low_quality BOOLEAN,
    obvious_watermark BOOLEAN,
    duplicate_risk TEXT,
    sensuality_level TEXT,
    explicitness_level TEXT,
    content_type TEXT[],
    visual_style TEXT[],
    safety_json JSONB,
    visual_labels_json JSONB,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'skipped', 'review', 'failed')),
    skip_reason TEXT,
    recommended_title TEXT,
    recommended_tags TEXT[],
    selection_reason TEXT
);

CREATE TABLE IF NOT EXISTS beauty.ai_beauty_uploads (
    id BIGSERIAL PRIMARY KEY,
    aweme_id TEXT UNIQUE NOT NULL REFERENCES beauty.ai_beauty_candidates(aweme_id),
    youtube_video_id TEXT UNIQUE NOT NULL,
    youtube_url TEXT NOT NULL,
    youtube_channel_id TEXT,
    youtube_profile TEXT NOT NULL DEFAULT 'default' CHECK (youtube_profile = 'default'),
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '' CHECK (description = ''),
    tags TEXT[] CHECK (cardinality(tags) <= 5),
    privacy_status TEXT NOT NULL DEFAULT 'public' CHECK (privacy_status IN ('public', 'private', 'unlisted')),
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    upload_status TEXT NOT NULL,
    upload_response_json JSONB,
    screening_id BIGINT REFERENCES beauty.ai_beauty_screenings(id),
    selection_reason TEXT,
    local_file_deleted BOOLEAN DEFAULT false
);

CREATE TABLE IF NOT EXISTS beauty.ai_beauty_video_metrics (
    id BIGSERIAL PRIMARY KEY,
    youtube_video_id TEXT NOT NULL REFERENCES beauty.ai_beauty_uploads(youtube_video_id),
    metric_date DATE NOT NULL,
    views BIGINT,
    engaged_views BIGINT,
    estimated_minutes_watched NUMERIC,
    average_view_duration NUMERIC,
    average_view_percentage NUMERIC,
    likes BIGINT,
    comments BIGINT,
    shares BIGINT,
    subscribers_gained BIGINT,
    subscribers_lost BIGINT,
    impressions BIGINT,
    ctr NUMERIC,
    raw_metrics_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (youtube_video_id, metric_date)
);

CREATE TABLE IF NOT EXISTS beauty.ai_beauty_strategy_state (
    id BIGSERIAL PRIMARY KEY,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    strategy_version TEXT,
    strategy_json JSONB NOT NULL,
    evidence_json JSONB,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS beauty.ai_beauty_run_logs (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT UNIQUE NOT NULL,
    job_type TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    candidates_found INTEGER DEFAULT 0,
    candidates_screened INTEGER DEFAULT 0,
    videos_uploaded INTEGER DEFAULT 0,
    videos_skipped INTEGER DEFAULT 0,
    error_message TEXT,
    summary_json JSONB
);

CREATE INDEX IF NOT EXISTS idx_ai_beauty_candidates_status
ON beauty.ai_beauty_candidates(candidate_status);

CREATE INDEX IF NOT EXISTS idx_ai_beauty_candidates_priority
ON beauty.ai_beauty_candidates(priority_score DESC, discovered_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_beauty_screenings_aweme_decision
ON beauty.ai_beauty_screenings(aweme_id, decision);

CREATE INDEX IF NOT EXISTS idx_ai_beauty_uploads_uploaded_at
ON beauty.ai_beauty_uploads(uploaded_at DESC);
