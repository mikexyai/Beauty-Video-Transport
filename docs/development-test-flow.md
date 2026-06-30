# Development and Test Flow

## Goal

All architecture-improvement work should be delivered through Kanban tasks with test-first changes, small reviewable increments, and real verification output.

## Task lifecycle

1. **Specify**
   - Restate the task goal.
   - Identify boundaries: AI Beauty only, Bilibili/Cos/Dance only, or shared utility.
   - List files expected to change.
   - Define acceptance criteria.

2. **RED — write failing tests first**
   - Add or update unit tests before production code.
   - Run the focused test and confirm it fails for the expected missing behavior.
   - If the test passes immediately, revise the test.

3. **GREEN — implement minimal code**
   - Write only enough code to pass the new test.
   - Preserve existing behavior unless the task explicitly changes it.
   - Keep CLI entrypoints thin where possible.

4. **REFACTOR — clean boundaries**
   - Move shared logic into state/repository/service modules.
   - Keep direct SQL out of high-level CLIs when a repository exists.
   - Keep channel/profile rules in explicit guards.

5. **Verify**
   - Run focused tests.
   - Run the full local test command for touched area.
   - Run compile checks.
   - For DB/cron/upload work, run a dry-run or safe status command proving behavior.
- For uploaded AI Beauty records, treat `local_video_path` as a historical path when `local_file_deleted=true`; verify current file existence separately instead of assuming the path still exists.

6. **Document**
   - Update docs when workflow contracts, statuses, cron behavior, or recovery steps change.
   - Update relevant Hermes skills when operational rules change.

7. **Close Kanban task**
   - Include changed files, tests run, DB/cron changes, and remaining risks in the result.

## Required evidence by task type

### State-machine tasks

- Tests proving included/excluded statuses.
- DB query or dry-run proving active pool behavior when relevant.

### Repository/refactor tasks

- Tests proving repository behavior.
- Before/after note listing scripts migrated away from direct SQL.

### Cron/operator tasks

- Dry-run or manual run output.
- Confirmation cron prompt/job config was updated if applicable.
- Run-log row or output artifact path.

### Upload-related tasks

- Channel/profile guard output.
- Dry-run output before real upload logic is considered safe.
- `verify_uploads.py` output for recent videos when applicable.

### Bilibili tasks

- CDP/helper command output.
- `yt-dlp -F` or equivalent evidence for format availability.
- ffprobe evidence when a real download occurs.

## Safety constraints

- Never commit or print OAuth tokens, cookies, API keys, or DB passwords.
- Do not move AI Beauty data into shared Cos/Dance tables.
- Do not modify Cos/Dance routing from AI Beauty tasks.
- Real uploads require standing approval encoded in the relevant project skill and correct channel verification.
- Destructive cleanup must preserve analysis/contact sheet/screening JSON unless the task explicitly says otherwise.
