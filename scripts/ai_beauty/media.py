from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from scripts.ai_beauty.db import PROJECT_ROOT

DOWNLOAD_DIR = PROJECT_ROOT / "downloads" / "douyin_ai_beauty"
ANALYSIS_DIR = PROJECT_ROOT / "analysis" / "douyin_ai_beauty"


def ffprobe_json(path: str | Path) -> dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(path),
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=True)
    return json.loads(proc.stdout)


def _video_stream(probe: dict[str, Any]) -> dict[str, Any] | None:
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "video":
            return stream
    return None


def has_video_stream(probe: dict[str, Any]) -> bool:
    return _video_stream(probe) is not None


def duration_seconds(probe: dict[str, Any]) -> float | None:
    stream = _video_stream(probe) or {}
    for value in (stream.get("duration"), probe.get("format", {}).get("duration")):
        if value not in (None, "", "N/A"):
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def dimensions(probe: dict[str, Any]) -> tuple[int, int] | None:
    stream = _video_stream(probe)
    if not stream:
        return None
    width = stream.get("width")
    height = stream.get("height")
    if width and height:
        return int(width), int(height)
    return None


def make_contact_sheet(video_path: str | Path, output_dir: str | Path, *, frames: int = 12) -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    sheet = output / "contact_sheet.jpg"
    # Select evenly spaced frames by frame count approximation; works for MVP and avoids duration math.
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"select='not(mod(n,30))',scale=240:-1,tile=3x4",
        "-frames:v",
        "1",
        str(sheet),
    ]
    subprocess.run(cmd, text=True, capture_output=True, check=True)
    return sheet
