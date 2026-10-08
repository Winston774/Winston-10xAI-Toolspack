"""Local, stdlib-first production helpers. Never uploads or invokes TTS implicitly."""
from __future__ import annotations
import argparse, copy, hashlib, importlib.util, json, math, os, re, shutil, subprocess, sys, wave, zipfile
from pathlib import Path
from configure import default_config, normalize

SKILL=Path(__file__).resolve().parents[1]
WEIGHTS=dict(content_value=25,specificity=15,standalone=15,hook=10,narrative=10,emotion=5,actionability=10,audiovisual=10)
GATES=('complete_thought','context_preserved','faithful_claims')
NARRATION_REVIEW_CONTRACT='host-context-original-language-v1'
NARRATION_SNAPSHOT_FILES=('rundown.json','profile.json','narration-plan.json',
                          'voice/approved-narration.txt','subtitles/narration.json')

def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,data):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def resolved(root,p):
    if not p: raise ValueError('Required local path is empty')
    value=Path(p);return value.resolve() if value.is_absolute() else (root/value).resolve()
def safe_id(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}',value):raise ValueError(f'Invalid id: {value!r}')
    return value
def candidate_evidence(c):
    cid=safe_id(c['id']);evidence=c.get('evidence',{})
    if not isinstance(evidence.get('transcript'),str) or not evidence['transcript'].strip():raise ValueError(f'{cid}: evidence.transcript must locate source text or transcript with timestamps')
    if evidence['transcript'].strip().lower() in {'todo','tbd','unknown','待補','待確認','未提供'}:raise ValueError(f'{cid}: transcript placeholder is not source evidence')
    if set(c.get('gates',{}))!=set(GATES):raise ValueError(f'{cid}: provide all three gate keys, using null for unknown')
    for gate in GATES:
        value=c.get('gates',{}).get(gate)
        if value is not None and type(value) is not bool:raise ValueError(f'{cid}: gate {gate} must be true, false or null')
        reason=c.get('gate_reasons',{}).get(gate)
        if not isinstance(reason,str) or not reason.strip():raise ValueError(f'{cid}: provide gate_reasons.{gate}, including why an unknown gate needs review')
    for key,value in c.get('scores',{}).items():
        if value is not None:
            reason=c.get('score_reasons',{}).get(key)
            if not isinstance(reason,str) or not reason.strip():raise ValueError(f'{cid}: provide score_reasons.{key} for each numeric score')
        elif c.get('score_reasons',{}).get(key) is not None:raise ValueError(f'{cid}: score_reasons.{key} must be null when the score is unknown; track missing evidence separately')
def finite(value,label):
    if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value):raise ValueError(f'{label} must be a finite number')
    return float(value)
def probe(path,env):
    return json.loads(subprocess.check_output([env['ffprobe'],'-v','error','-show_format','-show_streams','-of','json',str(path)],encoding='utf-8'))
def duration(path,env):
    if not path.is_file():raise FileNotFoundError(path)
    if path.suffix.lower()=='.wav':
        with wave.open(str(path),'rb') as w:return w.getnframes()/w.getframerate()
    return float(probe(path,env)['format']['duration'])

def scaffold_rows(questions,profile):
    voice=profile['narration'];rows=[]
    for chapter,q in enumerate(questions,1):
        qid=safe_id(q['id']);title=q.get('question','')
        rows.append(dict(id=f'i{chapter:02d}',type='opening' if chapter==1 else 'bridge',chapter=chapter,question_id=qid,question=title,title=title,text='',audio_path=f'voice/i{chapter:02d}.wav',lead=voice['lead_seconds'],tail=voice['tail_seconds'],card_beats=[] if chapter==1 else None,visual=dict(layout='question',lines=[],nodes=[])))
        rows.append(dict(id=f'c{chapter:02d}-01',type='source',chapter=chapter,question_id=qid,title=title,source_id='s1',**{'in':None,'out':None},clip_path=f'media/c{chapter:02d}-01.mp4',candidate_id=None))
    if questions:rows.append(dict(id='o01',type='outro',chapter=len(questions),title='觀看完整版與訂閱頻道',text='',audio_path='voice/o01.wav',lead=voice['lead_seconds'],tail=voice['outro_tail_seconds']))
    return rows

def plan_questions(args):
    root=Path(args.workdir).resolve();questions=read(root/'questions.json')['questions'];profile=read(root/'profile.json')
    if not questions:raise ValueError('Review the whole source and author questions.json before planning; no fixed question quota')
    ids=[safe_id(q['id']) for q in questions]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate question IDs')
    if any(not q.get('question','').strip() for q in questions):raise ValueError('Every planned question needs an authored question')
    if read(root/'rundown.json')['items']:raise FileExistsError('Existing rundown is not empty; preserve and edit it deliberately')
    orders=[q.get('order') for q in questions]
    if any(type(order) is not int for order in orders) or sorted(orders)!=list(range(1,len(questions)+1)):raise ValueError('Question order must be a unique contiguous 1..N sequence')
    questions=sorted(questions,key=lambda q:q['order'])
    write(root/'rundown.json',dict(items=scaffold_rows(questions,profile)))
    print(json.dumps(dict(questions=len(questions),status='scaffolded_from_authored_questions',next='Author source cuts and opening-selection.json; the first answer must match the selected packaging promise'),ensure_ascii=False))

def init(args):
    out=Path(args.out).resolve()
    if out.exists():raise FileExistsError(f'Refusing to overwrite existing workdir: {out}')
    profile=read(args.profile or SKILL/'templates/profile.json')
    questions=args.questions if args.questions is not None else profile.get('default_question_count')
    minimum=args.minimum_seconds if args.minimum_seconds is not None else profile['minimum_duration_seconds']
    if questions is not None and (type(questions) is not int or questions<1):raise ValueError('questions must be a positive integer when explicitly requested; otherwise leave it undecided')
    if finite(minimum,'minimum-seconds')<=0:raise ValueError('minimum-seconds must be positive')
    profile.update(minimum_duration_seconds=minimum,default_question_count=questions)
    if args.brand is not None:
        if not args.brand.strip():raise ValueError('brand must be nonempty')
        profile['brand']=args.brand.strip()
    voice=profile['narration']
    if args.narration_tempo is not None:voice['native_tempo_factor']=finite(args.narration_tempo,'narration-tempo')
    if not .5<=finite(voice['native_tempo_factor'],'native_tempo_factor')<=2:raise ValueError('Narration tempo must be 0.5..2; adjust only after listening')
    for key in ('lead_seconds','tail_seconds','outro_tail_seconds'):
        if finite(voice[key],key)<0:raise ValueError(f'{key} must be nonnegative')
    requested=args.environment or os.environ.get('SOURCE_LED_VIDEO_ENV')
    env_path=Path(requested).expanduser().resolve() if requested else default_config()
    if requested and not env_path.is_file():raise FileNotFoundError(env_path)
    if not env_path.is_file():env_path=SKILL/'templates/environment.json'
    environment=normalize(read(env_path),env_path.parent)
    out.mkdir(parents=True)
    for f in ['assets','media','voice','subtitles','qa','exports','research']:(out/f).mkdir()
    write(out/'profile.json',profile)
    write(out/'environment.json',environment)
    write(out/'qa/config-origin.json',dict(environment=str(env_path),profile=str(Path(args.profile).resolve()) if args.profile else 'bundled profile',environment_sha256=hashlib.sha256(env_path.read_bytes()).hexdigest()))
    write(out/'brief.json',dict(episode_id=out.name,title='',audience='',promise='',source_url=args.source_url,approved=[],requested_changes=[],status='authoring'))
    write(out/'sources.json',dict(sources=[dict(id='s1',url=args.source_url,path=None,title='',channel='',duration_seconds=None,metadata_verified=False,transcript_path=None)]))
    authored=[dict(id=f'q{i:02d}',order=i,question='',viewer_pain='',key_answer='',packaging_promise=None) for i in range(1,(questions or 0)+1)]
    write(out/'questions.json',dict(selection_policy='content-led; no fixed quota',questions=authored))
    write(out/'candidates.json',dict(weights=WEIGHTS,candidates=[]))
    write(out/'rundown.json',dict(items=scaffold_rows(authored,profile)))
    write(out/'opening-selection.json',read(SKILL/'templates/opening-selection.json'))
    thumbnail=read(SKILL/'templates/thumbnail-brief.json');thumbnail.update(brand=profile['brand'],style=profile['thumbnail_style'])
    write(out/'thumbnail-brief.json',thumbnail)
    write(out/'narration-plan.json',read(SKILL/'templates/narration-plan.json'))
    write(out/'art-direction.json',dict(assets=dict(host=None,guest=None,hook=None,workflow=None),source_channel='',source_topic_lines=[],guest_line='',runtime_label='',source_topic_label='內容導讀'))
    write(out/'markers.json',dict(clock='original source seconds',review=[],markers=[]))
    write(out/'subtitles/source.json',dict(cues=[]))
    write(out/'subtitles/narration.json',dict(items=[]))
    write(out/'qa/film-scorecard.json',read(SKILL/'templates/film-scorecard.json'))
    print(json.dumps(dict(created=str(out),next='Fill brief, sources, questions, candidates, and rundown from source evidence; read references/quickstart.md'),ensure_ascii=False))

def score(args):
    data=read(args.input);weights=data.get('weights',WEIGHTS)
    if set(weights)!=set(WEIGHTS) or any(finite(v,k)<0 for k,v in weights.items()) or sum(weights.values())!=100:raise ValueError('Weights must cover the 8 dimensions and sum to 100')
    output=[];ids=set()
    for c in data['candidates']:
        cid=safe_id(c['id'])
        candidate_evidence(c)
        if cid in ids:raise ValueError('Duplicate candidate id')
        ids.add(cid)
        if finite(c['end'],'end')<=finite(c['start'],'start') or c['start']<0:raise ValueError(f'Invalid source range: {cid}')
        gates=c.get('gates',{});scores=c.get('scores',{});evidence=c.get('evidence',{})
        if set(scores)!=set(weights):raise ValueError(f'{cid}: provide all dimensions, using null for unknown')
        observed=0;known_sum=0
        for key,weight in weights.items():
            value=scores[key]
            if value is None:continue
            if not 0<=finite(value,key)<=5:raise ValueError(f'{cid}: score {key} outside 0..5')
            if key=='audiovisual' and not (evidence.get('visual_review') and evidence.get('audio_review')):raise ValueError(f'{cid}: audiovisual needs both listening and viewing evidence; use null')
            known_sum+=weight*value/5;observed+=weight
        for gate in GATES:
            if gates.get(gate) not in (True,False,None):raise ValueError(f'{cid}: gate {gate} must be true, false or null')
        failed=[g for g in GATES if gates.get(g) is False]
        unknown=[g for g in GATES if gates.get(g) is None]
        missing=[key for key,value in scores.items() if value is None]
        status='reject_or_recut' if failed else 'needs_gate_review' if unknown else 'eligible' if observed==100 else 'eligible_pending_av' if missing==['audiovisual'] else 'eligible_pending_review'
        output.append(dict(id=cid,status=status,gate_failures=failed,unreviewed_gates=unknown,unreviewed_dimensions=missing,total_score=round(known_sum,2) if observed==100 else None,observed_weight=observed,lower_bound=round(known_sum,2),upper_bound=round(known_sum+100-observed,2),source_range=[c['start'],c['end']]))
    report=dict(schema_version='1.0',unit='source_candidate',weights=weights,results=output,note='Unknown dimensions are not rescaled; gates override numeric score; this is not the finished-film score.')
    write(args.out,report);print(json.dumps(report,ensure_ascii=False))

def doctor(args):
    root=Path(args.workdir).resolve();env=read(root/'environment.json');rows=[]
    for extra in env.get('python_extra_paths',[]):
        folder=resolved(root,extra)
        if folder.is_dir():sys.path.insert(0,str(folder))
    for key in ['python','ffmpeg','ffprobe','npx','gsap_js','sans_ttf','serif_ttf','voice_tool']:
        p=env.get(key);path=None
        if p:path=Path(shutil.which(p) or resolved(root,p))
        found=bool(path and path.is_file())
        rows.append(dict(id=key,configured=p,available=found))
    for module in ['fontTools','brotli','PIL']:
        rows.append(dict(id='python:'+module,available=bool(importlib.util.find_spec(module)),note='current interpreter'))
    available={r['id']:r['available'] for r in rows}
    def capability(keys,limit):
        return dict(dependencies_found=all(available[k] for k in keys),missing=[k for k in keys if not available[k]],execution_verified=False,limit=limit)
    capabilities=dict(
        planning=dict(available=True,note='stdlib metadata, scoring, rundown authoring'),
        source_cut=capability(['ffmpeg','ffprobe'],'Executable files found; cutting/codec access has not been tested by doctor.'),
        visual_build=capability(['gsap_js','sans_ttf','serif_ttf','python:fontTools','python:brotli'],'Uses the current Python interpreter; no build performed by doctor.'),
        rendering=capability(['npx'],'HyperFrames package, browser, GPU, and real rendering remain untested.'),
        external_narration=dict(accepts='Prepared local WAV files from recording or an authorized TTS tool',configured_tool=env.get('voice_tool'),execution_verified=False,note='No voice tool is required for planning or consuming prepared WAVs. Synthesis, access, licensing, and pronunciation are not tested.'),
        review_frames=capability(['python:PIL'],'Image library available in current interpreter; no visual acceptance inferred.'))
    report=dict(checks=rows,capabilities=capabilities,current_interpreter=sys.executable,configured_python=env.get('python'),ready_for_build=capabilities['visual_build']['dependencies_found'],environment_unchanged=True,read_only=True,note='Only local paths/import availability inspected; writes this QA report. No install, download, model load, or synthesis.')
    write(root/'qa/doctor.json',report);print(json.dumps(report,ensure_ascii=False,indent=2))

def inputs(root):return read(root/'profile.json'),read(root/'environment.json'),read(root/'rundown.json')['items'],{s['id']:s for s in read(root/'sources.json')['sources']}
def cut(args):
    root=Path(args.workdir).resolve();profile,env,rows,sources=inputs(root);fps=profile['canvas']['fps'];result=[]
    for row in rows:
        if row['type']!='source':continue
        safe_id(row['id']);src=resolved(root,sources[row['source_id']]['path']);a=finite(row['in'],'in');b=finite(row['out'],'out')
        if a<0 or b<=a or b>duration(src,env)+.05:raise ValueError(f'Invalid cut range {row["id"]}')
        out=resolved(root,row['clip_path'])
        if out.exists():raise FileExistsError(f'Cut already exists; inspect/reuse deliberately: {out}')
        if not out.is_relative_to(root):raise ValueError('New cut outputs must remain inside episode directory')
        out.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run([env['ffmpeg'],'-v','error','-ss',str(a),'-i',str(src),'-t',str(b-a),'-map','0:v:0','-map','0:a:0','-vf',f'fps={fps}','-c:v','libx264','-crf','18','-preset','medium','-g',str(fps),'-keyint_min',str(fps),'-sc_threshold','0','-c:a','aac','-b:a','192k','-movflags','+faststart',str(out)],check=True)
        result.append(dict(id=row['id'],path=str(out),source_range=[a,b],sha256=hashlib.file_digest(out.open('rb'),'sha256').hexdigest()))
    write(root/'qa/cuts.json',dict(cuts=result,source_playback_rate=1));print(json.dumps(dict(cuts=len(result)),ensure_ascii=False))

def check_narration_plan(root,profile):
    # New episodes opt into the contract via their versioned profile; legacy episodes remain readable.
    if profile.get('narration_review_contract')!=NARRATION_REVIEW_CONTRACT:return
    from check_narration import audit
    root=Path(root);text_file=root/'voice/approved-narration.txt'
    # Production stages require the retained input file; only standalone drafting permits omission.
    report=audit(root,text_file=text_file)
    write(root/'qa/narration-preflight.json',report)
    if not report['passed']:raise ValueError('Narration context or original-language terms need correction; inspect qa/narration-preflight.json')

def narration_input_snapshot(root,profile):
    """Bind resolved narration to its authored inputs and current delivery WAV bytes."""
    if profile.get('narration_review_contract')!=NARRATION_REVIEW_CONTRACT:return None
    root=Path(root).resolve()
    def digest(path):
        with Path(path).open('rb') as stream:
            sha=hashlib.sha256()
            for block in iter(lambda:stream.read(1024*1024),b''):sha.update(block)
            return sha.hexdigest()
    try:
        files={name:digest(root/name) for name in NARRATION_SNAPSHOT_FILES}
        audio=[]
        for row in read(root/'rundown.json')['items']:
            if row['type']=='source':continue
            path=resolved(root,row['audio_path'])
            audio.append(dict(item=row['id'],audio_path=str(path),sha256=digest(path)))
    except (OSError,ValueError,KeyError,TypeError) as exc:
        raise ValueError(f'Cannot snapshot narration inputs: {exc}. Correct the inputs and run interview.py resolve again.') from exc
    return dict(schema_version='1.0',contract=NARRATION_REVIEW_CONTRACT,files=files,audio=audio)

def check_narration_snapshot(root,profile,plan):
    """Reject stale resolved narration before a new-contract build consumes it."""
    if profile.get('narration_review_contract')!=NARRATION_REVIEW_CONTRACT:return
    saved=plan.get('narration_input_snapshot')
    if not isinstance(saved,dict):
        raise ValueError('Resolved plan lacks a narration input snapshot; run interview.py resolve again before building.')
    if saved!=narration_input_snapshot(root,profile):
        raise ValueError('Narration inputs or WAV bytes changed since resolve; run interview.py resolve again before building.')

def resolve(args):
    root=Path(args.workdir).resolve();profile,env,rows,sources=inputs(root);fps=profile['canvas']['fps']
    from opening_selection import validate_opening
    opening_report=validate_opening(root,rows)
    write(root/'qa/opening-selection.json',opening_report)
    if not opening_report['valid']:raise ValueError('Opening selection is incomplete or mismatched; inspect qa/opening-selection.json')
    check_narration_plan(root,profile)
    narration_snapshot=narration_input_snapshot(root,profile)
    if fps!=30 or profile['canvas']['width']!=1920 or profile['canvas']['height']!=1080:raise ValueError('v1 visual builder supports 1920x1080 at 30 fps; adapt and verify before changing canvas')
    source_cues=read(root/'subtitles/source.json')['cues'];nc={x['item']:x['cues'] for x in read(root/'subtitles/narration.json')['items']}
    candidates={x['id']:x for x in read(root/'candidates.json')['candidates']}
    timeline=[];cues=[];frame=0;ids=set()
    for row in rows:
        rid=safe_id(row['id'])
        if rid in ids:raise ValueError('Duplicate rundown id')
        ids.add(rid);kind=row['type'];it=copy.deepcopy(row);it['start']=frame/fps
        if not row.get('title'):raise ValueError(f'{rid}: title is required')
        if kind=='source':
            source=sources[row['source_id']];a=finite(row['in'],'in');b=finite(row['out'],'out')
            candidate=candidates.get(row.get('candidate_id'))
            if not candidate or any(candidate.get('gates',{}).get(g) is not True for g in GATES):raise ValueError(f'{rid}: selected candidate must pass all semantic gates')
            candidate_evidence(candidate)
            if candidate['source_id']!=row['source_id'] or abs(candidate['start']-a)>.03 or abs(candidate['end']-b)>.03:raise ValueError(f'{rid}: changed cut boundaries require an updated candidate review')
            if a<0 or b<=a:raise ValueError(f'{rid}: bad source range')
            if source.get('duration_seconds') is not None and b>source['duration_seconds']+.05:raise ValueError(f'{rid}: cut exceeds source metadata duration')
            media=resolved(root,row['clip_path']);raw=b-a
            if abs(duration(media,env)-raw)>.15:raise ValueError(f'{rid}: prepared clip duration differs from requested source range')
            it.update(kind='source',source_start=a,source_end=b,media_path=str(media),source_credit=str(source.get('credit_label') or '原片：')+source['channel'])
            selected=[c for c in source_cues if c['source_id']==row['source_id'] and c['end']>a+.001 and c['start']<b-.001]
            if not selected:raise ValueError(f'{rid}: source subtitles are required')
            for c in selected:
                if c['start']<a-.03 or c['end']>b+.03:raise ValueError(f'{rid}: subtitle crosses cut; author a faithful boundary cue before resolving')
                cues.append(dict(start=it['start']+max(0,c['start']-a),end=it['start']+min(raw,c['end']-a),zh=c['zh'],en=c.get('en_display',c.get('en','')),kind='source',item=rid))
        elif kind in ('opening','bridge','outro'):
            if not row.get('text'):raise ValueError(f'{rid}: narration text is required')
            audio=resolved(root,row['audio_path']);speech=duration(audio,env);lead=finite(row.get('lead',.4),'lead');tail=finite(row.get('tail',2 if kind=='outro' else .9),'tail')
            if min(lead,tail)<0:raise ValueError('Lead/tail must be nonnegative')
            raw=lead+speech+tail
            it.update(kind='outro' if kind=='outro' else 'intro',audio_path=str(audio),audio_lead=lead,tail_hold=tail,speech_duration=speech,speech_start=it['start']+lead,speech_end=it['start']+lead+speech)
            if rid not in nc or not nc[rid]:raise ValueError(f'{rid}: narration subtitles are required')
            for c in nc[rid]:
                if not 0<=c['start']<c['end']<=speech+.02:raise ValueError(f'{rid}: subtitle outside measured voice')
                cues.append(dict(start=it['speech_start']+c['start'],end=min(it['speech_end'],it['speech_start']+c['end']),zh=c['zh'],en='',kind=it['kind'],item=rid))
            if kind=='opening':
                if rid!='i01' or len(it.get('card_beats') or [])<3:raise ValueError('Opening must be i01 with authored hook/person/question beats aligned to actual speech')
                beats=it['card_beats']
                for index,b in enumerate(beats):
                    if not 0<=b['start']<b['end']<=speech+.02:raise ValueError('Opening beat outside actual voice')
                    if index and abs(b['start']-beats[index-1]['end'])>.03:raise ValueError('Opening beats must be contiguous')
                if abs(beats[0]['start'])>.001 or abs(beats[-1]['end']-speech)>.03:raise ValueError('Opening beats must cover actual speech')
        else:raise ValueError(f'Unknown type: {kind}')
        it['raw_duration']=raw;it['frames']=math.ceil(raw*fps-1e-8);it['duration']=it['frames']/fps
        frame+=it['frames'];it['end']=frame/fps;timeline.append(it)
    total=frame/fps
    if total<profile['minimum_duration_seconds']:raise ValueError(f'Measured film {total:.3f}s is below required {profile["minimum_duration_seconds"]}s. Revisit source selection; do not add filler.')
    plan=dict(schema_version='1.0',brand=profile['brand'],duration=total,frames=frame,fps=fps,minimum_duration_seconds=profile['minimum_duration_seconds'],voice_status='authored-local-audio',timeline=timeline)
    if narration_snapshot is not None:
        plan['narration_input_snapshot']=narration_snapshot
        # A WAV or script edited while probing must not be recorded as the measured input.
        check_narration_snapshot(root,profile,plan)
    cues.sort(key=lambda c:(c['start'],c['end']))
    for i,c in enumerate(cues):
        if c['end']<=c['start'] or (i and c['start']<cues[i-1]['end']-.03):raise ValueError('Caption overlap or invalid time')
    write(root/'qa/resolved-plan.json',plan);write(root/'subtitles/timeline.json',dict(cues=cues))
    def stamp(t):
        ms=round(t*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
        return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'
    for lang in ('zh','en'):
        selected=[c for c in cues if c.get(lang)]
        (root/'exports'/f'full-{lang}.srt').write_text('\n\n'.join(f'{i+1}\n{stamp(c["start"])} --> {stamp(c["end"])}\n{c[lang]}' for i,c in enumerate(selected))+'\n',encoding='utf-8')
    chapter_lines=[];rundown_lines=['# 實測 Rundown','', '| 場景 | 起點 | 終點 | 類型 | 問題／標題 | 來源／旁白 |','|---|---:|---:|---|---|---|']
    for it in timeline:
        if it['type'] in ('opening','bridge','outro'):
            sec=int(it['start']);chapter_lines.append(f'{sec//60:02d}:{sec%60:02d} {it["title"]}')
        evidence=f'{it["source_id"]} {it["source_start"]:.2f}–{it["source_end"]:.2f}' if it['kind']=='source' else it['text']
        rundown_lines.append(f'| {it["id"]} | {it["start"]:.3f} | {it["end"]:.3f} | {it["type"]} | {it["title"].replace("|","／")} | {evidence.replace("|","／").replace(chr(10)," ")} |')
    (root/'exports/chapters.txt').write_text('\n'.join(chapter_lines)+'\n',encoding='utf-8')
    (root/'qa/rundown.resolved.md').write_text('\n'.join(rundown_lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(duration=total,frames=frame,scenes=len(timeline),cues=len(cues)),ensure_ascii=False))

def check(args):
    root=Path(args.workdir).resolve();plan=read(root/'qa/resolved-plan.json');fps=plan['fps'];cursor=0
    for row in plan['timeline']:
        if abs(row['start']-cursor/fps)>.001:raise ValueError('Timeline gap/overlap')
        if row['frames']<=0 or abs(row['duration']-row['frames']/fps)>.001:raise ValueError('Invalid frame alignment')
        if not Path(row['media_path'] if row['kind']=='source' else row['audio_path']).is_file():raise FileNotFoundError(row['id'])
        cursor+=row['frames']
        if abs(row['end']-cursor/fps)>.001:raise ValueError('End time mismatch')
    if cursor!=plan['frames'] or cursor/fps<plan['minimum_duration_seconds']:raise ValueError('Duration/frame requirement failed')
    cues=read(root/'subtitles/timeline.json')['cues']
    for i,c in enumerate(cues):
        if not 0<=c['start']<c['end']<=plan['duration']+.001 or not c.get('zh'):raise ValueError('Invalid caption')
        if i and c['start']<cues[i-1]['end']-.03:raise ValueError('Caption overlap')
    report=dict(structural_pass=True,duration=plan['duration'],frames=cursor,semantic_review='not inferred',audio_listening=False,continuous_viewing=False)
    if args.video:
        env=read(root/'environment.json');video=Path(args.video).resolve();p=probe(video,env);v=next(x for x in p['streams'] if x['codec_type']=='video');a=next(x for x in p['streams'] if x['codec_type']=='audio')
        if (v['width'],v['height'],v['r_frame_rate'])!=(1920,1080,'30/1') or int(v.get('nb_frames',-1))!=plan['frames'] or abs(float(p['format']['duration'])-plan['duration'])>.034:raise ValueError('Final media differs from resolved timeline')
        report.update(file=str(video),sha256=hashlib.file_digest(video.open('rb'),'sha256').hexdigest(),audio_codec=a['codec_name'])
        if args.decode:
            done=subprocess.run([env['ffmpeg'],'-v','error','-i',str(video),'-map','0:v:0','-map','0:a:0','-f','null','-'],capture_output=True,text=True)
            if done.returncode or done.stderr.strip():raise RuntimeError(done.stderr[-2000:])
            report['full_decode_passed']=True
    write(root/'qa/structural-check.json',report);print(json.dumps(report,ensure_ascii=False))

def package(args):
    target=Path(args.out).resolve();manifest_path=target.with_suffix('.manifest.json')
    if target.suffix.lower()!='.zip':raise ValueError('Package output must use .zip')
    for output in (target,manifest_path):
        if output.exists():raise FileExistsError(f'Refusing to overwrite {output}')
        if output.is_relative_to(SKILL.resolve()):raise ValueError('Archive and manifest must be outside skill directory')
    files=[];manifest=[]
    forbidden={'.wav','.mp3','.mp4','.safetensors','.pt','.ckpt','.env','.zip'}
    for p in SKILL.rglob('*'):
        if p.is_symlink() or getattr(p,'is_junction',lambda:False)():raise ValueError(f'Linked paths cannot be packaged: {p}')
        if not p.resolve().is_relative_to(SKILL.resolve()):raise ValueError(f'Path escapes the skill: {p}')
        if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc':continue
        relative=p.relative_to(SKILL)
        if any(part.startswith('.') for part in relative.parts) or p.suffix.lower() in forbidden or p.stat().st_size>15_000_000:raise ValueError(f'Unexpected private, hidden, large, or nested artifact: {p}')
        name=relative.as_posix()
        if name.startswith('/') or '..' in relative.parts:raise ValueError('Unsafe archive entry')
        blob=p.read_bytes();files.append((name,blob));manifest.append(dict(path=name,bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest()))
    if not files:raise ValueError('Empty skill cannot be packaged')
    target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,strict_timestamps=False) as archive:
        for name,blob in sorted(files):archive.writestr(SKILL.name+'/'+name,blob)
    # Reopen the finished archive and compare entry count, safe paths, byte sizes and SHA-256.
    with zipfile.ZipFile(target,'r') as archive:
        expected={SKILL.name+'/'+row['path']:row for row in manifest}
        if len(archive.namelist())!=len(expected) or set(archive.namelist())!=set(expected):raise ValueError('Archive inventory verification failed')
        if archive.testzip() is not None:raise ValueError('Archive CRC verification failed')
        for info in archive.infolist():
            row=expected[info.filename];blob=archive.read(info)
            if len(blob)!=row['bytes'] or hashlib.sha256(blob).hexdigest()!=row['sha256']:raise ValueError('Archive content verification failed: '+info.filename)
    report=dict(skill=SKILL.name,files=manifest,zip_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),zip_reopened_and_verified=True)
    with manifest_path.open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print(json.dumps(dict(archive=str(target),manifest=str(manifest_path),files=len(files),bytes=target.stat().st_size,zip_reopened_and_verified=True),ensure_ascii=False))

def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='command',required=True)
    p=sub.add_parser('init');p.add_argument('--out',required=True);p.add_argument('--source-url',default='');p.add_argument('--questions',type=int);p.add_argument('--minimum-seconds',type=float);p.add_argument('--profile');p.add_argument('--environment');p.add_argument('--brand');p.add_argument('--narration-tempo',type=float);p.set_defaults(run=init)
    p=sub.add_parser('score');p.add_argument('input');p.add_argument('--out',required=True);p.set_defaults(run=score)
    for name,func in [('plan',plan_questions),('doctor',doctor),('cut',cut),('resolve',resolve),('check',check)]:
        p=sub.add_parser(name);p.add_argument('workdir');p.set_defaults(run=func)
        if name=='check':p.add_argument('--video');p.add_argument('--decode',action='store_true')
    p=sub.add_parser('package');p.add_argument('--out',required=True);p.set_defaults(run=package)
    args=ap.parse_args()
    try:args.run(args)
    except (ValueError,KeyError,FileNotFoundError,FileExistsError,RuntimeError,subprocess.CalledProcessError) as exc:
        print(f'ERROR: {exc}',file=sys.stderr);return 2
    return 0
if __name__=='__main__':raise SystemExit(main())
