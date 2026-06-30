from __future__ import annotations
import argparse, base64, json, time, urllib.request
from pathlib import Path
import websocket  # type: ignore


def page_for(url_part):
    pages=json.load(urllib.request.urlopen('http://127.0.0.1:9222/json', timeout=5))
    matches=[p for p in pages if p.get('type')=='page' and url_part in p.get('url','')]
    if not matches: raise SystemExit(f'No page matching {url_part}')
    return matches[0]

class CDP:
    def __init__(self, ws):
        self.ws=websocket.create_connection(ws, timeout=240, suppress_origin=True); self.n=0
    def call(self,m,params=None):
        self.n+=1; self.ws.send(json.dumps({'id':self.n,'method':m,'params':params or {}}))
        while True:
            msg=json.loads(self.ws.recv())
            if msg.get('id')==self.n: return msg
    def eval(self,expr):
        return self.call('Runtime.evaluate', {'expression':expr,'awaitPromise':True,'returnByValue':True,'timeout':180000})

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('aweme_id'); ap.add_argument('--out',required=True); ap.add_argument('--seconds',type=float,default=59.5)
    a=ap.parse_args()
    p=page_for('douyin.com')
    c=CDP(p['webSocketDebuggerUrl']); c.call('Runtime.enable'); c.call('Page.enable')
    c.call('Page.navigate', {'url':f'https://www.douyin.com/video/{a.aweme_id}'})
    time.sleep(8)
    expr=r'''
(async (seconds) => {
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 let v=null;
 for (let i=0;i<30;i++) {
   const vids=Array.from(document.querySelectorAll('video')).filter(x=>isFinite(x.duration)&&x.duration>1&&x.readyState>=2);
   if (vids.length) { v=vids[0]; break; }
   await sleep(1000);
 }
 if (!v) return {ok:false, error:'no ready video', html:document.body.innerText.slice(0,500)};
 v.pause(); v.currentTime=0; await sleep(1000);
 const stream = v.captureStream ? v.captureStream() : (v.mozCaptureStream ? v.mozCaptureStream() : null);
 if (!stream) return {ok:false, error:'captureStream unavailable'};
 let mime='video/webm;codecs=vp9,opus';
 if (!MediaRecorder.isTypeSupported(mime)) mime='video/webm;codecs=vp8,opus';
 if (!MediaRecorder.isTypeSupported(mime)) mime='video/webm';
 const chunks=[];
 const rec=new MediaRecorder(stream,{mimeType:mime});
 rec.ondataavailable=e=>{ if(e.data&&e.data.size) chunks.push(e.data); };
 const done=new Promise(resolve=>{ rec.onstop=resolve; });
 rec.start(1000);
 await v.play();
 await sleep(Math.round(seconds*1000));
 try { v.pause(); } catch(e) {}
 if (rec.state !== 'inactive') rec.stop();
 await done;
 const blob=new Blob(chunks,{type:mime});
 const buf=await blob.arrayBuffer();
 const bytes=new Uint8Array(buf);
 let binary=''; const step=0x8000;
 for (let i=0;i<bytes.length;i+=step) binary += String.fromCharCode.apply(null, bytes.subarray(i,i+step));
 return {ok:true, mime, size:bytes.length, duration:v.currentTime, b64:btoa(binary)};
})
'''
    res=c.eval(expr+f'({a.seconds})')
    val=res.get('result',{}).get('result',{}).get('value')
    if not val: val={'ok':False,'cdp':res}
    print(json.dumps({k:v for k,v in val.items() if k!='b64'}, ensure_ascii=False, indent=2))
    if not val.get('ok'): return 2
    Path(a.out).write_bytes(base64.b64decode(val['b64']))
    print('wrote', a.out)
    return 0
if __name__=='__main__': raise SystemExit(main())
