from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
CRED_PATH = Path("C:/Project/Setup/postgresql/postgres-credentials.txt")
DB_NAME = "beauty"
TABLE_NAME = "upload_records"


def read_credentials(path: Path = CRED_PATH) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key in {"host", "port", "username", "password"}:
            out[key] = value
    missing = {"host", "port", "username", "password"} - set(out)
    if missing:
        raise SystemExit(f"Missing PostgreSQL credential fields: {sorted(missing)}")
    return out


def connect():
    c = read_credentials()
    return psycopg.connect(
        host=c["host"],
        port=int(c["port"]),
        dbname=DB_NAME,
        user=c["username"],
        password=c["password"],
    )


def list_records(args: argparse.Namespace) -> list[dict]:
    where = []
    params = {}
    if args.platform:
        where.append("source_platform = %(platform)s")
        params["platform"] = args.platform
    if args.profile:
        where.append("youtube_profile = %(profile)s")
        params["profile"] = args.profile
    if args.search:
        where.append("(source_title ILIKE %(search)s OR youtube_title ILIKE %(search)s OR bvid ILIKE %(search)s OR youtube_video_id ILIKE %(search)s)")
        params["search"] = f"%{args.search}%"
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    query = f"""
        SELECT recorded_at, source_platform, bvid, source_title, source_up,
               youtube_profile, youtube_video_id, youtube_url, youtube_title, notes
        FROM {TABLE_NAME}
        {where_sql}
        ORDER BY recorded_at DESC NULLS LAST, id DESC
        LIMIT %(limit)s
    """
    params["limit"] = args.limit
    with connect() as conn:
        cur = conn.execute(query, params)
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def main() -> None:
    p = argparse.ArgumentParser(description="Query Beauty upload records from PostgreSQL database 'beauty'.")
    p.add_argument("--platform", choices=["Bilibili", "Douyin"])
    p.add_argument("--profile", choices=["default", "channelCos", "channelDance"])
    p.add_argument("--search", help="Search source/youtube title, source id, or YouTube video id")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--json", action="store_true", help="Print JSON instead of a compact table")
    args = p.parse_args()
    rows = list_records(args)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))
        return
    for r in rows:
        print(f"{r['recorded_at']} | {r['source_platform']} | {r['bvid']} | {r['youtube_profile']} | {r['youtube_video_id']} | {r['youtube_title']} | {r['youtube_url']}")


if __name__ == "__main__":
    main()
