# Codex Task Packet Protocol

Codex receives bounded development work through repo-local task packets under `.hermes/tasks/`.

## Required Packet Fields

Each packet frontmatter must include:

- `task_id`: stable repo task ID such as `TASK-0001`
- `kanban_task_id`: Hermes Kanban ID or `MANUAL` for a manually tracked task
- `role`: one primary role for the worker
- `worker`: `codex`
- `status`: `packet_written` when created
- `repo`: absolute or repo-root path
- `branch`: current branch at packet creation time
- `allowed_files`: paths Codex may modify
- `out_of_scope`: paths or behaviors Codex must not modify
- `evidence_dir`: `.hermes/evidence/TASK-000N`
- `result_file`: `.hermes/tasks/TASK-000N-result.md`

## Standard Launch Command

Run Codex from Hermes with a PTY:

```bash
codex exec -C C:/Project/Beauty-Video-Transport --sandbox workspace-write "Read .hermes/tasks/TASK-000N.md and complete the bounded task."
```

Each packet must include a role activation sentence for the installed Agency Agents subset:

```text
Use the agency-agents role: <Role Name>.
```

Notes:

- The current local Codex CLI (`0.142.2`) does not support `--ask-for-approval`; rely on Codex config/profile approval behavior instead of passing that flag.
- If the service context cannot use the workspace sandbox, Hermes PM may use `--sandbox danger-full-access` only after checking git status and keeping the workdir scoped to the repo.
- On Windows/PowerShell, worker prompts should prefer `python` for Python CLIs and `npm.cmd` for Node package scripts when `npm.ps1` is blocked by execution policy.

## Compact Packet Requirement

PDD/Hermes must summarize large design/spec/plan documents before dispatch. A Codex packet should include exact scope, allowed files, acceptance criteria, focused file ranges or snippets, and cheap validation commands. Do not ask Codex to read whole large plans/specs by default; excessive context reading has repeatedly caused 600s timeouts.

Every implementation packet should fill the context-budget sections in `.hermes/templates/task-packet.md` instead of relying on broad “read the whole spec/design” instructions:

- `Relevant Docs Summary`: task-specific summary of approved docs, with file/range references when useful.
- `Targeted Code Context`: exact files, symbols, line ranges, or short snippets the worker should inspect first.
- `Frontend Touchpoints`: component, API client, locale, and E2E paths for frontend-affecting work; explicitly say `none` for irrelevant categories.
- `Backend Touchpoints`: route, schema, service/repository, migration, and test paths for backend-affecting work; explicitly say `none` for irrelevant categories.
- `Do Not Read Entirely`: large/background documents that should not be dumped wholesale unless the summary proves insufficient and the worker records why.

Use `.hermes/scripts/pm_dispatch.py` flags to populate these fields: `--doc-summary`, `--code-context`, `--frontend-touchpoint`, `--backend-touchpoint`, and `--forbid-doc-read`.

## Validation Split

- Codex Dev runs cheap scoped checks: lint/build or focused unit/smoke checks listed in the packet.
- PDD/Test Agent owns full dry-run/live operational verification, browser/CDP evidence when relevant, generated artifact cleanup, final secret/placeholder scans, and final gate.
- If Codex creates a partial diff but times out, PDD inspects the diff before retry/fallback and passes the current state to Claude Code when needed.

## Failure Handling: Retry Once, Then Claude Code

If Codex fails because of a transient provider/network/WAF issue, CLI crash, sandbox failure, or any non-zero exit before a valid result file is produced, Hermes PM must use this policy:

1. Keep the same task packet and evidence directory.
2. Retry Codex exactly once, but switch the retry attempt to the same model name with a `-pro` suffix and set reasoning effort to `medium`.
   - Example from the current baseline: first attempt `openai.global.gpt-5.5` / `medium`; retry `openai.global.gpt-5.5-pro` / `medium`.
3. If the retry also fails, stop using Codex for that task and hand the same packet to Claude Code.
4. Claude Code inherits the same bounded worker contract: allowed files, out-of-scope files, result file, evidence directory, required validation, and non-recursion rules.
5. Claude Code fallback should stay narrow: inspect current diff, fix obvious blockers, write/update the result, and report blocked validation rather than repeatedly trying commands blocked by tool guards.
6. Record the first Codex attempt, the `-pro`/`medium` retry, and any Claude Code fallback in the result file or PM notes.

Recommended Codex retry command:

```bash
codex exec -C C:/Project/Beauty-Video-Transport --sandbox workspace-write -m openai.global.gpt-5.5-pro -c model_reasoning_effort="medium" "Read .hermes/tasks/TASK-000N.md and complete the bounded task."
```

Recommended Claude Code fallback command:

```bash
claude -p "Read .hermes/tasks/TASK-000N.md and complete the bounded task. Obey all allowed_files, out_of_scope, validation, result-file, and non-recursion rules. Do not invoke Hermes, Codex, OpenCode, Copilot, subagents, cron jobs, or background autonomous loops." --max-turns 10 --allowedTools "Read,Edit,Write,Bash"
```

## Result Contract

Codex writes `.hermes/tasks/TASK-000N-result.md` early, even for a partial/blocker status, with:

- summary
- changed files
- commands run
- pass/fail status
- blockers
- evidence paths

Codex must not commit automatically. Hermes PM reviews the diff and decides the next step.
