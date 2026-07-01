# Beauty Multi-Agent v3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development if installed (recommended) or executing-plans if installed to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the approved Beauty Video Transport multi-agent v3 design into a safe, auditable blank-profile role system without cloning the existing `beauty` PDD profile.

**Architecture:** Use repo-committed shared governance docs and role identity templates as the source of truth, then create blank Hermes profiles one by one and install only the minimum role identity/skills/toolsets needed for a local CLI pilot. Discord/Gateway setup is a later gate after local role-boundary verification succeeds.

**Tech Stack:** Hermes CLI profiles, repo-local Markdown governance docs, Kanban for implementation tracking, Python/unittest project validation, git commits.

## Global Constraints

- Do not clone `beauty` into worker profiles.
- Do not configure Discord/Gateway until local CLI pilot succeeds.
- Do not copy `beauty` memory, sessions, current Discord routing, or broad credentials into worker profiles.
- Do not run real YouTube uploads/deletes, Bilibili/Douyin favorite mutations, or destructive cleanup during bootstrap.
- Profile-local files under `C:/Users/Michael Xiao/AppData/Local/hermes/profiles/<profile>/` are not committed to the repo.
- Repo-shared governance artifacts live under `docs/multi-agent/` and `.hermes/roles/profile/`.
- PDD (`beauty`) remains final authority for Kanban completion, final verification, and commits.
- The existing stash `stash@{0}` for out-of-scope `upload_records.csv` must remain untouched unless the user explicitly asks to restore/drop it.

---

## File Structure

### Already created and committed

- `docs/multi-agent/beauty-multi-agent-role-architecture-v3.md`
  - Canonical project-specific multi-agent v3 design.
- `.hermes/roles/profile/beauty-pm.md`
  - Planning/intake role identity template.
- `.hermes/roles/profile/beauty-dev.md`
  - Development controller role identity template.
- `.hermes/roles/profile/beauty-test.md`
  - Independent QA/evidence role identity template.
- `.hermes/roles/profile/beauty-review.md`
  - Independent review/platform-safety role identity template.
- `.hermes/roles/profile/beauty-strategy.md`
  - Optional content/analytics strategy role identity template.

### To create or modify during implementation

- Profile-local files under:
  - `C:/Users/Michael Xiao/AppData/Local/hermes/profiles/beauty-pm/`
  - `C:/Users/Michael Xiao/AppData/Local/hermes/profiles/beauty-dev/`
  - `C:/Users/Michael Xiao/AppData/Local/hermes/profiles/beauty-test/`
  - `C:/Users/Michael Xiao/AppData/Local/hermes/profiles/beauty-review/`
- Optional future profile-local files under:
  - `C:/Users/Michael Xiao/AppData/Local/hermes/profiles/beauty-strategy/`
- Repo evidence directory for bootstrap task:
  - `.hermes/evidence/<TASK-ID>/`
- Repo result reports for bootstrap task:
  - `.hermes/tasks/<TASK-ID>-result.md`
  - `.hermes/tasks/<TASK-ID>-test-report.md`
  - `.hermes/tasks/<TASK-ID>-review.md`

---

### Task 1: Create a Kanban bootstrap implementation card

**Files:**
- No production files.
- Create during execution: `.hermes/tasks/<TASK-ID>.md`
- Create during execution: `.hermes/evidence/<TASK-ID>/`

**Interfaces:**
- Consumes: `docs/multi-agent/beauty-multi-agent-role-architecture-v3.md`
- Produces: a Kanban card that authorizes blank-profile bootstrap and local pilot only.

- [ ] **Step 1: Confirm current workspace is clean**

Run:

```bash
git status --short --untracked-files=all
```

Expected:

```text
# no output
```

If output appears, stop and inspect before continuing.

- [ ] **Step 2: Create the Kanban card**

Run:

```bash
hermes kanban create "BOOTSTRAP Beauty multi-agent v3 blank profiles" \
  --workspace "dir:C:/Project/Beauty-Video-Transport" \
  --priority 1 \
  --body "Goal: Bootstrap Beauty Video Transport multi-agent v3 using blank Hermes profiles, repo role templates, and local CLI pilot only. Scope: create beauty-pm/beauty-dev/beauty-test/beauty-review blank profiles if missing; install/record profile-local identity from .hermes/roles/profile/*.md; verify no clone/routing/memory inheritance; run local CLI smoke checks; do not configure Discord/Gateway; do not run real upload/delete/cron operations. Evidence: profile list/show outputs, copied identity paths, smoke command logs, git status."
```

Expected:

```text
Created <kanban_task_id>
```

- [ ] **Step 3: Write repo-local task packet**

Create `.hermes/tasks/<TASK-ID>.md` with:

```yaml
---
task_id: <TASK-ID>
kanban_task_id: <kanban_task_id>
role: PDD
worker: pdd
status: packet_written
repo: C:/Project/Beauty-Video-Transport
branch: main
allowed_files:
  - .hermes/tasks/<TASK-ID>-result.md
  - .hermes/tasks/<TASK-ID>-test-report.md
  - .hermes/tasks/<TASK-ID>-review.md
  - .hermes/evidence/<TASK-ID>/**
out_of_scope:
  - youtube-upload/**
  - scripts/**
  - sql/**
  - downloads/**
  - outputs/**
  - analysis/**
  - upload_records.csv
  - C:/Users/Michael Xiao/AppData/Local/hermes/profiles/beauty/**
evidence_dir: .hermes/evidence/<TASK-ID>
result_file: .hermes/tasks/<TASK-ID>-result.md
---

# Task

Bootstrap Beauty multi-agent v3 blank profiles and local CLI pilot only.

# Non-Recursion

Do not spawn autonomous loops. Do not configure Discord/Gateway. Do not run real uploads/deletes/cron jobs. Do not clone the `beauty` profile.
```

Expected: packet exists and references the Kanban task.

- [ ] **Step 4: Comment on Kanban**

Run:

```bash
hermes kanban comment <kanban_task_id> "PDD started <TASK-ID>. Packet: .hermes/tasks/<TASK-ID>.md; evidence: .hermes/evidence/<TASK-ID>/; plan: docs/superpowers/plans/2026-07-01-beauty-multi-agent-v3.md."
```

Expected:

```text
Comment added to <kanban_task_id>
```

---

### Task 2: Create blank profiles without cloning `beauty`

**Files:**
- Profile-local create/modify only:
  - `C:/Users/Michael Xiao/AppData/Local/hermes/profiles/beauty-pm/`
  - `C:/Users/Michael Xiao/AppData/Local/hermes/profiles/beauty-dev/`
  - `C:/Users/Michael Xiao/AppData/Local/hermes/profiles/beauty-test/`
  - `C:/Users/Michael Xiao/AppData/Local/hermes/profiles/beauty-review/`
- Evidence logs under `.hermes/evidence/<TASK-ID>/`

**Interfaces:**
- Consumes: Hermes profile CLI.
- Produces: blank profiles with descriptions, not cloned from `beauty`.

- [ ] **Step 1: Record current profile list**

Run:

```bash
hermes profile list > .hermes/evidence/<TASK-ID>/profile-list-before.txt
```

Expected: command exits 0.

- [ ] **Step 2: Create missing blank profiles**

Run these only if the profile is missing from the before list:

```bash
hermes profile create beauty-pm --description "Planning and Kanban intake for Beauty Video Transport. Does not implement production code or dispatch development workers."
hermes profile create beauty-dev --description "Development controller for bounded Beauty Video Transport task packets. Uses Codex first and Claude Code as narrow fallback."
hermes profile create beauty-test --description "Independent QA and evidence collector for Beauty Video Transport. Reports only and does not fix code."
hermes profile create beauty-review --description "Independent code, DB, cron, upload, and platform-safety reviewer for Beauty Video Transport diffs. Reports only."
```

Expected: each created profile reports success. No command includes `--clone`, `--clone-from`, or `--clone-all`.

- [ ] **Step 3: Record profile details**

Run:

```bash
{
  hermes profile show beauty-pm
  hermes profile show beauty-dev
  hermes profile show beauty-test
  hermes profile show beauty-review
} > .hermes/evidence/<TASK-ID>/profile-show-after.txt
```

Expected: all profiles exist and descriptions match the intended role.

- [ ] **Step 4: Verify no repo changes were made by profile creation**

Run:

```bash
git status --short --untracked-files=all
```

Expected: only `.hermes/tasks/` and `.hermes/evidence/` runtime artifacts, which are ignored, or no output.

---

### Task 3: Install profile-local role identity from repo templates

**Files:**
- Read:
  - `.hermes/roles/profile/beauty-pm.md`
  - `.hermes/roles/profile/beauty-dev.md`
  - `.hermes/roles/profile/beauty-test.md`
  - `.hermes/roles/profile/beauty-review.md`
- Write profile-local identity files. Use the profile-local path supported by the current Hermes setup. If no dedicated SOUL path is configured, use a clearly named profile-local role file:
  - `C:/Users/Michael Xiao/AppData/Local/hermes/profiles/<profile>/ROLE.md`

**Interfaces:**
- Consumes: repo role templates.
- Produces: profile-local identity artifacts for local pilot.

- [ ] **Step 1: Inspect profile directories**

Run:

```bash
for p in beauty-pm beauty-dev beauty-test beauty-review; do
  echo "--- $p ---"
  ls -la "$HOME/AppData/Local/hermes/profiles/$p"
done > .hermes/evidence/<TASK-ID>/profile-dir-listing.txt
```

Expected: directories exist.

- [ ] **Step 2: Copy role templates into profile-local ROLE.md files**

Run:

```bash
cp .hermes/roles/profile/beauty-pm.md "$HOME/AppData/Local/hermes/profiles/beauty-pm/ROLE.md"
cp .hermes/roles/profile/beauty-dev.md "$HOME/AppData/Local/hermes/profiles/beauty-dev/ROLE.md"
cp .hermes/roles/profile/beauty-test.md "$HOME/AppData/Local/hermes/profiles/beauty-test/ROLE.md"
cp .hermes/roles/profile/beauty-review.md "$HOME/AppData/Local/hermes/profiles/beauty-review/ROLE.md"
```

Expected: files exist in profile-local directories.

- [ ] **Step 3: Record installed identity checksums and heads**

Run:

```bash
for p in beauty-pm beauty-dev beauty-test beauty-review; do
  f="$HOME/AppData/Local/hermes/profiles/$p/ROLE.md"
  echo "--- $p ROLE.md ---"
  wc -l "$f"
  sha256sum "$f"
  sed -n '1,40p' "$f"
done > .hermes/evidence/<TASK-ID>/profile-role-installed.txt
```

Expected: each role file has content matching the repo template.

---

### Task 4: Run local CLI pilot smoke checks

**Files:**
- Evidence logs under `.hermes/evidence/<TASK-ID>/`
- No repo production changes.

**Interfaces:**
- Consumes: created profiles and installed identity templates.
- Produces: local CLI smoke evidence proving profiles are addressable and do not need Gateway.

- [ ] **Step 1: PM profile smoke check**

Run:

```bash
hermes --profile beauty-pm --skills superpowers-brainstorming,superpowers-writing-plans,kanban-backed-pm-orchestration chat -q "Smoke check only. State your role in one sentence and list two things you must not do in this project. Do not call tools." > .hermes/evidence/<TASK-ID>/smoke-beauty-pm.txt
```

Expected: response identifies planning/intake role and says it must not implement production code or dispatch development workers.

- [ ] **Step 2: Dev profile smoke check**

Run:

```bash
hermes --profile beauty-dev --skills test-driven-development,systematic-debugging,codex,claude-code chat -q "Smoke check only. State your role in one sentence and list two things you must not do in this project. Do not call tools." > .hermes/evidence/<TASK-ID>/smoke-beauty-dev.txt
```

Expected: response identifies dev controller role and says it must not final-gate/mark Kanban done or widen allowed_files.

- [ ] **Step 3: Test profile smoke check**

Run:

```bash
hermes --profile beauty-test --skills agency-evidence-collector,agency-api-tester,douyin-ai-beauty-channel-manager chat -q "Smoke check only. State your role in one sentence and list two things you must not do in this project. Do not call tools." > .hermes/evidence/<TASK-ID>/smoke-beauty-test.txt
```

Expected: response identifies independent QA/evidence role and says it must not fix code or run unauthorized uploads/deletes.

- [ ] **Step 4: Review profile smoke check**

Run:

```bash
hermes --profile beauty-review --skills requesting-code-review,agency-code-reviewer,github-code-review chat -q "Smoke check only. State your role in one sentence and list two things you must not do in this project. Do not call tools." > .hermes/evidence/<TASK-ID>/smoke-beauty-review.txt
```

Expected: response identifies independent reviewer role and says it must not modify code or run platform mutations.

- [ ] **Step 5: Verify smoke outputs**

Run:

```bash
rg -n "production code|dispatch|final|Kanban|fix code|upload|delete|modify code|platform" .hermes/evidence/<TASK-ID>/smoke-beauty-*.txt
```

Expected: outputs include role-boundary language. If a profile acts like PDD or claims final authority, stop and adjust profile identity/config before continuing.

---

### Task 5: Final verification, result, review, and completion

**Files:**
- Create: `.hermes/tasks/<TASK-ID>-result.md`
- Create: `.hermes/tasks/<TASK-ID>-test-report.md`
- Create: `.hermes/tasks/<TASK-ID>-review.md`
- Evidence under `.hermes/evidence/<TASK-ID>/`

**Interfaces:**
- Consumes: profile evidence and smoke outputs.
- Produces: final audited bootstrap result.

- [ ] **Step 1: Run repo validation**

Run:

```bash
python -m unittest discover -s tests -p 'test_ai_beauty_core.py' -v > .hermes/evidence/<TASK-ID>/final-unittest.log 2>&1
python -m compileall -q scripts tests/test_ai_beauty_core.py > .hermes/evidence/<TASK-ID>/final-compileall.log 2>&1
git status --short --untracked-files=all > .hermes/evidence/<TASK-ID>/final-git-status.txt
```

Expected: tests and compileall pass; git status has no production changes.

- [ ] **Step 2: Write result report**

Write `.hermes/tasks/<TASK-ID>-result.md`:

```markdown
---
task_id: <TASK-ID>
status: pass
evidence_dir: .hermes/evidence/<TASK-ID>
---

# Result

## Summary

Created/verified blank Beauty role profiles and installed profile-local role identity templates. No profile was cloned from `beauty`. No Discord/Gateway was configured. No production code or platform operation changed.

## Profiles

- beauty-pm
- beauty-dev
- beauty-test
- beauty-review

## Evidence

- profile-list-before.txt
- profile-show-after.txt
- profile-role-installed.txt
- smoke-beauty-*.txt
- final-unittest.log
- final-compileall.log
- final-git-status.txt

## Blockers

None.
```

- [ ] **Step 3: Write independent-style test report**

Because bootstrap affects profile-local state, write `.hermes/tasks/<TASK-ID>-test-report.md` with:

```markdown
---
task_id: <TASK-ID>
role: test-agent
decision: passed
---

# Test Report

Verified profile existence, role identity installation, local CLI smoke checks, repo tests, compileall, and no production git diff.
```

- [ ] **Step 4: Write review report**

Write `.hermes/tasks/<TASK-ID>-review.md` with:

```markdown
---
task_id: <TASK-ID>
role: reviewer-agent
decision: approved
---

# Review

Approved. Profiles were created blank, role identities match repo templates, no Gateway/Discord configuration was changed, no production scripts or platform operations were modified, and evidence is complete.
```

- [ ] **Step 5: Complete Kanban**

Run:

```bash
hermes kanban complete <kanban_task_id> --result "<TASK-ID> complete. Bootstrapped Beauty multi-agent v3 blank profiles locally; installed role identities; local smoke checks passed; no Gateway/Discord changes; no production code/platform changes."
```

Expected: Kanban status is `done`.

---

## Self-Review

### Spec coverage

- Blank-profile principle: Task 2.
- Role identity templates: Task 3.
- Local CLI pilot before Gateway: Task 4.
- No clone / no Gateway / no platform side effects: Global constraints plus Tasks 2, 4, 5.
- Evidence and final gate: Task 5.

### Placeholder scan

This plan intentionally contains no `TBD`, `TODO`, or unspecified implementation steps. All commands and expected outcomes are explicit.

### Type / path consistency

- Profile names match `docs/multi-agent/beauty-multi-agent-role-architecture-v3.md`.
- Evidence path consistently uses `.hermes/evidence/<TASK-ID>/`.
- Reports consistently use `.hermes/tasks/<TASK-ID>-*.md`.
- Profile-local examples use `C:/Users/Michael Xiao/AppData/Local/hermes/profiles/<profile>/` through `$HOME/AppData/Local/hermes/profiles/<profile>/` in Git Bash.

## Execution Handoff

Plan complete. Recommended execution mode: PDD inline execution for Tasks 1-5, because profile creation and profile-local identity installation affect local Hermes state and should remain under the current PDD operator's direct control rather than being delegated to a worker.
