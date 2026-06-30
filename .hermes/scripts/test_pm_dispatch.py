from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SCRIPT_PATH = Path(__file__).with_name("pm_dispatch.py")
spec = importlib.util.spec_from_file_location("pm_dispatch", SCRIPT_PATH)
pm_dispatch = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = pm_dispatch
spec.loader.exec_module(pm_dispatch)


TASK_TEMPLATE = """---
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

# Acceptance Criteria

{{ACCEPTANCE_CRITERIA_MD}}

# Relevant Docs Summary

{{DOC_SUMMARIES_MD}}

# Targeted Code Context

{{CODE_CONTEXT_MD}}

# Frontend Touchpoints

{{FRONTEND_TOUCHPOINTS_MD}}

# Backend Touchpoints

{{BACKEND_TOUCHPOINTS_MD}}

# Do Not Read Entirely

{{FORBIDDEN_DOC_READS_MD}}

# Role

You are acting as: {{ROLE}}.

Use the agency-agents role: {{ROLE}}.

# Required Validation

{{VALIDATION_COMMANDS_MD}}
"""


class DispatchTests(unittest.TestCase):
    def make_repo(self) -> Path:
        root = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "-b", "master"], cwd=root, check=True, capture_output=True)
        templates = root / ".hermes" / "templates"
        templates.mkdir(parents=True)
        (templates / "task-packet.md").write_text(TASK_TEMPLATE, encoding="utf-8")
        return root

    def test_next_task_id_uses_highest_existing_number(self) -> None:
        root = self.make_repo()
        tasks = root / ".hermes" / "tasks"
        tasks.mkdir(parents=True)
        (tasks / "TASK-0001.md").write_text("one", encoding="utf-8")
        (tasks / "TASK-0007.md").write_text("seven", encoding="utf-8")
        self.assertEqual(pm_dispatch.next_task_id(tasks), "TASK-0008")

    def test_write_task_packet_creates_packet_and_evidence_dir(self) -> None:
        root = self.make_repo()
        request = pm_dispatch.DispatchRequest(
            repo=root,
            task_body="Add a visible save confirmation after session save.",
            role="Frontend Developer",
            kanban_task_id="KANBAN-123",
            allowed_files=("frontend/src/**",),
            out_of_scope=("backend/**",),
            acceptance=("User sees a success message after saving.",),
            validation=("cd frontend && npm run lint",),
            sandbox="workspace-write",
            launch=False,
        )

        packet = pm_dispatch.write_task_packet(request)

        self.assertEqual(packet.name, "TASK-0001.md")
        self.assertTrue((root / ".hermes" / "evidence" / "TASK-0001").is_dir())
        text = packet.read_text(encoding="utf-8")
        self.assertIn("task_id: TASK-0001", text)
        self.assertIn("kanban_task_id: KANBAN-123", text)
        self.assertIn("- frontend/src/**", text)
        self.assertIn("Add a visible save confirmation", text)
        self.assertIn("Use the agency-agents role: Frontend Developer.", text)
        self.assertNotIn("{{", text)

    def test_task_packet_includes_context_budget_sections(self) -> None:
        root = self.make_repo()
        request = pm_dispatch.DispatchRequest(
            repo=root,
            task_body="Improve the save session UX.",
            role="Frontend Developer",
            kanban_task_id="KANBAN-456",
            allowed_files=("frontend/src/App.tsx",),
            out_of_scope=("backend/**",),
            acceptance=("Save feedback is visible.",),
            validation=("cd frontend && npm run lint",),
            sandbox="workspace-write",
            launch=False,
            doc_summaries=("docs/product/save-session.md: Only the success/error toast copy is relevant; do not read the full document.",),
            code_context=("frontend/src/App.tsx: saveSession handles the API call and snackbar state.",),
            frontend_touchpoints=("component: frontend/src/App.tsx; api: frontend/src/api/sessions.ts; locales: frontend/src/locales/*.json; e2e: frontend/e2e/main-flow.mock.spec.ts",),
            backend_touchpoints=("none; backend behavior is out of scope",),
            forbidden_doc_reads=("docs/product/save-session.md",),
        )

        packet = pm_dispatch.write_task_packet(request)
        text = packet.read_text(encoding="utf-8")

        self.assertIn("# Relevant Docs Summary", text)
        self.assertIn("Only the success/error toast copy is relevant", text)
        self.assertIn("# Targeted Code Context", text)
        self.assertIn("saveSession handles the API call", text)
        self.assertIn("# Frontend Touchpoints", text)
        self.assertIn("component: frontend/src/App.tsx", text)
        self.assertIn("# Backend Touchpoints", text)
        self.assertIn("backend behavior is out of scope", text)
        self.assertIn("# Do Not Read Entirely", text)
        self.assertIn("docs/product/save-session.md", text)
        self.assertNotIn("{{", text)

    def test_cli_accepts_context_budget_arguments(self) -> None:
        args = pm_dispatch.parse_args([
            "--repo", ".",
            "--task-body", "Do work",
            "--kanban-task-id", "KANBAN-789",
            "--doc-summary", "docs/a.md: relevant summary",
            "--code-context", "src/a.ts: function foo",
            "--frontend-touchpoint", "component: src/A.tsx",
            "--backend-touchpoint", "route: src/routes.ts",
            "--forbid-doc-read", "docs/a.md",
        ])
        request = pm_dispatch.request_from_args(args)

        self.assertEqual(request.doc_summaries, ("docs/a.md: relevant summary",))
        self.assertEqual(request.code_context, ("src/a.ts: function foo",))
        self.assertEqual(request.frontend_touchpoints, ("component: src/A.tsx",))
        self.assertEqual(request.backend_touchpoints, ("route: src/routes.ts",))
        self.assertEqual(request.forbidden_doc_reads, ("docs/a.md",))

    def test_codex_command_points_to_packet_without_removed_approval_flag(self) -> None:
        root = self.make_repo()
        packet = root / ".hermes" / "tasks" / "TASK-0003.md"
        command = pm_dispatch.codex_command(root, packet, "workspace-write")
        self.assertEqual(command[0:4], ["codex", "exec", "-C", root.as_posix()])
        self.assertNotIn("--ask-for-approval", command)
        self.assertNotIn("never", command)
        self.assertIn("Read .hermes/tasks/TASK-0003.md and complete the bounded task.", command)

    def test_codex_retry_command_uses_pro_model_and_medium_reasoning(self) -> None:
        root = self.make_repo()
        packet = root / ".hermes" / "tasks" / "TASK-0003.md"
        command = pm_dispatch.codex_command(
            root,
            packet,
            "workspace-write",
            model=pm_dispatch.pro_model_name("openai.global.gpt-5.5"),
            reasoning_effort="medium",
        )
        self.assertIn("openai.global.gpt-5.5-pro", command)
        self.assertIn('model_reasoning_effort="medium"', command)

    def test_claude_fallback_command_is_bounded(self) -> None:
        root = self.make_repo()
        packet = root / ".hermes" / "tasks" / "TASK-0003.md"
        command = pm_dispatch.claude_command(packet, root)
        self.assertEqual(command[:2], ["claude", "-p"])
        self.assertIn("--max-turns", command)
        self.assertIn("--allowedTools", command)
        self.assertIn("Do not invoke Hermes", command[2])

    def test_create_kanban_task_returns_created_id(self) -> None:
        root = self.make_repo()
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"id":"t_abc123","status":"ready"}',
            stderr="",
        )
        with patch.object(pm_dispatch.subprocess, "run", Mock(return_value=completed)) as run:
            task_id = pm_dispatch.create_kanban_task(
                repo=root,
                title="Implement save confirmation",
                body="Repo packet will be generated after Kanban creation.",
            )

        self.assertEqual(task_id, "t_abc123")
        command = run.call_args.args[0]
        self.assertEqual(command[:4], ["hermes", "kanban", "create", "Implement save confirmation"])
        self.assertIn("--json", command)
        self.assertIn(f"dir:{root.as_posix()}", command)

    def test_request_requires_kanban_id_or_create_kanban(self) -> None:
        args = pm_dispatch.parse_args([
            "--repo", ".",
            "--task-body", "Do work",
        ])
        with self.assertRaises(SystemExit):
            pm_dispatch.request_from_args(args)


if __name__ == "__main__":
    unittest.main(verbosity=2)
