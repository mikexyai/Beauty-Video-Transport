from __future__ import annotations
import argparse, csv
from pathlib import Path
from datetime import datetime, timezone, timedelta

COLUMNS = ['recorded_at','source_platform','source_url','bvid','source_title','source_up','local_download_file','local_output_file','youtube_profile','youtube_channel_title','youtube_channel_handle','youtube_channel_id','youtube_video_id','youtube_url','youtube_title','youtube_privacy_status','notes']

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--csv', default='upload_records.csv'); ap.add_argument('--source-id', required=True); ap.add_argument('--old-id', required=True); ap.add_argument('--new-id', required=True); ap.add_argument('--new-url', required=True); ap.add_argument('--local-output-file', required=True); ap.add_argument('--note', required=True)
    a=ap.parse_args(); p=Path(a.csv)
    rows=list(csv.DictReader(p.open('r',encoding='utf-8-sig',newline='')))
    changed=0
    for r in rows:
        if r.get('bvid')==a.source_id and r.get('youtube_video_id')==a.old_id:
            r['youtube_video_id']=a.new_id; r['youtube_url']=a.new_url; r['local_output_file']=a.local_output_file; r['notes']=a.note; changed+=1
    if changed != 1:
        raise SystemExit(f'Expected 1 row changed, got {changed}')
    tmp=p.with_suffix('.csv.tmp')
    with tmp.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f, fieldnames=COLUMNS, extrasaction='ignore'); w.writeheader(); w.writerows(rows)
    tmp.replace(p)
    print({'updated_rows':changed,'csv':str(p),'old_id':a.old_id,'new_id':a.new_id})
if __name__=='__main__': main()
