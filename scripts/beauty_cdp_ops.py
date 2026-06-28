#!/usr/bin/env python
"""Bilibili favorite operations through an existing logged-in Chrome CDP tab.

Uses the browser's login cookies via Runtime.evaluate(fetch(..., credentials:'include')).
Does not print cookie values.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
import urllib.request
from itertools import count
from typing import Any

import websockets


def cdp_json(port: int, path: str) -> Any:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def choose_page(tabs: list[dict[str, Any]]) -> dict[str, Any]:
    pages = [t for t in tabs if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
    for tab in pages:
        if "bilibili.com" in tab.get("url", ""):
            return tab
    if pages:
        return pages[0]
    raise SystemExit("No controllable Chrome page found")


class CDP:
    def __init__(self, ws):
        self.ws = ws
        self.ids = count(1)

    async def send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        msg_id = next(self.ids)
        await self.ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        while True:
            raw = await self.ws.recv()
            msg = json.loads(raw)
            if msg.get("id") == msg_id:
                return msg

    async def eval(self, expression: str, await_promise: bool = True) -> Any:
        response = await self.send(
            "Runtime.evaluate",
            {"expression": expression, "awaitPromise": await_promise, "returnByValue": True},
        )
        if "exceptionDetails" in response.get("result", {}):
            raise RuntimeError(json.dumps(response["result"]["exceptionDetails"], ensure_ascii=False))
        result = response.get("result", {}).get("result", {})
        return result.get("value", result)

    async def api_get(self, url: str) -> Any:
        js = f"fetch({json.dumps(url)},{{credentials:'include'}}).then(r=>r.text())"
        return json.loads(await self.eval(js))

    async def api_post(self, url: str, data: dict[str, Any]) -> Any:
        js_template = """
        (async()=>{
          const data = __DATA__;
          const body = new URLSearchParams();
          for (const [k,v] of Object.entries(data)) body.append(k, v == null ? '' : String(v));
          const r = await fetch(__URL__, {method:'POST', credentials:'include', headers:{'content-type':'application/x-www-form-urlencoded'}, body});
          return await r.text();
        })()
        """
        js = js_template.replace("__DATA__", json.dumps(data, ensure_ascii=False)).replace("__URL__", json.dumps(url))
        return json.loads(await self.eval(js))

    async def csrf(self) -> str:
        js = r"""
        (()=>{
          const m = document.cookie.match(/(?:^|;\s*)bili_jct=([^;]+)/);
          return m ? decodeURIComponent(m[1]) : '';
        })()
        """
        return await self.eval(js, await_promise=False)

    async def pause(self) -> Any:
        js = r"""
        (()=>{
          const vids=[...document.querySelectorAll('video')];
          for (const v of vids) { try { v.pause(); v.muted = true; } catch(e){} }
          return {paused: vids.map(v=>v.paused), count: vids.length, url: location.href, title: document.title};
        })()
        """
        return await self.eval(js, await_promise=False)

    async def open_and_pause(self, bvid: str, wait_seconds: float = 8.0) -> Any:
        await self.send("Page.navigate", {"url": f"https://www.bilibili.com/video/{bvid}/"})
        deadline = time.monotonic() + wait_seconds
        state = None
        while time.monotonic() < deadline:
            try:
                state = await self.pause()
                if bvid in str(state.get("url", "")) and state.get("count", 0) > 0:
                    break
            except Exception:
                pass
            await asyncio.sleep(0.35)
        # Pause repeatedly to defeat delayed autoplay.
        for _ in range(5):
            try:
                state = await self.pause()
            except Exception:
                pass
            await asyncio.sleep(0.2)
        return state


async def main_async(args: argparse.Namespace) -> int:
    tabs = cdp_json(args.port, "/json")
    tab = choose_page(tabs)
    async with websockets.connect(tab["webSocketDebuggerUrl"], max_size=20_000_000) as ws:
        cdp = CDP(ws)
        await cdp.send("Page.enable")
        await cdp.send("Runtime.enable")
        if "bilibili.com" not in tab.get("url", ""):
            await cdp.send("Page.navigate", {"url": "https://www.bilibili.com/"})
            await asyncio.sleep(2)
        nav = await cdp.api_get("https://api.bilibili.com/x/web-interface/nav")
        mid = (nav.get("data") or {}).get("mid")
        if not mid:
            raise SystemExit(json.dumps({"error":"not_logged_in", "nav": nav}, ensure_ascii=False))
        folders = await cdp.api_get(f"https://api.bilibili.com/x/v3/fav/folder/created/list-all?up_mid={mid}&jsonp=jsonp")
        folder_list = (folders.get("data") or {}).get("list") or []
        by_title = {f.get("title"): f for f in folder_list}
        default_folder = by_title.get("默认收藏夹") or (folder_list[0] if folder_list else None)
        if not default_folder:
            raise SystemExit("No favorite folders returned")

        if args.cmd == "folders":
            print(json.dumps({"login": {"mid": mid, "uname": (nav.get("data") or {}).get("uname")}, "folders": folder_list}, ensure_ascii=False, indent=2))
            return 0

        if args.cmd == "list-default":
            media_id = default_folder.get("id")
            url = f"https://api.bilibili.com/x/v3/fav/resource/list?media_id={media_id}&pn={args.pn}&ps={args.ps}&keyword=&order=mtime&type=0&tid=0&platform=web"
            listing = await cdp.api_get(url)
            print(json.dumps({"login": {"mid": mid, "uname": (nav.get("data") or {}).get("uname")}, "default_folder": default_folder, "listing": listing}, ensure_ascii=False, indent=2))
            return 0

        if args.cmd == "inspect":
            bvid = args.bvid
            state = await cdp.open_and_pause(bvid, args.wait)
            view = await cdp.api_get(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}")
            relation = await cdp.api_get(f"https://api.bilibili.com/x/web-interface/archive/relation?bvid={bvid}")
            print(json.dumps({"pause_state": state, "view": view, "relation": relation}, ensure_ascii=False, indent=2))
            return 0

        if args.cmd == "deal":
            csrf = await cdp.csrf()
            if not csrf:
                raise SystemExit("Could not read Bilibili csrf token from logged-in page")
            target = by_title.get(args.target_folder) if args.target_folder else None
            if args.target_folder and not target:
                raise SystemExit(f"Target folder not found: {args.target_folder}")
            view = await cdp.api_get(f"https://api.bilibili.com/x/web-interface/view?bvid={args.bvid}")
            aid = (view.get("data") or {}).get("aid")
            if not aid:
                raise SystemExit(json.dumps({"error":"no_aid", "view":view}, ensure_ascii=False))
            data = {"rid": aid, "type": 2, "csrf": csrf}
            if args.action == "remove-default":
                data["del_media_ids"] = default_folder.get("id")
            elif args.action == "move":
                data["add_media_ids"] = target.get("id")
                data["del_media_ids"] = default_folder.get("id")
            else:
                raise SystemExit(f"Unknown deal action: {args.action}")
            result = await cdp.api_post("https://api.bilibili.com/x/v3/fav/resource/deal", data)
            print(json.dumps({"action": args.action, "bvid": args.bvid, "aid": aid, "default_folder": default_folder, "target_folder": target, "api_result": result}, ensure_ascii=False, indent=2))
            return 0
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=9222)
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("folders")
    sp = sub.add_parser("list-default")
    sp.add_argument("--pn", type=int, default=1)
    sp.add_argument("--ps", type=int, default=20)
    sp = sub.add_parser("inspect")
    sp.add_argument("bvid")
    sp.add_argument("--wait", type=float, default=8.0)
    sp = sub.add_parser("deal")
    sp.add_argument("action", choices=["remove-default", "move"])
    sp.add_argument("bvid")
    sp.add_argument("--target-folder", default="")
    return asyncio.run(main_async(p.parse_args()))

if __name__ == "__main__":
    raise SystemExit(main())
