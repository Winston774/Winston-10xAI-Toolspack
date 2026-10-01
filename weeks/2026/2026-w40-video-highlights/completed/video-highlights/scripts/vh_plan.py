"""Grounded highlight validation, ranking and selection. No model/API calls."""
import argparse
import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path

WEIGHTS = dict(content_value=25, specificity=15, standalone=15, hook=10,
               narrative=10, emotion=5, actionability=10, audiovisual=10)
GATES = ('complete_thought', 'context_preserved', 'faithful_claims')


def number(value, label, lo=None, hi=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label}: expected finite number')
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        raise ValueError(f'{label}: outside [{lo}, {hi}]')
    return value


def read_json(path):
    def reject(value):
        raise ValueError(f'Invalid JSON numeric constant: {value}')
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), parse_constant=reject)


def write_json(path, data):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def text_field(obj, key):
    if not isinstance(obj.get(key), str) or not obj[key].strip():
        raise ValueError(f'{key}: nonempty text required')
    return obj[key]


def interval(obj, duration, label):
    start = number(obj.get('start'), f'{label}.start', 0, duration)
    end = number(obj.get('end'), f'{label}.end', 0, duration)
    if end <= start:
        raise ValueError(f'{label}: end must be greater than start')
    return start, end


def validate_project(project):
    if project.get('schema_version') != 1:
        raise ValueError('Unsupported project schema_version')
    source = project['source']
    duration = number(source['duration'], 'source.duration', 0.001)
    if not re.fullmatch('[a-f0-9]{64}', source['sha256']):
        raise ValueError('Invalid source hash')
    if source.get('clock') != 'zero_based_media':
        raise ValueError('Unsupported source clock')
    if not isinstance(source.get('has_audio'), bool):
        raise ValueError('source.has_audio must be boolean')
    if not Path(source['path']).is_absolute():
        raise ValueError('source.path must be absolute')
    for key in ('width', 'height'):
        number(source[key], key, 1)
    segments = project['transcript']['segments']
    if not isinstance(segments, list):
        raise ValueError('transcript.segments must be an array')
    ids = set()
    previous = -1
    for segment in segments:
        sid = text_field(segment, 'id')
        if sid in ids:
            raise ValueError(f'Duplicate transcript id: {sid}')
        ids.add(sid)
        start, _ = interval(segment, duration, sid)
        if start < previous:
            raise ValueError('Transcript must be sorted by start time')
        previous = start
        text_field(segment, 'text')
    return duration


def validate_coverage(coverage, duration):
    if not isinstance(coverage, list) or not coverage:
        raise ValueError('coverage must describe the entire source')
    position = 0.0
    for index, part in enumerate(coverage):
        start, end = interval(part, duration, f'coverage[{index}]')
        if abs(start - position) > 0.05:
            raise ValueError(f'Coverage gap/overlap near {position:.3f}s')
        if part.get('kind') not in ('speech', 'silence', 'unreviewed'):
            raise ValueError('Invalid coverage kind')
        text_field(part, 'summary')
        position = end
    if abs(position - duration) > 0.05:
        raise ValueError('Coverage does not reach source end')


def validate_candidate(candidate, project, project_dir):
    cid = text_field(candidate, 'id')
    if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,47}', cid):
        raise ValueError('Candidate id must be a short safe filename')
    for key in ('title', 'topic', 'summary', 'hook', 'reason'):
        text_field(candidate, key)
    start, end = interval(candidate, project['source']['duration'], cid)
    scores = candidate['scores']
    if set(scores) != set(WEIGHTS):
        raise ValueError(f'{cid}: scores must contain exactly {list(WEIGHTS)}')
    for key, value in scores.items():
        number(value, f'{cid}.scores.{key}', 0, 5)
    if candidate.get('confidence') not in ('low', 'medium', 'high'):
        raise ValueError(f'{cid}: invalid confidence')
    gates = candidate['gates']
    if set(gates) != set(GATES) or any(type(v) is not bool for v in gates.values()):
        raise ValueError(f'{cid}: three boolean gates required')
    unresolved = candidate.get('unresolved')
    if not isinstance(unresolved, list) or any(not isinstance(s, str) or not s.strip() for s in unresolved):
        raise ValueError(f'{cid}: unresolved must be an array of nonempty strings')
    review = candidate['review']
    if review.get('visual') not in ('unreviewed', 'sampled', 'watched'):
        raise ValueError(f'{cid}: invalid visual review')
    if review.get('audio') not in ('unreviewed', 'transcript_only', 'listened', 'no_audio'):
        raise ValueError(f'{cid}: invalid audio review')
    has_audio = project['source']['has_audio']
    if has_audio and review['audio'] == 'no_audio':
        raise ValueError(f'{cid}: source has audio')
    if not has_audio and review['audio'] in ('listened', 'transcript_only'):
        raise ValueError(f'{cid}: source has no audio')
    evidence = review.get('evidence')
    if not isinstance(evidence, list):
        raise ValueError(f'{cid}: evidence must be an array')
    root = Path(project_dir).resolve()
    for item in evidence:
        if not isinstance(item, str) or Path(item).is_absolute():
            raise ValueError(f'{cid}: evidence paths must be relative')
        target = (root / item).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise ValueError(f'{cid}: missing/outside evidence: {item}')
        if target.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp', '.mp4', '.mov', '.wav', '.mp3', '.m4a', '.mkv'):
            raise ValueError(f'{cid}: evidence must refer to inspectable media')
    if (review['visual'] != 'unreviewed' or review['audio'] == 'listened') and not evidence:
        raise ValueError(f'{cid}: review needs media evidence')
    if review['visual'] == 'unreviewed' and scores['audiovisual'] > 2:
        raise ValueError(f'{cid}: unreviewed visuals cannot score audiovisual above 2')
    framing = candidate['framing']
    if framing.get('mode') not in ('pad', 'crop'):
        raise ValueError(f'{cid}: framing.mode must be pad or crop')
    if framing['mode'] == 'crop':
        number(framing.get('x'), 'crop.x', 0, 1)
        number(framing.get('y'), 'crop.y', 0, 1)
        text_field(framing, 'reason')
        if review['visual'] == 'unreviewed' or not evidence:
            raise ValueError(f'{cid}: crop requires visual inspection')
    quotes = candidate.get('quotes')
    if not isinstance(quotes, list) or not quotes:
        raise ValueError(f'{cid}: at least one grounded transcript quote required')
    segments = {s['id']: s for s in project['transcript']['segments']}
    for quote in quotes:
        segment = segments.get(quote.get('segment_id'))
        if segment is None:
            raise ValueError(f'{cid}: unknown transcript reference')
        value = text_field(quote, 'text')
        if value not in segment['text']:
            raise ValueError(f'{cid}: quote is absent from referenced transcript')
        if min(end, segment['end']) <= max(start, segment['start']):
            raise ValueError(f'{cid}: quote lies outside candidate')
    return start, end


def validate_candidates(data, project, project_dir):
    duration = validate_project(project)
    if data.get('schema_version') != 1 or data.get('source_sha256') != project['source']['sha256']:
        raise ValueError('Candidate schema/source hash mismatch')
    validate_coverage(data.get('coverage'), duration)
    if not isinstance(data.get('candidates'), list):
        raise ValueError('candidates must be an array')
    ids = set()
    for candidate in data['candidates']:
        validate_candidate(candidate, project, project_dir)
        if candidate['id'].casefold() in ids:
            raise ValueError('Duplicate candidate id (case insensitive)')
        ids.add(candidate['id'].casefold())


def validate_weights(weights):
    if not isinstance(weights, dict) or set(weights) != set(WEIGHTS):
        raise ValueError('weights must contain all eight score dimensions')
    for key, value in weights.items():
        number(value, 'weight.' + key, 0)
    if sum(weights.values()) <= 0:
        raise ValueError('weights sum must be positive')


def score(candidate, weights):
    return round(sum(candidate['scores'][key] * value for key, value in weights.items()) /
                 (5 * sum(weights.values())) * 100, 2)


def review_status(candidate):
    review = candidate['review']
    return 'reviewed' if review['visual'] == 'watched' and review['audio'] in ('listened', 'no_audio') and not candidate['unresolved'] else 'partial'


def overlaps(a, b):
    shared = max(0, min(a['end'], b['end']) - max(a['start'], b['start']))
    return shared / min(a['end'] - a['start'], b['end'] - b['start'])


def select(data, project_path, *, min_seconds=30, max_seconds=90, count=5,
           min_score=65, max_overlap=0.35, per_topic=2, weights=None):
    project_path = Path(project_path).resolve()
    project = read_json(project_path)
    validate_candidates(data, project, project_path.parent)
    weights = WEIGHTS.copy() if weights is None else weights
    validate_weights(weights)
    number(min_seconds, 'min_seconds', 0.01)
    number(max_seconds, 'max_seconds', min_seconds)
    number(min_score, 'min_score', 0, 100)
    number(max_overlap, 'max_overlap', 0, 1)
    for name, value in (('count', count), ('per_topic', per_topic)):
        if type(value) is not int or value <= 0:
            raise ValueError(f'{name} must be positive integer')
    ranked = sorted(data['candidates'], key=lambda c: (-score(c, weights), c['start'], c['id']))
    selected, rejected, topics = [], [], {}
    for candidate in ranked:
        reasons = []
        value = score(candidate, weights)
        duration = candidate['end'] - candidate['start']
        if not min_seconds <= duration <= max_seconds:
            reasons.append('duration_out_of_range')
        if value < min_score:
            reasons.append('below_min_score')
        reasons.extend('gate_' + key for key in GATES if not candidate['gates'][key])
        if any(p['kind'] == 'unreviewed' and min(p['end'], candidate['end']) > max(p['start'], candidate['start']) for p in data['coverage']):
            reasons.append('unreviewed_source_range')
        if any(overlaps(candidate, other) > max_overlap for other in selected):
            reasons.append('duplicate_time_range')
        topic = candidate['topic'].strip().casefold()
        if topics.get(topic, 0) >= per_topic:
            reasons.append('topic_limit')
        if len(selected) >= count:
            reasons.append('count_limit')
        if reasons:
            rejected.append(dict(id=candidate['id'], title=candidate['title'], score=value, reasons=reasons))
        else:
            selected.append(dict(candidate, score=value, review_status=review_status(candidate)))
            topics[topic] = topics.get(topic, 0) + 1
    complete = all(p['kind'] != 'unreviewed' for p in data['coverage'])
    status = 'reviewed' if selected and complete and all(c['review_status'] == 'reviewed' for c in selected) else 'partial'
    return dict(schema_version=1, project=str(project_path), source_sha256=project['source']['sha256'],
                constraints=dict(min_seconds=min_seconds, max_seconds=max_seconds, count=count, min_score=min_score,
                                 max_overlap=max_overlap, per_topic=per_topic), weights=weights,
                coverage=data['coverage'], selected=selected, rejected=rejected, status=status,
                score_notice='Editorial rubric score; not calibrated probability, accuracy or predicted views.')


def validate_plan(path):
    plan = read_json(path)
    project_path = Path(plan['project'])
    if not project_path.is_absolute():
        raise ValueError('plan.project must be absolute')
    project = read_json(project_path)
    validate_candidates(dict(schema_version=plan.get('schema_version'), source_sha256=plan.get('source_sha256'),
                             coverage=plan.get('coverage'), candidates=plan.get('selected')), project, project_path.parent)
    validate_weights(plan['weights'])
    constraints = plan['constraints']
    rebuilt = select(dict(schema_version=1, source_sha256=plan['source_sha256'], coverage=plan['coverage'],
                          candidates=plan['selected']), project_path, weights=plan['weights'], **constraints)
    if [c['id'] for c in rebuilt['selected']] != [c['id'] for c in plan['selected']]:
        raise ValueError('Selected candidates violate ranking or selection constraints')
    if rebuilt['status'] != plan['status']:
        raise ValueError('Plan review status mismatch')
    for expected, actual in zip(rebuilt['selected'], plan['selected']):
        number(actual.get('score'), 'score', 0, 100)
        if expected['score'] != actual['score'] or expected['review_status'] != actual['review_status']:
            raise ValueError('Stored score/review status mismatch')
    return plan, project


def stamp(seconds):
    whole = int(seconds)
    return f'{whole // 3600:02d}:{whole // 60 % 60:02d}:{seconds % 60:06.3f}'


def report(plan, out):
    out = Path(out)
    lines = ['# Video Highlights 選段報告', '', f"狀態：{plan['status']}；入選 {len(plan['selected'])} 段。", '',
             '分數為可調整的編輯判斷，無法代表實際觀看數或模型正確率。', '',
             '## 全片內容地圖', '']
    for part in plan['coverage']:
        lines.append(f"- {stamp(part['start'])}–{stamp(part['end'])} [{part['kind']}] {part['summary']}")
    for clip in plan['selected']:
        lines += ['', f"## {clip['id']} · {clip['title']}", '',
                  f"{stamp(clip['start'])}–{stamp(clip['end'])}｜{clip['end']-clip['start']:.2f} 秒｜{clip['score']}/100｜把握度 {clip['confidence']}｜{clip['review_status']}", '',
                  clip['summary'], '', f"入選理由：{clip['reason']}", f"開場：{clip['hook']}", '',
                  '分項（0–5）：' + '、'.join(f'{k}={v}' for k, v in clip['scores'].items()), '',
                  '原文依據：' + '；'.join(f"{q['segment_id']}「{q['text']}」" for q in clip['quotes']), '',
                  f"畫面：{clip['review']['visual']}；聲音：{clip['review']['audio']}；取景：{clip['framing']['mode']}",
                  '檢視註記：' + str(clip['review'].get('notes', '')), '待確認：' + ('；'.join(clip['unresolved']) or '無已記錄項目')]
    lines += ['', '## 未入選', '']
    lines.extend(f"- {c['id']} {c['title']} ({c['score']}): {', '.join(c['reasons'])}" for c in plan['rejected'])
    (out / 'HIGHLIGHTS.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    with (out / 'scores.csv').open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.writer(handle)
        writer.writerow(['id', 'title', 'start', 'end', 'seconds', 'score', 'confidence', 'review_status', *WEIGHTS])
        for clip in plan['selected']:
            title = clip['title']
            if title.startswith(('=', '+', '-', '@', '\t', '\r')):
                title = "'" + title
            writer.writerow([clip['id'], title, clip['start'], clip['end'], clip['end'] - clip['start'],
                             clip['score'], clip['confidence'], clip['review_status'], *[clip['scores'][k] for k in WEIGHTS]])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project')
    parser.add_argument('candidates')
    parser.add_argument('--out', required=True)
    parser.add_argument('--min-seconds', type=float, default=30)
    parser.add_argument('--max-seconds', type=float, default=90)
    parser.add_argument('--count', type=int, default=5)
    parser.add_argument('--min-score', type=float, default=65)
    parser.add_argument('--max-overlap', type=float, default=0.35)
    parser.add_argument('--per-topic', type=int, default=2)
    parser.add_argument('--weights', help='JSON file with eight nonnegative weights')
    args = parser.parse_args(argv)
    try:
        plan = select(read_json(args.candidates), args.project, min_seconds=args.min_seconds, max_seconds=args.max_seconds,
                      count=args.count, min_score=args.min_score, max_overlap=args.max_overlap, per_topic=args.per_topic,
                      weights=read_json(args.weights) if args.weights else None)
        out = Path(args.out).resolve()
        out.mkdir(parents=True, exist_ok=False)
        write_json(out / 'plan.json', plan)
        report(plan, out)
        print(f"Selected {len(plan['selected'])}; status={plan['status']}; {out / 'plan.json'}")
        if not plan['selected']:
            print('No eligible clips. Inspect rejected reasons; revise grounded boundaries or user constraints.')
        return 0
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
