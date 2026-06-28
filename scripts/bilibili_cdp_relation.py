#!/usr/bin/env python
"""Check/control a Bilibili video page through an already-running Chrome CDP session.

This is intended for the user's normal, logged-in Chrome, e.g. one started with
`--remote-debugging-port=9222`. It does not read or print cookie values; it runs
Bilibili API checks inside the existing browser tab so the tab's login state is
used.

Examples:
  python scripts/bilibili_cdp_relation.py BV1WgEk63EKa
  python scripts/bilibili_cdp_relation.py https://www.bilibili.com/video/BV1WgEk63EKa/ --port 9222
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
import urllib.error
import urllib.request
from itertools import count
from typing import Any

try:
    import websockets
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Missing dependency: websockets. Install with: python -m pip install websockets") from exc


def extract_bvid(value: str) -> str:
    match = re.search(r"BV[0-9A-Za-z]+", value)
    if not match:
        raise SystemExit(f"Could not find BVID in: {value}")
    return match.group(0)


def cdp_json(port: int, path: str) -> Any:
    url = f"http://127.0.0.1:{port}{path}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"Cannot connect to Chrome CDP at {url}. Start/use Chrome with --remote-debugging-port={port}."
        ) from exc


def choose_bilibili_page(tabs: list[dict[str, Any]]) -> dict[str, Any] | None:
    pages = [t for t in tabs if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
    for tab in pages:
        if "bilibili.com" in tab.get("url", ""):
            return tab
    return pages[0] if pages else None


async def run_cdp(ws_url: str, bvid: str, navigate: bool, wait_seconds: float) -> dict[str, Any]:
    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        ids = count(1)

        async def send(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            msg_id = next(ids)
            await ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
            while True:
                raw = await ws.recv()
                msg = json.loads(raw)
                if msg.get("id") == msg_id:
                    return msg

        async def eval_js(expression: str, await_promise: bool = True) -> Any:
            response = await send(
                "Runtime.evaluate",
                {
                    "expression": expression,
                    "awaitPromise": await_promise,
                    "returnByValue": True,
                },
            )
            if "exceptionDetails" in response.get("result", {}):
                raise RuntimeError(json.dumps(response["result"]["exceptionDetails"], ensure_ascii=False))
            result = response.get("result", {}).get("result", {})
            if "value" in result:
                return result["value"]
            return result

        await send("Page.enable")
        await send("Runtime.enable")

        target_url = f"https://www.bilibili.com/video/{bvid}/"
        if navigate:
            await send("Page.navigate", {"url": target_url})
            deadline = time.monotonic() + wait_seconds
            while time.monotonic() < deadline:
                current = await eval_js("location.href", await_promise=False)
                ready = await eval_js("document.readyState", await_promise=False)
                if bvid in str(current) and ready in {"interactive", "complete"}:
                    break
                await asyncio.sleep(0.5)

        relation_text = await eval_js(
            "fetch('https://api.bilibili.com/x/web-interface/archive/relation?bvid="
            + bvid
            + "',{credentials:'include'}).then(r=>r.text())"
        )
        relation = json.loads(relation_text)

        nav_text = await eval_js(
            "fetch('https://api.bilibili.com/x/web-interface/nav',{credentials:'include'}).then(r=>r.text()).catch(e=>JSON.stringify({code:-999,message:String(e)}))"
        )
        nav = json.loads(nav_text)

        page_state_json = await eval_js(
            "JSON.stringify({title:document.title,url:location.href,"
            "likeClass:document.querySelector('.video-like')?.className||'',"
            "coinClass:document.querySelector('.video-coin')?.className||'',"
            "favClass:document.querySelector('.video-fav')?.className||'',"
            "toolbar:document.querySelector('.video-toolbar-container')?.innerText||''})"
        )
        page_state = json.loads(page_state_json)

        data = relation.get("data") or {}
        return {
            "bvid": bvid,
            "page": page_state,
            "login": {
                "isLogin": bool((nav.get("data") or {}).get("isLogin")),
                "uname": (nav.get("data") or {}).get("uname"),
                "mid": (nav.get("data") or {}).get("mid"),
            },
            "relation": {
                "like": data.get("like"),
                "coin": data.get("coin"),
                "favorite": data.get("favorite"),
                "attention": data.get("attention"),
                "dislike": data.get("dislike"),
                "season_fav": data.get("season_fav"),
            },
            "raw_relation_code": relation.get("code"),
            "raw_relation_message": relation.get("message"),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Use existing Chrome CDP login state to inspect Bilibili video relation")
    parser.add_argument("bvid_or_url", help="Bilibili BVID or URL")
    parser.add_argument("--port", type=int, default=9222, help="Chrome remote debugging port; default 9222")
    parser.add_argument("--no-navigate", action="store_true", help="Do not navigate the chosen tab to the video page")
    parser.add_argument("--wait", type=float, default=15.0, help="Max seconds to wait after navigation; default 15")
    args = parser.parse_args()

    bvid = extract_bvid(args.bvid_or_url)
    tabs = cdp_json(args.port, "/json")
    tab = choose_bilibili_page(tabs)
    if not tab:
        raise SystemExit("No controllable Chrome page found in CDP tab list")

    result = asyncio.run(run_cdp(tab["webSocketDebuggerUrl"], bvid, not args.no_navigate, args.wait))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
