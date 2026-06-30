from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'youtube-upload'))
from googleapiclient.errors import HttpError  # type: ignore
from youtube_upload import build_youtube  # type: ignore

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('video_id'); ap.add_argument('--profile', default='default')
    a=ap.parse_args(); y=build_youtube(a.profile)
    try:
        y.videos().delete(id=a.video_id).execute()
        print(json.dumps({'deleted': a.video_id, 'profile': a.profile}, ensure_ascii=False, indent=2))
        return 0
    except HttpError as e:
        payload=getattr(e,'content',b'').decode('utf-8','ignore')
        print(json.dumps({'error':'HttpError','status':getattr(e.resp,'status',None),'content':payload}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
if __name__=='__main__': raise SystemExit(main())
