# Beauty Video Transport Architecture Improvement Plan

## Purpose

This document turns the current architecture review into an executable Kanban roadmap. The goal is to move Beauty Video Transport from prompt-orchestrated scripts toward a reliable workflow system with explicit state machines, reusable repositories, strong validation, and auditable run logs.

## Architectural north star

```text
Sources: Bilibili / Douyin
  -> collectors
  -> candidate repository
  -> ranking / selection state machine
  -> deterministic download + media verification
  -> Hermes vision only for visual judgment
  -> normalized screening record
  -> guarded YouTube upload
  -> post-upload verification
  -> local cleanup
  -> DB run logs / metrics
```

Key principles:

1. **Python owns deterministic operations.** DB writes, downloads, uploads, verification, cleanup, retries, counters, and state transitions should be Python code with tests.
2. **Hermes owns multimodal judgment.** Vision analysis can remain Hermes-driven, but raw model output must be normalized before DB writes.
3. **Explicit state machine.** Candidate states and legal transitions are centralized and tested.
4. **Repository layer.** Scripts should use repositories/services rather than scattered SQL.
5. **One orchestrator per workflow.** Cron should call stable workflow entrypoints instead of encoding business logic in long prompts.
6. **Audit everything important.** Each run records inputs, selections, decisions, uploads, blockers, and cleanup results.
7. **Channel isolation.** AI Beauty remains isolated from Beauty Cosplay/Dancing and Bilibili shared workflows unless explicitly changed.
8. **Controlled CDP fallback.** AI Beauty should prefer lightweight HTTP/CLI collection, but read-only Chrome CDP is allowed for dedicated cookie export and Douyin detail/playback metadata when page context is required; it must not touch Cos/Dance state or favorite operations.

## Roadmap phases

### Phase 0 — Governance and safety

- Document development/test flow and Kanban lifecycle.
- Ensure generated/secret files are ignored.
- Fix status semantics drift in `record_screening.py`.
- Centralize AI Beauty candidate statuses.

### Phase 1 — AI Beauty domain consolidation

- Add `scripts/ai_beauty/state.py`.
- Add candidate/screening/upload repositories.
- Add screening JSON normalization.
- Add DB status constraints after historical values are cleaned.

### Phase 2 — AI Beauty operator

- Add run logging to `ai_beauty_run_logs`.
- Implement `scripts/ai_beauty/operator.py` that loops until 3 uploads or a hard blocker.
- Shrink AI Beauty cron prompt to call the operator.
- Add delayed health-check cron / workflow.

### Phase 3 — Shared guards and Bilibili consolidation

- Add `scripts/youtube_profile_guard.py` for channel/profile verification.
- Add Bilibili pipeline entrypoint using highest-quality download helper.
- Keep Cos/Dance workflow separate from AI Beauty.

### Phase 4 — Optimization

- Duplicate detection beyond source ID.
- YouTube analytics metrics fetch.
- Strategy update loop after enough upload samples exist.

## Kanban task standards

Each task should include:

- Scope boundaries and touched files.
- Required tests and exact commands.
- Acceptance criteria.
- Rollback/recovery notes for DB or cron changes.
- Verification evidence in the task result.

## Default verification commands

For AI Beauty code changes:

```bash
python -m unittest discover -s tests -p 'test_ai_beauty_core.py' -v
python -m compileall -q scripts tests/test_ai_beauty_core.py
```

For YouTube-related changes:

```bash
python youtube-upload/youtube_upload.py check-auth --profile default
python youtube-upload/youtube_upload.py list-channels --profile default
python scripts/ai_beauty/verify_uploads.py --limit 10
```

For Bilibili download-quality changes:

```bash
python scripts/bilibili_download_best.py <BVID> --out 'downloads/bilibili/<BVID>.%(ext)s' --print-command
python -m yt_dlp -F --cookies downloads/bilibili/bilibili-cookies.txt 'https://www.bilibili.com/video/<BVID>/'
```
