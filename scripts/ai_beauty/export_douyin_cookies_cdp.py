from __future__ import annotations

import argparse
import json
import time
import urllib.request
from http.cookiejar import Cookie, MozillaCookieJar
from pathlib import Path
from typing import Any

import websocket

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COOKIE_PATH = PROJECT_ROOT / "config" / "douyin_ai_beauty_cookies.txt"
CDP_JSON = "http://127.0.0.1:9222/json/list"


def cdp_call(ws, method: str, params: dict[str, Any] | None = None, *, msg_id: int) -> Any:
    ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == msg_id:
            if "error" in msg:
                raise RuntimeError(f"CDP {method} error: {msg['error']}")
            return msg.get("result")


def find_douyin_target() -> dict[str, Any]:
    data = urllib.request.urlopen(CDP_JSON, timeout=5).read().decode("utf-8", "ignore")
    targets = json.loads(data)
    pages = [t for t in targets if t.get("type") == "page" and "douyin.com" in (t.get("url") or "")]
    if not pages:
        raise RuntimeError("No open Douyin page found in Chrome CDP on 127.0.0.1:9222")
    return pages[0]


def chrome_cookie_to_netscape(c: dict[str, Any]) -> Cookie:
    domain = c.get("domain") or ".douyin.com"
    return Cookie(
        version=0,
        name=c["name"],
        value=c.get("value", ""),
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=True,
        domain_initial_dot=domain.startswith("."),
        path=c.get("path") or "/",
        path_specified=True,
        secure=bool(c.get("secure")),
        expires=int(c["expires"]) if c.get("expires") and c.get("expires") > 0 else None,
        discard=not bool(c.get("expires") and c.get("expires") > 0),
        comment=None,
        comment_url=None,
        rest={"HttpOnly": None} if c.get("httpOnly") else {},
        rfc2109=False,
    )


def export_cookies(cookie_path: Path = DEFAULT_COOKIE_PATH) -> dict[str, Any]:
    target = find_douyin_target()
    ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=10, suppress_origin=True)
    try:
        cdp_call(ws, "Page.bringToFront", msg_id=1)
        # Let the already-open page settle; do not click/type/navigate.
        time.sleep(0.5)
        result = cdp_call(ws, "Network.getCookies", {"urls": ["https://www.douyin.com/"]}, msg_id=2)
    finally:
        ws.close()
    cookies = result.get("cookies", [])
    douyin = [c for c in cookies if "douyin.com" in (c.get("domain") or "")]
    if not douyin:
        raise RuntimeError("CDP returned no douyin.com cookies")
    cookie_path.parent.mkdir(parents=True, exist_ok=True)
    jar = MozillaCookieJar(str(cookie_path))
    for c in douyin:
        jar.set_cookie(chrome_cookie_to_netscape(c))
    jar.save(ignore_discard=True, ignore_expires=True)
    safe_names = sorted(c["name"] for c in douyin)
    return {
        "target_url": target.get("url"),
        "cookie_path": str(cookie_path),
        "cookie_count": len(douyin),
        "cookie_names": safe_names,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Douyin cookies from existing Chrome CDP into AI Beauty cookie jar.")
    parser.add_argument("--output", type=Path, default=DEFAULT_COOKIE_PATH)
    args = parser.parse_args()
    print(json.dumps(export_cookies(args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
