from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

TASK_ID_RE = re.compile(r"^TASK-(\d{4})\.md$")


@dataclass(frozen=True)
class DispatchRequest:
    repo: Path
    task_body: str
    role: str
    kanban_task_id: str
    allowed_files: tuple[str, ...]
    out_of_scope: tuple[str, ...]
    acceptance: tuple[str, ...]
    validation: tuple[str, ...]
    sandbox: str
    launch: bool
    doc_summaries: tuple[str, ...] = ()
    code_context: tuple[str, ...] = ()
    frontend_touchpoints: tuple[str, ...] = ()
    backend_touchpoints: tuple[str, ...] = ()
    forbidden_doc_reads: tuple[str, ...] = ()
    codex_model: str = "openai.global.gpt-5.5"


def repo_root(path: str | None) -> Path:
    return Path(path or ".").resolve()


def task_number_from_name(path: Path) -> int | None:
    match = TASK_ID_RE.match(path.name)
    if match is None:
        return None
    return int(match.group(1))


def next_task_id(tasks_dir: Path) -> str:
    numbers = [n for n in (task_number_from_name(path) for path in tasks_dir.glob("TASK-*.md")) if n is not None]
    next_number = max(numbers, default=0) + 1
    return f"TASK-{next_number:04d}"


def yaml_list(items: tuple[str, ...]) -> str:
    if not items:
        return "  - none"
    return "\n".join(f"  - {item}" for item in items)


def markdown_list(items: tuple[str, ...]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def current_branch(repo: Path) -> str:
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo,
        check=False,
        text=True,
        capture_output=True,
    )
    branch = result.stdout.strip()
    return branch or "unknown"


def create_kanban_task(repo: Path, title: str, body: str, assignee: str | None = None) -> str:
    command = [
        "hermes",
        "kanban",
        "create",
        title,
        "--body",
        body,
        "--workspace",
        f"dir:{repo.as_posix()}",
        "--created-by",
        "Hermes PM",
        "--json",
    ]
    if assignee:
        command.extend(["--assignee", assignee])
    result = subprocess.run(command, cwd=repo, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create Kanban task:\n{result.stderr or result.stdout}")
    data = json.loads(result.stdout)
    task_id = data.get("id") or data.get("task_id") or data.get("key")
    if not task_id:
        raise RuntimeError(f"Kanban create did not return an id: {result.stdout}")
    return str(task_id)


def comment_kanban_task(repo: Path, kanban_task_id: str, comment: str) -> None:
    result = subprocess.run(
        ["hermes", "kanban", "comment", kanban_task_id, comment],
        cwd=repo,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to comment on Kanban task {kanban_task_id}:\n{result.stderr or result.stdout}")


def render_template(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    missing = sorted(set(re.findall(r"{{[A-Z0-9_]+}}", rendered)))
    if missing:
        raise ValueError(f"Unresolved template tokens: {', '.join(missing)}")
    return rendered


def build_task_packet(repo: Path, task_id: str, request: DispatchRequest) -> str:
    template_path = repo / ".hermes" / "templates" / "task-packet.md"
    template = template_path.read_text(encoding="utf-8")
    values = {
        "TASK_ID": task_id,
        "KANBAN_TASK_ID": request.kanban_task_id,
        "ROLE": request.role,
        "REPO_PATH": repo.as_posix(),
        "BRANCH": current_branch(repo),
        "ALLOWED_FILES_YAML": yaml_list(request.allowed_files),
        "OUT_OF_SCOPE_YAML": yaml_list(request.out_of_scope),
        "TASK_BODY": request.task_body.strip(),
        "DOC_SUMMARIES_MD": markdown_list(request.doc_summaries),
        "CODE_CONTEXT_MD": markdown_list(request.code_context),
        "FRONTEND_TOUCHPOINTS_MD": markdown_list(request.frontend_touchpoints),
        "BACKEND_TOUCHPOINTS_MD": markdown_list(request.backend_touchpoints),
        "FORBIDDEN_DOC_READS_MD": markdown_list(request.forbidden_doc_reads),
        "ACCEPTANCE_CRITERIA_MD": markdown_list(request.acceptance),
        "VALIDATION_COMMANDS_MD": markdown_list(request.validation),
    }
    return render_template(template, values)


def write_task_packet(request: DispatchRequest) -> Path:
    tasks_dir = request.repo / ".hermes" / "tasks"
    evidence_root = request.repo / ".hermes" / "evidence"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    evidence_root.mkdir(parents=True, exist_ok=True)

    task_id = next_task_id(tasks_dir)
    packet_path = tasks_dir / f"{task_id}.md"
    evidence_dir = evidence_root / task_id
    evidence_dir.mkdir(parents=True, exist_ok=False)

    packet = build_task_packet(request.repo, task_id, request)
    packet_path.write_text(packet, encoding="utf-8")
    return packet_path


def pro_model_name(model: str) -> str:
    return model if model.endswith("-pro") else f"{model}-pro"


def codex_command(
    repo: Path,
    packet_path: Path,
    sandbox: str,
    *,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> list[str]:
    relative_packet = packet_path.relative_to(repo).as_posix()
    command = [
        "codex",
        "exec",
        "-C",
        repo.as_posix(),
        "--sandbox",
        sandbox,
    ]
    if model:
        command.extend(["-m", model])
    if reasoning_effort:
        command.extend(["-c", f"model_reasoning_effort=\"{reasoning_effort}\""])
    command.append(f"Read {relative_packet} and complete the bounded task.")
    return command


def claude_command(packet_path: Path, repo: Path) -> list[str]:
    relative_packet = packet_path.relative_to(repo).as_posix()
    prompt = (
        f"Read {relative_packet} and complete the bounded task/current diff. "
        "Keep scope narrow. Obey all allowed_files, out_of_scope, validation, result-file, evidence, and non-recursion rules. "
        "If validation is blocked by tool guards, record the blocker rather than repeatedly retrying. "
        "Do not invoke Hermes, Codex, OpenCode, Copilot, subagents, cron jobs, or background autonomous loops."
    )
    return ["claude", "-p", prompt, "--max-turns", "10", "--allowedTools", "Read,Edit,Write,Bash"]


def launch_codex(repo: Path, packet_path: Path, sandbox: str, base_model: str = "openai.global.gpt-5.5") -> int:
    command = codex_command(repo, packet_path, sandbox)
    first = subprocess.run(command, cwd=repo, check=False).returncode
    if first == 0:
        return 0
    retry_model = pro_model_name(base_model)
    retry_command = codex_command(repo, packet_path, sandbox, model=retry_model, reasoning_effort="medium")
    print(f"Codex failed; retrying once with {retry_model} and reasoning effort medium.")
    second = subprocess.run(retry_command, cwd=repo, check=False).returncode
    if second == 0:
        return 0
    print("Codex retry failed; handing the same bounded task packet/current diff to Claude Code.")
    return subprocess.run(claude_command(packet_path, repo), cwd=repo, check=False).returncode


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a Hermes PM Kanban-backed task packet and evidence directory.")
    parser.add_argument("--repo", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument("--title", default="", help="Kanban task title when --create-kanban is used.")
    parser.add_argument("--task-body", required=True, help="Concrete task description for the worker.")
    parser.add_argument("--role", default="Frontend Developer", help="Primary worker role.")
    parser.add_argument("--kanban-task-id", default="", help="Existing Hermes Kanban task ID. Required unless --create-kanban is set.")
    parser.add_argument("--create-kanban", action="store_true", help="Create a Hermes Kanban task first, then write the repo-local packet.")
    parser.add_argument("--assignee", default="", help="Optional Kanban assignee profile when --create-kanban is used.")
    parser.add_argument("--allowed-file", action="append", default=[], help="Allowed file glob. Repeatable.")
    parser.add_argument("--out-of-scope", action="append", default=[], help="Out-of-scope file glob. Repeatable.")
    parser.add_argument("--acceptance", action="append", default=[], help="Acceptance criterion. Repeatable.")
    parser.add_argument("--validation", action="append", default=[], help="Validation command or requirement. Repeatable.")
    parser.add_argument("--doc-summary", action="append", default=[], help="Task-relevant document summary. Repeatable. Format: path/range: summary.")
    parser.add_argument("--code-context", action="append", default=[], help="Targeted code context, symbol, snippet, or file-range guidance. Repeatable.")
    parser.add_argument("--frontend-touchpoint", action="append", default=[], help="Frontend touchpoint such as component/API client/locale/E2E path. Repeatable.")
    parser.add_argument("--backend-touchpoint", action="append", default=[], help="Backend touchpoint such as route/schema/repository/service/migration path. Repeatable.")
    parser.add_argument("--forbid-doc-read", action="append", default=[], help="Large doc that worker should not read entirely unless explicitly unblocked. Repeatable.")
    parser.add_argument("--sandbox", default="workspace-write", choices=["workspace-write", "danger-full-access"], help="Codex sandbox mode.")
    parser.add_argument("--codex-model", default="openai.global.gpt-5.5", help="Base Codex model. Retry uses the same name with a -pro suffix and medium reasoning effort.")
    parser.add_argument("--launch", action="store_true", help="Launch Codex after writing the packet.")
    return parser.parse_args(argv)


def request_from_args(args: argparse.Namespace) -> DispatchRequest:
    repo = repo_root(args.repo)
    kanban_task_id = str(args.kanban_task_id or "").strip()
    if not kanban_task_id:
        raise SystemExit("A Kanban task is required. Pass --kanban-task-id <id> or use --create-kanban.")
    return DispatchRequest(
        repo=repo,
        task_body=args.task_body,
        role=args.role,
        kanban_task_id=kanban_task_id,
        allowed_files=tuple(args.allowed_file),
        out_of_scope=tuple(args.out_of_scope),
        acceptance=tuple(args.acceptance),
        validation=tuple(args.validation),
        sandbox=args.sandbox,
        launch=args.launch,
        doc_summaries=tuple(args.doc_summary),
        code_context=tuple(args.code_context),
        frontend_touchpoints=tuple(args.frontend_touchpoint),
        backend_touchpoints=tuple(args.backend_touchpoint),
        forbidden_doc_reads=tuple(args.forbid_doc_read),
        codex_model=args.codex_model,
    )


def main() -> int:
    args = parse_args()
    repo = repo_root(args.repo)
    if args.create_kanban:
        title = args.title.strip() or args.task_body.strip().splitlines()[0][:80]
        kanban_body = (
            "Hermes PM task created before repo-local packet generation.\n\n"
            f"Role: {args.role}\n"
            "Repo packet/result/evidence paths will be added after packet creation."
        )
        args.kanban_task_id = create_kanban_task(repo, title, kanban_body, args.assignee or None)

    request = request_from_args(args)
    packet_path = write_task_packet(request)
    evidence_path = request.repo / ".hermes" / "evidence" / packet_path.stem
    result_path = request.repo / ".hermes" / "tasks" / f"{packet_path.stem}-result.md"

    if args.create_kanban:
        comment_kanban_task(
            request.repo,
            request.kanban_task_id,
            "Repo-local audit paths:\n"
            f"- Packet: {packet_path.relative_to(request.repo).as_posix()}\n"
            f"- Result: {result_path.relative_to(request.repo).as_posix()}\n"
            f"- Evidence: {evidence_path.relative_to(request.repo).as_posix()}/",
        )

    print(f"kanban_task_id={request.kanban_task_id}")
    print(packet_path.relative_to(request.repo).as_posix())
    print(evidence_path.relative_to(request.repo).as_posix())
    if request.launch:
        return launch_codex(request.repo, packet_path, request.sandbox, base_model=request.codex_model)
    print("Codex launch skipped. Re-run with --launch after PM review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
