# Beauty Multi-Agent v3 Bootstrap Handoff

## Status

Beauty Video Transport multi-agent v3 phase-1 bootstrap is complete for local CLI use.

This handoff records the current operational state after `TASK-0020` and defines the safe next gates before any Gateway, Discord, cron, or dispatcher integration. It is Beauty-project scope only. Car Kanban tasks and Car project files are out of scope for this Beauty PDD thread unless the user explicitly switches project scope.

## Completed Profiles

The following blank Hermes profiles were created for Beauty phase 1:

| Profile | Role | Current intended use | Gateway status |
|---|---|---|---|
| `beauty-pm` | Planning / Intake PM | Requirements clarification, planning handoff, Kanban intake drafts | Stopped / not configured for Discord |
| `beauty-dev` | Development controller | Bounded task packet implementation orchestration with coding workers | Stopped / not configured for Discord |
| `beauty-test` | Independent QA and evidence collector | Safe validation commands, dry-runs, evidence reports | Stopped / not configured for Discord |
| `beauty-review` | Independent reviewer | Scope, quality, DB/cron/upload/platform-safety review | Stopped / not configured for Discord |

The existing `beauty` profile remains the PDD / main controller / Discord execution entrypoint and final authority for:

- Kanban task creation and completion;
- repo-local task packet creation;
- independent Test/Review gate coordination;
- final verification;
- git commits;
- current-thread completion notices.

## Bootstrap Method

Profiles were created as blank Hermes profiles. The bootstrap did not use any of the following clone forms:

```bash
hermes profile create beauty-dev --clone beauty
hermes profile create beauty-test --clone beauty
hermes profile create beauty-review --clone-all beauty
```

Role identity was installed profile-locally from the repo templates:

| Template | Installed profile files |
|---|---|
| `.hermes/roles/profile/beauty-pm.md` | `beauty-pm/ROLE.md`, `beauty-pm/SOUL.md` |
| `.hermes/roles/profile/beauty-dev.md` | `beauty-dev/ROLE.md`, `beauty-dev/SOUL.md` |
| `.hermes/roles/profile/beauty-test.md` | `beauty-test/ROLE.md`, `beauty-test/SOUL.md` |
| `.hermes/roles/profile/beauty-review.md` | `beauty-review/ROLE.md`, `beauty-review/SOUL.md` |

The profile-local files live under:

```text
C:/Users/Michael Xiao/AppData/Local/hermes/profiles/beauty-pm/
C:/Users/Michael Xiao/AppData/Local/hermes/profiles/beauty-dev/
C:/Users/Michael Xiao/AppData/Local/hermes/profiles/beauty-test/
C:/Users/Michael Xiao/AppData/Local/hermes/profiles/beauty-review/
```

Those profile-local files are runtime machine state and are not committed to the repository.

## Credential Handling

The new blank profiles initially had no usable API credentials. During bootstrap, the existing `beauty` profile `.env` was copied to the four new Beauty role profiles only after explicit user approval.

Rules for this credential state:

- Do not print `.env` contents.
- Do not commit `.env` files or profile-local secrets.
- Do not copy credentials to additional profiles without explicit approval.
- Treat the copied `.env` as local bootstrap enablement for CLI smoke tests, not as approval for live platform operations.
- If a profile no longer needs model access, remove or rotate its profile-local `.env` through normal Hermes/operator procedures.

Evidence recorded only metadata such as file size/checksum with redacted paths. No secret values are present in the repository evidence.

## Validation Evidence

Bootstrap evidence is recorded under `.hermes/evidence/TASK-0020/` and summarized in `.hermes/tasks/TASK-0020-result.md`.

Key evidence files:

| Evidence | Purpose |
|---|---|
| `.hermes/evidence/TASK-0020/profile-list-before.txt` | Baseline profile list before creation |
| `.hermes/evidence/TASK-0020/profile-create.log` | Profile creation output |
| `.hermes/evidence/TASK-0020/profile-show-after.txt` | Profile show/list output after creation |
| `.hermes/evidence/TASK-0020/profile-role-installed.txt` | Installed `ROLE.md` / `SOUL.md` line counts and checksums |
| `.hermes/evidence/TASK-0020/profile-env-copy.txt` | User-approved `.env` copy metadata, without contents |
| `.hermes/evidence/TASK-0020/profile-config-after.txt` | Profile-local model/provider/workdir config evidence |
| `.hermes/evidence/TASK-0020/smoke-beauty-pm.txt` | PM role smoke check |
| `.hermes/evidence/TASK-0020/smoke-beauty-dev.txt` | Dev role smoke check |
| `.hermes/evidence/TASK-0020/smoke-beauty-test.txt` | Test role smoke check |
| `.hermes/evidence/TASK-0020/smoke-beauty-review.txt` | Review role smoke check |
| `.hermes/evidence/TASK-0020/profile-alias-repair.txt` | Wrapper/alias verification |
| `.hermes/evidence/TASK-0020/final-unittest.log` | Repo unit validation at bootstrap time |
| `.hermes/evidence/TASK-0020/final-compileall.log` | Repo compile validation at bootstrap time |

Independent reports:

- `.hermes/tasks/TASK-0020-test-report.md` — decision `passed`.
- `.hermes/tasks/TASK-0020-review.md` — decision `approved`.

Kanban bootstrap card:

- `t_cf3f8adf` — `BOOTSTRAP Beauty multi-agent v3 blank profiles`, completed.

## Current Boundary Contract

The phase-1 role profiles are approved for local CLI smoke/pilot use only.

They are not approved for:

- Discord routing;
- Gateway services;
- cron scheduling;
- background autonomous loops;
- direct Kanban completion;
- commits without PDD final gate;
- real YouTube uploads/deletes;
- Bilibili/Douyin favorite mutations;
- destructive cleanup;
- credential propagation;
- Car project or Car Kanban execution.

The new profiles may be used manually for bounded local CLI checks when the PDD task packet or user explicitly authorizes that role. PDD must still verify all outputs before reporting success.

## Wrapper / Alias Notes

Wrapper evidence showed the intended local wrapper mapping after repair:

```text
beauty.bat        -> hermes -p beauty
beauty-pm.bat     -> hermes -p beauty-pm
beauty-dev.bat    -> hermes -p beauty-dev
beauty-test.bat   -> hermes -p beauty-test
beauty-review.bat -> hermes -p beauty-review
```

If `hermes profile list` displays a stale-looking alias label, inspect the actual wrapper files before assuming routing is wrong.

## Rollback / Disable Procedure

Use the least destructive rollback that satisfies the incident.

### Disable local role use without deleting profiles

1. Stop any running CLI sessions for the affected profile.
2. Confirm no Gateway is running for the profile:

```bash
hermes profile show beauty-dev
hermes profile show beauty-test
hermes profile show beauty-review
hermes profile show beauty-pm
```

3. Remove or rename the relevant wrapper under:

```text
C:/Users/Michael Xiao/.local/bin/
```

4. Remove the copied profile-local `.env` only if model access must be revoked. Do not print its contents.

### Delete a profile

Only delete a profile when the user explicitly approves destructive profile cleanup:

```bash
hermes profile delete beauty-dev
hermes profile delete beauty-test
hermes profile delete beauty-review
hermes profile delete beauty-pm
```

Before deletion, export or preserve any profile-local evidence that the user wants to keep. Profile deletion is local machine state and should not be represented as a repo commit unless documentation changes are also required.

### Rebuild from repo templates

If a profile must be recreated, use blank-profile creation and reinstall role identity from `.hermes/roles/profile/*.md`. Do not clone `beauty`.

## Future Dispatcher / Gateway Gate

Before connecting any of these profiles to Gateway, Discord, or automatic Kanban dispatcher, create a separate Beauty-specific Kanban task with explicit approval.

That task must document:

- exact profiles being connected;
- Discord channel/thread routing target;
- whether the profile can read/write Kanban directly;
- allowed toolsets and disabled toolsets;
- credential source and rotation plan;
- schedule or dispatcher trigger, if any;
- rollback steps;
- proof that `beauty` remains final PDD authority;
- proof that real uploads/deletes require explicit authorization or a standing project-approved operational policy;
- how Test/Review independence is preserved;
- how logs/evidence are captured and where users will see completion notices.

Do not perform Gateway/Discord/cron changes as part of documentation-only handoff work.

## Car Task Exclusion

The shared Kanban board may show Car tasks, such as role topology or Car dispatcher checklist cards. Those tasks are not part of Beauty Video Transport execution.

Beauty PDD must skip Car tasks unless the user explicitly says to switch to the Car project. When operating from `C:/Project/Beauty-Video-Transport`, Beauty work should create or complete Beauty-scoped cards only.

## Recommended Next Beauty Work

After this handoff, the safest next Beauty-specific task is an AI Beauty operator dry-run audit:

- run the deterministic operator in dry-run mode;
- inspect the latest `ai_beauty_run_logs.summary_json` shape;
- inspect `report_status.py` output;
- perform no upload/delete/download/cron mutations;
- record evidence and recommendations.

This should be a separate Kanban card and final-gated like other PDD tasks.
