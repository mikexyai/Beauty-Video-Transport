from __future__ import annotations

import argparse
import json
import subprocess
import urllib.request
from http.cookiejar import Cookie, MozillaCookieJar
from pathlib import Path

import sys

PROJECT_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_BOOTSTRAP_ROOT))

from scripts.ai_beauty.db import PROJECT_ROOT

COOKIE_PATH = PROJECT_ROOT / "config" / "douyin_ai_beauty_cookies.txt"
CHALLENGE_JS_PATH = PROJECT_ROOT / "analysis" / "douyin_ai_beauty" / "douyin_acrawler_challenge.js"
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def _save_challenge_js(html: str) -> None:
    starts = []
    pos = 0
    while True:
        start = html.find("<script>", pos)
        if start == -1:
            break
        end = html.find("</script>", start)
        if end == -1:
            break
        starts.append((start + len("<script>"), end))
        pos = end + len("</script>")
    if len(starts) < 2:
        raise RuntimeError("Douyin challenge page did not contain expected inline scripts")
    js = "\n".join(html[s:e] for s, e in starts[:2])
    CHALLENGE_JS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHALLENGE_JS_PATH.write_text(js, encoding="utf-8")


def _cookie(name: str, value: str) -> Cookie:
    return Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain=".douyin.com",
        domain_specified=True,
        domain_initial_dot=True,
        path="/",
        path_specified=True,
        secure=True,
        expires=None,
        discard=True,
        comment=None,
        comment_url=None,
        rest={},
        rfc2109=False,
    )


def _sign_with_node(js_path: Path, nonce: str, url: str, user_agent: str = DEFAULT_UA) -> str:
    node_script = f"""
const fs = require('fs');
let js = fs.readFileSync({json.dumps(str(js_path))}, 'utf8');
let first = js.slice(0, js.indexOf('function _f1'));
global.window = global; global.global = global;
global.document = {{cookie: '', referrer: ''}};
global.location = {{protocol: 'https:', href: {json.dumps(url)}, pathname: new URL({json.dumps(url)}).pathname, search: '', host: 'www.douyin.com'}};
global.window.location = global.location;
global.navigator = {{userAgent: {json.dumps(user_agent)}}};
global.history = {{}}; global.Image = function(){{}}; global.PluginArray = function(){{}}; global.indexedDB = {{}};
global.DOMException = function(){{}}; global.Request = function(){{}}; global.Headers = function(){{}};
eval(first);
module.exports.init({{aid: 99999999, dfp: 0}});
console.log(module.exports.sign('', {json.dumps(nonce)}));
"""
    return subprocess.check_output(["node", "-e", node_script], text=True).strip()


def refresh_cookies(url: str, cookie_path: Path = COOKIE_PATH) -> dict:
    cookie_path.parent.mkdir(parents=True, exist_ok=True)
    jar = MozillaCookieJar(str(cookie_path))
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": DEFAULT_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.douyin.com/",
        },
    )
    with opener.open(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", "ignore")
    nonce = next((c.value for c in jar if c.name == "__ac_nonce"), None)
    if not nonce:
        raise RuntimeError("Douyin did not set __ac_nonce")
    _save_challenge_js(html)
    signature = _sign_with_node(CHALLENGE_JS_PATH, nonce, url)
    jar.set_cookie(_cookie("__ac_signature", signature))
    jar.set_cookie(_cookie("__ac_referer", "__ac_blank"))
    jar.save(ignore_discard=True, ignore_expires=True)
    return {"cookie_path": str(cookie_path), "nonce_present": True, "signature_prefix": signature[:18], "cookie_count": len(jar)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh a lightweight Douyin cookie jar without Chrome/CDP.")
    parser.add_argument("--url", default="https://www.douyin.com/")
    args = parser.parse_args()
    print(refresh_cookies(args.url))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
