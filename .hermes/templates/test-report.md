---
task_id: {{TASK_ID}}
worker: test-agent
status: {{STATUS}}
evidence_dir: .hermes/evidence/{{TASK_ID}}
---

# Test Report

## Commands Run

{{COMMANDS_RUN_MD}}

## Results

| Check | Status | Notes |
|---|---|---|
| Backend lint/build | {{BACKEND_STATUS}} | {{BACKEND_NOTES}} |
| Frontend lint/build | {{FRONTEND_STATUS}} | {{FRONTEND_NOTES}} |
| E2E/browser | {{E2E_STATUS}} | {{E2E_NOTES}} |

## Browser Evidence

{{BROWSER_EVIDENCE_MD}}

## Issues Found

{{ISSUES_FOUND}}
