---
name: douyin-ai-beauty-channel-manager
description: "Use when autonomously operating only the AI Beauty YouTube channel from Douyin beauty content using lightweight non-CDP collection, isolated AI Beauty database tables, visual screening, YouTube uploads, and Analytics-driven strategy updates."
version: 0.1.0-draft
author: Hermes Agent
license: private
metadata:
  hermes:
    tags: [beauty, douyin, youtube, analytics, upload, ai-beauty]
    related_skills: [youtube-data-api-upload]
    created_by: agent
---

# Douyin AI Beauty Channel Manager

## Overview

This skill defines the agent role for autonomously operating the YouTube **AI Beauty** channel from Douyin beauty content. The operating loop is:

1. collect Douyin beauty candidates with lightweight non-browser tooling;
2. store candidates in AI-Beauty-only database tables;
3. download and verify candidate videos;
4. screen visual content and generate metadata;
5. upload selected videos only to the AI Beauty YouTube profile;
6. record uploads in isolated AI Beauty tables;
7. analyze AI Beauty YouTube performance;
8. update future selection strategy based on real channel data.

The goal is to improve AI Beauty channel views, retention, and subscriber growth while keeping this role fully isolated from the existing Beauty Cosplay and Beauty Dancing workflows.

## Scope and hard boundaries

### Managed channel

This skill manages only:

- YouTube profile: `default`
- YouTube channel: `AI Beauty` / `@ai-beauty-1`
- Source category: Douyin beauty content

### Channels not managed by this role

This skill does **not** manage or change:

- `channelCos` / Beauty Cosplay / `@beautycosplay`
- `channelDance` / Beauty Dancing / `@beautydanc`
- existing Bilibili-to-YouTube workflows
- existing Cosplay/Dancing Douyin workflows
- existing channel routing rules for Cosplay/Dancing

Do not modify Beauty Cosplay or Beauty Dancing behavior unless the user explicitly instructs it.

### Source collection boundary

Use lightweight collection first, but controlled Chrome CDP is allowed for AI Beauty when Douyin web endpoints or direct extractors cannot safely return candidate/detail/playback data.

Allowed CDP use is narrow:

- read-only Douyin web detail/search/playback requests;
- exporting a separate AI Beauty cookie jar into `config/douyin_ai_beauty_cookies.txt`;
- fetching `aweme/detail` or equivalent play-address metadata from a Douyin page context;
- pausing any opened Douyin videos immediately;
- writing only AI Beauty artifacts and `beauty.ai_beauty_*` records.

CDP restrictions:

- do not use current Cosplay/Dancing Douyin favorite workflows for AI Beauty state changes;
- do not move/remove Bilibili/Douyin favorites from this role;
- do not upload, delete, or alter non-AI-Beauty channel content through CDP;
- do not print or commit cookies/tokens;
- record whether a run used `yt-dlp`, direct HTTP, or `cdp-detail-play-url` so fallback behavior is auditable.

Preferred collection order:

- direct HTTP client (`httpx`, `requests`, `curl`) where practical;
- `yt-dlp` or another CLI extractor where practical;
- a separate cookie/session file dedicated to this AI Beauty role if login state is needed;
- controlled CDP fallback for Douyin web detail/playback when lightweight paths fail;
- a third-party Douyin parser/API only if explicitly configured and safe to use.

### Database isolation boundary

AI Beauty candidates and uploads must use separate tables from the existing two-channel workflow.

Do not use existing Cosplay/Dancing candidate tables as primary storage. Do not use the existing shared upload table as the primary AI Beauty upload record.

It is acceptable to **read** existing upload records for global duplicate detection, but do not write AI Beauty upload state into Cosplay/Dancing workflow tables.

## Key paths

Project root:

```text
C:/Project/Beauty-Video-Transport
```

Recommended AI Beauty working paths:

```text
C:/Project/Beauty-Video-Transport/downloads/douyin_ai_beauty/
C:/Project/Beauty-Video-Transport/analysis/douyin_ai_beauty/<aweme_id>/
C:/Project/Beauty-Video-Transport/config/douyin_ai_beauty_cookies.txt
C:/Project/Beauty-Video-Transport/config/douyin_ai_beauty_session.json
```

YouTube uploader:

```text
C:/Project/Beauty-Video-Transport/youtube-upload/youtube_upload.py
```

MVP helper scripts:

```text
C:/Project/Beauty-Video-Transport/sql/ai_beauty_schema.sql
C:/Project/Beauty-Video-Transport/scripts/ai_beauty/db.py
C:/Project/Beauty-Video-Transport/scripts/ai_beauty/init_schema.py
C:/Project/Beauty-Video-Transport/scripts/ai_beauty/collect_urls.py
C:/Project/Beauty-Video-Transport/scripts/ai_beauty/download_candidate.py
C:/Project/Beauty-Video-Transport/scripts/ai_beauty/media.py
C:/Project/Beauty-Video-Transport/scripts/ai_beauty/record_screening.py
C:/Project/Beauty-Video-Transport/scripts/ai_beauty/upload_ai_beauty.py
C:/Project/Beauty-Video-Transport/scripts/ai_beauty/report_status.py
```

MVP commands:

```bash
python scripts/ai_beauty/db.py --check
python scripts/ai_beauty/init_schema.py
python scripts/ai_beauty/collect_urls.py --file config/ai_beauty_sources.txt --dry-run --no-resolve-short
python scripts/ai_beauty/collect_urls.py --file config/ai_beauty_sources.txt --source-type url_list --source-value manual
python scripts/ai_beauty/download_candidate.py --aweme-id <aweme_id>
python scripts/ai_beauty/record_screening.py --aweme-id <aweme_id> --json analysis/douyin_ai_beauty/<aweme_id>/screening.json
python scripts/ai_beauty/upload_ai_beauty.py --aweme-id <aweme_id> --dry-run
python scripts/ai_beauty/upload_ai_beauty.py --aweme-id <aweme_id> --upload
python scripts/ai_beauty/report_status.py --limit 20 --json
```

## Agent responsibilities

### 1. Candidate collection

Collect Douyin beauty candidates without Chrome/CDP.

Candidate sources may include:

- manually supplied Douyin video URLs;
- configured Douyin user pages/accounts;
- configured Douyin tags or keywords;
- configured URL lists;
- future lightweight parser/API outputs.

Each collection run should upsert candidate metadata into `beauty.ai_beauty_candidates` and log the run in `beauty.ai_beauty_run_logs`.

Minimum candidate metadata:

- `aweme_id`
- `douyin_url`
- source type and source value
- caption/title if available
- author ID/name if available
- hashtags if available
- duration if available
- width/height if available
- source stats if available: likes, comments, shares, collects
- discovery timestamp
- collection run ID

Completion criteria:

- every discovered candidate is deduplicated by `aweme_id`;
- all writes go only to AI Beauty tables;
- no Chrome/CDP calls were used;
- collection errors are logged with enough detail to retry or replace the source.

### 2. Candidate download and media verification

For selected candidates:

1. Download the best available video stream with lightweight tooling.
2. Verify with `ffprobe`:
   - file exists;
   - file has a video stream;
   - duration is readable;
   - dimensions are readable;
   - file is not obviously corrupt.
3. Generate sampled frames/contact sheet under `analysis/douyin_ai_beauty/<aweme_id>/`.
4. Update candidate status.

Completion criteria:

- invalid, audio-only, corrupt, or missing files are marked failed/skipped and removed;
- valid videos have an analysis folder and contact sheet;
- no local file path is recorded as valid unless the file actually exists.

### 3. Visual screening

Use visual analysis on sampled frames/contact sheet to decide whether the candidate is suitable for AI Beauty.

Record structured screening results in `beauty.ai_beauty_screenings`.

Suggested screening schema:

```yaml
is_beauty_content: true/false
suitable_for_ai_beauty: true/false
visible_minor_risk: true/false
low_quality: true/false
obvious_watermark: true/false
duplicate_risk: low/medium/high
sensuality_level: low/medium/high
explicitness_level: low/medium/high
content_type:
  - beauty
  - portrait
  - fashion
  - selfie
  - street_snap
  - dance
  - cosplay
  - transformation
  - ai_style
  - other
visual_style:
  - close_up
  - full_body
  - mirror
  - outdoor
  - indoor
  - studio
  - casual
  - elegant
  - cute
  - glamorous
motion_type:
  - static_pose
  - light_posing
  - walking
  - dance
  - transition
  - other
decision: approved/skipped/review/failed
skip_reason: null_or_text
recommended_title: English title
recommended_tags: [max, five, tags]
selection_reason: text
```

Important content policy for this role:

- Do **not** automatically skip merely because content is low俗, explicit-looking, or strongly suggestive.
- Do **not** automatically skip merely because content contains cosplay or dance elements.
- These traits may be recorded as content attributes and used for data analysis, but they are not default rejection rules.

Default skip/fail conditions:

- likely visible minor risk;
- not beauty content;
- corrupt video or no video stream;
- severe unusable quality;
- high-confidence duplicate of an already uploaded AI Beauty video;
- clearly incompatible with YouTube platform rules or upload API requirements;
- technical download/upload blocker that prevents safe publication.

`review` means do not upload automatically in that run.

Completion criteria:

- every screened candidate has exactly one decision: `approved`, `skipped`, `review`, or `failed`;
- all decisions include enough evidence in `visual_labels_json`, `safety_json`, and `selection_reason` or `skip_reason`;
- approved candidates have an English title and at most five tags.

### 4. Candidate ranking

Rank approved candidates using both source signals and AI Beauty strategy state.

Initial ranking signals:

- visual quality;
- subject clarity;
- strong beauty appeal;
- short-form suitability;
- current AI Beauty strategy preferences;
- source engagement if available;
- duplicate risk;
- prior performance of similar visual labels.

Example scoring components:

```text
candidate_score =
  visual_quality_score
+ beauty_fit_score
+ source_engagement_score
+ strategy_match_score
- duplicate_penalty
- technical_risk_penalty
```

The exact weights may change, but the reason for ranking must be written to the candidate or screening record.

### 5. AI Beauty upload

Upload only to the AI Beauty default profile.

Required upload settings:

- profile: `default`
- privacy: `public`, unless the user explicitly says otherwise
- description: empty string
- tags: no more than 5
- title: English
- target channel: AI Beauty / `@ai-beauty-1`

Use the local YouTube uploader from:

```text
C:/Project/Beauty-Video-Transport/youtube-upload/youtube_upload.py
```

Before a real upload, verify the uploader profile points to the AI Beauty channel when needed:

```bash
python youtube_upload.py check-auth
python youtube_upload.py list-channels
```

For scheduled/approved autonomous runs, uploads may proceed under the user-approved AI Beauty automation goal. For one-off manual experiments, use dry-run first unless the user explicitly requests an immediate upload.

After upload:

1. verify the returned YouTube video ID exists through YouTube Data API;
2. verify target profile/channel is AI Beauty;
3. write upload record to `beauty.ai_beauty_uploads`;
4. update candidate status to `uploaded`;
5. delete local video files and partials after verification;
6. record whether local deletion succeeded.

Completion criteria:

- no upload is reported as successful without a verified YouTube video ID;
- upload record exists in `beauty.ai_beauty_uploads`;
- no write was made to Cosplay/Dancing workflow tables;
- local downloaded file is deleted or a deletion failure is reported.

### 6. YouTube Analytics feedback loop

Analyze only AI Beauty channel/video performance.

Metrics to collect where available:

- `views`
- `engagedViews`
- `estimatedMinutesWatched`
- `averageViewDuration`
- `averageViewPercentage`
- `likes`
- `comments`
- `shares`
- `subscribersGained`
- `subscribersLost`
- `impressions`
- CTR if available

Store daily snapshots in `beauty.ai_beauty_video_metrics`.

Recommended derived metrics:

```text
view_velocity_24h
view_velocity_48h
view_velocity_7d
like_rate = likes / views
comment_rate = comments / views
share_rate = shares / views
subscriber_conversion = subscribersGained / views
retention_score = averageViewPercentage
watch_time_score = estimatedMinutesWatched
```

Recommended performance score:

```text
performance_score =
  0.30 * normalized_views_48h
+ 0.25 * averageViewPercentage
+ 0.20 * subscribersGained_per_1000_views
+ 0.10 * like_rate
+ 0.10 * share_rate
+ 0.05 * comment_rate
```

The score is a starting point. Adjust only when there is evidence from AI Beauty channel data.

Completion criteria:

- metrics are upserted by `(youtube_video_id, metric_date)`;
- analytics only cover AI Beauty uploads for this role;
- each strategy update cites the metrics or labels that drove it.

### 7. Strategy state update

Update `beauty.ai_beauty_strategy_state` based on observed performance.

Strategy state should capture:

- preferred duration ranges;
- preferred visual styles;
- preferred content types;
- underperforming patterns;
- high-performing tags/labels;
- recommended next collection priorities;
- evidence summary.

Example:

```json
{
  "duration": {"preferred": "8-25 seconds"},
  "boost_labels": ["close_up", "portrait", "bright_lighting"],
  "reduce_labels": ["low_resolution", "unclear_subject"],
  "evidence": "Last 14 days: close-up portrait videos had higher subscriber conversion and retention."
}
```

Completion criteria:

- strategy changes are stored with timestamp and evidence;
- no strategy update changes Beauty Cosplay or Beauty Dancing behavior;
- strategy is used to rank future AI Beauty candidates.

## Recommended database schema

Use the `beauty` PostgreSQL database but separate AI Beauty tables.

### `beauty.ai_beauty_sources`

```sql
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
```

### `beauty.ai_beauty_candidates`

```sql
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
    notes TEXT
);
```

### `beauty.ai_beauty_screenings`

```sql
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
    decision TEXT NOT NULL,
    skip_reason TEXT,
    recommended_title TEXT,
    recommended_tags TEXT[],
    selection_reason TEXT
);
```

### `beauty.ai_beauty_uploads`

```sql
CREATE TABLE IF NOT EXISTS beauty.ai_beauty_uploads (
    id BIGSERIAL PRIMARY KEY,
    aweme_id TEXT UNIQUE NOT NULL REFERENCES beauty.ai_beauty_candidates(aweme_id),
    youtube_video_id TEXT UNIQUE NOT NULL,
    youtube_url TEXT NOT NULL,
    youtube_channel_id TEXT,
    youtube_profile TEXT NOT NULL DEFAULT 'default',
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    tags TEXT[],
    privacy_status TEXT NOT NULL DEFAULT 'public',
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    upload_status TEXT NOT NULL,
    upload_response_json JSONB,
    screening_id BIGINT REFERENCES beauty.ai_beauty_screenings(id),
    selection_reason TEXT,
    local_file_deleted BOOLEAN DEFAULT false
);
```

### `beauty.ai_beauty_video_metrics`

```sql
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
```

### `beauty.ai_beauty_strategy_state`

```sql
CREATE TABLE IF NOT EXISTS beauty.ai_beauty_strategy_state (
    id BIGSERIAL PRIMARY KEY,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    strategy_version TEXT,
    strategy_json JSONB NOT NULL,
    evidence_json JSONB,
    notes TEXT
);
```

### `beauty.ai_beauty_run_logs`

```sql
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
```

## Suggested cron/job layout

Prefer separate jobs instead of one large monolithic job.

### Job A: AI Beauty analytics update

Frequency: daily.

Responsibilities:

- fetch AI Beauty metrics;
- upsert `ai_beauty_video_metrics`;
- update `ai_beauty_strategy_state`;
- report major trend changes only.

### Job B: lightweight Douyin candidate collection

Frequency: daily or every 12 hours.

Responsibilities:

- read enabled `ai_beauty_sources`;
- collect new candidates with lightweight HTTP/CLI first, then controlled read-only CDP fallback when Douyin detail/playback requires page context;
- upsert `ai_beauty_candidates`;
- log run results.

### Job C: screening and upload

Frequency: daily or as YouTube quota allows.

Responsibilities:

- select top pending candidates;
- download and verify;
- screen with vision;
- upload approved candidates to AI Beauty only;
- write `ai_beauty_uploads`;
- delete local files;
- report uploaded/skipped/review items.

## Reporting

### If videos were uploaded

```text
AI Beauty upload completed:

Uploaded:
1. <English title>
   YouTube: https://youtu.be/<id>
   Source: Douyin aweme_id <id>
   Reason: <selection reason>
   Tags: <up to 5 tags>

Skipped/Review:
- <aweme_id>: <reason>

Strategy note:
<short data-driven observation if available>
```

### If only analytics changed

```text
AI Beauty analytics update:
<short trend summary>
Next selection bias: <updated preference>
```

### If nothing changed

```text
No AI Beauty channel changes.
```

### If blocked

```text
AI Beauty automation blocked:
<blocker>
Next required action: <specific action>
```

## Common pitfalls

1. **Uncontrolled Chrome/CDP use.** CDP is allowed only as a controlled read-only fallback for AI Beauty candidate/detail/playback data and separate cookie export; keep Cosplay/Dancing workflows isolated.
2. **Mixing records with Cosplay/Dancing.** AI Beauty candidates/uploads/metrics must use `ai_beauty_*` tables.
3. **Treating suggestive content as an automatic skip.** Record sensuality/explicitness levels, but do not reject solely for that reason.
4. **Uploading without verification.** Never report success without a verified YouTube video ID and AI Beauty upload record.
5. **Overfitting from tiny data.** Strategy updates should cite evidence and avoid large changes from one weak data point.
6. **Forgetting local cleanup.** Delete downloaded videos and partials after verified upload or failed validation.
7. **Changing other channels by implication.** Do not modify Beauty Cosplay/Dancing behavior, tables, or routing from this role.

## Verification checklist

Before completing an AI Beauty run, verify:

- [ ] Chrome/CDP/browser-session use, if any, was controlled read-only AI Beauty fallback and did not touch Cosplay/Dancing operations;
- [ ] all candidate writes went to `beauty.ai_beauty_candidates` or related `ai_beauty_*` tables;
- [ ] uploads targeted only YouTube profile `default` / AI Beauty;
- [ ] title is English;
- [ ] description is empty;
- [ ] tags count is 5 or fewer;
- [ ] YouTube video ID was verified after upload;
- [ ] upload record exists in `beauty.ai_beauty_uploads`;
- [ ] local video files were deleted or cleanup failure was reported;
- [ ] Cosplay/Dancing workflows and tables were not modified;
- [ ] final report includes uploaded URLs, skipped/review reasons, and blockers if any.
