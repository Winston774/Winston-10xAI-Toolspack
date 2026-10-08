"""Validate authored opening context, original-language terms, and optional WAV review bindings.

This tool never generates speech, edits a script, or infers semantic/phonetic truth.
The terminology inventory and listening observations are authored review claims.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re
import wave


NARRATION_TYPES = {'opening', 'bridge', 'outro'}
PLACEHOLDERS = {'todo', 'tbd', 'unknown', 'pending', 'n/a', 'null', 'none',
                '...', '…', '待補', '待確認', '待填', '待查', '未提供', '尚未確認'}
HAN = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U000323af]')
LATIN = re.compile(r'[A-Za-z\u00c0-\u024f\u1e00-\u1eff]')


def _text(value):
    if not isinstance(value, str) or not value.strip():
        return False
    value = value.strip()
    return (value.lower() not in PLACEHOLDERS
            and not re.fullmatch(r'[\[<｛{].*[\]>｝}]', value)
            and not re.match(r'^(?:todo|tbd|待補|待填|待確認)\s*[:：]', value, re.I))


def _number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _contains(text, form):
    """Preserve spelling/case and avoid matching English names inside larger words."""
    if not isinstance(text, str) or not isinstance(form, str) or not form:
        return False
    left = r'(?<![A-Za-z0-9_])' if form[0].isascii() and form[0].isalnum() else ''
    right = r'(?![A-Za-z0-9_])' if form[-1].isascii() and form[-1].isalnum() else ''
    return re.search(left + re.escape(form) + right, text) is not None


def _resolve(root, value):
    path = Path(value)
    return (path if path.is_absolute() else root / path).resolve()


def _wav_info(path):
    """Hash the same opened file whose complete PCM frames were checked."""
    with path.open('rb') as raw:
        with wave.open(raw, 'rb') as audio:
            frame_rate = audio.getframerate()
            frame_count = audio.getnframes()
            if frame_rate <= 0 or frame_count <= 0:
                raise ValueError('WAV must contain audio frames.')
            expected = frame_count * audio.getnchannels() * audio.getsampwidth()
            actual = 0
            while chunk := audio.readframes(65536):
                actual += len(chunk)
            if actual != expected:
                raise ValueError('WAV frame data is truncated.')
            duration = frame_count / frame_rate
        raw.seek(0)
        digest = hashlib.sha256()
        while chunk := raw.read(1024 * 1024):
            digest.update(chunk)
    return {'duration_seconds': duration, 'sha256': digest.hexdigest()}


def validate_narration(root, text_file=None, require_listening=False):
    """Return a report without writing inputs or performing automated listening.

    Relative text/audio paths are relative to ``root``. Script mode does not need
    rendered audio. Listening mode verifies review bindings, not pronunciation.
    """
    root = Path(root).resolve()
    errors, warnings = [], []

    def fail(code, path, message):
        errors.append(dict(code=code, path=path, message=message))

    def listening_issue(code, path, message):
        target = errors if require_listening else warnings
        target.append(dict(code=code, path=path, message=message))

    def read(name):
        try:
            result = json.loads((root / name).read_text(encoding='utf-8-sig'))
        except (OSError, UnicodeError, ValueError) as exc:
            fail('input_unreadable', name, str(exc))
            return {}
        return mapping(result, name)

    def mapping(value, path):
        if not isinstance(value, dict):
            fail('input_shape', path, 'Expected an object.')
            return {}
        return value

    def objects(value, path):
        if not isinstance(value, list):
            fail('input_shape', path, 'Expected an array of objects.')
            return []
        result = []
        for index, item in enumerate(value):
            if isinstance(item, dict):
                result.append((index, item))
            else:
                fail('input_shape', f'{path}[{index}]', 'Expected an object.')
        return result

    def require_text(value, path):
        if not _text(value):
            fail('text_required', path, 'Provide non-placeholder authored text.')
            return ''
        return value

    def require_date(value, path):
        try:
            if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                raise ValueError('Use YYYY-MM-DD.')
            return date.fromisoformat(value)
        except ValueError:
            fail('date_required', path, 'Provide a valid date in YYYY-MM-DD format.')
            return None

    data = read('narration-plan.json')
    if data.get('schema_version') != '1.0':
        fail('schema_version', 'schema_version', 'Expected narration-plan schema_version "1.0".')
    rundown = read('rundown.json')
    rows = []
    source_rows_ignored = 0
    row_by_id = {}
    for index, row in objects(rundown.get('items'), 'rundown.json.items'):
        path = f'rundown.json.items[{index}]'
        kind = row.get('type')
        if kind == 'source':
            source_rows_ignored += 1
            continue
        if not isinstance(kind, str) or kind not in NARRATION_TYPES:
            fail('narration_type', path + '.type', 'Expected opening, bridge, outro, or source.')
            continue
        rid = require_text(row.get('id'), path + '.id')
        text = require_text(row.get('text'), path + '.text')
        if rid in row_by_id:
            fail('duplicate_id', path + '.id', f'Duplicate narration item: {rid}.')
        elif rid:
            row_by_id[rid] = row
        rows.append(dict(id=rid, text=text, row=row, path=path))
    openings = [item for item in rows if item['row'].get('type') == 'opening']
    if len(openings) != 1:
        fail('opening_required', 'rundown.json.items', 'Provide exactly one opening narration row.')
    opening_text = openings[0]['text'] if len(openings) == 1 else ''
    if not rows:
        fail('narration_required', 'rundown.json.items', 'Provide authored narration.')

    opening = mapping(data.get('opening'), 'opening')
    source_format = opening.get('source_format', 'interview')
    if source_format not in ('interview', 'solo'):
        fail('source_format', 'opening.source_format', 'Choose interview or solo.')
    source_date = require_date(opening.get('source_published_at'), 'opening.source_published_at')
    host = mapping(opening.get('host'), 'opening.host')
    if source_format == 'solo':
        guest = {}
        if 'guest' not in opening or opening['guest'] is not None:
            fail('solo_guest_forbidden', 'opening.guest', 'Use null for a solo source; do not invent an interview guest.')
    else:
        guest = mapping(opening.get('guest'), 'opening.guest')
    why_now = mapping(opening.get('why_now'), 'opening.why_now')
    coverage = mapping(opening.get('coverage'), 'opening.coverage')
    for key in ('name', 'program', 'positioning', 'credibility', 'evidence'):
        require_text(host.get(key), f'opening.host.{key}')
    if source_format != 'solo':
        for key in ('name', 'role', 'evidence'):
            require_text(guest.get(key), f'opening.guest.{key}')
        role_date = require_date(guest.get('role_as_of'), 'opening.guest.role_as_of')
        if source_date and role_date and role_date > source_date:
            fail('role_after_source', 'opening.guest.role_as_of',
                 'The guest role must be sourced as of the source period, not a later appointment.')
    for key in ('explanation', 'evidence'):
        require_text(why_now.get(key), f'opening.why_now.{key}')
    time_basis = why_now.get('time_basis')
    if time_basis not in ('source_period', 'current_verified', 'evergreen'):
        fail('time_basis', 'opening.why_now.time_basis',
             'Choose source_period, current_verified, or evergreen.')
    verified_at = why_now.get('verified_at')
    if time_basis == 'current_verified' or verified_at not in (None, ''):
        verified_date = require_date(verified_at, 'opening.why_now.verified_at')
        if verified_date and verified_date > date.today():
            fail('future_verification', 'opening.why_now.verified_at', 'Verification cannot be in the future.')

    excerpts = {}
    for key in ('host_excerpt', 'guest_excerpt', 'why_now_excerpt', 'question_excerpt'):
        if source_format == 'solo' and key == 'guest_excerpt':
            if key not in coverage or coverage[key] is not None:
                fail('solo_guest_forbidden', 'opening.coverage.guest_excerpt',
                     'Use null for guest_excerpt in a solo source.')
            excerpts[key] = ''
            continue
        excerpt = require_text(coverage.get(key), f'opening.coverage.{key}')
        excerpts[key] = excerpt
        if excerpt and excerpt not in opening_text:
            fail('coverage_missing', f'opening.coverage.{key}',
                 'The exact excerpt must occur in opening narration text; a visual card is insufficient.')
    for value, key, field in ((host.get('positioning'), 'host_excerpt', 'host.positioning'),
                              (host.get('credibility'), 'host_excerpt', 'host.credibility'),
                              (guest.get('role'), 'guest_excerpt', 'guest.role'),
                              (why_now.get('explanation'), 'why_now_excerpt', 'why_now.explanation')):
        if _text(value) and value not in excerpts[key]:
            fail('context_not_spoken', f'opening.{field}',
                 f'This short authored clause must occur in coverage.{key}.')

    if data.get('terminology_reviewed') is not True:
        fail('terminology_review_required', 'terminology_reviewed',
             'Explicitly review the complete original-language terminology inventory.')
    terms = objects(data.get('terms'), 'terms')
    normalized_terms = []
    canonical_seen = set()
    all_avoided = set()
    for index, term in terms:
        path = f'terms[{index}]'
        canonical = require_text(term.get('canonical'), path + '.canonical')
        language = require_text(term.get('language'), path + '.language')
        require_text(term.get('source_evidence'), path + '.source_evidence')
        if canonical in canonical_seen:
            fail('duplicate_term', path + '.canonical', f'Duplicate canonical term: {canonical}.')
        if canonical:
            canonical_seen.add(canonical)

        def forms(key, allow_empty=False):
            values = term.get(key)
            if not isinstance(values, list) or (not values and not allow_empty):
                fail('input_shape', path + '.' + key, 'Expected an array of non-placeholder strings.')
                return []
            result = []
            for number, value in enumerate(values):
                value = require_text(value, f'{path}.{key}[{number}]')
                if value:
                    result.append(value)
            return result

        spoken = forms('spoken_forms')
        avoided = forms('avoid_forms', allow_empty=True)
        all_avoided.update(avoided)
        if language.lower().split('-')[0] == 'en' and any(HAN.search(value) for value in [canonical] + spoken):
            fail('english_term_han', path,
                 'English canonical terms and spoken forms must retain original spelling, without Han aliases.')
        if any(form in avoided for form in spoken) or canonical in avoided:
            fail('term_form_conflict', path, 'Approved and avoided forms must not conflict.')
        containing = [item for item in rows if any(_contains(item['text'], form) for form in spoken)]
        if not containing:
            fail('unused_term', path, 'At least one approved spoken form must occur in narration.')
        normalized_terms.append(dict(term=term, path=path, canonical=canonical, spoken=spoken,
                                     containing=containing))

    def check_identity(value, excerpt_key, field):
        if not _text(value):
            return
        approved = [value]
        registered = False
        for term in normalized_terms:
            if term['canonical'] == value or value in term['spoken']:
                registered = True
                approved.extend(term['spoken'])
        if LATIN.search(value) and not registered:
            fail('identity_term_required', f'opening.{field}',
                 'Names and program titles with Latin letters need a matching canonical or spoken form in terms for pronunciation review.')
        if not any(_contains(excerpts[excerpt_key], form) for form in approved):
            fail('identity_not_spoken', f'opening.{field}',
                 f'Include the original name or its approved spoken form in coverage.{excerpt_key}.')

    check_identity(host.get('name'), 'host_excerpt', 'host.name')
    check_identity(host.get('program'), 'host_excerpt', 'host.program')
    check_identity(guest.get('name'), 'guest_excerpt', 'guest.name')
    for item in rows:
        for avoided in sorted(all_avoided):
            if avoided in item['text']:
                fail('avoided_form', item['path'] + '.text', f'Remove the avoided narration form: {avoided}.')

    tts_text_matches = None
    if text_file is not None:
        try:
            supplied = _resolve(root, text_file).read_text(encoding='utf-8-sig')
            expected = '\n\n'.join(item['text'] for item in rows)
            # Accept the single final newline commonly added by text editors.
            # read_text already accepts a UTF-8 BOM and normalizes CRLF to LF.
            tts_text_matches = supplied in (expected, expected + '\n')
            if not tts_text_matches:
                fail('tts_text_mismatch', str(text_file),
                     'TTS input must equal narration row text joined with two newlines; only a BOM and one final newline are optional.')
            for avoided in sorted(all_avoided):
                if avoided in supplied:
                    fail('avoided_form', str(text_file), f'TTS input contains an avoided form: {avoided}.')
        except (OSError, UnicodeError, ValueError) as exc:
            tts_text_matches = False
            fail('input_unreadable', str(text_file), str(exc))

    audio_cache = {}
    bound_reviews = []
    for normalized in normalized_terms:
        term, path = normalized['term'], normalized['path']
        if not _text(term.get('pronunciation_reference')):
            listening_issue('pronunciation_reference_pending', path + '.pronunciation_reference',
                            'Record the original-language pronunciation reference before listening approval.')
        reviews = term.get('audio_reviews', [])
        if not require_listening:
            warnings.append(dict(code='listening_not_checked', path=path + '.audio_reviews',
                                 message='Script stage does not inspect audio or establish listening approval.'))
            continue
        if not isinstance(reviews, list):
            fail('input_shape', path + '.audio_reviews', 'Expected an array of listening review objects.')
            reviews = []
        containing_ids = {item['id'] for item in normalized['containing']}
        reviewed = set()
        for index, review in enumerate(reviews):
            review_path = f'{path}.audio_reviews[{index}]'
            if not isinstance(review, dict):
                fail('input_shape', review_path, 'Expected a listening review object.')
                continue
            before = len(errors)
            item_id = review.get('item')
            if not isinstance(item_id, str) or item_id not in containing_ids:
                fail('review_item_mismatch', review_path + '.item',
                     'Review must identify a current narration row that speaks this term.')
                continue
            row = row_by_id.get(item_id, {})
            if not _text(row.get('audio_path')) or not _text(review.get('audio_path')):
                fail('audio_path_required', review_path + '.audio_path', 'Both rundown and review need the current WAV path.')
                continue
            try:
                audio_path = _resolve(root, row['audio_path'])
                review_audio_path = _resolve(root, review['audio_path'])
                if audio_path != review_audio_path:
                    fail('audio_path_mismatch', review_path + '.audio_path', 'Review path differs from the current rundown audio.')
                    continue
                if audio_path.suffix.lower() != '.wav':
                    raise ValueError('Listening delivery evidence must be a WAV file.')
                if audio_path not in audio_cache:
                    audio_cache[audio_path] = _wav_info(audio_path)
                audio = audio_cache[audio_path]
            except (OSError, ValueError, wave.Error, EOFError) as exc:
                fail('audio_unreadable', review_path + '.audio_path', str(exc))
                continue
            digest = review.get('audio_sha256')
            if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', digest):
                fail('audio_hash_required', review_path + '.audio_sha256', 'Record the actual WAV SHA-256.')
            elif digest.lower() != audio['sha256']:
                fail('audio_hash_mismatch', review_path + '.audio_sha256', 'Audio changed after the recorded listening review.')
            start, end = review.get('start'), review.get('end')
            if not (_number(start) and _number(end) and 0 <= start < end <= audio['duration_seconds']):
                fail('review_time_range', review_path, 'Use finite seconds with 0 <= start < end <= WAV duration.')
            if review.get('heard_original_language') is not True:
                fail('listening_unconfirmed', review_path + '.heard_original_language',
                     'A reviewer must explicitly confirm hearing the original-language pronunciation.')
            require_text(review.get('notes'), review_path + '.notes')
            if len(errors) == before:
                reviewed.add(item_id)
                bound_reviews.append(dict(term=normalized['canonical'], item=item_id,
                                          audio_path=str(audio_path), audio_sha256=audio['sha256'],
                                          duration_seconds=audio['duration_seconds'], start=start, end=end))
        for item_id in sorted(containing_ids - reviewed):
            fail('listening_review_required', path + '.audio_reviews',
                 f'No valid current-audio listening review for narration item {item_id}.')

    return dict(schema_version='1.0', valid=not errors, passed=not errors,
                stage='listening' if require_listening else 'script',
                narration_items=[item['id'] for item in rows], source_rows_ignored=source_rows_ignored,
                terminology_reviewed=data.get('terminology_reviewed') is True,
                terms_checked=len(normalized_terms), tts_text_matches=tts_text_matches,
                listening_review_bindings_checked=bool(require_listening),
                listening_review_bindings_passed=bool(require_listening and not errors),
                bound_reviews=bound_reviews, automated_phonetic_verification=False,
                scope=('Checks authored context excerpts, spelling, exact optional TTS text, and optional current WAV review bindings. '
                       'Factual support, inventory completeness, question relevance, and heard pronunciation remain authored human-review claims; '
                       'this tool performs no semantic verification, speech recognition, or listening.'),
                errors=errors, warnings=warnings)


def audit(root, text_file=None, require_listening=False):
    """Entry point for production workflow checks (``passed`` report flag)."""
    return validate_narration(root, text_file, require_listening)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workdir')
    parser.add_argument('--text-file', help='Exact TTS paragraphs, relative to workdir or absolute.')
    parser.add_argument('--require-listening', action='store_true')
    parser.add_argument('--out', help='Optional report path, relative to workdir or absolute; default is stdout only.')
    args = parser.parse_args()
    root = Path(args.workdir).resolve()
    report = validate_narration(root, args.text_file, args.require_listening)
    if args.out:
        try:
            out = _resolve(root, args.out)
            protected = {root / 'rundown.json', root / 'narration-plan.json'}
            if args.text_file:
                protected.add(_resolve(root, args.text_file))
            try:
                rows = json.loads((root / 'rundown.json').read_text(encoding='utf-8-sig')).get('items', [])
                for row in rows if isinstance(rows, list) else []:
                    if isinstance(row, dict) and _text(row.get('audio_path')):
                        protected.add(_resolve(root, row['audio_path']))
            except (OSError, UnicodeError, ValueError, AttributeError):
                pass
            if out in {path.resolve() for path in protected}:
                raise ValueError('Report output cannot overwrite a plan, rundown, TTS input, or rundown audio file.')
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        except (OSError, ValueError) as exc:
            report['valid'] = False
            report['passed'] = False
            report['listening_review_bindings_passed'] = False
            report['errors'].append(dict(code='report_output_failed', path=args.out, message=str(exc)))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['valid'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
