#!/usr/bin/env python
"""Ensure reusable Chrome CDP pages exist without opening duplicates.

Beauty profile helper for cron/manual runs:
- starts Chrome CDP with the reusable project profile if port is not listening;
- reuses an existing Bilibili/Douyin tab when present;
- optionally closes duplicate tabs for the same site;
- pauses Douyin videos after opening/focusing/navigating.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

try:
    import websocket  # type: ignore
except Exception as exc:  # pragma: no cover
    websocket = None
    WEBSOCKET_IMPORT_ERROR = exc
else:
    WEBSOCKET_IMPORT_ERROR = None

PROJECT_ROOT = Path("C:/Project/Beauty-Video-Transport")
CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE_DIR = Path("C:/Project/Chrome/chrome_profile")
DEFAULT_PAGES = {
    "bilibili": "https://www.bilibili.com/",
    "douyin": "https://www.douyin.com/jingxuan",
}


def cdp_url(port: int, path: str) -> str:
    return f"http://127.0.0.1:{port}{path}"


def request_json(url: str, *, method: str = "GET", timeout: float = 5.0) -> Any:
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw) if raw.strip() else None


def is_cdp_alive(port: int) -> bool:
    try:
        request_json(cdp_url(port, "/json/version"), timeout=2.0)
        return True
    except Exception:
        return False


def start_chrome(port: int, start_url: str) -> None:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [
            CHROME_EXE,
            f"--remote-debugging-port={port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={PROFILE_DIR.as_posix()}",
            "--restore-last-session",
            start_url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if is_cdp_alive(port):
            return
        time.sleep(0.5)
    raise RuntimeError(f"Chrome CDP did not become ready on 127.0.0.1:{port}")


def get_pages(port: int) -> list[dict[str, Any]]:
    tabs = request_json(cdp_url(port, "/json/list"), timeout=5.0)
    return [t for t in tabs if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]


def site_key_for_url(url: str) -> str | None:
    host = urllib.parse.urlparse(url).netloc.lower()
    if "bilibili.com" in host:
        return "bilibili"
    if "douyin.com" in host:
        return "douyin"
    return None


def open_new_page(port: int, url: str) -> dict[str, Any]:
    encoded = urllib.parse.quote(url, safe=":/?&=%#")
    return request_json(cdp_url(port, f"/json/new?{encoded}"), method="PUT", timeout=5.0)


def activate_page(port: int, tab_id: str) -> None:
    try:
        request_json(cdp_url(port, f"/json/activate/{tab_id}"), timeout=3.0)
    except Exception:
        pass


def close_page(port: int, tab_id: str) -> None:
    try:
        request_json(cdp_url(port, f"/json/close/{tab_id}"), timeout=3.0)
    except Exception:
        pass


class CDP:
    def __init__(self, ws_url: str) -> None:
        if websocket is None:
            raise RuntimeError(f"websocket-client unavailable: {WEBSOCKET_IMPORT_ERROR!r}")
        self.ws = websocket.create_connection(ws_url, timeout=5)
        self.next_id = 0

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.next_id += 1
        msg = {"id": self.next_id, "method": method}
        if params is not None:
            msg["params"] = params
        self.ws.send(json.dumps(msg))
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            reply = json.loads(self.ws.recv())
            if reply.get("id") == self.next_id:
                return reply
        raise TimeoutError(method)

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass


def eval_js(tab: dict[str, Any], expression: str, *, await_promise: bool = False) -> Any:
    cdp = CDP(tab["webSocketDebuggerUrl"])
    try:
        cdp.call("Runtime.enable")
        reply = cdp.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": await_promise,
                "returnByValue": True,
                "timeout": 10000,
            },
        )
        return reply.get("result", {}).get("result", {}).get("value")
    finally:
        cdp.close()


def navigate(tab: dict[str, Any], url: str) -> None:
    cdp = CDP(tab["webSocketDebuggerUrl"])
    try:
        cdp.call("Page.enable")
        cdp.call("Page.navigate", {"url": url})
    finally:
        cdp.close()


def pause_douyin(tab: dict[str, Any], seconds: float = 6.0) -> Any:
    # Install a short-lived pause loop because Douyin may autoplay after load or after focus.
    js = f"""
(() => {{
  const end = Date.now() + {int(seconds * 1000)};
  let ticks = 0;
  function pauseAll() {{
    ticks += 1;
    for (const v of Array.from(document.querySelectorAll('video'))) {{
      try {{ v.pause(); v.muted = true; }} catch (e) {{}}
    }}
    if (Date.now() < end) setTimeout(pauseAll, 500);
  }}
  pauseAll();
  return {{videos: document.querySelectorAll('video').length, ticks}};
}})()
"""
    return eval_js(tab, js, await_promise=False)


def choose_tab(tabs: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    candidates = [t for t in tabs if site_key_for_url(t.get("url", "")) == key]
    if not candidates:
        return None
    # Prefer the canonical/current desired URL, otherwise keep the first existing site tab.
    canonical = DEFAULT_PAGES[key]
    for tab in candidates:
        if tab.get("url", "").rstrip("/") == canonical.rstrip("/"):
            return tab
    return candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9222)
    parser.add_argument("--bilibili-url", default=DEFAULT_PAGES["bilibili"])
    parser.add_argument("--douyin-url", default=DEFAULT_PAGES["douyin"])
    parser.add_argument("--keep-duplicates", action="store_true", help="Do not close extra Bilibili/Douyin tabs")
    parser.add_argument("--no-navigate", action="store_true", help="Do not navigate existing site tabs to canonical URLs")
    args = parser.parse_args()

    DEFAULT_PAGES["bilibili"] = args.bilibili_url
    DEFAULT_PAGES["douyin"] = args.douyin_url

    if not is_cdp_alive(args.port):
        start_chrome(args.port, args.douyin_url)

    pages = get_pages(args.port)
    kept: dict[str, dict[str, Any]] = {}
    opened: list[str] = []
    reused: list[str] = []
    navigated: list[str] = []

    for key, url in DEFAULT_PAGES.items():
        tab = choose_tab(pages, key)
        if tab is None:
            tab = open_new_page(args.port, url)
            opened.append(key)
            time.sleep(1.0)
        else:
            reused.append(key)
            activate_page(args.port, tab["id"])
            if not args.no_navigate and tab.get("url", "").rstrip("/") != url.rstrip("/"):
                navigate(tab, url)
                navigated.append(key)
                time.sleep(1.5)
        kept[key] = tab
        pages = get_pages(args.port)

    # Refresh websocket URLs after any navigation/open.
    pages = get_pages(args.port)
    for key in list(kept):
        chosen = choose_tab(pages, key)
        if chosen:
            kept[key] = chosen

    if not args.keep_duplicates:
        keep_ids = {tab["id"] for tab in kept.values() if tab.get("id")}
        closed = []
        for tab in pages:
            key = site_key_for_url(tab.get("url", ""))
            if key in DEFAULT_PAGES and tab.get("id") not in keep_ids:
                close_page(args.port, tab["id"])
                closed.append({"site": key, "url": tab.get("url", "")})
        if closed:
            time.sleep(0.5)
    else:
        closed = []

    # Pause Douyin after final focus/open/navigate and again after a short wait.
    pause_result = None
    if "douyin" in kept:
        activate_page(args.port, kept["douyin"]["id"])
        time.sleep(0.5)
        pause_result = pause_douyin(kept["douyin"], seconds=8.0)

    final_pages = get_pages(args.port)
    summary = {
        "port": args.port,
        "profile_dir": PROFILE_DIR.as_posix(),
        "opened": opened,
        "reused": reused,
        "navigated": navigated,
        "closed_duplicates": closed,
        "douyin_pause_result": pause_result,
        "site_tabs": [
            {"site": site_key_for_url(t.get("url", "")), "title": t.get("title", ""), "url": t.get("url", "")}
            for t in final_pages
            if site_key_for_url(t.get("url", ""))
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
