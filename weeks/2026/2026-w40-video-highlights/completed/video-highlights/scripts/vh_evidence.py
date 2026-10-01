"""Prepare a bounded preview for actual visual/audio review, without claiming review."""
import argparse
import json
import math
import subprocess
import sys
from pathlib import Path
from vh_plan import interval, number, read_json, sha256, validate_project, write_json


def run(command):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', errors='replace')
    if result.returncode:
        raise ValueError(result.stderr[-3000:])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project')
    parser.add_argument('--start', required=True, type=float)
    parser.add_argument('--end', required=True, type=float)
    parser.add_argument('--out', required=True)
    parser.add_argument('--every', type=float, default=3)
    parser.add_argument('--max-frames', type=int, default=120)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    args = parser.parse_args(argv)
    try:
        project = read_json(args.project)
        duration = validate_project(project)
        start, end = interval(vars(args), duration, 'preview')
        number(args.every, 'every', 0.02)
        if args.max_frames < 2 or args.max_frames > 1000:
            raise ValueError('max-frames must be between 2 and 1000')
        total = math.ceil((end-start) / args.every)
        if total > args.max_frames:
            raise ValueError('Too many frames; shorten the range or increase --every')
        source = project['source']
        if sha256(source['path']) != source['sha256']:
            raise ValueError('Source changed; prepare a new project')
        out = Path(args.out).resolve()
        out.mkdir(parents=True, exist_ok=False)
        ff = [args.ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-n']
        length = end-start
        video_map = f"0:{source['video_stream_index']}" if 'video_stream_index' in source else '0:v:0'
        audio_map = f"0:{source['audio_stream_index']}" if source.get('audio_stream_index') is not None else '0:a:0?'
        normalize = f"scale={source['width']}:{source['height']},setsar=1"
        command = ff + ['-ss', str(start), '-i', source['path'], '-t', str(length), '-map', video_map,
                        '-map', audio_map, '-vf', normalize + ',scale=960:-2',
                        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '25', '-pix_fmt', 'yuv420p',
                        '-c:a', 'aac', '-movflags', '+faststart', str(out / 'preview.mp4')]
        run(command)
        frames = []
        for index in range(total):
            requested = start + index * args.every
            name = f'frame-{index+1:04d}.jpg'
            run(ff + ['-ss', str(requested), '-i', source['path'], '-map', video_map, '-frames:v', '1',
                      '-vf', normalize + ',scale=1280:-2', '-q:v', '3', str(out/name)])
            if not (out/name).is_file():
                raise ValueError(f'No decoded frame near {requested}; shorten the interval')
            frames.append(dict(file=name, requested_source_time=requested))
        if source['has_audio']:
            run(ff + ['-ss', str(start), '-i', source['path'], '-t', str(length), '-map', audio_map,
                      '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(out/'audio.wav')])
        manifest = dict(schema_version=1, source_sha256=source['sha256'], start=start, end=end,
                        preview='preview.mp4', preview_zero_source_seconds=start, frames=frames,
                        audio='audio.wav' if source['has_audio'] else None,
                        review=dict(visual='unreviewed', audio='unreviewed'),
                        limitation='Frame times are seek requests, not decoded PTS. Preview audio is lossy; use source for mix/sync sign-off.')
        write_json(out/'evidence.json', manifest)
        print(out/'evidence.json')
        return 0
    except (OSError, KeyError, ValueError, TypeError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
