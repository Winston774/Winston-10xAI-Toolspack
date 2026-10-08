"""Create a machine-local dependency config without installing software or loading voices."""
from __future__ import annotations
import argparse, json, shutil, sys
from pathlib import Path

KEYS=('python','ffmpeg','ffprobe','npx','gsap_js','sans_ttf','serif_ttf','voice_tool')
LIST_KEYS=('python_extra_paths','font_licenses')
def default_config():
    return Path.home()/'.config/source-led-video/environment.json'

def normalize(data,base):
    result={'schema_version':'1.1'}
    for key in KEYS:
        value=data.get(key)
        if value is not None and (not isinstance(value,str) or not value.strip()):
            raise ValueError(f'{key}: expected a nonempty path or null')
        if value:
            found=shutil.which(value) if key in ('python','ffmpeg','ffprobe','npx') else None
            path=Path(found or value).expanduser()
            # Keep an unresolved executable name to make doctor report it as missing.
            value=str((path if path.is_absolute() else base/path).resolve()) if found or '/' in value or '\\' in value or key not in ('python','ffmpeg','ffprobe','npx') else value
        result[key]=value
    for key in LIST_KEYS:
        values=data.get(key,[])
        if not isinstance(values,list) or any(not isinstance(v,str) or not v.strip() for v in values):
            raise ValueError(f'{key}: expected a list of paths')
        result[key]=[str((Path(v).expanduser() if Path(v).expanduser().is_absolute() else base/Path(v).expanduser()).resolve()) for v in values]
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',default=str(default_config()))
    ap.add_argument('--from',dest='source',help='Import dependency paths from an existing environment.json')
    for key in KEYS:ap.add_argument('--'+key.replace('_','-'))
    for key in LIST_KEYS:ap.add_argument('--'+key.replace('_','-'),action='append')
    args=ap.parse_args();out=Path(args.out).expanduser().resolve()
    if out.exists():raise FileExistsError(f'Refusing to overwrite config: {out}; use a new filename and review the change')
    data={};base=Path.cwd()
    if args.source:
        source=Path(args.source).expanduser().resolve();base=source.parent
        data=json.loads(source.read_text(encoding='utf-8-sig'))
    data.setdefault('python',sys.executable)
    for key in ('ffmpeg','ffprobe','npx'):
        data.setdefault(key,shutil.which('npx.cmd' if key=='npx' and sys.platform=='win32' else key))
    data=normalize(data,base)
    overrides={key:getattr(args,key) for key in (*KEYS,*LIST_KEYS) if getattr(args,key) is not None}
    data.update(normalize({**data,**overrides},Path.cwd()))
    out.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation avoids accidental overwrite if another process creates it.
    with out.open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'created':str(out),'configured_keys':[k for k in KEYS if data.get(k)],'software_installed':False,'voice_loaded':False},ensure_ascii=False))

if __name__=='__main__':
    try:main()
    except (ValueError,FileExistsError,FileNotFoundError) as exc:
        print(f'ERROR: {exc}',file=sys.stderr);raise SystemExit(2)
