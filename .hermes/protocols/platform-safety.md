# Platform Safety Protocol

Beauty Video Transport touches real platform accounts, uploads, downloads, browser sessions, PostgreSQL data, and OAuth credentials. Treat operational side effects as high-risk.

## Secrets and Local Artifacts

Do not commit or print:

- OAuth tokens or refresh tokens
- Google OAuth client secrets
- Douyin/Bilibili cookies or browser session files
- API keys
- DB passwords or credential files
- downloaded videos or generated media outputs
- raw analysis frames/contact sheets unless explicitly designated as evidence and safe to share

Ignored paths include:

- `apiKey/`
- `youtube-upload/config/`
- `config/*` except committed examples
- `downloads/`
- `outputs/`
- `analysis/`

## Upload/Delete Safety

- Default to dry-run.
- Real YouTube upload/delete requires explicit user approval or standing approval documented in the relevant project skill/task.
- Before upload, verify the intended YouTube profile/channel identity with `check-auth`, `list-channels`, or `scripts/youtube_profile_guard.py`.
- Record upload/delete command, target profile, target channel, and redacted result summary in task evidence.

## Channel Isolation

- AI Beauty automation must use the AI Beauty/default profile contract unless the user explicitly changes it.
- Do not modify Beauty Cosplay (`channelCos`) or Beauty Dancing (`channelDance`) behavior from AI Beauty tasks.
- It is acceptable to read shared historical records for duplicate detection, but do not write AI Beauty primary state into Cos/Dance workflow tables.

## DB and Cron Safety

- DB schema/status changes need migration/rollback or compatibility notes plus safe query evidence.
- Cron changes need schedule, delivery target, expected side effects, rollback plan, and verification output.
- Destructive cleanup must preserve evidence/analysis/contact-sheet/screening JSON unless the task explicitly says otherwise.
