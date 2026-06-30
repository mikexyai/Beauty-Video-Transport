# Verification Gates

A task is complete only after PDD verifies required artifacts and checks.

## Required Artifacts

For each development task:

- `.hermes/tasks/TASK-000N.md`
- `.hermes/tasks/TASK-000N-result.md`
- `.hermes/tasks/TASK-000N-test-report.md`
- `.hermes/tasks/TASK-000N-review.md`
- `.hermes/evidence/TASK-000N/` for operational evidence when required

## Default Checks

AI Beauty code changes:

```bash
python -m unittest discover -s tests -p 'test_ai_beauty_core.py' -v
python -m compileall -q scripts tests/test_ai_beauty_core.py
```

YouTube upload/profile changes:

```bash
cd youtube-upload && python youtube_upload.py check-auth --profile default
cd youtube-upload && python youtube_upload.py list-channels --profile default
python scripts/youtube_profile_guard.py --profile default
python scripts/ai_beauty/upload_ai_beauty.py --aweme-id <aweme_id> --dry-run
```

Bilibili download-quality changes:

```bash
python scripts/bilibili_download_best.py <BVID> --out 'downloads/bilibili/<BVID>.%(ext)s' --print-command
python -m yt_dlp -F --cookies downloads/bilibili/bilibili-cookies.txt 'https://www.bilibili.com/video/<BVID>/'
```

DB/status changes:

```bash
python scripts/ai_beauty/db.py --check
python scripts/ai_beauty/report_status.py --limit 20 --json
python scripts/query_upload_records.py --limit 20
```

## Evidence Requirements

Use `.hermes/evidence/TASK-000N/` for task evidence. Evidence can include:

- command logs
- dry-run JSON/text output
- DB query output
- channel/profile guard output
- screenshots for browser/CDP work
- ffprobe / yt-dlp output
- redacted API response summaries

## Platform Safety Gate

Before completion, PDD checks:

- no OAuth tokens, cookies, API keys, client secrets, DB passwords, downloaded media, or generated analysis frames are staged;
- real upload/delete did not run unless explicitly authorized;
- upload/profile changes include channel identity verification and dry-run evidence;
- cron changes document schedule, delivery target, rollback plan, and verification output;
- DB changes include migration/rollback or compatibility notes and safe query evidence.

## Placeholder / Secret Scan

When changed files include scripts, docs, task packets, or evidence text, scan scoped changed files for obvious placeholders and secret patterns:

```bash
rg -n "\?\?\?\?|�|TODO|TBD|client_secret|refresh_token|access_token|api_key|cookie|password" <changed-files>
```

Treat real secret-looking hits as blockers. Expected prose references to ignored secret paths are allowed when documented.

## Final PDD Checklist

- Kanban task exists and references packet/result/evidence.
- Result, test report, and review report exist.
- Required commands passed or blockers are explicitly documented.
- Evidence exists for operationally sensitive work.
- `git diff --check` passes.
- Generated/secret artifacts are ignored or absent from `git status --short --untracked-files=all`.
- Kanban task is marked done only after all gates pass.
