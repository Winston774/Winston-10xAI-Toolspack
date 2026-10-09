#!/usr/bin/env python3
"""Check/render an editorial revision with explicitly supplied local tools."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('revision');p.add_argument('action',choices=['check','render'])
    p.add_argument('--hyperframes',required=True,help='Existing local HyperFrames executable')
    p.add_argument('--browser',required=True,help='Existing local Chrome executable')
    a=p.parse_args();root=Path(a.revision).resolve();binary=Path(a.hyperframes).resolve();browser=Path(a.browser).resolve()
    if not (root/'motion/index.html').is_file():p.error('Revision has no motion/index.html')
    if not binary.is_file() or not browser.is_file():p.error('Supply existing local executables; nothing is downloaded')
    output=root/'exports/final.mp4'
    if a.action=='render' and output.exists():p.error('Existing final.mp4 refused; choose a new revision')
    qa=root/'qa';qa.mkdir(exist_ok=True);stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    env=os.environ.copy();env.update(DO_NOT_TRACK='1',HYPERFRAMES_BROWSER_PATH=str(browser),PRODUCER_BROWSER_GPU_MODE='software')
    check=qa/f'browser-check-{stamp}.json'
    with check.open('w',encoding='utf-8') as out,(qa/f'browser-check-{stamp}.stderr').open('w',encoding='utf-8') as err:
        result=subprocess.run([str(binary),'check',str(root/'motion'),'--timeout','30000','--snapshots','--json'],env=env,stdout=out,stderr=err)
    if result.returncode:return result.returncode
    try:verified=json.loads(check.read_text(encoding='utf-8'))
    except (ValueError,OSError):p.error('Check did not return a readable JSON report')
    if verified.get('ok') is not True:p.error('Check has errors; inspect '+str(check))
    if a.action=='check':print(check);return 0
    output.parent.mkdir(exist_ok=True)
    with (qa/f'render-{stamp}.log').open('w',encoding='utf-8') as log:
        result=subprocess.run([str(binary),'render',str(root/'motion'),'--quality','delivery','--fps','30','--workers','2','--strict','--no-best-effort','--no-browser-gpu','--output',str(output)],env=env,stdout=log,stderr=subprocess.STDOUT)
    print(output if result.returncode==0 else 'Render failed; inspect the revision qa logs')
    return result.returncode

if __name__=='__main__':raise SystemExit(main())
