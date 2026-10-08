"""Shared approved caption edge and source-annotation review contract (no fixed point quota)."""
from __future__ import annotations
import json,math
from pathlib import Path

STYLE='paper-tear-and-semantic-reframe-v1'
POINTS='0,11 50,2.64 110,9.46 160,1.54 210,8.36 280,3.08 350,11.66 410,4.84 490,1.1 550,9.24 620,3.74 690,11.44 770,1.54 840,9.46 910,4.18 960,9.68 1000,1.98 1000,22 0,22'
CSS='''
/* The edge is an actual SVG child so subtitle layers retain it across renderers. */
.caption-band{background:#171815;overflow:visible}
.caption-band::before{display:none}
.slv-caption-tear{position:absolute;left:0;top:-17px;width:100%;height:22px;display:block;fill:#171815;pointer-events:none}
.slv-progress-track{display:block;position:relative;width:120px;height:6px;background:#c6c0b0;overflow:hidden}
.slv-progress-track span{display:block;height:100%;background:#171815}
.process-page{position:absolute;left:0;right:0;bottom:0;display:flex;gap:38px;align-items:center}
'''
def caption_band(narration=False):
    cls='caption-band narration-band' if narration else 'caption-band'
    return f'<div class="{cls}" data-slv-component="torn-caption-band-v1" data-layout-ignore><svg class="slv-caption-tear" viewBox="0 0 1000 22" preserveAspectRatio="none" aria-hidden="true"><polygon points="{POINTS}"/></svg></div>'

def finite(value,name):
    if type(value) not in (int,float) or not math.isfinite(value):raise ValueError(f'{name}: expected a finite number')
    return float(value)
def text(value,name):
    if not isinstance(value,str) or not value.strip() or value.strip().lower() in ('todo','tbd','pending','待補','待確認'):
        raise ValueError(f'{name}: provide source-grounded review evidence')
    return value

def review_markers(root,items):
    root=Path(root);data=json.loads((root/'markers.json').read_text(encoding='utf-8-sig'))
    markers=data.get('markers',[]);reviews=data.get('review',[])
    source={i['id']:i for i in items if i['kind']=='source'}
    by_item={k:[] for k in source};ids=set();proofs=[]
    for m in markers:
        mid=text(m.get('id'),'marker.id')
        if mid in ids:raise ValueError(f'Duplicate marker: {mid}')
        ids.add(mid)
        if m.get('item') not in source:raise ValueError(f'{mid}: marker must reference a source item')
        it=source[m['item']];a=finite(m.get('start'),mid+'.start');b=finite(m.get('end'),mid+'.end')
        if not it['source_start']<=a<b<=it['source_end']-.7+.001:raise ValueError(f'{mid}: keep marker inside source range and leave 0.7s for return animation')
        text(m.get('eyebrow'),mid+'.eyebrow')
        if not m.get('steps'):raise ValueError(f'{mid}: annotate actual source points; an empty card is invalid')
        previous=None
        for step in m['steps']:
            at=finite(step.get('at'),mid+'.step.at');text(step.get('text'),mid+'.step.text')
            if not a<=at<b-.6 or (previous is not None and at<=previous):raise ValueError(f'{mid}: reveal points in spoken order with visible hold time; do not reveal all at once')
            previous=at
        by_item[it['id']].append(m)
        local=a-it['source_start'];end=b-it['source_start'];origin=it['start']
        proofs.append(dict(marker=mid,item=it['id'],points=len(m['steps']),source_range=[a,b],times=dict(before=max(origin,origin+local-.55),entry_mid=origin+max(0,local-.45)+.35,settled=origin+local+1.0,steps=[origin+s['at']-it['source_start']+.7 for s in m['steps']],exit=origin+end-.2,restored=origin+end+.7),expected=dict(full_scale=1,reframe_scale=.66,x=625,y=64,card_overlap_px=49,source_audio_rate=1)))
    reviewed={}
    for r in reviews:
        rid=r.get('item')
        if rid not in source or rid in reviewed:raise ValueError('Review each source item exactly once')
        text(r.get('reason'),rid+'.reason');text(r.get('source_evidence'),rid+'.source_evidence')
        actual={m['id'] for m in by_item[rid]};listed=r.get('marker_ids')
        if not isinstance(listed,list) or len(listed)!=len(set(listed)) or set(listed)!=actual:raise ValueError(f'{rid}: reviewed marker_ids must match the authored markers')
        if r.get('decision')=='annotate' and not actual:raise ValueError(f'{rid}: important points were selected but no marker animation was authored')
        if r.get('decision')=='keep_source' and actual:raise ValueError(f'{rid}: decision contradicts authored markers')
        if r.get('decision') not in ('annotate','keep_source'):raise ValueError(f'{rid}: choose annotate or keep_source after reviewing content')
        reviewed[rid]=r
    if set(reviewed)!=set(source):raise ValueError('Missing source-annotation review. Read each selected answer, author semantic markers or record why its existing visuals suffice.')
    for rid,own in by_item.items():
        ordered=sorted(own,key=lambda m:m['start'])
        for a,b in zip(ordered,ordered[1:]):
            if a['end']+.7>b['start']-.45:raise ValueError(f'{rid}: note return overlaps next reframe; merge related notes or adjust source timing')
    return dict(style=STYLE,source_items_reviewed=len(reviewed),markers=len(markers),points=sum(len(m['steps']) for m in markers),proofs=proofs,review=reviews,visual_acceptance=False,note='Authored timing/review contract; inspect actual rendered edge, reframe, sequential points, restoration and source faces.')
