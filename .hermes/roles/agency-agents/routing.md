# Agency Agents Routing

Hermes PM owns role selection. Codex and Claude Code are bounded leaf workers that execute exactly one selected role.

## Installed agency-agents subset

The following `msitarzewski/agency-agents` roles are installed in this project's Hermes `car` profile and in the local Codex/Claude Code user agent stores:

| Work type | Primary role to assign | Hermes skill | Codex custom agent | Claude Code agent file |
|---|---|---|---|---|
| Frontend/UI implementation | Frontend Developer | `agency-frontend-developer` | `frontend-developer` | `engineering-frontend-developer.md` |
| Backend/API architecture | Backend Architect | `agency-backend-architect` | `backend-architect` | `engineering-backend-architect.md` |
| Code review | Code Reviewer | `agency-code-reviewer` | `code-reviewer` | `engineering-code-reviewer.md` |
| API or integration testing | API Tester | `agency-api-tester` | `api-tester` | `testing-api-tester.md` |
| Evidence capture / validation artifacts | Evidence Collector | `agency-evidence-collector` | `evidence-collector` | `testing-evidence-collector.md` |
| Scope/risk sanity check | Reality Checker | `agency-reality-checker` | `reality-checker` | `testing-reality-checker.md` |
| Product requirements / prioritization | Product Manager | `agency-product-manager` | `product-manager` | `product-manager.md` |
| Technical docs | Technical Writer | `agency-technical-writer` | `technical-writer` | `engineering-technical-writer.md` |
| Security-sensitive implementation/review | Application Security Engineer | `agency-application-security-engineer` | `application-security-engineer` | `security-appsec-engineer.md` |

## Dispatch rule

Every Codex or Claude Code worker packet must name exactly one role. Put the role in frontmatter (`role: ...`) and in the prompt body using this exact activation sentence:

```text
Use the agency-agents role: <Role Name>.
```

Examples:

```text
Use the agency-agents role: Frontend Developer.
Use the agency-agents role: Code Reviewer.
Use the agency-agents role: API Tester.
```

## Non-recursion boundary

Agency Agents roles are persona/context only. They do not grant orchestration authority.

Every worker prompt must preserve these rules:

- Do not invoke Hermes.
- Do not spawn Codex, Claude Code, OpenCode, Copilot, or subagents.
- Do not schedule cron jobs.
- Do not start background autonomous loops.
- If blocked, stop and write the blocker in the task result/report.

## Hermes PM usage

When preparing a task packet:

1. Pick the row above that matches the task.
2. Load the matching Hermes skill if more detailed role context is needed.
3. Set `--role` or packet `role:` to the human-readable role name.
4. Keep one primary role per worker. If multiple perspectives are needed, create separate Kanban-backed packets.
5. Verify the packet includes `.hermes/protocols/non-recursion.md`, `.hermes/protocols/codex-task-packet.md`, and `.hermes/protocols/verification-gates.md` by reference or by equivalent inline rules.
