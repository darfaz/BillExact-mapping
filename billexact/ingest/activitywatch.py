import datetime as dt
from urllib.parse import urlparse
from pathlib import Path
import requests, yaml

AW_BASE = "http://127.0.0.1:5600/api/0"

def _iso(ts):
    if isinstance(ts, str): return ts
    if isinstance(ts, dt.datetime): return ts.replace(microsecond=0).isoformat()
    raise ValueError("start/end must be ISO string or datetime")

def _parse_ts(s):
    if not s: return None
    s=s.replace("Z","+00:00")
    try: return dt.datetime.fromisoformat(s)
    except Exception: return None

def _filters():
    p=Path('billexact/config/filter.yml')
    if p.exists():
        try: return (yaml.safe_load(p.read_text()) or {}).get('filters', {})
        except Exception: return {}
    return {}

F=_filters()
NB_APPS=set([a.lower() for a in F.get('nonbillable_apps',[])])
NB_HOSTS=set([h.lower() for h in F.get('nonbillable_hosts',[])])
NB_WORDS=[w.lower() for w in F.get('nonbillable_title_keywords',[])]
MIN_SECONDS=int(F.get('min_seconds',120))
GAP_MERGE_SECONDS=int(F.get('gap_merge_seconds',300))

def list_buckets():
    try:
        r=requests.get(f"{AW_BASE}/buckets", timeout=5); r.raise_for_status(); data=r.json()
    except Exception: return []
    if isinstance(data, dict):
        out=[]
        for k,v in data.items():
            b=v if isinstance(v,dict) else {}; b=dict(b); b.setdefault('id',k); out.append(b)
        return out
    if isinstance(data, list): return data
    return []

def fetch_events(bucket_id, start_iso, end_iso):
    try:
        r=requests.get(f"{AW_BASE}/buckets/{bucket_id}/events", params={'start':start_iso,'end':end_iso}, timeout=10)
        r.raise_for_status(); return r.json()
    except Exception: return []

def summarize_events(start, end, min_seconds=MIN_SECONDS, gap_merge_seconds=GAP_MERGE_SECONDS):
    start_iso, end_iso = _iso(start), _iso(end)
    buckets=[b.get('id','') for b in list_buckets() if isinstance(b,dict)]
    buckets=[bid for bid in buckets if bid.startswith('aw-watcher-window_')]
    rows=[]
    for bid in buckets:
        for ev in fetch_events(bid, start_iso, end_iso):
            dur=(ev.get('duration') or 0) or 0
            if dur<=0: continue
            ts=_parse_ts(ev.get('timestamp') or '')
            data=ev.get('data') or {}
            title=data.get('title') or data.get('app') or data.get('url') or 'activity'
            app=(data.get('app') or '').strip()
            host=''
            if isinstance(title,str) and title.startswith('http'):
                try:
                    u=urlparse(title); host=(u.netloc or 'web').lower(); title=(u.netloc or 'web')+(u.path or '')
                except Exception: host=''
            rows.append({'start':ts,'end':(ts+dt.timedelta(seconds=dur)) if ts else None,'dur':dur,'title':str(title)[:255],'app':app,'host':host})
    rows=[r for r in rows if r['start'] is not None]
    rows.sort(key=lambda r:r['start'])
    def key_of(r):
        t=r['title'].lower(); a=(r['app'] or '').lower(); h=(r['host'] or '').lower()
        if h: return f'web:{h}'
        if 'word' in a: return f'word:{t}'
        if 'preview' in a or t.endswith('.pdf'): return f'pdf:{t}'
        return f'{a}:{t}' if a else t
    agg=[]
    for r in rows:
        a=(r['app'] or '').lower(); h=(r['host'] or '').lower(); t=r['title'].lower()
        if a in NB_APPS or h in NB_HOSTS or any(k in t for k in NB_WORDS):
            continue
        if r['dur']<min_seconds: continue
        k=key_of(r)
        if agg and agg[-1]['key']==k:
            gap=(r['start']-agg[-1]['end']).total_seconds()
            if gap<=gap_merge_seconds:
                agg[-1]['end']=r['end']; agg[-1]['dur']+=r['dur']; continue
        agg.append({'key':k,'start':r['start'],'end':r['end'],'dur':r['dur'],'title':r['title'],'app':r['app'],'host':r['host']})
    items=[]
    for a in agg:
        date=a['start'].date().isoformat(); desc=a['title']; hours=round(a['dur']/3600.0,4)
        items.append({'date':date,'description':desc,'duration_hours':hours,'app':a['app'],'host':a['host']})
    return items
