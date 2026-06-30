---
task_id: {{TASK_ID}}
kanban_task_id: {{KANBAN_TASK_ID}}
role: {{ROLE}}
worker: codex
status: packet_written
repo: {{REPO_PATH}}
branch: {{BRANCH}}
allowed_files:
{{ALLOWED_FILES_YAML}}
out_of_scope:
{{OUT_OF_SCOPE_YAML}}
evidence_dir: .hermes/evidence/{{TASK_ID}}
result_file: .hermes/tasks/{{TASK_ID}}-result.md
---

# Task

{{TASK_BODY}}

# Role

You are acting as: {{ROLE}}.

Use the agency-agents role: {{ROLE}}.

Use only the role instructions included in this packet, `.hermes/roles/standard/codex-dev.md`, or `.hermes/roles/agency-agents/routing.md`. If a dynamic role from `agency-agents` is included, treat it as role context only, not as permission to spawn agents.

# Methodology

Use `obra/superpowers`-style development:

1. Read this packet completely.
2. Clarify assumptions internally and keep them narrow.
3. Plan briefly.
4. Prefer TDD where practical.
5. Implement minimally.
6. Run required checks.
7. Report evidence.

# Non-Recursion Rules

- You are a bounded leaf worker.
- Do not invoke Hermes.
- Do not spawn Codex, Claude, OpenCode, Copilot, or other coding agents.
- Do not call delegate_task or any subagent mechanism.
- Do not schedule cron jobs.
- Do not start background autonomous loops.
- Do not ask another agent to continue.
- If blocked, stop and report the blocker in the result file.

# Acceptance Criteria

{{ACCEPTANCE_CRITERIA_MD}}

# Worker Context Budget

- Treat this packet as the primary source of truth. Do not read whole design/spec/plan documents unless this packet explicitly lists narrow sections or ranges to inspect.
- Prefer targeted reads of allowed files and exact snippets over dumping complete large files.
- Write the result file as soon as a coherent implementation/partial status exists; do not wait until every expensive validation finishes.

# Relevant Docs Summary

{{DOC_SUMMARIES_MD}}

# Targeted Code Context

{{CODE_CONTEXT_MD}}

# Implementation Touchpoints

List scripts, modules, CLIs, docs, SQL, tests, and evidence paths that are relevant to this task. If a category is not relevant, say so explicitly.

{{FRONTEND_TOUCHPOINTS_MD}}

# Data / Platform Touchpoints

List database tables, cron jobs, YouTube profiles/channels, Douyin/Bilibili sources, credential paths, and operational safety checks that are relevant to this task. If a category is not relevant, say so explicitly.

{{BACKEND_TOUCHPOINTS_MD}}

# Do Not Read Entirely

The following files are large/background references. Do not read them entirely unless the targeted summary above is insufficient and you record why in the result file.

{{FORBIDDEN_DOC_READS_MD}}

# Required Validation

{{VALIDATION_COMMANDS_MD}}

Worker validation is intentionally cheap and scoped. On Windows/PowerShell, use `python` for Python CLIs and `npm.cmd` instead of `npm` if PowerShell execution policy blocks `npm.ps1`. Do not run full operational pipelines, real uploads/deletes, or broad browser/CDP runs unless this packet explicitly requests it; PDD/Test Agent owns full dry-run/live verification, evidence, artifact cleanup, and final gate.

# Secret / Placeholder Guard

If you modify scripts, docs, SQL, task packets, or evidence text, check changed scoped files for `????`, `�`, `TODO`, `TBD`, and secret-like strings such as `client_secret`, `refresh_token`, `access_token`, `api_key`, `cookie`, and `password` before reporting success. Real secrets are blockers; expected prose references to ignored secret paths are allowed when documented.

# Failure Policy

Hermes PM will run Codex at most twice for this task: the initial attempt plus one retry. The retry must use the same model name with a `-pro` suffix and `model_reasoning_effort="medium"` (for example, `openai.global.gpt-5.5`/`medium` then `openai.global.gpt-5.5-pro`/`medium`). If Codex fails twice before producing a valid result, Hermes PM will hand this same bounded packet and any current partial diff to Claude Code. The fallback worker must obey the same allowed files, out-of-scope list, validation, result file, evidence, and non-recursion rules, and should report blocked validation instead of repeatedly attempting commands blocked by tool guards.

# Result Requirements

Write `.hermes/tasks/{{TASK_ID}}-result.md` with:

- summary
- changed files
- commands run
- pass/fail status
- blockers
- evidence paths
