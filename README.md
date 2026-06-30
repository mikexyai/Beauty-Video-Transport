# Beauty Video Transport

Operational tooling for the Beauty video workflow: collecting, screening, downloading, verifying, uploading, auditing, and cleaning up beauty videos across Douyin/Bilibili and YouTube.

## What is in this repo

- `youtube-upload/` — local YouTube Data API OAuth and upload CLI.
- `scripts/ai_beauty/` — isolated AI Beauty Douyin → YouTube workflow using `beauty.ai_beauty_*` tables.
- `scripts/bilibili_pipeline.py` — Bilibili Cos/Dance pipeline planner and guard entrypoint.
- `scripts/bilibili_download_best.py` — highest-quality Bilibili download helper.
- `scripts/youtube_profile_guard.py` — validates uploader profile/channel identity before channel-specific uploads.
- `scripts/check_youtube_video_status.py` — YouTube post-upload compliance/status helper.
- `scripts/import_upload_records_to_postgres.py` — imports legacy `upload_records.csv` into PostgreSQL database `beauty`.
- `scripts/query_upload_records.py` — queries shared upload records from PostgreSQL.
- `upload_records.csv` — legacy/export upload record snapshot.

## Workflow boundaries

- AI Beauty writes only `beauty.ai_beauty_*` tables and uploads through YouTube profile `default` / `@ai-beauty-1`.
- Beauty Cosplay and Beauty Dancing use `channelCos` / `channelDance` and shared `beauty.upload_records`.
- AI Beauty prefers lightweight Douyin HTTP/CLI collection, but controlled read-only Chrome CDP fallback is allowed for dedicated cookie export and Douyin detail/playback metadata when page context is required.
- Bilibili light movement/posing/lip-sync routes to `channelCos`; only clear dance routes to `channelDance`.

## Not committed

The repository intentionally ignores credentials, OAuth tokens, downloaded videos, and generated analysis frames:

- `youtube-upload/config/`
- `apiKey/`
- `downloads/`
- `analysis/`
- `outputs/`

## Upload records

PostgreSQL is the source of truth for shared Cos/Dance records:

- Database: `beauty`
- Table: `upload_records`
- View: `records`

AI Beauty has isolated tables:

- `beauty.ai_beauty_sources`
- `beauty.ai_beauty_candidates`
- `beauty.ai_beauty_screenings`
- `beauty.ai_beauty_uploads`
- `beauty.ai_beauty_video_metrics`
- `beauty.ai_beauty_strategy_state`
- `beauty.ai_beauty_run_logs`

Credentials file location on the local machine: `C:/Project/Setup/postgresql/postgres-credentials.txt`

Useful commands:

```bash
python scripts/query_upload_records.py --limit 20
python scripts/query_upload_records.py --platform Douyin --limit 20
python scripts/query_upload_records.py --platform Bilibili --limit 20
python scripts/query_upload_records.py --search '<title-or-id>'
python scripts/ai_beauty/db.py --check
python scripts/ai_beauty/report_status.py --limit 20 --json
python scripts/ai_beauty/report_status.py --uploads --limit 10 --json
```

To import/sync the CSV snapshot into PostgreSQL:

```bash
python scripts/import_upload_records_to_postgres.py
```

## YouTube upload helper

The upload helper supports dry-run and real uploads with named profiles such as `channelCos` and `channelDance`.

```bash
cd youtube-upload
python youtube_upload.py check-auth --profile channelCos
python youtube_upload.py list-channels --profile channelCos
```

Do not commit files under `youtube-upload/config/`; they contain Google OAuth client secrets and refresh tokens.

## Local verification

```bash
python -m unittest discover -s tests -p 'test_ai_beauty_core.py' -v
python -m compileall -q scripts tests/test_ai_beauty_core.py
```

AI Beauty uploaded rows keep `local_video_path` as the historical download path. Use `local_file_deleted` and report fields such as `local_path_exists` / `local_video_path_role` to distinguish deleted files from current local artifacts.
