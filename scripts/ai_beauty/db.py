from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import psycopg

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CRED_PATH = Path("C:/Project/Setup/postgresql/postgres-credentials.txt")
DB_NAME = "beauty"


def read_credentials(path: Path = CRED_PATH) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"PostgreSQL credentials file not found: {path}")
    text = path.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key in {"host", "port", "database", "username", "password"}:
            out[key] = value
    required = {"host", "port", "username", "password"}
    missing = required - set(out)
    if missing:
        raise RuntimeError(f"Missing PostgreSQL credential fields: {sorted(missing)}")
    return out


def connect(dbname: str = DB_NAME, *, autocommit: bool = False) -> psycopg.Connection[Any]:
    c = read_credentials()
    return psycopg.connect(
        host=c["host"],
        port=int(c["port"]),
        dbname=dbname,
        user=c["username"],
        password=c["password"],
        autocommit=autocommit,
    )


def check() -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT current_database(), current_schema(), version()").fetchone()
    return {"database": row[0], "schema": row[1], "version": row[2].splitlines()[0]}


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Beauty PostgreSQL helpers")
    parser.add_argument("--check", action="store_true", help="Check DB connectivity without printing secrets")
    args = parser.parse_args()
    if args.check:
        print(check())
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
