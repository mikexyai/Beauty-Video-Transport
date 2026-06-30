from __future__ import annotations

import argparse
import base64
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Any

import websocket  # type: ignore


def get_pages() -> list[dict[str, Any]]:
    return json.load(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5))


def pick_page(url_contains: str) -> dict[str, Any]:
    pages = [p for p in get_pages() if p.get("type") == "page" and url_contains in p.get("url", "")]
    if not pages:
        raise SystemExit(f"No CDP page URL containing {url_contains!r}")
    return pages[0]


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=180, suppress_origin=True)
        self.n = 0

    def call(self, method: str, params: dict | None = None) -> Any:
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result")

    def eval(self, expr: str, await_promise: bool = True) -> Any:
        return self.call("Runtime.evaluate", {"expression": expr, "awaitPromise": await_promise, "returnByValue": True, "timeout": 120000})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("aweme_id")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    page = pick_page("douyin.com")
    c = CDP(page["webSocketDebuggerUrl"])
    c.call("Page.enable")
    c.call("Runtime.enable")
    target_url = f"https://www.douyin.com/video/{args.aweme_id}"
    c.call("Page.navigate", {"url": target_url})
    time.sleep(6)
    # Pause any autoplaying video.
    c.eval("Array.from(document.querySelectorAll('video')).forEach(v=>v.pause())", await_promise=False)
    expr = r'''
(async (awemeId) => {
  try {
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    for (let i=0; i<20; i++) {
      const vids = Array.from(document.querySelectorAll('video'));
      for (const v of vids) {
        try { v.pause(); } catch(e) {}
        const srcs = [v.currentSrc, v.src, ...(Array.from(v.querySelectorAll('source')).map(s => s.src))].filter(Boolean);
        for (const src of srcs) {
          if (src && src.startsWith('http')) return {kind:'video-element', url:src, href:location.href, title:document.title};
        }
      }
      // Look for SSR/app state containing play_addr URLs.
      const text = document.documentElement.innerHTML;
      const candidates = text.match(/https?:[^\"'<> ]+/g) || [];
      const m = candidates.find(u => (/\.mp4|mime_type=video|video_id=|playwm|play_addr|douyinvod|bytev/i.test(u)) && !/\.js($|[?&])|\.exe|\.png|\.jpg|\.webp|\.css|douyin_pc_client/i.test(u));
      if (m) return {kind:'html-regex', url:m.replaceAll('\\\\u0026','&').replaceAll('\\u0026','&'), href:location.href, title:document.title};
      await sleep(1000);
    }
    return {kind:'not-found', href:location.href, title:document.title, html: document.documentElement.innerText.slice(0,1000)};
  } catch(e) {
    return {kind:'exception', message: String(e && (e.stack || e.message || e)), href: location.href, title: document.title};
  }
})
'''
    res = c.eval(expr + f"({json.dumps(args.aweme_id)})")
    val = res.get("result", {}).get("value")
    if val is None and "exceptionDetails" in res:
        val = {"kind":"cdp-exception", "exceptionDetails": res.get("exceptionDetails")}
    if val is None:
        val = {"kind":"cdp-no-value", "response": res}
    print(json.dumps(val, ensure_ascii=False, indent=2))
    if not val or not val.get("url"):
        return 2
    url = val["url"]
    # Fetch in browser to bypass anti-hotlink/cookies, returning base64.
    fetch_expr = r'''
(async (url) => {
  const r = await fetch(url, {credentials:'include', referrer: location.href});
  const ab = await r.arrayBuffer();
  let binary = '';
  const bytes = new Uint8Array(ab);
  const chunk = 0x8000;
  for (let i=0; i<bytes.length; i+=chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i+chunk));
  }
  return {ok:r.ok, status:r.status, type:r.headers.get('content-type'), length:bytes.length, b64:btoa(binary)};
})
'''
    got = c.eval(fetch_expr + f"({json.dumps(url)})")
    fval = got.get("result", {}).get("value")
    print(json.dumps({k:fval.get(k) for k in fval if k!='b64'}, ensure_ascii=False, indent=2))
    if not fval or not fval.get("ok") or not fval.get("b64"):
        return 3
    Path(args.out).write_bytes(base64.b64decode(fval["b64"]))
    print(f"wrote {args.out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
