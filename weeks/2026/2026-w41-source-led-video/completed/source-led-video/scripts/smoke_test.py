"""Exercise observable contracts with a clearly synthetic, silent two-question episode."""
import argparse, copy, json, subprocess, sys, wave
from pathlib import Path
from interview import read,write,WEIGHTS,GATES

HERE=Path(__file__).resolve().parent
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--environment',required=True);args=ap.parse_args();out=Path(args.out).resolve()
    def run(script,*args,ok=True):
        result=subprocess.run([sys.executable,'-X','utf8',str(HERE/script),*map(str,args)],capture_output=True,text=True,encoding='utf-8')
        if (result.returncode==0)!=ok:raise AssertionError(result.stdout+result.stderr)
        return result
    run('interview.py','init','--out',out,'--questions','2','--minimum-seconds','1','--environment',args.environment)
    run('interview.py','init','--out',out,'--questions','2','--minimum-seconds','1',ok=False)
    env=read(out/'environment.json');profile=read(out/'profile.json')
    assert profile['brand']=='' and profile['minimum_duration_seconds']==1
    assert profile['narration']['engine']=='external-audio' and profile['narration']['native_tempo_factor']==1.0
    assert read(out/'thumbnail-brief.json')['reference'] is None
    profile['brand']='field notes';write(out/'profile.json',profile)
    # Two candidate outcomes: unknown AV remains null; a false gate overrides perfect scores.
    scores={key:5 for key in WEIGHTS};scores['audiovisual']=None
    candidate=dict(id='a',source_id='s1',question_id='q01',start=1,end=5,gates=dict(complete_thought=True,context_preserved=True,faithful_claims=True),scores=scores,evidence=dict(transcript='synthetic test fixture',audio_review=None,visual_review=None))
    candidate['gate_reasons']={key:'Synthetic positive fixture only; no real editorial acceptance.' for key in GATES}
    candidate['score_reasons']={key:'Synthetic score contract fixture.' if value is not None else None for key,value in scores.items()}
    rejected=copy.deepcopy(candidate);rejected['id']='b';rejected['gates']['context_preserved']=False
    write(out/'candidates.json',dict(candidates=[candidate,rejected]))
    run('interview.py','score',out/'candidates.json','--out',out/'qa/score-test.json')
    result=read(out/'qa/score-test.json')['results']
    assert result[0]['total_score'] is None and result[0]['observed_weight']==90
    assert result[1]['status']=='reject_or_recut'
    invalid=copy.deepcopy(candidate);invalid['scores']['audiovisual']=5
    invalid['score_reasons']['audiovisual']='Fixture: this must still fail without AV review evidence.'
    write(out/'qa/invalid-score.json',dict(candidates=[invalid]))
    run('interview.py','score',out/'qa/invalid-score.json','--out',out/'qa/invalid-result.json',ok=False)
    unreviewed=copy.deepcopy(candidate);unreviewed['scores']['emotion']=None
    unreviewed['score_reasons']['emotion']=None
    write(out/'qa/unreviewed-score.json',dict(candidates=[unreviewed]))
    run('interview.py','score',out/'qa/unreviewed-score.json','--out',out/'qa/unreviewed-result.json')
    assert read(out/'qa/unreviewed-result.json')['results'][0]['status']=='eligible_pending_review'
    for field in ('gate_reasons','score_reasons','evidence'):
        invalid=copy.deepcopy(candidate);invalid.pop(field)
        write(out/'qa/invalid-score.json',dict(candidates=[invalid]))
        run('interview.py','score',out/'qa/invalid-score.json','--out',out/'qa/invalid-result.json',ok=False)
    for mutation in ('placeholder','missing-gate','null-rationale'):
        invalid=copy.deepcopy(candidate)
        if mutation=='placeholder':invalid['evidence']['transcript']='TODO'
        elif mutation=='missing-gate':invalid['gates'].pop('complete_thought')
        else:invalid['score_reasons']['audiovisual']='Unreviewed score must not have a numeric-score rationale.'
        write(out/'qa/invalid-score.json',dict(candidates=[invalid]))
        run('interview.py','score',out/'qa/invalid-score.json','--out',out/'qa/invalid-result.json',ok=False)
    # Generate small local fixtures; these are never presented as voice or editorial acceptance.
    from PIL import Image,ImageDraw
    for key,color in [('host','#92724c'),('guest','#47736e'),('hook','#c7ba89'),('workflow','#c7ba89')]:
        image=Image.new('RGB',(640,605),color);ImageDraw.Draw(image).rectangle((50,50,590,555),outline='white',width=6);image.save(out/'assets'/f'{key}.png')
    source=out/'media/original.mp4'
    subprocess.run([env['ffmpeg'],'-v','error','-f','lavfi','-i','color=c=0x35524a:s=320x180:r=30:d=12','-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t','12','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(source)],check=True)
    write(out/'sources.json',dict(sources=[dict(id='s1',path=str(source),url='https://example.invalid/synthetic',channel='田野筆記',title='避免灌溉過度',duration_seconds=12,metadata_verified=True)]))
    rows=read(out/'rundown.json')['items'];narr=[]
    for row in rows:
        if row['type']=='source':
            a,b=(1,5) if row['chapter']==1 else (7,11);row.update(**{'in':a,'out':b},title='植物真的需要水嗎？',candidate_id='a' if row['chapter']==1 else 'c')
        else:
            seconds=8 if row['type']!='outro' else 6
            with wave.open(str(out/row['audio_path']),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000);w.writeframes(bytes(seconds*48000*2))
            row.update(title='植物真的需要水嗎？',text='合成測試：這是靜音技術樣本。')
            narr.append(dict(item=row['id'],cues=[dict(start=.1,end=seconds-.1,zh='技術測試；無真實旁白。')]))
            if row['type']=='opening':
                row['text']='田野筆記聚焦園藝，主持人林雨是園藝教育者。她訪問園藝工作者陳禾。先看土壤能避免澆水過量，植物真的需要水嗎？'
                row['card_beats']=[dict(type='chapter',start=0,end=1,title='植物需要水，\n還是需要先觀察？',kicker='本集問題'),dict(type='person',start=1,end=3,name='林雨',role='主持人｜田野筆記',body='園藝教育者',person_role='host',portrait_key='host'),dict(type='person',start=3,end=5,name='陳禾',role='園藝工作者',body='灌溉研究',person_role='guest',portrait_key='guest'),dict(type='chapter',start=5,end=8,title='灌溉以前，\n先確認什麼？',kicker='第一個問題')]
            elif row['type']=='bridge':row['visual']=dict(layout='compare',lines=['葉子變黃，','一定缺水嗎？'],nodes=['土壤乾燥','根部缺氧'])
    write(out/'rundown.json',dict(items=rows))
    # Authored context is synthetic; the WAVs remain silent and unreviewed.
    narration_plan=dict(schema_version='1.0',terminology_reviewed=True,terms=[],opening=dict(source_format='interview',source_published_at='2026-10-08',host=dict(name='林雨',program='田野筆記',positioning='聚焦園藝',credibility='園藝教育者',evidence='Synthetic fictional host fixture.'),guest=dict(name='陳禾',role='園藝工作者',role_as_of='2026-10-08',evidence='Synthetic fictional guest fixture.'),why_now=dict(explanation='先看土壤能避免澆水過量',time_basis='evergreen',evidence='Synthetic source fixture.',verified_at=None),coverage=dict(host_excerpt='田野筆記聚焦園藝，主持人林雨是園藝教育者。',guest_excerpt='她訪問園藝工作者陳禾。',why_now_excerpt='先看土壤能避免澆水過量',question_excerpt='植物真的需要水嗎？')))
    write(out/'narration-plan.json',narration_plan)
    (out/'voice/approved-narration.txt').write_text('\n\n'.join(row['text'] for row in rows if row['type']!='source'),encoding='utf-8')
    c=copy.deepcopy(candidate);c.update(id='c',question_id='q02',start=7,end=11)
    write(out/'candidates.json',dict(candidates=[candidate,c]))
    write(out/'questions.json',dict(questions=[dict(id='q01',order=1,question='植物真的需要水嗎？'),dict(id='q02',order=2,question='葉子變黃，一定缺水嗎？')]))
    from opening_selection import WEIGHTS as OPENING_WEIGHTS
    choices=[]
    for qid,item,grade in [('q01','c01-01',5),('q02','c02-01',3)]:
        gates=dict(promise_supported=True,answer_present=True,context_preserved=True)
        choices.append(dict(question_id=qid,first_source_item=item,gates=gates,gate_reasons={k:'Synthetic review fixture, not real editorial acceptance.' for k in gates},scores={k:grade for k in OPENING_WEIGHTS},score_reasons={k:'Synthetic comparison fixture.' for k in OPENING_WEIGHTS},evidence='Synthetic transcript fixture 1–11 seconds.'))
    write(out/'opening-selection.json',dict(packaging=dict(title='先觀察，再澆水',thumbnail_promise='植物真的需要水嗎？',viewer_question='先確認土壤狀態'),coverage=dict(whole_source_reviewed=True,evidence='Complete synthetic 12s fixture reviewed for this test.'),candidates=choices,selected_question_id='q01',selected_source_item='c01-01',selection_reason='The synthetic first question directly answers the authored packaging promise.'))
    write(out/'subtitles/narration.json',dict(items=narr))
    write(out/'subtitles/source.json',dict(cues=[dict(source_id='s1',start=1,end=5,zh='觀察土壤再決定。',en='Observe the soil first.'),dict(source_id='s1',start=7,end=11,zh='避免讓根部積水。',en='Avoid waterlogged roots.')]))
    write(out/'art-direction.json',dict(assets={x:f'assets/{x}.png' for x in ('host','guest','hook','workflow')},source_channel='田野筆記',source_topic_lines=['先看土壤，','再決定是否澆水'],guest_line='陳禾｜園藝工作者',runtime_label='測試來源 0:12'))
    write(out/'markers.json',dict(review=[dict(item='c01-01',decision='annotate',reason='The fixture introduces a two-step decision worth showing in order.',source_evidence='Synthetic cue: observe the soil first, source 1–5s.',marker_ids=['soil']),dict(item='c02-01',decision='keep_source',reason='A single short conclusion needs no additional list.',source_evidence='Synthetic cue: avoid waterlogged roots, source 7–11s.',marker_ids=[])],markers=[dict(id='soil',item='c01-01',start=1.8,end=4.1,type='pair',eyebrow='先觀察',steps=[dict(at=1.8,text='檢查土壤'),dict(at=2.8,text='再決定用水')])]))
    run('interview.py','cut',out)
    # A rejected candidate must not pass the actual timeline resolver.
    bad=copy.deepcopy(candidate);bad['gates']['faithful_claims']=False
    write(out/'candidates.json',dict(candidates=[bad,c]));run('interview.py','resolve',out,ok=False)
    write(out/'candidates.json',dict(candidates=[candidate,c]))
    bad_narration=copy.deepcopy(narration_plan);bad_narration['opening']['coverage']['host_excerpt']='Only present on a visual card, absent from narration.'
    write(out/'narration-plan.json',bad_narration);run('interview.py','resolve',out,ok=False)
    assert not read(out/'qa/narration-preflight.json')['passed']
    write(out/'narration-plan.json',narration_plan);run('interview.py','resolve',out)
    assert read(out/'qa/narration-preflight.json')['passed']
    run('interview.py','check',out)
    blank=copy.deepcopy(profile);blank['brand']='';write(out/'profile.json',blank)
    result=run('build_film.py',out,ok=False);assert 'profile.brand' in result.stderr
    write(out/'profile.json',profile);run('build_film.py',out)
    pages='\n'.join(p.read_text(encoding='utf-8') for p in (out/'motion/compositions').glob('*.html'))
    assert 'field notes' in pages and '02/02' in pages and '01/05' not in pages
    plan=read(out/'qa/resolved-plan.json');assert plan['frames']==round(plan['duration']*30)
    write(out/'qa/smoke-report.json',dict(passed=True,contracts=['no-overwrite','null-score','gate-priority','AV-evidence-required','all-missing-dimensions-reported','transcript-and-reasons-required','placeholder-rejected','explicit-gate-keys','unknown-score-reason-null','rejected-candidate-cannot-resolve','measured-frame-alignment','blank-brand-authoring-default','external-audio-default','no-forced-minimum-duration','no-personal-thumbnail-reference','build-requires-authored-brand','fresh-episode-content','dynamic-question-count','opening-context-must-be-spoken','narration-plan-integrates-with-build'],fixture='synthetic silent local media; no real provider or audiovisual acceptance',browser_check='run separately'))
    print(json.dumps(dict(passed=True,workdir=str(out),duration=plan['duration'],project=str(out/'motion')),ensure_ascii=False))
if __name__=='__main__':main()
