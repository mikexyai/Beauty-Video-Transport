#!/usr/bin/env python
"""YouTube Data API OAuth helper for local upload workflow.

Commands:
  python youtube_oauth.py check
  python youtube_oauth.py check --profile channel2
  python youtube_oauth.py auth-url --client-secret path/to/client_secret.json
  python youtube_oauth.py auth-url --profile channel2 --client-secret path/to/client_secret.json
  python youtube_oauth.py exchange "http://localhost:.../?code=..."
  python youtube_oauth.py exchange --profile channel2 "http://localhost:.../?code=..."
  python youtube_oauth.py revoke
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
CLIENT_SECRET_PATH = CONFIG_DIR / "client_secret.json"
TOKEN_PATH = CONFIG_DIR / "youtube_token.json"
PENDING_PATH = CONFIG_DIR / "oauth_pending.json"
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
REDIRECT_URI = "http://localhost:8080/"


def ensure_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)


def profile_path(profile: str, kind: str) -> Path:
    if profile == "default":
        return TOKEN_PATH if kind == "token" else PENDING_PATH
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in profile).strip("._-")
    if not safe:
        raise ValueError("profile must contain at least one letter, number, dot, dash, or underscore")
    suffix = "token" if kind == "token" else "pending"
    return TOKENS_DIR / f"{safe}_{suffix}.json"


def load_credentials(profile: str = "default") -> Credentials | None:
    token_path = profile_path(profile, "token")
    if not token_path.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def cmd_check(args: argparse.Namespace) -> int:
    ensure_dirs()
    token_path = profile_path(args.profile, "token")
    result = {
        "client_secret_exists": CLIENT_SECRET_PATH.exists(),
        "profile": args.profile,
        "token_file": str(token_path),
        "token_exists": token_path.exists(),
        "authenticated": False,
        "token_valid": False,
        "scopes": SCOPES,
        "config_dir": str(CONFIG_DIR),
    }
    try:
        creds = load_credentials(args.profile)
        if creds:
            result["authenticated"] = bool(creds.valid or (creds.expired and creds.refresh_token))
            result["token_valid"] = bool(creds.valid)
            result["token_scopes"] = list(creds.scopes or [])
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("authenticated") else 1


def cmd_auth_url(args: argparse.Namespace) -> int:
    ensure_dirs()
    src = Path(args.client_secret).expanduser().resolve()
    if not src.exists():
        print(json.dumps({"error": f"client_secret not found: {src}"}, ensure_ascii=False), file=sys.stderr)
        return 2
    CLIENT_SECRET_PATH.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    flow = Flow.from_client_secrets_file(
        str(CLIENT_SECRET_PATH),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        autogenerate_code_verifier=True,
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    pending_path = profile_path(args.profile, "pending")
    pending_path.write_text(json.dumps({
        "state": state,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": flow.code_verifier,
        "profile": args.profile,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "profile": args.profile,
        "auth_url": auth_url,
        "redirect_uri": REDIRECT_URI,
        "pending_file": str(pending_path),
        "instructions": "Open auth_url, approve access, then copy the full redirected URL from the address bar and run exchange. If localhost fails to load after approval, copy that failed localhost URL."
    }, ensure_ascii=False, indent=2))
    return 0


def extract_code(value: str) -> str:
    value = value.strip().strip('"').strip("'")
    if value.startswith("http://") or value.startswith("https://"):
        qs = parse_qs(urlparse(value).query)
        if "code" in qs and qs["code"]:
            return qs["code"][0]
        raise ValueError("URL does not contain code= parameter")
    return value


def cmd_exchange(args: argparse.Namespace) -> int:
    ensure_dirs()
    if not CLIENT_SECRET_PATH.exists():
        print(json.dumps({"error": f"missing client secret: {CLIENT_SECRET_PATH}"}, ensure_ascii=False), file=sys.stderr)
        return 2
    pending_path = profile_path(args.profile, "pending")
    token_path = profile_path(args.profile, "token")
    if not pending_path.exists():
        print(json.dumps({"error": f"missing pending oauth state: {pending_path}; run auth-url first"}, ensure_ascii=False), file=sys.stderr)
        return 2
    pending = json.loads(pending_path.read_text(encoding="utf-8"))
    code = extract_code(args.code_or_url)
    flow = Flow.from_client_secrets_file(
        str(CLIENT_SECRET_PATH),
        scopes=SCOPES,
        state=pending.get("state"),
        redirect_uri=pending.get("redirect_uri", REDIRECT_URI),
        code_verifier=pending.get("code_verifier"),
        autogenerate_code_verifier=False,
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    token_path.write_text(creds.to_json(), encoding="utf-8")
    try:
        pending_path.unlink()
    except FileNotFoundError:
        pass
    print(json.dumps({
        "status": "authenticated",
        "profile": args.profile,
        "token_file": str(token_path),
        "scopes": list(creds.scopes or SCOPES),
        "has_refresh_token": bool(creds.refresh_token),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_revoke(args: argparse.Namespace) -> int:
    ensure_dirs()
    removed = []
    for p in [profile_path(args.profile, "token"), profile_path(args.profile, "pending")]:
        if p.exists():
            p.unlink()
            removed.append(str(p))
    print(json.dumps({"removed": removed}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="YouTube OAuth helper")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check")
    p.add_argument("--profile", default="default", help="Token profile name; default uses config/youtube_token.json")
    p.set_defaults(func=cmd_check)
    p = sub.add_parser("auth-url")
    p.add_argument("--profile", default="default", help="Token profile name; use one profile per YouTube channel")
    p.add_argument("--client-secret", required=True, help="Downloaded OAuth Desktop client JSON")
    p.set_defaults(func=cmd_auth_url)
    p = sub.add_parser("exchange")
    p.add_argument("--profile", default="default", help="Token profile name used with auth-url")
    p.add_argument("code_or_url", help="Full redirected URL or bare code")
    p.set_defaults(func=cmd_exchange)
    p = sub.add_parser("revoke")
    p.add_argument("--profile", default="default", help="Token profile name to remove")
    p.set_defaults(func=cmd_revoke)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
