# Dynamic Roles from agency-agents

Special tasks may use a role adapted from `https://github.com/msitarzewski/agency-agents`. The installed and approved routing table lives in `.hermes/roles/agency-agents/routing.md`.

## Policy

- Hermes PM selects dynamic roles only when the standard Codex Dev, Test Agent, and Reviewer Agent roles are not specific enough.
- A worker packet gets one primary role.
- Multiple expert perspectives require multiple explicit Kanban tasks.
- Dynamic roles remain bounded leaf workers.
- Dynamic roles must obey `.hermes/protocols/non-recursion.md`.

## Common Role Choices

- Frontend/UI implementation: Frontend Developer
- Backend/API architecture: Backend Architect
- API or integration testing: API Tester
- Code review: Code Reviewer
- Evidence capture: Evidence Collector
- Product requirements: Product Manager
- Documentation/spec work: Technical Writer
- Security-sensitive work: Application Security Engineer

## Usage

Use `.hermes/roles/agency-agents/routing.md` when choosing a role. Every Codex or Claude Code worker prompt must include `Use the agency-agents role: <Role Name>.` Do not ask a worker to fetch or load a role library unless Hermes PM explicitly decides that network access is required for the task.
