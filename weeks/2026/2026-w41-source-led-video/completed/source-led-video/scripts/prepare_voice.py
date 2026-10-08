"""Split a completed recorded or generated PCM master by reviewed sample boundaries; apply tempo once."""
import argparse,hashlib,subprocess,wave
from pathlib import Path
from interview import read,write,resolved,safe_id,finite,check_narration_plan
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('workdir');ap.add_argument('--segments',default='voice/segments.json');ap.add_argument('--tempo',type=float);args=ap.parse_args()
    root=Path(args.workdir).resolve();env=read(root/'environment.json');profile=read(root/'profile.json');cfg=read(resolved(root,args.segments))
    check_narration_plan(root,profile)
    if cfg.get('input_kind') not in ('generated-native-master','recorded-native-master'):raise ValueError('Use a recorded or generated native narration master; reference voices and already processed takes are excluded')
    tempo=finite(args.tempo if args.tempo is not None else profile['narration']['native_tempo_factor'],'tempo')
    if not .5<=tempo<=2:raise ValueError('Supported tempo is 0.5..2; choose by listening')
    master=resolved(root,cfg['master_path']);rows={r['id']:r for r in read(root/'rundown.json')['items'] if r['type']!='source'}
    with wave.open(str(master),'rb') as w:params=w.getparams();pcm=w.readframes(params.nframes)
    if params.sampwidth!=2 or params.comptype!='NONE':raise ValueError('Expected uncompressed PCM16 narration master')
    stride=params.nchannels*params.sampwidth;prepared=[];seen=set();previous=0
    for segment in cfg['segments']:
        rid=safe_id(segment['id']);row=rows[rid];a=segment['start_frame'];b=segment['end_frame']
        if rid in seen or type(a) is not int or type(b) is not int or not previous<=a<b<=params.nframes:raise ValueError('Need unique ids and ordered, nonoverlapping integer sample boundaries')
        if segment['text']!=row['text']:raise ValueError(f'{rid}: segment text differs from approved rundown')
        seen.add(rid);previous=b;native=root/'voice/native'/f'{rid}.wav';delivery=resolved(root,row['audio_path'])
        if not delivery.is_relative_to(root) or delivery==native or delivery==master:raise ValueError('Delivery must be a new file within episode, distinct from native/master')
        for p in (native,delivery):
            if p.exists():raise FileExistsError(f'Refusing overwrite: {p}; review prior output/manifest before reusing')
        prepared.append((segment,row,native,delivery,a,b))
    if seen!=set(rows):raise ValueError('Provide exactly one reviewed segment for every narration row')
    report=[]
    for segment,row,native,delivery,a,b in prepared:
        native.parent.mkdir(parents=True,exist_ok=True);delivery.parent.mkdir(parents=True,exist_ok=True)
        with wave.open(str(native),'wb') as w:
            w.setnchannels(params.nchannels);w.setsampwidth(params.sampwidth);w.setframerate(params.framerate);w.writeframes(pcm[a*stride:b*stride])
        subprocess.run([env['ffmpeg'],'-v','error','-nostdin','-n','-i',str(native),'-af',f'atempo={tempo}','-c:a','pcm_s16le',str(delivery)],check=True)
        with wave.open(str(delivery),'rb') as w:seconds=w.getnframes()/w.getframerate()
        report.append(dict(id=row['id'],text=row['text'],native_path=str(native),delivery_path=str(delivery),native_duration=(b-a)/params.framerate,delivery_duration=seconds,source_frames=[a,b],native_sha256=hashlib.sha256(native.read_bytes()).hexdigest(),delivery_sha256=hashlib.sha256(delivery.read_bytes()).hexdigest()))
    write(root/'qa/voice-preparation.json',dict(master=str(master),master_sha256=hashlib.sha256(master.read_bytes()).hexdigest(),tempo_applied_once=tempo,sample_rate=params.framerate,items=report,listening_completed=False,note='Boundaries are supplied by reviewed sample metadata. This tool does not infer, ASR, or certify spoken content. Align captions against each delivered WAV.'))
    print(f'Prepared {len(report)} narration files from reviewed native sample ranges at tempo {tempo}.')
if __name__=='__main__':main()
