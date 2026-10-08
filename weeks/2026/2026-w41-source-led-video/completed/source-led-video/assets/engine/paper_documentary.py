"""Build the deterministic HyperFrames documentary from resolved media and captions.

This is a source-led edit: source audio and sequence come exclusively from plan.
All display text is authored HTML, never text rasterized by an image model.
"""
from __future__ import annotations
import html
import json
from pathlib import Path
import shutil


PROJECT = None
EPISODE = None

def _unbound(*args, **kwargs):
    raise RuntimeError("Use scripts/build_film.py to bind episode-specific scene authoring.")

channel_lockup = opening = question = outro = _unbound

COLORS = {"paper":"#eee9df", "ink":"#171815", "yellow":"#f4db24", "muted":"#595a51"}

def esc(s): return html.escape(str(s), quote=True)
def n(x): return f"{float(x):.6f}".rstrip("0").rstrip(".") or "0"
def dump(p, obj): p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

CSS = """
@font-face{font-family:'Documentary Serif';src:url('../assets/fonts/serif.woff2') format('woff2');font-weight:100 900;font-style:normal}
@font-face{font-family:'Documentary Sans';src:url('../assets/fonts/sans.woff2') format('woff2');font-weight:100 900;font-style:normal}
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden;background:transparent}
#root{position:absolute;inset:0;width:100%;height:100%;overflow:hidden;color:#171815;font-family:'Documentary Sans',sans-serif}
.paper-base{position:absolute;inset:0;background:#eee9df}.paper-base:after{content:'';position:absolute;inset:0;background-image:url('../assets/paper-grain.svg');opacity:.48;pointer-events:none}
.channel-lockup{position:absolute;right:58px;top:38px;z-index:18;display:flex;align-items:center;gap:20px;height:52px;text-align:right;padding:10px 16px;color:#171815;background:#eee9df}
.channel-name{position:relative;top:-1.5px;font-family:'Documentary Serif',serif;font-size:30px;font-weight:900;line-height:32px;white-space:nowrap}
.channel-progress{display:flex;justify-content:flex-end;align-items:center;gap:12px;height:32px;font-size:22px;font-weight:700;line-height:32px;white-space:nowrap}
.question-count{position:relative;top:-2.5px;display:block;height:32px;line-height:32px;font-variant-numeric:tabular-nums}
.question-icon{display:block;width:28px;height:28px;flex:0 0 28px}.question-icon path{stroke:#171815;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round;fill:none}.question-icon circle{fill:#171815}
.progress-nodes{display:flex;align-items:center;gap:8px;height:32px;margin-left:0}.progress-node{width:12px;height:12px;border:2px solid #171815;border-radius:50%;background:transparent}.progress-node.done{background:#171815}.progress-node.current{background:#f4db24}
.top-rule{position:absolute;left:76px;right:78px;top:110px;height:3px;background:#171815;transform-origin:left}
.stage{position:absolute;inset:0;width:100%;height:100%}
.story-content{position:absolute;left:80px;right:80px;top:170px;height:605px}
.eyebrow{font-size:30px;font-weight:700;line-height:1.5;letter-spacing:.12em;margin:0 0 20px}
.headline{font-family:'Documentary Serif',serif;font-size:118px;font-weight:900;line-height:1.17;letter-spacing:-.04em;margin:0;max-width:1160px}
.headline .line{display:block;position:relative;width:max-content;max-width:100%;padding:0 8px}
.yellow{background:#f4db24;box-shadow:12px 0 #f4db24,-12px 0 #f4db24}
.mark{display:block;height:15px;background:#f4db24;transform-origin:left;margin-top:12px}
.deck{font-size:40px;line-height:1.55;font-weight:600;max-width:940px;margin:32px 0 0}
.cutline{font-size:27px;line-height:1.5;font-weight:500;letter-spacing:.03em}
.art{position:absolute;right:-35px;top:0;width:790px;height:620px;object-fit:contain;transform-origin:center}
.title-copy{position:absolute;left:0;top:50px;z-index:3}
.title-copy .headline{font-size:119px;max-width:1140px}
.hook .title-copy{top:10px}.hook .headline{font-size:111px;max-width:1050px}.hook .art{width:700px;right:-35px}
.person-photo{position:absolute;left:26px;top:0;width:640px;height:605px;background:#f8f4e9;border:18px solid #f8f4e9;box-shadow:14px 18px 0 #17181520;transform-origin:center}
.person-photo img{width:100%;height:100%;object-fit:cover;object-position:center 35%}
.photo-tape{position:absolute;left:142px;top:-54px;width:320px;height:90px;background:#f4db24;opacity:.94;clip-path:polygon(2% 7%,100% 0,97% 89%,0 100%)}
.person-copy{position:absolute;left:765px;top:60px;width:970px}
.person-name{font-family:'Documentary Serif',serif;font-size:94px;font-weight:900;line-height:1.16;margin:0 0 26px;letter-spacing:-.035em}
.person-role{display:inline-block;font-size:45px;font-weight:800;line-height:1.5;background:#f4db24;padding:4px 18px;max-width:965px}
.person-body{font-size:46px;font-weight:500;line-height:1.5;margin-top:30px;max-width:910px;white-space:pre-line}
.person-index{font-family:'Documentary Serif',serif;font-size:180px;color:#c4bfae;font-weight:900;position:absolute;right:5px;bottom:12px;line-height:1}
.arrow{position:absolute;width:195px;height:105px;left:587.55px;top:244.2px;z-index:4;overflow:visible}
.arrow path{stroke:#171815;stroke-width:9;fill:none;stroke-linecap:round;stroke-linejoin:round}
.question-number{position:absolute;right:0;top:-58px;font-family:'Documentary Serif',serif;font-size:360px;font-weight:900;color:#d8d2c4;line-height:1;letter-spacing:-.09em}
.question-header{max-width:1520px;position:relative;z-index:2}
.question-header .headline{font-size:101px;max-width:1510px;line-height:1.18}
.process{position:absolute;left:0;right:0;bottom:0;display:flex;align-items:center;gap:38px}
.process-node{position:relative;flex:1;min-height:185px;padding:25px 28px;background:#f8f5ec;box-shadow:10px 11px 0 #1718151a;border:2px solid #171815}
.process-node .num{display:block;font-size:25px;font-weight:700;color:#595a51;margin-bottom:14px}
.process-node .name{font-size:42px;font-weight:800;line-height:1.3}
.process-node.focus{background:#f4db24}.process-arrow{width:110px;height:60px;flex:0 0 110px;overflow:visible}
.variant-i02 .process{gap:70px}.variant-i02 .process-node{min-height:210px;max-width:820px}.variant-i02 .process-node .name{font-size:53px}.variant-i02 .process-node.focus{background:#f8f5ec}.variant-i02 .process-node:first-child{background:#f4db24}
.workflow-art{position:absolute;left:20px;top:235px;width:1650px;height:380px;object-fit:contain}.variant-i03 .question-header .headline{font-size:88px}.variant-i03 .process{left:30px;right:100px;bottom:0;gap:65px}.variant-i03 .process-node{min-height:105px;padding:15px 24px;box-shadow:8px 9px 0 #1718151a}.variant-i03 .process-node .num{display:none}.variant-i03 .process-node .name{font-size:39px}.variant-i03 .process-arrow{width:80px;flex-basis:80px}
.variant-i04 .process-node:nth-child(1){min-height:155px}.variant-i04 .process-node:nth-child(3){min-height:190px}.variant-i04 .process-node:nth-child(5){min-height:230px}.variant-i04 .process{align-items:flex-end}
.process-arrow path{fill:none;stroke:#171815;stroke-width:7;stroke-linecap:round;stroke-linejoin:round}
.notes{position:absolute;right:-16px;top:340px;width:570px;font-size:40px;line-height:1.5;font-weight:600}
.note-paper{background:#f4db24;padding:18px 24px;box-shadow:9px 11px 0 #1718151a}
.caption-band{position:absolute;left:0;right:0;bottom:0;height:260px;background:#171815;z-index:20}
.caption-band:before{content:'';position:absolute;left:0;right:0;top:-17px;height:22px;background:#171815;clip-path:polygon(0 50%,5% 12%,11% 43%,16% 7%,21% 38%,28% 14%,35% 53%,41% 22%,49% 5%,55% 42%,62% 17%,69% 52%,77% 7%,84% 43%,91% 19%,96% 44%,100% 9%,100% 100%,0 100%)}
.caption{position:absolute;left:76px;right:76px;bottom:26px;height:213px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;z-index:25;text-align:center;color:#faf7ec}
.caption .zh{font-size:62px;font-weight:800;line-height:1.14;max-width:1768px;margin:0;white-space:pre-line;text-wrap:balance}
.caption .en{font-size:33px;font-weight:400;line-height:1.24;max-width:1720px;margin:0;text-wrap:balance}
.narration-caption{bottom:26px;height:180px}.narration-caption .zh{font-size:60px;line-height:1.25}.narration-band{height:220px}
.source-video{position:absolute;left:0;top:0;width:100%;height:100%;object-fit:cover}
.footage-world{position:absolute;inset:0;width:100%;height:100%;transform-origin:left top}
.source-label{position:absolute;left:56px;top:44px;max-width:1250px;z-index:12}
.source-label-inner{display:flex;align-items:center;gap:20px;min-height:72px;padding:12px 26px;background:#f4db24;box-shadow:6px 8px 0 #17181526}
.source-label .qnum{font-family:'Documentary Serif',serif;font-size:36px;font-weight:900;border-right:2px solid #171815;padding-right:20px}
.source-label .qtext{font-size:34px;font-weight:800;line-height:1.35}
.source-credit{position:absolute;left:76px;top:746px;z-index:19;padding:5px 10px;font-size:21px;font-weight:500;color:#fff;background:#171815}
.callout{position:absolute;left:64px;top:175px;width:610px;z-index:13}
.callout-inner{background:#eee9df;padding:23px 28px;box-shadow:10px 12px 0 #17181520}
.callout-kicker{font-size:23px;font-weight:700;letter-spacing:.09em;margin-bottom:10px}
.callout-text{font-family:'Documentary Serif',serif;font-size:53px;line-height:1.23;font-weight:900;white-space:pre-line;margin:0}
.callout-foot{font-size:26px;margin-top:12px;line-height:1.35}
.marker-step{font-size:38px;font-weight:800;line-height:1.32;padding:11px 0;border-top:2px solid #c6c0b0}.marker-step:first-of-type{border-top:0}.marker-line{display:block;white-space:nowrap}.marker-note{font-size:26px;font-weight:600;line-height:1.35;margin-top:8px;padding:6px 9px;background:#f4db24}.callout.ladder .marker-step{font-size:34px}.callout.quote .marker-step{font-family:'Documentary Serif',serif;font-size:44px;font-weight:900}.callout.compare .marker-step:last-child{background:#f4db24;padding:10px 8px}
.cta-left{position:absolute;left:0;top:10px;width:1020px}.cta-right{position:absolute;right:20px;top:10px;width:655px;height:560px;background:#171815;color:#eee9df;padding:64px 48px;display:flex;flex-direction:column;justify-content:center;align-items:flex-start}
.source-channel{font-family:'Documentary Serif',serif;font-size:60px;font-weight:900;line-height:1.2;letter-spacing:-.025em;margin:18px 0 24px}
.cta-topic-kicker{font-size:25px;font-weight:600;line-height:1.4;color:#595a51;margin-bottom:12px}.cta-topic{font-family:'Documentary Serif',serif;font-size:56px;font-weight:900;line-height:1.3}.cta-topic span{display:block}.cta-guest{font-size:28px;font-weight:600;line-height:1.4;margin-top:18px}
.runtime-label{font-size:25px;font-weight:500;line-height:1.4;margin-top:22px}.cta-description{font-size:48px;font-weight:800;line-height:1.4;margin-top:22px}
.cta-label{font-size:34px;font-weight:600;line-height:1.3;letter-spacing:.04em}.cta-name{font-family:'Documentary Serif',serif;font-size:68px;font-weight:900;line-height:1.2;margin-top:30px;white-space:nowrap}.cta-action{font-size:50px;font-weight:800;line-height:1.3;background:#f4db24;color:#171815;padding:15px 24px;display:inline-block;margin-top:48px}
"""

def css_for_root(): return CSS.replace("../assets/", "assets/")

def copy_asset(source: Path, target: Path):
    if not source.exists(): raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve()==target.resolve(): return
    if target.exists() and target.stat().st_size==source.stat().st_size and target.stat().st_mtime>=source.stat().st_mtime: return
    shutil.copy2(source,target)

def asset_path(src, name):
    p=Path(src)
    target=PROJECT/"assets"/name
    copy_asset(p,target)
    return "assets/"+name.replace("\\","/")



def base(id, number,completed=False):
    chapter=int(str(number).split('/')[0].strip()) if '/' in str(number) else 1
    return f'<div class="paper-base" data-layout-ignore></div>{channel_lockup(chapter,completed=completed)}<div class="top-rule" id="{id}-rule" data-layout-ignore></div>'

def arrow(id, cls="arrow"):
    return f'<svg class="{cls}" viewBox="0 0 200 100" data-layout-ignore><path id="{id}" d="M8 38 C70 36 80 68 179 51 M154 27 L182 51 L157 73"/></svg>'

def draw_js(selector, at, dur=.7):
    return f'{{const p=document.querySelector("{selector}");const l=p.getTotalLength();p.style.strokeDasharray=l;p.style.strokeDashoffset=l;tl.fromTo(p,{{strokeDashoffset:l}},{{strokeDashoffset:0,duration:{dur},ease:"power2.out"}},{at});}}'

def arrive(selector,at,dur=.65,x=0,y=45,rot=0,scale=1):
    return f'tl.fromTo("{selector}",{{x:{x},y:{y},rotation:{rot},scale:{scale},opacity:0}},{{x:0,y:0,rotation:0,scale:1,opacity:1,duration:{dur},ease:"power3.out"}},{at});'

def reveal(selector,at,dur=.65):
    return f'tl.fromTo("{selector}",{{scaleX:0}},{{scaleX:1,duration:{dur},ease:"power3.out"}},{at});'

def person_phase(id,beat,index,portrait):
    start=float(beat["local_start"]); end=float(beat["local_end"])
    key=f"{id}-p{index}"
    name=beat.get("name", "")
    position=esc(beat.get('object_position','center 35%'))
    role=beat.get('person_role','speaker')
    labels={'host':'主持人','guest':'受訪者','speaker':'講者'}
    if role not in labels:raise ValueError('person_role must be host, guest or speaker')
    label=esc(beat.get('person_label') or labels[role])
    person_number=esc(beat.get('person_index') or ('01' if role in ('host','speaker') else '02'))
    markup=f'''<section class="clip stage" id="{key}" data-start="{n(start)}" data-duration="{n(end-start)}" data-track-index="4"><div class="story-content"><div class="person-photo" id="{key}-photo"><img src="{portrait}" alt="{esc(name)} 原訪談影格" style="object-position:{position}"><div class="photo-tape" id="{key}-tape" data-layout-ignore></div></div><div class="person-copy"><p class="eyebrow" id="{key}-eyebrow">{label}</p><h1 class="person-name" id="{key}-name">{esc(name)}</h1><div class="person-role" id="{key}-role">{esc(beat.get('role',''))}</div><div class="person-body" id="{key}-body">{esc(beat.get('body',''))}</div></div>{arrow(key+'-arrow')}<div class="person-index" data-layout-ignore>{person_number}</div></div></section>'''
    js=arrive(f"#{key}-photo",start+.02,.75,x=-95,y=10,rot=-4)+arrive(f"#{key}-tape",start+.45,.3,y=-25)+arrive(f"#{key}-eyebrow",start+.25,.4,x=30,y=0)+arrive(f"#{key}-name",start+.4,.55,y=42)+arrive(f"#{key}-role",start+.72,.6,x=60,y=0)+arrive(f"#{key}-body",start+1.25,.6,y=26)+draw_js(f"#{key}-arrow",start+1.3)
    return markup,js

def question_phase(id,beat,index,art):
    start=float(beat["local_start"]); end=float(beat["local_end"])
    key=f"{id}-q{index}"
    lines=beat.get("title", "").split("\n")
    body=''.join(f'<span class="line {"yellow" if j==len(lines)-1 else ""}" id="{key}-line{j}">{esc(x)}</span>' for j,x in enumerate(lines))
    markup=f'''<section class="clip stage hook" id="{key}" data-start="{n(start)}" data-duration="{n(end-start)}" data-track-index="4"><div class="story-content"><img class="art" id="{key}-art" src="{art}" alt="{esc(beat.get('art_alt','本集主題插圖'))}"><div class="title-copy"><p class="eyebrow" id="{key}-eyebrow">{esc(beat.get('kicker','第一個關鍵問題'))}</p><h1 class="headline">{body}</h1></div></div></section>'''
    js=arrive(f"#{key}-art",start+.1,.85,x=160,y=30,rot=3)+arrive(f"#{key}-eyebrow",start+.1,.45,y=20)
    for j in range(len(lines)): js+=arrive(f"#{key}-line{j}",start+.25+j*.16,.6,y=70)
    return markup,js






def source_scene(item):
    id=item['id'];d=item['duration'];c=item['chapter']
    media=asset_path(item['media_path'],f"video/{id}.mp4")
    track=2000+int(''.join(x for x in id if x.isdigit()))
    markup=f'<div class="paper-base" data-layout-ignore></div><div class="footage-world" id="{id}-footage"><video class="clip source-video" id="{id}-video" src="{media}" data-start="0" data-duration="{n(d)}" data-track-index="{track}" data-has-audio="true" data-volume="1" playsinline></video></div>'
    markup+=channel_lockup(c,source=True)+f'<div class="clip source-label" id="{id}-label" data-start="0" data-duration="{n(min(8,d))}" data-track-index="10"><div class="source-label-inner" id="{id}-label-inner"><span class="qnum">{int(c):02d}</span><span class="qtext">{esc(item["title"])}</span></div></div><div class="source-credit">{esc(item["source_credit"])}</div><div class="caption-band" data-layout-ignore></div>'
    js=arrive(f'#{id}-label-inner',.08,.65,x=-150,y=0)
    js+=f'tl.to("#{id}-label-inner",{{x:-90,opacity:0,duration:.5,ease:"power2.in"}},{n(min(7.5,d-.5))});'
    marker_file=EPISODE/'markers.json'
    markers=json.loads(marker_file.read_text(encoding='utf-8-sig')).get('markers',[]) if marker_file.exists() else []
    markers=[m for m in markers if m.get('item')==id]
    for k,m in enumerate(markers):
        local=float(m['start'])-float(item['source_start']);end=min(d,float(m['end'])-float(item['source_start']))
        if local<0 or end<=local:continue
        key=f'{id}-marker{k}'
        steps=[]
        for j,step in enumerate(m['steps']):
            note=f'<div class="marker-note">{esc(step["note"])}</div>' if step.get('note') else ''
            text=esc(step['text'])
            if step.get('display_lines'):
                text=''.join(f'<span class="marker-line">{esc(line)}</span>' for line in step['display_lines'])
            steps.append(f'<div class="marker-step" id="{key}-step{j}">{text}{note}</div>')
        markup+=f'<div class="clip callout {esc(m["type"])}" id="{key}" data-start="{n(local)}" data-duration="{n(end-local)}" data-track-index="12"><div class="callout-inner" id="{key}-inner"><div class="callout-kicker">{esc(m["eyebrow"])}</div>{"".join(steps)}</div></div>'
        # The full interview frame moves into a picture zone before the note arrives.
        # This preserves both faces across camera cuts without guessing a facial safe area.
        js+=f'tl.fromTo("#{id}-footage",{{x:0,y:0,scale:1}},{{x:625,y:64,scale:.66,duration:.7,ease:"power3.inOut",immediateRender:false}},{n(max(0,local-.45))});'
        js+=arrive(f'#{key}-inner',local+.18,.6,x=-80,y=20,rot=-1)
        for j,step in enumerate(m['steps']):
            t=max(local,float(step['at'])-float(item['source_start']))
            js+=arrive(f'#{key}-step{j}',t+.1,.5,x=25,y=0)
        js+=f'tl.to("#{key}-inner",{{x:-45,opacity:0,duration:.4,ease:"power2.in"}},{n(end-.4)});'
        restore_start=min(end,max(local+.8,d-.7))
        js+=f'tl.fromTo("#{id}-footage",{{x:625,y:64,scale:.66}},{{x:0,y:0,scale:1,duration:.7,ease:"power3.inOut",immediateRender:false}},{n(restore_start)});'
    return markup,js


def write_scene(item,assets):
    id=item['id'];d=item['duration']
    if item['kind']=='source':body,js=source_scene(item)
    else:
        if id=='i01':body,js=opening(item,assets)
        elif item['kind']=='outro':body,js=outro(item)
        else:body,js=question(item,assets)
        audio=asset_path(item['audio_path'],f"audio/{id}.wav")
        lead=float(item.get('audio_lead',.4));speech=float(item.get('speech_duration', d-lead-float(item.get('tail_hold',.9))))
        track=1000+int(''.join(x for x in id if x.isdigit()))+(100 if item['kind']=='outro' else 0)
        body+=f'<audio id="{id}-voice" src="{audio}" data-start="{n(lead)}" data-duration="{n(speech)}" data-track-index="{track}" data-volume="1"></audio><div class="caption-band narration-band" data-layout-ignore></div>'
    page=f'<!doctype html><html lang="zh-Hant"><head><meta charset="UTF-8"></head><body><template><style>{css_for_root()}</style><div id="root" data-composition-id="{id}" data-duration="{n(d)}" data-width="1920" data-height="1080">{body}</div><script>const tl=gsap.timeline({{paused:true}});{js}window.__timelines["{id}"]=tl;</script></template></body></html>'
    (PROJECT/f'compositions/{id}.html').write_text(page,encoding='utf-8')
    assertions=[]
    if item['kind']=='source':assertions.append(dict(kind='appearsBy',selector=f'#{id}-label-inner',bySec=.9))
    elif id!='i01' and item['kind']!='outro':assertions.append(dict(kind='appearsBy',selector=f'#{id}-line0',bySec=1.0))
    if assertions:dump(PROJECT/f'compositions/{id}.motion.json',dict(duration=d,assertions=assertions))
    return js


