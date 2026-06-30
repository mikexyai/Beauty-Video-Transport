# Non-Recursion Protocol

Hermes `car` profile is the only orchestration root for this project.

## Worker Rules

Every Codex, test, review, or dynamic-role worker is a bounded leaf worker.

Workers must not:

- invoke Hermes
- spawn Codex, Claude, OpenCode, Copilot, or other coding agents
- call `delegate_task` or any subagent mechanism
- schedule cron jobs
- start background autonomous loops
- ask another agent to continue the task
- mark a Kanban task completed

If a worker is blocked, it must stop and report the blocker in its result, test report, or review report.

## PM Rules

Hermes PM may:

- create Kanban tasks
- write repo-local task packets
- launch Codex CLI
- dispatch local test and review leaf agents
- run final verification
- mark tasks completed after verification

Worker self-reports are evidence, not final truth. Completion requires PM verification.

## Failure Handling

When a test or review worker finds a problem, it reports the issue only. Hermes PM creates an explicit fix task for Codex. Workers never call each other directly.
