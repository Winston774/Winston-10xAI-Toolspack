"""Video Highlights: lightweight agent-assisted local video workflow."""
import importlib
import importlib.util
import json
import shutil
import subprocess
import sys


def doctor(argv):
    import argparse
    parser = argparse.ArgumentParser(description='Check local dependencies without installation or network access')
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--ffprobe', default='ffprobe')
    args = parser.parse_args(argv)
    checks = dict(python=sys.version.split()[0], python_ok=sys.version_info >= (3, 10),
                  optional_faster_whisper=importlib.util.find_spec('faster_whisper') is not None)
    ok = checks['python_ok']
    for name in ('ffmpeg', 'ffprobe'):
        executable = getattr(args, name)
        try:
            process = subprocess.run([executable, '-version'], capture_output=True, text=True, errors='replace', timeout=15)
            value = process.stdout.splitlines()[0] if process.stdout else 'unavailable'
            checks[name] = dict(path=shutil.which(executable), version=value, ok=process.returncode == 0)
            ok = ok and process.returncode == 0
        except (OSError, subprocess.TimeoutExpired) as error:
            checks[name] = dict(ok=False, error=str(error))
            ok = False
    if checks['ffmpeg']['ok']:
        try:
            result = subprocess.run([args.ffmpeg, '-hide_banner', '-encoders'], capture_output=True, text=True, errors='replace', timeout=15)
            encoders = result.stdout
            required = ('libx264', 'aac', 'mjpeg', 'pcm_s16le')
            checks['required_encoders'] = {name: name in encoders for name in required}
            ok = ok and result.returncode == 0 and all(checks['required_encoders'].values())
            result = subprocess.run([args.ffmpeg, '-hide_banner', '-filters'], capture_output=True, text=True, errors='replace', timeout=15)
            checks['optional_subtitle_filter'] = 'subtitles' in result.stdout
        except (OSError, subprocess.TimeoutExpired) as error:
            checks['capability_error'] = str(error)
            ok = False
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if ok else 2


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    commands = dict(prepare='vh_prepare', inspect='vh_evidence', select='vh_plan', render='vh_render')
    if not argv or argv[0] in ('-h', '--help'):
        print('Video Highlights\nCommands: doctor, prepare, inspect, select, validate, render\n'
              'Run: python highlights.py <command> --help\n'
              'Agent reads the transcript/media and writes candidates.json between prepare and select.\n'
              'No API calls or semantic scoring are performed by this CLI.')
        return 0
    if argv[0] == 'doctor':
        return doctor(argv[1:])
    if argv[0] == 'validate':
        import argparse
        from vh_plan import validate_plan
        parser = argparse.ArgumentParser(description='Validate plan structure, score arithmetic and evidence references')
        parser.add_argument('plan')
        args = parser.parse_args(argv[1:])
        try:
            plan, _ = validate_plan(args.plan)
            print(f"VALID ({plan['status']}): structure only; editorial and audiovisual judgment not verified.")
            return 0
        except (OSError, KeyError, ValueError, TypeError) as error:
            print(f'ERROR: {error}', file=sys.stderr)
            return 2
    if argv[0] not in commands:
        print(f'Unknown command: {argv[0]}', file=sys.stderr)
        return 2
    return importlib.import_module(commands[argv[0]]).main(argv[1:])


if __name__ == '__main__':
    raise SystemExit(main())
