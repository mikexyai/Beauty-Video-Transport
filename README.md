# Beauty Video Transport

Operational tooling for the Beauty video workflow: preparing Bilibili/Douyin beauty videos for YouTube, uploading through the YouTube Data API, and tracking upload records.

## What is in this repo

- `youtube-upload/` — local YouTube Data API OAuth and upload CLI.
- `scripts/import_upload_records_to_postgres.py` — imports legacy `upload_records.csv` into PostgreSQL database `beauty`.
- `scripts/query_upload_records.py` — queries upload records from PostgreSQL.
- `upload_records.csv` — legacy/export upload record snapshot.
- `2026-06-23_235108-bilibili-douyin-to-youtube-prep.md` — initial planning notes.

## Not committed

The repository intentionally ignores credentials, OAuth tokens, downloaded videos, and generated analysis frames:

- `youtube-upload/config/`
- `apiKey/`
- `downloads/`
- `analysis/`
- `outputs/`

## Upload records

PostgreSQL is the source of truth for current records:

- Database: `beauty`
- Table: `upload_records`
- View: `records`
- Credentials file location on the local machine: `C:/Project/Setup/postgresql/postgres-credentials.txt`

Useful commands:

```bash
python scripts/query_upload_records.py --limit 20
python scripts/query_upload_records.py --platform Douyin --limit 20
python scripts/query_upload_records.py --platform Bilibili --limit 20
python scripts/query_upload_records.py --search '<title-or-id>'
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
