# AGENTS.md

## Project Overview

Beauty Video Transport is an operational media workflow repository for collecting, screening, downloading, verifying, uploading, and auditing beauty video content across Douyin/Bilibili and YouTube.

Core domains:

- AI Beauty Douyin → YouTube AI Beauty channel automation.
- Bilibili → YouTube transport pipeline.
- YouTube upload, post-upload compliance, and health checks.
- PostgreSQL-backed upload/candidate/run-log records.
- Local evidence and analysis artifacts for media verification and operational audits.

Read the relevant docs before changing behavior:

- `README.md`
- `docs/architecture-improvement-plan.md`
- `docs/development-test-flow.md`
- `douyin-ai-beauty-channel-manager.SKILL.md`
- `youtube-upload/README.md`

## Hermes PDD / Codex Multi-Agent Collaboration

The `beauty` Hermes profile is the project operator/PM context for this repository. For implementation work, prefer the PDD-centered Kanban workflow below instead of ad-hoc edits.

### Session and Agent Role Boundaries

- `PDD` owns execution: repo-local task packets, development handoff, evidence, implementation docs/status, independent Test/Review gates, commits, Kanban completion, and current-thread completion notices.
- `PM` handles intake/planning: operational requirements, implementation planning, and Kanban intake/planning cards. It must not dispatch development workers or mark implementation tasks done unless explicitly promoted into the execution role.
- `PD` / content strategy sessions may propose channel, content, title/tag, visual-style, or product/strategy improvements and may write product/content briefs after approval. They must not edit production scripts, create development packets, dispatch workers, or mark implementation tasks done.
- Codex and Claude Code are development-stage workers only. They run after design/plan approval from a bounded task packet and must obey `allowed_files`, `out_of_scope`, validation, evidence, result-file, and non-recursion rules.
- Test Agent and Reviewer Agent are independent verification workers. They report only; fixes go through a new explicit PDD-created development task or correction round.

Mandatory workflow:

1. PDD creates or confirms a Hermes Kanban task first. Do not start from only a repo-local task packet.
2. PDD writes `.hermes/tasks/TASK-000N.md` and includes the Kanban task ID in `kanban_task_id` frontmatter.
3. PDD records packet/result/evidence paths in the Kanban body or comment.
4. Codex Dev Worker implements according to a compact bounded task packet and writes a result file early. Codex should run only cheap scoped validation listed in the packet.
5. If Codex fails, PDD retries Codex exactly once using the same model name with a `-pro` suffix and reasoning effort `medium`; if the retry fails, PDD hands the same bounded task packet/current diff to Claude Code.
6. Claude Code fallback should be narrow: inspect the current diff, fix obvious blockers, preserve scope, write/update the result file, and report blocked validation instead of fighting tool guards.
7. Test Agent independently tests the change and writes a test report.
8. Reviewer Agent independently reviews the change and writes a review report.
9. PDD runs final verification, checks generated artifacts, scans for secret leakage, checks git diff, and only then marks the Kanban task complete and commits.

Task packets must assign both:

- Methodology: `obra/superpowers` style workflow, written directly into the packet unless the Codex plugin is known to be installed.
- Role: one selected role, preferably from the local `.hermes/roles/` summaries or agency-agents routing.

### Worker Execution Budget

- PDD/Hermes should summarize large specs/plans before dispatch. Do not make Codex read whole planning documents when a focused task packet can name exact files, ranges, acceptance criteria, and validation commands.
- Worker packets should prefer `npm.cmd` on Windows/PowerShell for Node package scripts when PowerShell execution policy blocks `npm.ps1`; Python commands should use `python` from the active environment.
- Codex should not run full operational pipelines by default. PDD/Test Agent owns full dry-run/live verification, evidence capture, artifact cleanup, and final gate.
- After any Codex/Claude diff touching platform/API output, PDD must scan for leaked secrets, tokens, cookies, credentials, and placeholder/corruption markers before final review.

Required protocols:

- `.hermes/protocols/non-recursion.md`
- `.hermes/protocols/codex-task-packet.md`
- `.hermes/protocols/verification-gates.md`
- `.hermes/protocols/platform-safety.md`

For Discord thread/session identity, follow `.hermes/protocols/discord-session-identity.md`.

No worker may invoke Hermes, start Codex/Claude/OpenCode/Copilot, create subagents, create cron jobs, or start background autonomous loops. When a worker finds a problem, it only reports the issue. PDD creates a new explicit fix task.

## Tech Stack and Core Paths

- Language/runtime: Python scripts and CLIs.
- Database: PostgreSQL database `beauty` for upload/candidate/run-log records.
- Media tooling: `yt-dlp`, `ffprobe`/FFmpeg where applicable.
- Browser/CDP tooling: only for workflows that explicitly allow it; AI Beauty Douyin role forbids Chrome/CDP collection unless the user changes the role contract.
- YouTube API tooling: `youtube-upload/youtube_upload.py` and `youtube-upload/youtube_oauth.py`.
- Key directories:
  - `scripts/ai_beauty/`
  - `scripts/ai_beauty/repositories/`
  - `youtube-upload/`
  - `sql/`
  - `docs/`
  - `tests/`
  - `.hermes/`

## Common Commands

Run from repo root unless noted.

### Core AI Beauty checks

```bash
python -m unittest discover -s tests -p 'test_ai_beauty_core.py' -v
python -m compileall -q scripts tests/test_ai_beauty_core.py
```

### Database/status checks

```bash
python scripts/ai_beauty/db.py --check
python scripts/ai_beauty/report_status.py --limit 20 --json
python scripts/query_upload_records.py --limit 20
```

### YouTube profile and upload checks

```bash
cd youtube-upload && python youtube_upload.py check-auth --profile default
cd youtube-upload && python youtube_upload.py list-channels --profile default
python scripts/youtube_profile_guard.py --profile default
python scripts/ai_beauty/upload_ai_beauty.py --aweme-id <aweme_id> --dry-run
python scripts/ai_beauty/verify_uploads.py --limit 10
```

### Bilibili download-quality checks

```bash
python scripts/bilibili_download_best.py <BVID> --out 'downloads/bilibili/<BVID>.%(ext)s' --print-command
python -m yt_dlp -F --cookies downloads/bilibili/bilibili-cookies.txt 'https://www.bilibili.com/video/<BVID>/'
```

## Development Constraints

- Do not commit OAuth tokens, cookies, API keys, client secrets, DB passwords, downloaded media, or generated analysis frames.
- Do not commit `apiKey/`, `youtube-upload/config/`, `config/*` except committed examples, `downloads/`, `outputs/`, or `analysis/`.
- Keep AI Beauty data isolated from Beauty Cosplay / Beauty Dancing workflows unless the user explicitly requests a shared workflow change.
- Real YouTube uploads/deletes require explicit user approval or a standing approval documented in the relevant project skill/task. Default to dry-run.
- Cron changes must document schedule, delivery target, rollback plan, and verification evidence.
- DB schema/status changes must include SQL/migration notes, rollback or compatibility notes, and verification output.
- Keep changes focused. Do not opportunistically refactor unrelated pipeline scripts.

## Documentation and Evidence Artifacts

- Implementation/task evidence lives under `.hermes/evidence/TASK-000N/`.
- Repo-local task packets and worker reports live under `.hermes/tasks/` but are runtime audit artifacts and should generally remain ignored unless explicitly requested for a committed audit trail.
- Evidence may include command logs, dry-run JSON/text output, DB query output, channel/profile guard output, screenshots, ffprobe/yt-dlp output, and redacted API response summaries.
- Product/content strategy docs belong under `docs/` unless a task specifies another location.

## Verification Guidance

Choose the smallest safe validation for the change scope:

- AI Beauty Python code: run unit tests and compileall.
- YouTube upload/profile changes: run auth/profile/channel guard checks and dry-run before any real upload.
- Bilibili changes: run print-command and format availability checks; include ffprobe evidence when a real download occurs.
- DB changes: run safe status/query commands and document migration/rollback considerations.
- Cron/operator changes: run dry-run/manual safe status command and record cron schedule/delivery changes.
- Browser/CDP changes: capture screenshot/log evidence under `.hermes/evidence/TASK-000N/`.

## Code Style and Collaboration

- Follow existing Python module layout and naming.
- Prefer explicit, testable state/repository/service modules over scattered SQL in high-level CLIs.
- Keep channel/profile rules in explicit guards.
- Fix root causes rather than superficial compatibility symptoms.
- If unrelated issues are discovered, mention them in the final report but do not fix them without explicit scope.

## Commit Conventions

- Check `git status --short --untracked-files=all` before committing and confirm only task-related changes are staged.
- Commit messages should use `type: summary` with a concise English or Chinese summary.
- Common types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`.
- Keep each commit focused on one topic.
- Do not create branches, tags, merge branches, or rewrite git history unless the user explicitly asks.
