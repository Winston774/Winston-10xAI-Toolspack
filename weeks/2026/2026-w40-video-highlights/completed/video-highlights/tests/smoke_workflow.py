"""Reproducible one-hour synthetic CLI smoke test. No real speech or ASR evaluation."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from vh_plan import WEIGHTS, GATES, read_json, sha256


def run(args):
    subprocess.run([str(v) for v in args], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--ffprobe', default='ffprobe')
    args = parser.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    video = out/'synthetic-hour.mp4'
    run([args.ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-n',
         '-f', 'lavfi', '-i', 'color=c=0x152033:s=320x180:r=10',
         '-f', 'lavfi', '-i', 'anullsrc=r=16000:cl=mono', '-t', '3600',
         '-vf', 'drawbox=x=20:y=20:w=110:h=140:color=0x446ba0:t=fill,drawbox=x=190:y=20:w=110:h=140:color=0x4eaa88:t=fill',
         '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '30', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-b:a', '16k', video])
    subtitle = out/'synthetic.srt'
    subtitle.write_text('1\n00:00:10,000 --> 00:00:30,000\nSYNTHETIC FIXTURE: preserve the complete premise.\n\n'
                       '2\n00:00:30,000 --> 00:00:55,000\nSYNTHETIC FIXTURE: conclude the first example.\n\n'
                       '3\n00:58:20,000 --> 00:58:50,000\nSYNTHETIC FIXTURE: examine the result near the end.\n\n'
                       '4\n00:58:50,000 --> 00:59:20,000\nSYNTHETIC FIXTURE: finish the final explanation.\n', encoding='utf-8')
    cli = [sys.executable, str(ROOT/'scripts/highlights.py')]
    media = ['--ffmpeg', args.ffmpeg, '--ffprobe', args.ffprobe]
    run(cli + ['doctor'] + media)
    run(cli + ['prepare', video, '--srt', subtitle, '--out', out/'source', '--every', '300'] + media)
    project_path = out/'source/project.json'
    project = read_json(project_path)
    assert project['chunks'][0]['start'] == 0
    assert project['chunks'][-1]['end'] == project['source']['duration']
    assert len(project['chunks']) >= 12
    run(cli + ['inspect', project_path, '--start', '3500', '--end', '3506', '--every', '2',
               '--out', out/'source/evidence/late', '--ffmpeg', args.ffmpeg])
    candidates = []
    for cid, start, end, sid, quote, topic in [
        ('H001', 10, 55, 'S000001', 'preserve the complete premise', 'premise'),
        ('H002', 3500, 3560, 'S000003', 'examine the result near the end', 'result')]:
        candidates.append(dict(id=cid, title='合成測試 ' + cid, topic=topic, start=start, end=end,
            summary='純測試字幕和時鐘；無真實訪談內容。', hook='測試資料，不代表吸引力判斷。', reason='用於驗證早段與晚段可依規格匯出。',
            quotes=[dict(segment_id=sid, text=quote)], scores={k:(2 if k=='audiovisual' else 4) for k in WEIGHTS},
            confidence='low', gates={k:True for k in GATES},
            review=dict(visual='unreviewed', audio='transcript_only', evidence=[], notes='合成 fixtures，未作語義或視聽品質驗收。'),
            framing=dict(mode='pad'), unresolved=['測試分數預先指定，無法驗證真實選段品質。']))
    data = dict(schema_version=1, source_sha256=project['source']['sha256'],
                coverage=[dict(start=0, end=project['source']['duration'], kind='silence',
                               summary='全長一小時的合成靜音影片，字幕僅供時間與資料流程測試。')], candidates=candidates)
    candidate_path = out/'candidates.json'
    candidate_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    run(cli + ['select', project_path, candidate_path, '--out', out/'selection', '--count', '2',
               '--min-seconds', '45', '--max-seconds', '75'])
    plan = out/'selection/plan.json'
    run(cli + ['validate', plan])
    run(cli + ['render', plan, '--out', out/'exports', '--formats', 'portrait', 'landscape', '--height', '320'] + media)
    report = read_json(out/'exports/metadata/render.json')
    assert report['status'] == 'rendered' and report['review_status'] == 'partial'
    assert len(report['files']) == 4
    assert sha256(video) == project['source']['sha256']
    for item in report['files']:
        run([args.ffmpeg, '-v', 'error', '-i', out/'exports'/item['video'], '-f', 'null', '-'])
        assert (out/'exports'/item['subtitles']).read_text(encoding='utf-8').startswith('1\n00:00:00,000')
    result = dict(status='passed', source_seconds=project['source']['duration'], chunks=len(project['chunks']),
                  selected=2, exports=4, full_decode_passed=True, source_unchanged=True,
                  semantic_quality_validated=False, real_asr_tested=False, human_audiovisual_signoff=False)
    (out/'smoke-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
