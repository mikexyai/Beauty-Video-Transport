from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
YOUTUBE_UPLOAD = PROJECT_ROOT / "youtube-upload" / "youtube_upload.py"


def _norm(value: str | None) -> str:
    return str(value or "").strip().lower()


def validate_channel_identity(
    channel: dict[str, Any],
    *,
    expect_title: str | None = None,
    expect_handle: str | None = None,
    expect_channel_id: str | None = None,
) -> dict[str, Any]:
    actual = {
        "id": channel.get("id"),
        "title": channel.get("title") or channel.get("snippet", {}).get("title"),
        "customUrl": channel.get("customUrl") or channel.get("custom_url") or channel.get("snippet", {}).get("customUrl"),
    }
    problems: list[str] = []
    if expect_channel_id and actual["id"] != expect_channel_id:
        problems.append(f"channel_id mismatch: expected {expect_channel_id}, got {actual['id']}")
    if expect_title and _norm(actual["title"]) != _norm(expect_title):
        problems.append(f"title mismatch: expected {expect_title}, got {actual['title']}")
    if expect_handle and _norm(actual["customUrl"]) != _norm(expect_handle):
        problems.append(f"handle mismatch: expected {expect_handle}, got {actual['customUrl']}")
    return {"ok": not problems, "channel": actual, "problems": problems}


def load_channels(profile: str) -> list[dict[str, Any]]:
    proc = subprocess.run(
        ["python", str(YOUTUBE_UPLOAD), "list-channels", "--profile", profile],
        cwd=str(YOUTUBE_UPLOAD.parent),
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip())
    data = json.loads(proc.stdout)
    return list(data.get("channels") or [])


def guard_profile(
    *,
    profile: str,
    expect_title: str | None = None,
    expect_handle: str | None = None,
    expect_channel_id: str | None = None,
) -> dict[str, Any]:
    channels = load_channels(profile)
    if not channels:
        return {"ok": False, "profile": profile, "channels": [], "problems": ["no channels returned"]}
    checks = [
        validate_channel_identity(ch, expect_title=expect_title, expect_handle=expect_handle, expect_channel_id=expect_channel_id)
        for ch in channels
    ]
    ok = any(c["ok"] for c in checks)
    return {"ok": ok, "profile": profile, "checks": checks, "problems": [] if ok else [p for c in checks for p in c["problems"]]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a YouTube uploader profile resolves to the expected channel before upload.")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--expect-title")
    parser.add_argument("--expect-handle")
    parser.add_argument("--expect-channel-id")
    args = parser.parse_args()
    result = guard_profile(
        profile=args.profile,
        expect_title=args.expect_title,
        expect_handle=args.expect_handle,
        expect_channel_id=args.expect_channel_id,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
