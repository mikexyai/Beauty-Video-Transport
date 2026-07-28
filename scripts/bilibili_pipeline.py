from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CHANNELS = {
    "channelCos": {
        "title": "Beauty Spotlight",
        "handle": "@beautycosplay",
        "channel_id": "UC9NJrEfSwFaZUozGm2Xo6mg",
    },
    "channelDance": {
        "title": "Beauty Dancing",
        "handle": "@beautydanc",
        "channel_id": "UCeprMslY3py0HN2qY9MCQng",
    },
}


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "y", "clear", "beauty"}


def decide_bilibili_candidate_action(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return the high-level action before download/upload side effects.

    Rules preserved from the Bilibili skill:
    - non-beauty stops the run before coin cleanup;
    - beauty candidate with coin == 0 is removed from default favorites, not uploaded;
    - beauty candidate with coin > 0 continues to inspection/download/upload.
    """
    if not _truthy(candidate.get("is_beauty")):
        return {
            "action": "stop_non_beauty",
            "upload": False,
            "remove_favorite": False,
            "reason": "Next favorite is not a beauty/cosplay/dance/model video.",
        }
    try:
        coin = int(candidate.get("coin") or 0)
    except (TypeError, ValueError):
        coin = 0
    if coin <= 0:
        return {
            "action": "remove_default_favorite",
            "upload": False,
            "remove_favorite": True,
            "reason": "Beauty candidate has coin == 0; remove from 默认收藏夹 without upload.",
        }
    return {
        "action": "process_upload",
        "upload": True,
        "remove_favorite": False,
        "reason": "Beauty candidate is coined and processable.",
    }


def route_bilibili_upload(visual: dict[str, Any]) -> dict[str, str]:
    orientation = str(visual.get("orientation") or "vertical").strip().lower()
    is_horizontal = orientation in {"horizontal", "landscape", "横屏"}
    clear_dance = _truthy(visual.get("clear_dance"))
    profile = "channelDance" if clear_dance else "channelCos"
    return {
        "profile": profile,
        "target_folder": "美女-横屏" if is_horizontal else "美女-竖屏",
        "channel_title": CHANNELS[profile]["title"],
        "channel_handle": CHANNELS[profile]["handle"],
        "channel_id": CHANNELS[profile]["channel_id"],
    }


def build_guard_command(profile: str) -> str:
    meta = CHANNELS[profile]
    return (
        "python scripts/youtube_profile_guard.py "
        f"--profile {profile} "
        f"--expect-title '{meta['title']}' "
        f"--expect-handle '{meta['handle']}' "
        f"--expect-channel-id {meta['channel_id']}"
    )


def build_bilibili_pipeline_plan(*, max_items: int = 5, dry_run: bool = True) -> dict[str, Any]:
    return {
        "pipeline": "bilibili_cos_dance_nightly",
        "dry_run": dry_run,
        "max_items": max_items,
        "scope": "Bilibili 默认收藏夹 -> channelCos/channelDance only; no ai_beauty_* writes",
        "steps": [
            {
                "step": "list_default_favorites",
                "command": f"python scripts/beauty_cdp_ops.py list-default --ps {max_items}",
                "side_effect": False,
            },
            {
                "step": "inspect_next_candidate",
                "command": "python scripts/beauty_cdp_ops.py inspect <BVID> --wait 8",
                "side_effect": "opens Bilibili video page and pauses video",
            },
            {
                "step": "decide_coin_and_beauty_action",
                "rule": "non-beauty stops before coin cleanup; beauty coin==0 remove-default; coin>0 process upload",
                "side_effect": False,
            },
            {
                "step": "download_highest_quality",
                "command": "python scripts/bilibili_download_best.py <BVID> --out 'downloads/bilibili/<BVID>.%(ext)s'",
                "side_effect": "downloads media only for processable coined beauty candidates",
            },
            {
                "step": "verify_media_and_contact_sheet",
                "command": "ffprobe <downloaded-file> && ffmpeg sampled frames -> analysis/video_frames_<BVID>/contact_sheet.jpg",
                "side_effect": "writes analysis artifacts",
            },
            {
                "step": "vision_route",
                "rule": "channelDance only for clear dance; light movement/posing/lip-sync -> channelCos; tags <= 5; empty description",
                "side_effect": False,
            },
            {
                "step": "guard_channel_cos",
                "command": build_guard_command("channelCos"),
                "side_effect": False,
            },
            {
                "step": "guard_channel_dance",
                "command": build_guard_command("channelDance"),
                "side_effect": False,
            },
            {
                "step": "upload_and_record",
                "command": "python youtube-upload/youtube_upload.py upload --profile <channelCos|channelDance> ...",
                "side_effect": "real YouTube upload only after route/guard/dry-run; writes beauty.upload_records",
            },
            {
                "step": "post_upload_favorite_move_or_remove",
                "command": "python scripts/beauty_cdp_ops.py deal move <BVID> --target-folder '<美女-竖屏|美女-横屏>'",
                "side_effect": "moves uploaded coined favorite; coin==0 uses deal remove-default",
            },
            {
                "step": "cleanup",
                "rule": "delete local downloaded/output mp4 and .part files after verified upload/skip",
                "side_effect": "local file deletion only",
            },
        ],
    }


def run_command(command: list[str], *, timeout: int = 120) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=str(PROJECT_ROOT), text=True, capture_output=True, timeout=timeout)
    return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def main() -> int:
    parser = argparse.ArgumentParser(description="Stable Bilibili Cos/Dance pipeline entrypoint and dry-run planner.")
    parser.add_argument("--max-items", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true", help="Print plan only; no side-effecting upload/favorite operations")
    parser.add_argument("--list-default", action="store_true", help="Safely list current Bilibili 默认收藏夹 through CDP")
    parser.add_argument("--ps", type=int, default=5)
    args = parser.parse_args()

    plan = build_bilibili_pipeline_plan(max_items=args.max_items, dry_run=args.dry_run)
    report: dict[str, Any] = {"plan": plan}
    if args.list_default:
        report["list_default"] = run_command(["python", "scripts/beauty_cdp_ops.py", "list-default", "--ps", str(args.ps)])
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if not report.get("list_default") or report["list_default"]["returncode"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
