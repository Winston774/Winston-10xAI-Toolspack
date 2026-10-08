"""Data-driven HyperFrames adapter for source-led documentary scenes.

No episode facts are inferred. All text/media comes from the new episode inputs.
The bundled neutral engine supplies geometry and deterministic animation.
"""
from __future__ import annotations
import argparse, base64, importlib.util, json, mimetypes, shutil, sys
from pathlib import Path
from interview import read, write, resolved, safe_id, check_narration_plan, check_narration_snapshot
from visual_contract import CSS as CONTRACT_CSS, caption_band, review_markers, STYLE
from opening_selection import validate_opening

SKILL=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('paper_documentary',SKILL/'assets/engine/paper_documentary.py')
E=importlib.util.module_from_spec(spec);spec.loader.exec_module(E)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('workdir');ap.add_argument('--project',default='motion');args=ap.parse_args()
    root=Path(args.workdir).resolve();project=resolved(root,args.project)
    if not project.is_relative_to(root):raise ValueError('Generated project must be inside episode directory')
    profile=read(root/'profile.json');env=read(root/'environment.json');plan=read(root/'qa/resolved-plan.json');art=read(root/'art-direction.json');markers=read(root/'markers.json')['markers'];items=plan['timeline'];cues=read(root/'subtitles/timeline.json')['cues']
    if not isinstance(profile.get('brand'),str) or not profile['brand'].strip():raise ValueError('Set profile.brand to your channel or author name before building')
    if profile.get('visual_contract')!=STYLE:raise ValueError('This builder supports paper-tear-and-semantic-reframe-v1; a different design needs an explicitly adapted renderer and checks')
    opening_report=validate_opening(root,read(root/'rundown.json')['items'])
    write(root/'qa/opening-selection.json',opening_report)
    if not opening_report['valid']:raise ValueError('Opening selection is incomplete or mismatched; inspect qa/opening-selection.json')
    check_narration_snapshot(root,profile,plan)
    check_narration_plan(root,profile)
    annotation_report=review_markers(root,items)
    write(root/'qa/annotation-review.json',annotation_report)
    total=plan['duration'];chapters=max(int(x['chapter']) for x in items);brand=profile['brand'];esc=E.esc;n=E.n
    if not isinstance(brand,str) or not brand.strip():raise ValueError('Set profile.brand to your channel or author name before building')
    if (profile['canvas']['width'],profile['canvas']['height'],profile['canvas']['fps'])!=(1920,1080,30):raise ValueError('This visual baseline requires 1080p30; adapt before changing canvas')
    if not art.get('source_channel') or not art.get('source_topic_lines') or not art.get('runtime_label'):raise ValueError('Provide verified original channel, authored topic lines and a single runtime label')
    for folder in ['assets/fonts','compositions','qa','renders']:(project/folder).mkdir(parents=True,exist_ok=True)
    E.EPISODE=root;E.PROJECT=project;E.CSS+=CONTRACT_CSS
    # Marker containment is essential; do not silently drop or clip bad markers.
    by_id={x['id']:x for x in items}
    for m in markers:
        safe_id(m['id']);item=by_id[m['item']]
        if item['kind']!='source' or not item['source_start']<=m['start']<m['end']<=item['source_end']+.01:raise ValueError(f'Marker outside source clip: {m["id"]}')
        if m['type'] not in ('pair','compare','callout','flow','quote','ladder'):raise ValueError('Unknown marker visual type')
        if not m.get('steps'):raise ValueError('Marker needs steps')
        previous=m['start']
        for step in m['steps']:
            if not previous<=step['at']<m['end']:raise ValueError('Marker steps must be ordered inside marker')
            previous=step['at']
            if step.get('display_lines') and ''.join(step['display_lines'])!=step['text']:raise ValueError('Display line breaks may not alter marker text')
    for item in items:
        own=sorted([m for m in markers if m['item']==item['id']],key=lambda m:m['start'])
        for a,b in zip(own,own[1:]):
            if a['end']+.7>b['start']-.45:raise ValueError('Marker reframe/restore motions overlap; merge the annotation or adjust timing')

    def lockup(chapter,source=False,completed=False):
        chapter=max(1,min(chapters,int(chapter)))
        icon='<svg class="question-icon" viewBox="0 0 32 32" aria-label="問題"><path d="M4 4 H28 V24 H14 L8 28 V24 H4 Z"/><path d="M12.5 10.7 C12.5 6.8 19.6 6.8 19.6 10.9 C19.6 13.7 16 13.1 16 16.4"/><circle cx="16" cy="20" r="1.3"/></svg>'
        nodes=''.join(f'<span class="progress-node {"done" if completed or j<chapter else "current" if j==chapter else ""}"></span>' for j in range(1,chapters+1)) if chapters<=8 else f'<span class="slv-progress-track"><span style="width:{100 if completed else round(chapter/chapters*100,4)}%"></span></span>'
        return f'<div class="channel-lockup"><div class="channel-progress">{icon}<span class="question-count">{chapter:02d}/{chapters:02d}</span><div class="progress-nodes" aria-label="第{chapter}問，共{chapters}問">{nodes}</div></div><div class="channel-name">{esc(brand)}</div></div>'
    E.channel_lockup=lockup
    assets={}
    for key,value in art['assets'].items():
        if not value:continue
        p=resolved(root,value)
        if not p.is_file():raise FileNotFoundError(p)
        mime=mimetypes.guess_type(p.name)[0]
        if mime not in ('image/png','image/jpeg','image/webp'):raise ValueError('Use local PNG/JPEG/WebP for portraits and collage')
        assets[key]='data:'+mime+';base64,'+base64.b64encode(p.read_bytes()).decode('ascii')

    def opening(item,_assets):
        rid=item['id'];beats=item['card_beats'];lead=item['audio_lead'];body=E.base(rid,f'01 / {chapters:02d}');js=E.reveal(f'#{rid}-rule',.08,.6)
        for k,raw in enumerate(beats):
            beat=raw.copy();beat.update(local_start=0 if raw['start']==0 else raw['start']+lead,local_end=item['duration'] if k==len(beats)-1 else raw['end']+lead)
            if beat['type']=='person':
                key=beat.get('portrait_key')
                if not key or key not in assets:raise ValueError('Each person beat needs portrait_key with local sourced portrait')
                markup,anim=E.person_phase(rid,beat,k,assets[key])
            else:
                key=beat.get('art_key','hook')
                if key not in assets:raise ValueError('Hook/question beat needs an authored collage asset')
                markup,anim=E.question_phase(rid,beat,k,assets[key])
            body+=markup;js+=anim
        return body,js
    E.opening=opening

    def question(item,_assets):
        rid=item['id'];cfg=item['visual'];chapter=item['chapter'];d=item['duration'];layout=cfg.get('layout','process')
        variant={'compare':'i02','workflow':'i03','ladder':'i04','process':'i05','question':'i05'}.get(layout)
        if not variant or not 1<=len(cfg['lines'])<=3:raise ValueError('Bridge requires supported layout and legible title lines; split long questions by meaning')
        if layout!='question' and not cfg['nodes']:raise ValueError('Diagram layout requires points; use question layout for a simple spoken transition')
        header=''.join(f'<span class="line {"yellow" if j==len(cfg["lines"])-1 else ""}" id="{rid}-line{j}">{esc(line)}</span>' for j,line in enumerate(cfg['lines']))
        pages=[]
        all_nodes=[] if layout=='question' else cfg['nodes']
        for first in range(0,len(all_nodes),3):
            nodes=[];chunk=all_nodes[first:first+3]
            for offset,node in enumerate(chunk):
                j=first+offset
                nodes.append(f'<div class="process-node {"focus" if j==len(all_nodes)-1 else ""}" id="{rid}-node{j}"><span class="num">{j+1:02d}</span><span class="name">{esc(node)}</span></div>')
                if offset<len(chunk)-1 and layout!='compare':nodes.append(E.arrow(f'{rid}-arrow{j}','process-arrow'))
            pages.append(f'<div class="process-page" id="{rid}-page{first//3}">{"".join(nodes)}</div>')
        collage=''
        if layout=='workflow':
            key=cfg.get('art_key','workflow')
            if key not in assets:raise ValueError('Workflow layout needs artwork')
            collage=f'<img class="workflow-art" id="{rid}-workflow-art" src="{assets[key]}" alt="{esc(cfg.get("art_alt","本集流程拼貼"))}">'
        body=E.base(rid,f'{chapter:02d} / {chapters:02d}')+f'<div class="story-content variant-{variant}"><div class="question-number" data-layout-ignore>{chapter:02d}</div><div class="question-header"><p class="eyebrow" id="{rid}-eyebrow">接著問 · 第{chapter:02d}問</p><h1 class="headline">{header}</h1></div>{collage}<div class="process">{"".join(pages)}</div></div>'
        js=E.reveal(f'#{rid}-rule',.05,.6)+E.arrive(f'#{rid}-eyebrow',.1,.4,y=20)
        for j in range(len(cfg['lines'])):js+=E.arrive(f'#{rid}-line{j}',.2+j*.2,.65,y=65)
        if collage:js+=E.arrive(f'#{rid}-workflow-art',1.1,.9,y=80)
        for page_index in range(len(pages)):
            start=max(2.2,d*.20)+page_index*5.8
            js+=E.arrive(f'#{rid}-page{page_index}',start-.25,.4,y=0)
            count=min(3,len(all_nodes)-page_index*3)
            for offset in range(count):
                j=page_index*3+offset;t=start+offset*1.1
                if t+.7+1.4>d-.2:raise ValueError('Bridge needs more reading time; extend authored hold or move detail to source-timed notes. No points were dropped.')
                js+=E.arrive(f'#{rid}-node{j}',t,.7,y=65,rot=(-2 if j%2 else 2))
                if offset<count-1 and layout!='compare':js+=E.draw_js(f'#{rid}-arrow{j}',t+.65,.65)
            if page_index<len(pages)-1:js+=f'tl.to("#{rid}-page{page_index}",{{opacity:0,x:-35,duration:.4}},{n(start+4.6)});'
        return body,js
    E.question=question
    def outro(item):
        rid=item['id'];d=item['duration'];cta=profile['cta'];topic=''.join(f'<span>{esc(x)}</span>' for x in art['source_topic_lines'])
        body=E.base(rid,f'{chapters:02d} / {chapters:02d}',completed=True)+f'<div class="story-content"><div class="cta-left"><div class="eyebrow" id="{rid}-eyebrow">原頻道完整內容</div><div class="source-channel" id="{rid}-source">{esc(art["source_channel"])}</div><div id="{rid}-topic"><div class="cta-topic-kicker">{esc(art.get("source_topic_label","內容導讀"))}</div><div class="cta-topic">{topic}</div><div class="cta-guest">{esc(art.get("guest_line",""))}</div><div class="runtime-label">{esc(art["runtime_label"])}</div></div><div class="cta-description" id="{rid}-link"><span class="yellow">{esc(cta["source_link"])}</span></div></div><div class="cta-right" id="{rid}-subscribe"><div class="cta-label">{esc(cta["label"])}</div><div class="cta-name">{esc(brand)}</div><div class="cta-action">{esc(cta["action"])}</div></div></div>'
        js=E.reveal(f'#{rid}-rule',.05,.6)+E.arrive(f'#{rid}-eyebrow',.12,.4,y=20)+E.arrive(f'#{rid}-source',.3,.8,y=100,rot=-1)+E.arrive(f'#{rid}-topic',1.1,.6,y=20)+E.arrive(f'#{rid}-link',min(4,d*.25),.65,x=-80,y=0)+E.arrive(f'#{rid}-subscribe',min(d*.48,9),.85,x=180,y=20,rot=3)
        return body,js
    E.outro=outro
    original_write=E.write_scene
    def write_scene(item,assets):
        result=original_write(item,assets);path=project/f'compositions/{item["id"]}.html'
        html=path.read_text(encoding='utf-8')
        html=html.replace('<div class="caption-band" data-layout-ignore></div>',caption_band())
        html=html.replace('<div class="caption-band narration-band" data-layout-ignore></div>',caption_band(True))
        path.write_text(html,encoding='utf-8')
        return result
    E.write_scene=write_scene
    shutil.copy2(resolved(root,env['gsap_js']),project/'assets/gsap.min.js')
    marks=''.join(f'<circle cx="{(j*47+13)%256}" cy="{(j*89+29)%256}" r="{.3+(j%4)*.15}" fill="#776f5a" opacity=".16"/>' for j in range(90))
    (project/'assets/paper-grain.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256">'+marks+'</svg>',encoding='utf-8')
    mounts=[];assertions=[]
    for it in items:
        safe_id(it['id']);E.write_scene(it,assets)
        mounts.append(f'<div id="{it["id"]}-mount" class="clip scene" data-composition-id="{it["id"]}" data-composition-src="compositions/{it["id"]}.html" data-start="{n(it["start"])}" data-duration="{n(it["duration"])}" data-track-index="1" data-width="1920" data-height="1080"></div>')
        if it['kind']=='source':
            assertions.append(dict(kind='staysInFrame',selector=f'#{it["id"]}-footage'))
            for k,m in enumerate([m for m in markers if m['item']==it['id']]):
                local_assertions=[]
                for j,s in enumerate(m['steps']):
                    selector=f'#{it["id"]}-marker{k}-step{j}'
                    local_assertions.append(dict(kind='appearsBy',selector=selector,bySec=s['at']-it['source_start']+.75))
                    if j:local_assertions.append(dict(kind='before',a=f'#{it["id"]}-marker{k}-step{j-1}',b=selector))
                motion_path=project/f'compositions/{it["id"]}.motion.json';motion=read(motion_path);motion['assertions']+=local_assertions;write(motion_path,motion)
    caption_markup=[]
    for k,c in enumerate(cues):
        en=c.get('en','');classes='caption' if en else 'caption narration-caption'
        caption_markup.append(f'<div id="caption-{k:04d}" class="clip {classes}" data-start="{n(c["start"])}" data-duration="{n(c["end"]-c["start"])}" data-track-index="40" data-layout-allow-caption-zone><p class="zh">{esc(c["zh"])}</p>'+ (f'<p class="en">{esc(en)}</p>' if en else '')+'</div>')
    css=E.css_for_root()
    captions='<!doctype html><html lang="zh-Hant"><head><meta charset="UTF-8"></head><body><template><style>'+css+f'</style><div id="root" data-composition-id="caption-rail" data-duration="{n(total)}" data-width="1920" data-height="1080">'+''.join(caption_markup)+'</div><script>const tl=gsap.timeline({paused:true});window.__timelines["caption-rail"]=tl;</script></template></body></html>'
    (project/'compositions/captions.html').write_text(captions,encoding='utf-8')
    mounts.append(f'<div id="caption-rail-mount" class="clip scene" style="z-index:40" data-composition-id="caption-rail" data-composition-src="compositions/captions.html" data-start="0" data-duration="{n(total)}" data-track-index="40" data-width="1920" data-height="1080"></div>')
    page='<!doctype html><html lang="zh-Hant"><head><meta charset="UTF-8"><script src="assets/gsap.min.js"></script><style>'+css+'.scene{position:absolute;inset:0;width:100%;height:100%}</style></head><body>'+f'<div id="root" data-composition-id="interview-film" data-duration="{n(total)}" data-width="1920" data-height="1080">'+''.join(mounts)+'</div><script>const tl=gsap.timeline({paused:true});window.__timelines["interview-film"]=tl;</script></body></html>'
    (project/'index.html').write_text(page,encoding='utf-8')
    # Fresh font subsets include this episode's characters; never reuse a past CJK subset.
    for extra in env.get('python_extra_paths',[]):
        folder=resolved(root,extra)
        if folder.is_dir():sys.path.insert(0,str(folder))
    from fontTools import subset
    text=page+captions+''.join((project/f'compositions/{x["id"]}.html').read_text(encoding='utf-8') for x in items)
    for name,key in [('sans','sans_ttf'),('serif','serif_ttf')]:
        opts=subset.Options();opts.flavor='woff2';font=subset.load_font(str(resolved(root,env[key])),opts);sub=subset.Subsetter(options=opts);sub.populate(text=text);sub.subset(font);subset.save_font(font,str(project/f'assets/fonts/{name}.woff2'),opts)
    for path in env.get('font_licenses',[]):shutil.copy2(resolved(root,path),project/'assets/fonts'/Path(path).name)
    write(project/'index.motion.json',dict(version=1,duration=total,assertions=assertions))
    version=profile['hyperframes_version']
    write(project/'package.json',dict(name='interview-film',private=True,type='module',scripts=dict(check=f'npx --yes hyperframes@{version} check',dev=f'npx --yes hyperframes@{version} preview',render=f'npx --yes hyperframes@{version} render')))
    write(project/'qa/reframe-proof.json',annotation_report)
    write(project/'input-manifest.json',dict(episode=str(root),resolved_plan='qa/resolved-plan.json',duration=total,frames=plan['frames'],brand=brand,question_count=chapters,style=STYLE,engine='bundled neutral paper documentary engine',annotation_count=len(markers)))
    from check_style import audit
    style_report=audit(root,args.project);write(root/'qa/style-check.json',style_report)
    if not style_report['passed']:raise ValueError('Generated scene style contract failed; inspect qa/style-check.json')
    print(json.dumps(dict(project=str(project),scenes=len(items),captions=len(cues),duration=total,question_count=chapters),ensure_ascii=False))

if __name__=='__main__':
    try:main()
    except (KeyError,ValueError,FileNotFoundError) as exc:print(f'ERROR: {exc}',file=sys.stderr);raise SystemExit(2)
