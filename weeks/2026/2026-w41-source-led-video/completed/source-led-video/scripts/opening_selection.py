"""Validate evidence-backed question ordering without loading media or render tools."""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path


WEIGHTS = dict(promise_match=30, centrality=25, understanding_value=20,
               answer_strength=15, entry_clarity=10)
GATES = ('promise_supported', 'answer_present', 'context_preserved')
SOURCE_GATES = ('complete_thought', 'context_preserved', 'faithful_claims')
PLACEHOLDERS = {'todo', 'tbd', 'unknown', '待補', '待確認', '未提供'}


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and value.strip().lower() not in PLACEHOLDERS


def _number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _id(value):
    return isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9-]{0,63}', value) is not None


def validate_opening(root, rows=None):
    """Return a computed report; never mutate inputs or infer semantic truth from text.

    ``rows`` may contain the current authored rundown to avoid a second file read.
    Every source row counts as substantive: the contract has no teaser exemption.
    Evidence and reasons remain authored review claims, subject to human verification.
    """
    root = Path(root)
    errors = []
    warnings = []

    def fail(code, path, message):
        errors.append(dict(code=code, path=path, message=message))

    def read(name):
        try:
            value = json.loads((root / name).read_text(encoding='utf-8-sig'))
        except (OSError, UnicodeError, ValueError) as exc:
            fail('input_unreadable', name, str(exc))
            return {}
        if not isinstance(value, dict):
            fail('input_shape', name, 'Expected a JSON object.')
            return {}
        return value

    def objects(value, path):
        if not isinstance(value, list):
            fail('input_shape', path, 'Expected an array of objects.')
            return []
        result = []
        for i, item in enumerate(value):
            if not isinstance(item, dict):
                fail('input_shape', f'{path}[{i}]', 'Expected an object.')
            else:
                result.append(item)
        return result

    def mapping(value, path):
        if not isinstance(value, dict):
            fail('input_shape', path, 'Expected an object.')
            return {}
        return value

    def require_text(value, path):
        if not _text(value):
            fail('evidence_required', path, 'Provide authored, non-placeholder text.')

    def index(items, key, path):
        output = {}
        for i, item in enumerate(items):
            value = item.get(key)
            if not _id(value):
                fail('invalid_id', f'{path}[{i}].{key}', 'Use a stable lowercase ID.')
            elif value in output:
                fail('duplicate_id', f'{path}[{i}].{key}', f'Duplicate ID: {value}.')
            else:
                output[value] = item
        return output

    data = read('opening-selection.json')
    questions = objects(read('questions.json').get('questions'), 'questions.json.questions')
    question_by_id = index(questions, 'id', 'questions.json.questions')
    if not questions:
        fail('questions_required', 'questions.json.questions', 'Author at least one genuine source-backed question.')
    for i, question in enumerate(questions):
        require_text(question.get('question'), f'questions.json.questions[{i}].question')

    if rows is None:
        rows = read('rundown.json').get('items')
    rows = objects(rows, 'rundown.json.items')
    row_by_id = index(rows, 'id', 'rundown.json.items')
    source_rows = [r for r in rows if r.get('type') == 'source']
    first_by_question = {}
    for row in source_rows:
        qid = row.get('question_id')
        if not _id(qid) or qid not in question_by_id:
            fail('unknown_question', f'rundown.{row.get("id")}.question_id', 'Source row must reference an authored question.')
        elif qid not in first_by_question:
            first_by_question[qid] = row
    if not source_rows:
        fail('source_required', 'rundown.json.items', 'The opening must lead to an actual source answer.')
    elif type(source_rows[0].get('chapter')) is not int or source_rows[0]['chapter'] != 1:
        fail('first_source_chapter', 'rundown.json.items', 'The first source answer must be in chapter 1.')

    clips = objects(read('candidates.json').get('candidates'), 'candidates.json.candidates')
    clip_by_id = index(clips, 'id', 'candidates.json.candidates')
    sources = objects(read('sources.json').get('sources'), 'sources.json.sources')
    source_by_id = index(sources, 'id', 'sources.json.sources')

    packaging = mapping(data.get('packaging'), 'packaging')
    for key in ('title', 'thumbnail_promise', 'viewer_question'):
        require_text(packaging.get(key), f'packaging.{key}')
    coverage = mapping(data.get('coverage'), 'coverage')
    if coverage.get('whole_source_reviewed') is not True:
        fail('whole_source_review_required', 'coverage.whole_source_reviewed', 'Complete a whole-source review before selecting the opening.')
    require_text(coverage.get('evidence'), 'coverage.evidence')
    require_text(data.get('selection_reason'), 'selection_reason')
    if 'weights' in data and data['weights'] != WEIGHTS:
        fail('fixed_weights', 'weights', 'Opening selection uses the fixed question-level weights.')

    candidates = objects(data.get('candidates'), 'opening-selection.json.candidates')
    candidate_by_id = index(candidates, 'question_id', 'opening-selection.json.candidates')
    for qid in question_by_id:
        if qid not in candidate_by_id:
            fail('question_not_compared', 'candidates', f'Add the opening comparison for {qid}.')
    for qid in candidate_by_id:
        if qid not in question_by_id:
            fail('unknown_question', 'candidates', f'Question {qid} is absent from questions.json.')

    results = []
    ranking = []
    for i, candidate in enumerate(candidates):
        path = f'candidates[{i}]'
        before = len(errors)
        qid = candidate.get('question_id')
        gates = mapping(candidate.get('gates'), path + '.gates')
        gate_reasons = mapping(candidate.get('gate_reasons'), path + '.gate_reasons')
        scores = mapping(candidate.get('scores'), path + '.scores')
        score_reasons = mapping(candidate.get('score_reasons'), path + '.score_reasons')
        require_text(candidate.get('evidence'), path + '.evidence')
        if set(gates) != set(GATES):
            fail('gate_keys', path + '.gates', 'Provide exactly the three opening gates, using null for unknown.')
        if set(scores) != set(WEIGHTS):
            fail('score_keys', path + '.scores', 'Provide exactly the five opening dimensions, using null for unknown.')
        for gate in GATES:
            value = gates.get(gate)
            if value is not None and type(value) is not bool:
                fail('gate_value', path + '.gates.' + gate, 'Gate must be true, false or null.')
            require_text(gate_reasons.get(gate), path + '.gate_reasons.' + gate)
        failed = [g for g in GATES if gates.get(g) is False]
        unknown_gates = [g for g in GATES if gates.get(g) is None]
        missing = [k for k in WEIGHTS if scores.get(k) is None]
        observed = 0
        total = 0.0
        for key, weight in WEIGHTS.items():
            value = scores.get(key)
            reason = score_reasons.get(key)
            if value is None:
                if reason is not None:
                    fail('unknown_score_reason', path + '.score_reasons.' + key, 'Use null for an unknown score reason; explain missing review in evidence.')
                continue
            if not _number(value) or not 0 <= value <= 5:
                fail('score_value', path + '.scores.' + key, 'Score must be a finite number from 0 to 5, or null.')
                continue
            require_text(reason, path + '.score_reasons.' + key)
            observed += weight
            total += weight * value / 5

        rid = candidate.get('first_source_item')
        row = row_by_id.get(rid) if _id(rid) else None
        source_failures = []
        source_unknown = []
        if not row or row.get('type') != 'source':
            fail('source_item_missing', path + '.first_source_item', 'Reference an existing source row in the rundown.')
        elif row.get('question_id') != qid:
            fail('source_question_mismatch', path + '.first_source_item', 'The source row belongs to another question.')
        else:
            if not _id(qid) or first_by_question.get(qid) is not row:
                fail('first_answer_mismatch', path + '.first_source_item', 'Use this question\'s first source answer in the authored rundown.')
            cid = row.get('candidate_id')
            clip = clip_by_id.get(cid) if _id(cid) else None
            if not clip:
                fail('source_candidate_missing', path + '.first_source_item', 'The source row needs a reviewed candidates.json entry.')
            else:
                source_id = row.get('source_id')
                if not _id(source_id) or source_id not in source_by_id or clip.get('source_id') != source_id:
                    fail('source_identity_mismatch', path + '.first_source_item', 'Source row and clip candidate must reference the same known source.')
                if clip.get('question_id') != qid:
                    fail('source_candidate_question', path + '.first_source_item', 'The clip candidate must reference this authored question.')
                values = [row.get('in'), row.get('out'), clip.get('start'), clip.get('end')]
                if not all(_number(v) for v in values):
                    fail('source_range_invalid', path + '.first_source_item', 'Source and candidate ranges must be finite numbers.')
                else:
                    start, end, reviewed_start, reviewed_end = values
                    if start < 0 or end <= start or reviewed_start < 0 or reviewed_end <= reviewed_start:
                        fail('source_range_invalid', path + '.first_source_item', 'Source ranges must be positive intervals.')
                    elif abs(start - reviewed_start) > .03 or abs(end - reviewed_end) > .03:
                        fail('source_range_changed', path + '.first_source_item', 'Updated cut boundaries require updated clip evidence.')
                    source = source_by_id.get(source_id, {}) if _id(source_id) else {}
                    duration = source.get('duration_seconds')
                    if duration is not None and (not _number(duration) or duration <= 0 or end > duration + .05):
                        fail('source_duration_invalid', path + '.first_source_item', 'Source answer exceeds the declared source duration or duration is invalid.')
                evidence = mapping(clip.get('evidence'), path + '.source_candidate.evidence')
                require_text(evidence.get('transcript'), path + '.source_candidate.evidence.transcript')
                clip_gates = mapping(clip.get('gates'), path + '.source_candidate.gates')
                clip_reasons = mapping(clip.get('gate_reasons'), path + '.source_candidate.gate_reasons')
                if set(clip_gates) != set(SOURCE_GATES):
                    fail('source_gate_keys', path + '.source_candidate.gates', 'Provide all three source clip gates.')
                for gate in SOURCE_GATES:
                    value = clip_gates.get(gate)
                    if value is not None and type(value) is not bool:
                        fail('source_gate_value', path + '.source_candidate.gates.' + gate, 'Gate must be true, false or null.')
                    require_text(clip_reasons.get(gate), path + '.source_candidate.gate_reasons.' + gate)
                    if value is False:
                        source_failures.append(gate)
                    elif value is None:
                        source_unknown.append(gate)

        rejected = bool(failed or source_failures)
        pending = bool(unknown_gates or missing or source_unknown)
        invalid = len(errors) > before
        eligible = not invalid and not rejected and not pending
        status = 'invalid' if invalid else 'reject_or_recut' if rejected else 'needs_review' if pending else 'eligible'
        result = dict(question_id=qid, first_source_item=rid, status=status, eligible=eligible,
                      total_score=round(total, 2) if observed == 100 else None,
                      lower_bound=round(total, 2), upper_bound=round(total + 100 - observed, 2),
                      observed_weight=observed, gate_failures=failed,
                      unreviewed_gates=unknown_gates, unreviewed_dimensions=missing,
                      source_gate_failures=source_failures, unreviewed_source_gates=source_unknown)
        results.append(result)
        if eligible:
            ranking.append((qid, total))
        elif pending and not rejected:
            fail('comparison_incomplete', path, 'Complete this question\'s gate and score review before choosing the opening.')

    selected_qid = data.get('selected_question_id')
    selected_rid = data.get('selected_source_item')
    selected = next((r for r in results if r['question_id'] == selected_qid), None) if _id(selected_qid) else None
    if not selected or not selected['eligible']:
        fail('selected_ineligible', 'selected_question_id', 'Select a fully reviewed question that passes every gate.')
    elif selected_rid != selected['first_source_item']:
        fail('selected_item_mismatch', 'selected_source_item', 'Selection must use the selected question\'s reviewed first source item.')
    highest = max((score for _, score in ranking), default=None)
    winners = [qid for qid, score in ranking if highest is not None and math.isclose(score, highest, abs_tol=1e-9)]
    if selected and selected['eligible'] and selected_qid not in winners:
        fail('lower_ranked_selection', 'selected_question_id', 'Choose the highest-scoring eligible question; a tie may be resolved in selection_reason.')
    if source_rows and (source_rows[0].get('id') != selected_rid or source_rows[0].get('question_id') != selected_qid):
        fail('opening_source_mismatch', 'rundown.json.items', 'The first substantive source row must match the selected question and source item.')
    opening_rows = [row for row in rows if row.get('type') == 'opening']
    if len(opening_rows) != 1 or not rows or rows[0].get('type') != 'opening':
        fail('opening_intro_required', 'rundown.json.items', 'Begin with one authored introduction before the first source answer.')
    elif opening_rows[0].get('question_id') != selected_qid:
        fail('opening_intro_mismatch', f'rundown.{opening_rows[0].get("id")}.question_id', 'The introduction must frame the same selected question as the first source answer.')
    if len(winners) > 1:
        warnings.append(dict(code='tied_highest_score', question_ids=winners,
                             message='Review selection_reason for the authored tie decision.'))
    return dict(schema_version='1.0', unit='question_opening', valid=not errors,
                status='valid' if not errors else 'invalid', weights=WEIGHTS.copy(), results=results,
                selected_question_id=selected_qid, selected_source_item=selected_rid,
                highest_eligible_score=round(highest, 2) if highest is not None else None,
                highest_eligible_question_ids=winners, errors=errors, warnings=warnings,
                note='此報告檢查已撰寫的問題比較、分數與來源連結。語意判斷及全片檢視是作者的證據聲明，仍須人工查證；文字相同不構成承諾一致的證明。未知分數保留上下界，所有門檻優先於分數。')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workdir')
    parser.add_argument('--out', help='Report path; defaults to WORKDIR/qa/opening-selection.json')
    args = parser.parse_args(argv)
    root = Path(args.workdir).resolve()
    report = validate_opening(root)
    out = Path(args.out).resolve() if args.out else root / 'qa/opening-selection.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['valid'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
