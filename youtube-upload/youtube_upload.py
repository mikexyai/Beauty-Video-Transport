#!/usr/bin/env python
"""Upload a local video to YouTube with YouTube Data API v3.

Safe commands:
  python youtube_upload.py check-auth
  python youtube_upload.py check-auth --profile channel2
  python youtube_upload.py list-channels --profile channel2
  python youtube_upload.py dry-run --file path.mp4 --title "Title"

Side-effect command (uploads to YouTube):
  python youtube_upload.py upload --file path.mp4 --title "Title" --description "..." --privacyStatus private
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
TOKEN_PATH = CONFIG_DIR / "youtube_token.json"
TOKENS_DIR = CONFIG_DIR / "tokens"
SCOPES = [
    # Broad YouTube channel-management scopes requested by the user.
    # youtube.force-ssl covers authenticated read/write/delete operations over SSL.
    # youtube covers broad YouTube account management. Keep upload/readonly explicit for clarity.
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def profile_path(profile: str) -> Path:
    if profile == "default":
        return TOKEN_PATH
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in profile).strip("._-")
    if not safe:
        raise SystemExit("profile must contain at least one letter, number, dot, dash, or underscore")
    return TOKENS_DIR / f"{safe}_token.json"


def load_credentials(profile: str = "default") -> Credentials:
    token_path = profile_path(profile)
    if not token_path.exists():
        raise SystemExit(f"Not authenticated for profile '{profile}'. Run: python youtube_oauth.py auth-url --profile {profile} --client-secret <client_secret.json>")
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")
    if not creds.valid:
        raise SystemExit(f"Stored YouTube OAuth token is invalid for profile '{profile}'. Re-run youtube_oauth.py auth-url/exchange.")
    return creds


def build_metadata(args: argparse.Namespace) -> dict:
    snippet = {
        "title": args.title,
        "description": args.description or "",
        "categoryId": args.categoryId,
    }
    if args.tags:
        snippet["tags"] = [t.strip() for t in args.tags.split(",") if t.strip()]
    status = {
        "privacyStatus": args.privacyStatus,
        "selfDeclaredMadeForKids": bool(args.madeForKids),
    }
    if args.publishAt:
        # Requires privacyStatus=private per YouTube API semantics.
        status["publishAt"] = args.publishAt
    return {"snippet": snippet, "status": status}


def validate_file(path_str: str) -> Path:
    path = Path(path_str).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"Video file not found: {path}")
    if not path.is_file():
        raise SystemExit(f"Not a file: {path}")
    if path.stat().st_size <= 0:
        raise SystemExit(f"Video file is empty: {path}")
    return path


def build_youtube(profile: str):
    return build("youtube", "v3", credentials=load_credentials(profile))


def cmd_check_auth(args: argparse.Namespace) -> int:
    creds = load_credentials(args.profile)
    print(json.dumps({
        "authenticated": True,
        "profile": args.profile,
        "token_file": str(profile_path(args.profile)),
        "scopes": list(creds.scopes or SCOPES),
        "expired": bool(creds.expired),
        "valid": bool(creds.valid),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_list_channels(args: argparse.Namespace) -> int:
    youtube = build_youtube(args.profile)
    try:
        response = youtube.channels().list(part="id,snippet,contentDetails", mine=True, maxResults=50).execute()
    except HttpError as e:
        payload = getattr(e, "content", b"").decode("utf-8", "ignore")
        print(json.dumps({"error": "HttpError", "status": e.resp.status, "content": payload}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    items = response.get("items", [])
    print(json.dumps({
        "profile": args.profile,
        "count": len(items),
        "channels": [
            {
                "id": item.get("id"),
                "title": item.get("snippet", {}).get("title"),
                "customUrl": item.get("snippet", {}).get("customUrl"),
                "uploadsPlaylistId": item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads"),
            }
            for item in items
        ],
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_dry_run(args: argparse.Namespace) -> int:
    video = validate_file(args.file)
    metadata = build_metadata(args)
    mime_type = mimetypes.guess_type(video.name)[0] or "video/*"
    print(json.dumps({
        "mode": "dry-run",
        "profile": args.profile,
        "would_upload": str(video),
        "size_bytes": video.stat().st_size,
        "mime_type": mime_type,
        "part": "snippet,status",
        "metadata": metadata,
        "note": "No upload performed. Run the upload subcommand only after explicit user approval.",
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_upload(args: argparse.Namespace) -> int:
    video = validate_file(args.file)
    youtube = build_youtube(args.profile)
    body = build_metadata(args)
    mime_type = mimetypes.guess_type(video.name)[0] or "video/*"
    media = MediaFileUpload(str(video), mimetype=mime_type, chunksize=args.chunksize, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    try:
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(json.dumps({"progress": round(status.progress() * 100, 2)}, ensure_ascii=False), flush=True)
    except HttpError as e:
        payload = getattr(e, "content", b"").decode("utf-8", "ignore")
        print(json.dumps({"error": "HttpError", "status": e.resp.status, "content": payload}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    result = {
        "status": "uploaded",
        "profile": args.profile,
        "video_id": response.get("id"),
        "url": f"https://www.youtube.com/watch?v={response.get('id')}",
        "privacyStatus": body["status"]["privacyStatus"],
        "title": body["snippet"]["title"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def add_profile_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument("--profile", default="default", help="Token profile name; default uses config/youtube_token.json")


def add_video_args(p: argparse.ArgumentParser) -> None:
    add_profile_arg(p)
    p.add_argument("--file", required=True, help="Local video file to upload")
    p.add_argument("--title", required=True, help="YouTube video title")
    p.add_argument("--description", default="", help="YouTube video description")
    p.add_argument("--tags", default="", help="Comma-separated tags")
    p.add_argument("--categoryId", default="22", help="YouTube category ID; 22 = People & Blogs")
    p.add_argument("--privacyStatus", default="private", choices=["private", "unlisted", "public"], help="Initial privacy status")
    p.add_argument("--madeForKids", action="store_true", help="Mark as made for kids")
    p.add_argument("--publishAt", default="", help="RFC3339 scheduled publish time; requires privacyStatus=private")


def main() -> int:
    parser = argparse.ArgumentParser(description="YouTube Data API uploader")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check-auth")
    add_profile_arg(p)
    p.set_defaults(func=cmd_check_auth)
    p = sub.add_parser("list-channels")
    add_profile_arg(p)
    p.set_defaults(func=cmd_list_channels)
    p = sub.add_parser("dry-run")
    add_video_args(p)
    p.set_defaults(func=cmd_dry_run)
    p = sub.add_parser("upload")
    add_video_args(p)
    p.add_argument("--chunksize", type=int, default=8 * 1024 * 1024, help="Resumable upload chunk size")
    p.set_defaults(func=cmd_upload)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
