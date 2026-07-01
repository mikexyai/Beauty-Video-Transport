# AI Beauty Operator Cron Contract

This document records the repo-local contract for the AI Beauty autonomous operator. It documents the expected cron/operator handoff only; it does not change schedules or edit live job configuration. Do not edit `jobs.json` directly from a worker task.

## Stable Command

Use the deterministic Python operator command as the cron entrypoint:

```bash
python scripts/ai_beauty/operator.py --target-uploads 3 --run-id <run_id>
```

The live cron prompt for job `017a7053ee8f` is already aligned with this contract per TASK-0018 context: it names the stable operator command, vision handoff, rerun loop, delayed verification, and no recursive cron scheduling. No schedule change is required for this documentation-only clarification.

## Two-Stage Handoff

The workflow is two-stage:

1. deterministic Python owns collection, candidate selection, download, verification, contact-sheet generation, metadata template construction, upload after approval, run-log writes, and local cleanup;
2. Hermes vision supplies visual judgment by reviewing the contact sheet and returning normalized `screening.json` before approval/upload can continue.

When deterministic processing reaches a candidate that lacks vision review, it returns `needs_screening` and records a blocker like `vision_required:<aweme_id>`. The expected contact-sheet evidence is under `analysis/douyin_ai_beauty/<aweme_id>/contact_sheet` artifacts. Normalize the vision response with `normalize_screening_json.py` and save the resulting `screening.json` to `analysis/douyin_ai_beauty/<aweme_id>/screening.json`.

After `screening.json` exists, rerun the same operator command. For a single candidate continuation, the direct processing command is:

```bash
python -m scripts.ai_beauty.process_selected --aweme-id <aweme_id> --auto-upload
```

## Stop Conditions

Stop and report instead of looping indefinitely when any of these occurs:

- `needs_screening` or `vision_required:<aweme_id>` requires Hermes vision input;
- quota, auth, download, verification, upload, or platform safety blockers occur;
- no active candidates remain;
- the configured upload target is met;
- the configured max-iteration limit is reached.

## Evidence Expectations

Every operator run should write `ai_beauty_run_logs` with `run_id`, status, uploads, screened/skipped/reviewed candidates, blockers, and structured summary details. Reports should include uploaded/skipped/review reasons, preserved contact-sheet and `screening.json` paths, and local cleanup evidence for deleted downloads/partials or a clear cleanup blocker.

Cron/operator tasks should also follow `docs/development-test-flow.md`: use dry-run/manual safe validation when applicable, document cron schedule/delivery changes only when they are actually changed, and keep destructive cleanup from removing analysis/contact sheet/screening JSON evidence unless a task explicitly authorizes it.
