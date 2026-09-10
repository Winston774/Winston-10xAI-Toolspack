"""Occurrence-scoped transcript cuts and timeline clipboard insertion."""
import copy

from .core import EditorError, _cut_timeline, _id, clip_duration, mapped_captions


def cut_caption(project, params):
    row = next((c for c in mapped_captions(project)
                if c['source_caption_id'] == params['caption_id'] and c['clip_id'] == params['clip_id']), None)
    if row is None:
        raise EditorError('這句字幕已不在選取片段中，請重新選取。')
    if row['text'] != params['text']:
        raise EditorError('字幕內容已改變，請重新選取文字。')
    selection = params.get('selection')
    if selection is None:
        _cut_timeline(project, [(row['start'], row['end'])])
        return
    left, right = selection['start'], selection['end']
    if not 0 <= left < right <= len(row['text']):
        raise EditorError('請先選取要剪除的文字。')
    if not row.get('words') or row.get('alignment_status') == 'stale':
        raise EditorError('這句缺少有效的詞級時間，請先重新辨識字幕；仍可剪除整句。')
    joined = ''.join(w['text'] for w in row['words'])
    padding = len(joined) - len(joined.lstrip())
    left += padding
    right += padding
    cursor, selected, split_ids = 0, [], set()
    for word in row['words']:
        n = len(word['text'])
        a, z = max(left-cursor, 0), min(right-cursor, n)
        if a < z:
            if word['partial_word'] and (a != 0 or z != n):
                raise EditorError('選字跨到已裁切的詞，請選取完整詞句或重新辨識。')
            start = word['start'] + (word['end']-word['start'])*a/n
            end = word['start'] + (word['end']-word['start'])*z/n
            if end-start <= 1e-7:
                raise EditorError('選取文字沒有可用的聲音長度，請連同相鄰文字選取。')
            selected.append((start, end))
            if a != 0 or z != n:
                split_ids.add(word['source_word_id'])
        cursor += n
    if not selected:
        raise EditorError('選取文字無法對應聲音，請重新辨識字幕。')
    # Subword timing is estimated uniformly inside the ASR word. Keep the source
    # text intact so other placements and later paste operations retain it.
    caption = next(c for c in project['captions'] if c['id'] == params['caption_id'])
    words = []
    for word in caption['words']:
        if word['id'] not in split_ids:
            words.append(word)
            continue
        count = len(word['text'])
        for i, char in enumerate(word['text']):
            words.append({**word, 'id': _id(), 'text': char,
                          'start': word['start']+(word['end']-word['start'])*i/count,
                          'end': word['start']+(word['end']-word['start'])*(i+1)/count})
    caption['words'] = words
    # Include pauses between the first and last selected characters.
    _cut_timeline(project, [(selected[0][0], selected[-1][1])])


def insert_space(project, at, length):
    clips = []
    for original in project['clips']:
        clip = copy.deepcopy(original)
        start, end = clip['offset'], clip['offset'] + clip_duration(clip)
        if start >= at-1e-7:
            clip['offset'] += length
        elif end > at+1e-7:
            second = copy.deepcopy(clip)
            source_at = clip['start'] + (at-start)*clip['speed']
            clip['end'] = source_at
            clip['fade_out'] = 0
            second.update(id=_id(), start=source_at, offset=at+length, fade_in=0)
            clip['fade_in'] = min(clip['fade_in'], clip_duration(clip))
            second['fade_out'] = min(second['fade_out'], clip_duration(second))
            clips.append(clip)
            clip = second
        clips.append(clip)
    project['clips'] = clips
    titles = []
    for title in project['titles']:
        if title['start'] >= at:
            titles.append({**title, 'start': title['start']+length, 'end': title['end']+length})
        elif title['end'] > at:
            titles.extend([{**title, 'end': at}, {**title, 'id': _id(), 'start': at+length, 'end': title['end']+length}])
        else:
            titles.append(title)
    project['titles'] = titles
