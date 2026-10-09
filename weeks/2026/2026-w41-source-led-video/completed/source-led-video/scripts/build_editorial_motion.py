#!/usr/bin/env python3
"""Build an editable 1080p30 film from explicit prepared media and editorial cues.

No media download, voice synthesis, audio normalization, time stretching, or render.
All relative input paths resolve against the plan directory. Output must be new.
"""
import argparse
import datetime
import hashlib
import html
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageFont
from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
GEOMETRY = {'source_box':[320,80,1280,720], 'source_inset_box':[720,125,1120,630],
            'concept_box':[90,145,560,595], 'caption_box':[96,822,1728,258]}
PALETTE_KEYS = ('background','ink','secondary','accent','accent_text')

def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path, data): Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()
def esc(value): return html.escape(str(value),quote=True)
def numeric(value, context):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value): raise ValueError(context+' requires a finite number')
    return float(value)
def required_text(value, context):
    if not isinstance(value,str) or not value.strip(): raise ValueError(context+' requires nonempty text')
    return value
def frame(seconds): return math.ceil((seconds-1e-7)*30)/30
def srt_time(seconds):
    ms=round(seconds*1000); return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'
def wrap(text,font,width,latin=False):
    if not text: return []
    if '\n' in text or '\r' in text: raise ValueError('Text must use automatic wrapping, no manual newline')
    # Latin tokens stay intact even inside Chinese text. Never split a proper name.
    tokens=re.findall(r'[A-Za-z0-9]+(?:[’\'._:/+-][A-Za-z0-9]+)*|\s+|[^A-Za-z0-9\s]',text)
    if latin: tokens=re.findall(r'\S+\s*',text)
    lines=[];current=''
    for token in tokens:
        if font.getlength(token.strip())>width: raise ValueError('Unbreakable word exceeds text width: '+token)
        candidate=current+token
        if font.getlength(candidate.rstrip())>width and current.strip(): lines.append(current.strip());current=token.lstrip()
        else: current=candidate
    if current.strip(): lines.append(current.strip())
    return lines
def contrast(a,b):
    def luminance(color):
        c=[int(color[i:i+2],16)/255 for i in (1,3,5)]
        c=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in c]
        return sum(x*y for x,y in zip(c,(.2126,.7152,.0722)))
    x,y=sorted([luminance(a),luminance(b)]);return (y+.05)/(x+.05)

class Validator:
    def __init__(self,plan_path):
        self.path=Path(plan_path).resolve();self.base=self.path.parent;self.plan=read(self.path);self.inputs={};self.rows=[];self.cues=[];self.reveals=[];self.sources=[];self.total=0
    def asset(self,value,context):
        p=Path(required_text(value,context));p=(self.base/p).resolve() if not p.is_absolute() else p.resolve()
        if not p.is_file(): raise ValueError(context+' file missing: '+str(p))
        self.inputs[str(p)]={'sha256':sha(p),'bytes':p.stat().st_size};return p
    def text(self,value,context,font_size,width,max_lines):
        text=required_text(value,context)
        missing=sorted(set(text)-self.glyphs-{' ','\n','\t'})
        if missing: raise ValueError(context+' missing font glyphs: '+''.join(missing))
        lines=wrap(text,ImageFont.truetype(str(self.font),font_size),width)
        if len(lines)>max_lines: raise ValueError(context+' exceeds safe line count')
        return lines
    def probe(self,p):
        result=subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(p)],capture_output=True,text=True,check=True)
        data=json.loads(result.stdout);duration=numeric(float(data['format']['duration']),'media duration')
        if duration<=0: raise ValueError('Media is empty')
        return data,duration
    def audible_probe(self,p):
        # Decode/measure only; never write, filter, normalize, or replace input media.
        result=subprocess.run(['ffmpeg','-nostdin','-v','info','-i',str(p),'-map','0:a:0','-vn','-af','volumedetect','-f','null','-'],capture_output=True,text=True,check=True)
        match=re.search(r'max_volume:\s*(-?\d+(?:\.\d+)?|-inf)\s*dB',result.stderr)
        if not match: raise ValueError('Unable to measure prepared audio')
        peak=float(match.group(1))
        if peak<=-80: raise ValueError('Prepared audio is silent or below -80 dBFS; provide actual audible media')
        return {'max_volume_dbfs':peak,'status':'measured_non_silent','human_listening':'not_performed'}
    def validate(self):
        p=self.plan
        if p.get('schema_version')!=1 or p.get('canvas')!=[1920,1080] or p.get('fps')!=30: raise ValueError('Requires schema_version 1 and 1920×1080 at 30 fps')
        required_text(p.get('source_id'),'source_id');required_text(p.get('title'),'title')
        self.font=self.asset(p.get('font_path'),'font_path');self.gsap=self.asset(p.get('gsap_path'),'gsap_path')
        ft=TTFont(str(self.font))
        if 'fvar' in ft: raise ValueError('Use a static font, not a variable font')
        self.glyphs=set(chr(c) for table in ft['cmap'].tables for c in table.cmap);ft.close()
        # Renderer-owned labels, step numerals, and connectors need glyph coverage too.
        self.text('依本段發言整理0123456789↓＋','renderer fixed text',23,1700,1)
        theme=p.get('theme',{});registry_path=self.asset(theme.get('registry_path'),'theme.registry_path');registry=read(registry_path)
        if theme.get('key')!=p['source_id']: raise ValueError('theme.key must match source_id')
        record=registry.get('sources',{}).get(theme['key'])
        if not record: raise ValueError('Missing source theme registry entry')
        self.palette=record.get('palette',{})
        if set(self.palette)!=set(PALETTE_KEYS) or any(not re.fullmatch('#[0-9A-Fa-f]{6}',str(self.palette[k])) for k in PALETTE_KEYS): raise ValueError('Palette requires five exact hex color fields')
        if theme.get('snapshot'):
            snap=theme['snapshot']
            if snap.get('registry_sha256')!=sha(registry_path) or snap.get('palette')!=self.palette: raise ValueError('Theme snapshot does not match actual registry')
        for a,b in [('ink','background'),('secondary','background'),('accent_text','accent')]:
            if contrast(self.palette[a],self.palette[b])<4.5: raise ValueError('Palette contrast below 4.5: '+a+'/'+b)
        brand=p.get('brand',{})
        self.text(brand.get('publisher'),'brand.publisher',28,850,1);self.text(brand.get('label'),'brand.label',26,850,1)
        items=p.get('items')
        if not isinstance(items,list) or not items: raise ValueError('items must be nonempty')
        ids=set()
        for index,item in enumerate(items):
            id=required_text(item.get('id'),'item.id')
            if not re.fullmatch('[a-z][a-z0-9-]{0,63}',id) or id in ids: raise ValueError('Unique lowercase item id required')
            ids.add(id);kind=item.get('kind')
            if kind not in ('source','narration'): raise ValueError('item.kind must be source or narration')
            self.text(item.get('label'),'item.label',26,850,1)
            path=self.asset(item.get('media_path'),'item.media_path');data,native=self.probe(path)
            audio=[s for s in data['streams'] if s['codec_type']=='audio'];video=[s for s in data['streams'] if s['codec_type']=='video']
            if len(audio)!=1: raise ValueError('Prepared media requires exactly one audible audio stream')
            audio_start=float(audio[0].get('start_time',0));audio_duration=float(audio[0].get('duration',native))
            if abs(audio_start)>.05 or abs(audio_duration-native)>.1: raise ValueError('Prepared media audio must start at zero and cover its native duration')
            audio_flag=item.get('prepared_audio',{})
            if audio_flag.get('status') not in ('normalized_once','unchanged','unknown'): raise ValueError('prepared_audio.status required, use unknown if unverified')
            if audio_flag['status']=='normalized_once': required_text(audio_flag.get('evidence'),'normalized_once evidence')
            if kind=='source':
                if len(video)!=1 or path.suffix.lower()!='.mp4': raise ValueError('Source media must be a prepared MP4 with one video stream')
                stream=video[0];num,den=map(int,stream['avg_frame_rate'].split('/'))
                if abs(num/den-30)>.001 or abs(stream['width']/stream['height']-16/9)>.001: raise ValueError('Prepared source must be 16:9 at 30 fps')
                begin=numeric(item.get('source_start'),'source_start');end=numeric(item.get('source_end'),'source_end')
                if begin<0 or end<=begin or abs(native-(end-begin))>.08: raise ValueError('Prepared source duration must match source_end-source_start within 80 ms')
                self.text(item.get('credit'),'source.credit',25,1700,1)
            else:
                if video or path.suffix.lower()!='.wav': raise ValueError('Narration requires WAV audio only')
                begin,end=0,native
                if item.get('disclosure') is not None:
                    self.text(item['disclosure'],'narration.disclosure',25,1700,1)
            if 'duration' in item and abs(numeric(item['duration'],'duration')-native)>.05: raise ValueError('Declared duration does not match actual probe')
            audible=self.audible_probe(path)
            duration=frame(native);row=dict(item,start=self.total,end=self.total+duration,duration=duration,native_duration=native,media_sha256=sha(path),probe=data,audio_measurement=audible,asset=f'{index:03d}-{id}{path.suffix.lower()}')
            row['_path']=path;self.rows.append(row)
            cues=item.get('cues')
            if not isinstance(cues,list) or not cues: raise ValueError('Every item needs explicit cues')
            previous=begin
            for ci,cue in enumerate(cues):
                start=numeric(cue.get('start'),'cue.start');stop=numeric(cue.get('end'),'cue.end')
                if not previous<=start<stop<=end+.001: raise ValueError('Cue overlap/order/bounds error for '+id)
                previous=stop;zh=self.text(cue.get('zh'),'cue.zh',56,1728,2)
                en=cue.get('en','')
                if kind=='source':
                    required_text(en,'source cue.en');self.text(en,'cue.en',34,1728,2)
                    english=wrap(en,ImageFont.truetype(str(self.font),34),1728,latin=True)
                    if len(english)>2: raise ValueError('English cue exceeds 2 safe lines')
                else:
                    if en: raise ValueError('Narration captions must be Chinese only')
                    english=[]
                self.cues.append(dict(item_id=id,start=self.total+start-begin,end=self.total+stop-begin,zh=cue['zh'],en=en,zh_lines=zh,en_lines=english))
            if kind=='source': self.validate_markers(row,begin,end)
            else: self.validate_cards(row,native)
            self.total+=duration
        return self
    def validate_markers(self,row,begin,end):
        previous=begin;resolved=[]
        for mi,m in enumerate(row.get('markers',[])):
            start=numeric(m.get('start'),'marker.start');stop=numeric(m.get('end'),'marker.end')
            if not previous<=start<stop<=end-.7: raise ValueError('Marker bounds/order or 0.7 s restoration margin invalid')
            previous=stop+.7
            if m.get('diagram','sequence') not in ('sequence','contrast','cycle'): raise ValueError('Unsupported diagram')
            title_lines=self.text(m.get('title'),'marker.title',40,504,2)
            self.text(m.get('kicker','本段重點'),'marker.kicker',22,504,1)
            steps=m.get('steps',[])
            if not 2<=len(steps)<=3: raise ValueError('A concept card requires 2–3 points')
            previous_at=start+.7
            for step in steps:
                at=numeric(step.get('at'),'step.at');spoken=numeric(step.get('utterance_at'),'step.utterance_at')
                if not previous_at<=at<stop or not begin<=spoken<=at: raise ValueError('Point must be ordered, visible after card opens, and never precede authored utterance_at')
                previous_at=at;self.text(step.get('text'),'step.text',32,404,1)
            if stop-steps[-1]['at']<2: raise ValueError('Last point requires 2 s reading time')
            # Match actual CSS border/padding/line-height/margins, including a two-line title.
            card_height=6+52+(22*1.35+10)+(len(title_lines)*40*1.35+18)+len(steps)*(4+28+44+8)+(len(steps)-1)*22+(23*1.4+14)
            if card_height>595 or 145+card_height>740: raise ValueError('Concept contents exceed card safe height')
            resolved.append(dict(m,id=f'concept-{row["id"]}-{mi}',start=row['start']+start-begin,end=row['start']+stop-begin,measured_content_height=round(card_height,3),steps=[dict(s,at=row['start']+s['at']-begin) for s in steps]))
        self.sources.append(dict(id=row['id'],start=row['start'],end=row['end'],markers=resolved))
    def validate_cards(self,row,native):
        cards=row.get('cards',[]);previous=0
        if not cards: raise ValueError('Narration needs authored visual cards')
        for ci,card in enumerate(cards):
            start=numeric(card.get('start'),'card.start');end=numeric(card.get('end'),'card.end')
            if abs(start-previous)>.001 or not start<end<=native+.001: raise ValueError('Narration cards must continuously cover the actual WAV duration')
            previous=end;lines=card.get('lines',[])
            if not 1<=len(lines)<=3: raise ValueError('Narration card requires 1–3 progressive short phrases')
            self.text(card.get('kicker','中文導讀'),'card.kicker',30,950,1)
            previous_at=start;height=70;has_image=bool(card.get('image'));width=930 if has_image else 1600
            for line in lines:
                at=numeric(line.get('at'),'line.at')
                if not previous_at<=at<end: raise ValueError('Narration phrase timing/order invalid')
                previous_at=at;size=72 if line.get('emphasis') else 64
                measured=self.text(line.get('text'),'card.line',size,width-36,2)
                height+=len(measured)*size*1.35+24;line['_lines']=measured
            if height>580: raise ValueError('Narration card phrases exceed safe visual height')
            if end-lines[-1]['at']<2: raise ValueError('Narration final phrase requires 2 s reading time')
            if has_image:
                art=card['image'];path=self.asset(art.get('path'),'card.image.path')
                if path.suffix.lower()!='.png': raise ValueError('Card images must be local PNG')
                with Image.open(path) as im: im.verify()
                required_text(art.get('alt'),'image.alt');required_text(art.get('provenance'),'image.provenance')
                if art.get('role') not in ('concept','portrait'): raise ValueError('Image role must be concept or portrait')
                if art['role']=='portrait' and art.get('identity_verified') is not True: raise ValueError('Real portrait requires author identity_verified=true')
                art['_path']=path;art['_asset']=f'art-{row["id"]}-{ci}.png'
            # The last visual extends through the sub-frame rounding tail, but audio remains native length.
            card['_end']=row['duration'] if ci==len(cards)-1 else end
        if abs(previous-native)>.001: raise ValueError('Narration cards do not cover WAV end')

def build(v,output):
    output=Path(output).resolve()
    if output.exists(): raise ValueError('Refusing existing output path; choose a new revision')
    scenes=[];captions=[];reveals=[]
    for row in v.rows:
        id=row['id'];start=row['start'];duration=row['duration']
        if row['kind']=='source':
            scenes.append(f'<div id="frame-{id}" class="source-frame"><video id="video-{id}" class="clip source-video" src="assets/{row["asset"]}" data-start="{start}" data-duration="{duration}" data-track-index="2" data-has-audio="true" data-volume="1" data-hf-media-start-basis="global" playsinline></video></div>')
            scenes.append(f'<p id="credit-{id}" class="clip credit" data-start="{start}" data-duration="{duration}" data-track-index="15">{esc(row["credit"])}</p>')
            scenes.append(f'<div id="chapter-{id}" class="clip chapter" data-start="{start}" data-duration="{duration}" data-track-index="11">{esc(row["label"])}</div>')
            source=next(x for x in v.sources if x['id']==id)
            for m in source['markers']:
                mid=m['id'];body=f'<p class="concept-kicker">{esc(m.get("kicker","本段重點"))}</p><h2 id="{mid}-title">{esc(m["title"])}</h2>'
                for si,step in enumerate(m['steps']):
                    if si:
                        symbol='＋' if m.get('diagram')=='contrast' else '<svg width="24" height="24" viewBox="0 0 24 24" aria-label="循環"><path d="M19 8a8 8 0 1 0 1 8 M19 3v5h-5" fill="none" stroke="currentColor" stroke-width="2"/></svg>' if m.get('diagram')=='cycle' and si==len(m['steps'])-1 else '↓'
                        body+=f'<div id="{mid}-connector-{si}" class="connector">{symbol}</div>'
                    body+=f'<div id="{mid}-step-{si}" class="concept-item'+(' emphasis' if si==0 else '')+f'"><span class="step-number">{si+1:02d}</span><span>{esc(step["text"])}</span></div>'
                body+=f'<p id="{mid}-foot" class="concept-foot">依本段發言整理</p>'
                scenes.append(f'<div id="{mid}" class="concept">{body}</div>')
        else:
            scenes.append(f'<audio id="audio-{id}" src="assets/{row["asset"]}" data-start="{start}" data-duration="{row["native_duration"]}" data-track-index="1" data-volume="1" data-hf-media-start-basis="global"></audio>')
            for ci,card in enumerate(row['cards']):
                cid=f'card-{id}-{ci}';body=f'<p class="eyebrow">{esc(card.get("kicker","中文導讀"))}</p>'
                for li,line in enumerate(card['lines']):
                    lid=f'{cid}-line-{li}';body+=f'<div id="{lid}" class="phrase'+(' accent' if line.get('emphasis') else '')+'">'+'<br>'.join(esc(x) for x in line['_lines'])+'</div>'
                    reveals.append(dict(selector='#'+lid,at=start+line['at']))
                art=card.get('image');image=''
                if art:
                    aid=cid+'-image';image=f'<div id="{aid}" class="art art-'+esc(art['role'])+'"><img src="assets/'+art['_asset']+'" alt="'+esc(art['alt'])+'"></div>';reveals.append(dict(selector='#'+aid,at=start+card['start']))
                # HyperFrames owns clip visibility/display. The non-clip wrapper owns flex layout.
                scenes.append(f'<section id="{cid}" class="clip narration-card" data-start="{start+card["start"]}" data-duration="{card["_end"]-card["start"]}" data-track-index="4"><div class="card-layout"><div class="card-copy">{body}</div>{image}</div></section>')
            if row.get('disclosure') is not None:
                scenes.append(f'<p id="disclosure-{id}" class="clip narration-note" data-start="{start}" data-duration="{duration}" data-track-index="12">{esc(row["disclosure"])}</p>')
    for i,cue in enumerate(v.cues):
        text='<p class="zh">'+'<br>'.join(esc(x) for x in cue['zh_lines'])+'</p>'
        if cue['en_lines']: text+='<p class="en">'+'<br>'.join(esc(x) for x in cue['en_lines'])+'</p>'
        captions.append(f'<div id="caption-{i}" class="clip caption" data-start="{cue["start"]}" data-duration="{cue["end"]-cue["start"]}" data-track-index="40" data-layout-allow-caption-zone>{text}</div>')
    template=ROOT/'assets/engine/editorial-motion.html';engine=template.read_text(encoding='utf-8')
    tokens={'@@TOTAL@@':str(v.total),'@@PUBLISHER@@':esc(v.plan['brand']['publisher']),'@@LABEL@@':esc(v.plan['brand']['label']), '@@SCENES@@':''.join(scenes),'@@CAPTIONS@@':''.join(captions), '@@CONFIG@@':json.dumps(dict(reveals=reveals,sources=v.sources,geometry=GEOMETRY),ensure_ascii=False).replace('<','\\u003c')}
    tokens.update({'@@'+k.upper()+'@@':value for k,value in v.palette.items()})
    for key,value in tokens.items(): engine=engine.replace(key,value)
    if '@@' in engine: raise ValueError('Unresolved engine template token')
    # Validate before creating output. All generated content comes from this explicit plan.
    project=output/'motion';assets=project/'assets';assets.mkdir(parents=True);(project/'compositions').mkdir();exports=output/'exports';exports.mkdir();qa=output/'qa';qa.mkdir()
    for row in v.rows:
        shutil.copy2(row['_path'],assets/row['asset'])
        if sha(assets/row['asset'])!=row['media_sha256']: raise ValueError('Media copy checksum failed')
        for card in row.get('cards',[]):
            if card.get('image'): shutil.copy2(card['image']['_path'],assets/card['image']['_asset'])
    shutil.copy2(v.gsap,assets/'gsap.min.js')
    options=subset.Options();options.flavor='woff2';font=subset.load_font(str(v.font),options);sub=subset.Subsetter(options=options);sub.populate(text=engine);sub.subset(font);subset.save_font(font,str(assets/'caption.woff2'),options)
    css=re.search(r'<style>(.*?)</style>',engine,re.S).group(1);body=re.search(r'<body>(.*?)</body>',engine,re.S).group(1)
    (project/'compositions/stage.html').write_text('<!doctype html><html lang="zh-Hant"><head><meta charset="UTF-8"></head><body><template><style>'+css+'</style>'+body+'</template></body></html>',encoding='utf-8')
    (project/'index.html').write_text('<!doctype html><html lang="zh-Hant"><head><meta charset="UTF-8"><title>'+esc(v.plan['title'])+'</title><script src="assets/gsap.min.js"></script><style>html,body{margin:0;overflow:hidden;width:100%;height:100%}#root{position:absolute;inset:0}</style></head><body>'+f'<div id="root" data-composition-id="editorial-film" data-duration="{v.total}" data-width="1920" data-height="1080"><div id="stage-mount" class="clip" data-composition-id="editorial-stage" data-composition-src="compositions/stage.html" data-start="0" data-duration="{v.total}" data-track-index="1" data-width="1920" data-height="1080"></div></div>'+'<script>window.__timelines=window.__timelines||{};window.__timelines["editorial-film"]=gsap.timeline({paused:true});</script></body></html>',encoding='utf-8')
    def public(value):
        if isinstance(value,dict): return {k:public(x) for k,x in value.items() if not k.startswith('_')}
        if isinstance(value,list): return [public(x) for x in value]
        return value
    write(output/'resolved-timeline.json',dict(duration=v.total,timebase='final_seconds',items=public(v.rows),cues=v.cues,sources=v.sources,reveals=reveals,geometry=GEOMETRY))
    shutil.copy2(v.path,output/'editorial-motion.input.json')
    for language in ['zh-TW','en','bilingual']:
        rows=[]
        for cue in v.cues:
            lines=cue['zh_lines'] if language=='zh-TW' else cue['en_lines'] if language=='en' else cue['zh_lines']+cue['en_lines']
            if lines: rows.append(f'{len(rows)+1}\n{srt_time(cue["start"])} --> {srt_time(cue["end"])}\n'+'\n'.join(lines)+'\n')
        (exports/f'subtitles.{language}.srt').write_text('\n'.join(rows),encoding='utf-8')
    (exports/'chapters.txt').write_text('\n'.join(f'{int(r["start"])//60:02d}:{int(r["start"])%60:02d} {r["label"]}' for r in v.rows)+'\n',encoding='utf-8')
    write(qa/'build-report.json',dict(status='built_not_rendered',created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),plan_sha256=sha(v.path),builder_sha256=sha(Path(__file__)),engine_sha256=sha(template),inputs=v.inputs,duration=v.total,item_count=len(v.rows),cue_count=len(v.cues),marker_count=sum(len(x['markers']) for x in v.sources),source_speed=1,media_copy_verification='sha256_identical',audio_processing='none: prepared media copied byte-for-byte',prepared_audio=[dict(item_id=r['id'],**r['prepared_audio']) for r in v.rows],theme=dict(source_id=v.plan['source_id'],registry_sha256=sha(v.asset(v.plan['theme']['registry_path'],'registry')),palette=v.palette),human_listening='not_performed',semantic_faithfulness='requires_human_review',identity_verification='author_declaration_only',publication_authorized=False))
    return project

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('plan');parser.add_argument('--output');parser.add_argument('--validate-only',action='store_true');args=parser.parse_args()
    try:
        validator=Validator(args.plan).validate()
        if args.validate_only: print(json.dumps(dict(status='validated_not_built',item_count=len(validator.rows),duration=validator.total,semantic_faithfulness='requires_human_review',human_listening='not_performed')))
        else:
            if not args.output: parser.error('--output NEW_WORK is required for building')
            print(build(validator,args.output))
    except (ValueError,KeyError,TypeError,subprocess.CalledProcessError) as error: parser.exit(2,'Input/build rejected: '+str(error)+'\n')

if __name__=='__main__': main()
