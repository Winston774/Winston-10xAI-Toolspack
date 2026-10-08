"""Check generated scene structure and optional rendered-frame evidence against the configured documentary style."""
from pathlib import Path
from html.parser import HTMLParser
import argparse,json,re,sys
from visual_contract import review_markers

class Scene(HTMLParser):
    def __init__(self):super().__init__();self.bands=0;self.tears=0;self.polygons=[];self.ids=set()
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);classes=a.get('class','').split()
        if a.get('id'):self.ids.add(a['id'])
        if 'caption-band' in classes:
            if a.get('data-slv-component')=='torn-caption-band-v1':self.bands+=1
        if tag=='svg' and 'slv-caption-tear' in classes:self.tears+=1
        if tag=='polygon' and a.get('points'):self.polygons.append(a['points'])

def tweens(html,selector):
    # Read flat GSAP fromTo declarations as data; do not execute arbitrary project JS.
    pattern=r'tl\.fromTo\(\s*["\']'+re.escape(selector)+r'["\']\s*,\s*\{([^{}]+)\}\s*,\s*\{([^{}]+)\}\s*,\s*([0-9.]+)\s*\)'
    def props(text):return {k:float(v) for k,v in re.findall(r'\b(x|y|scale|opacity|duration)\s*:\s*(-?(?:\d+(?:\.\d*)?|\.\d+))',text)}
    return [(props(a),props(b),float(at)) for a,b,at in re.findall(pattern,html)]

def has_tween(found,initial,target,at):
    return any(abs(t-at)<.002 and all(abs(a.get(k,9999)-v)<.002 for k,v in initial.items()) and all(abs(b.get(k,9999)-v)<.002 for k,v in target.items()) for a,b,t in found)

def audit(root,project='motion',frame_manifest=None,delivery=False):
    root=Path(root);plan=json.loads((root/'qa/resolved-plan.json').read_text(encoding='utf-8-sig'))
    marker_report=review_markers(root,plan['timeline']);errors=[];scenes=[]
    for item in plan['timeline']:
        p=root/project/'compositions'/f'{item["id"]}.html'
        if not p.is_file():errors.append(f'Missing scene {item["id"]}');continue
        html=p.read_text(encoding='utf-8');s=Scene();s.feed(html)
        valid_edge=False
        for points in s.polygons:
            try:
                pairs=[tuple(map(float,v.split(','))) for v in points.split()]
                upper=[y for x,y in pairs[:-2]]
                valid_edge|=len(upper)>=10 and max(upper)-min(upper)>=5
            except (ValueError,TypeError):pass
        if s.bands!=1 or s.tears!=1 or not valid_edge:errors.append(f'{item["id"]}: missing shared irregular paper-edge caption component')
        own=[m for m in json.loads((root/'markers.json').read_text(encoding='utf-8-sig'))['markers'] if m['item']==item['id']]
        for k,m in enumerate(own):
            if f'{item["id"]}-footage' not in s.ids:errors.append(f'{item["id"]}: missing reframe wrapper')
            moves=tweens(html,f'#{item["id"]}-footage')
            enter=max(0,m['start']-item['source_start']-.45);leave=m['end']-item['source_start']
            if not has_tween(moves,dict(x=0,y=0,scale=1),dict(x=625,y=64,scale=.66,duration=.7),enter):errors.append(f'{m["id"]}: shrink-and-move animation missing or retimed')
            if not has_tween(moves,dict(x=625,y=64,scale=.66),dict(x=0,y=0,scale=1,duration=.7),leave):errors.append(f'{m["id"]}: source restoration animation missing or retimed')
            for j in range(len(m['steps'])):
                if f'{item["id"]}-marker{k}-step{j}' not in s.ids:errors.append(f'{m["id"]}: missing visible point {j+1}')
                reveal=tweens(html,f'#{item["id"]}-marker{k}-step{j}')
                if not has_tween(reveal,dict(opacity=0),dict(opacity=1,duration=.5),m['steps'][j]['at']-item['source_start']+.1):errors.append(f'{m["id"]}: point {j+1} lacks its source-timed reveal')
        scenes.append(dict(id=item['id'],caption_bands=s.bands,irregular_edges=s.tears))
    thumbnail_review=None
    if delivery:
        tb=json.loads((root/'thumbnail-brief.json').read_text(encoding='utf-8-sig'));opening=json.loads((root/'opening-selection.json').read_text(encoding='utf-8-sig'));profile=json.loads((root/'profile.json').read_text(encoding='utf-8-sig'))
        configured_style=profile.get('thumbnail_style')
        if configured_style not in ('photographic-closeup-white-yellow-v1','custom'):errors.append('Choose a supported thumbnail_style or custom in the profile')
        if tb.get('style')!=configured_style:errors.append('Thumbnail style differs from profile.thumbnail_style')
        reference=tb.get('reference');direction=tb.get('art_direction')
        has_reference=isinstance(reference,str) and bool(reference.strip()) and tb.get('reference_viewed') is True
        has_direction=isinstance(direction,str) and bool(direction.strip()) and tb.get('art_direction_reviewed') is True
        if not (has_reference or has_direction):errors.append('Provide a viewed reference or a written and reviewed art_direction; no personal reference image is bundled')
        for key in ('headline_context','headline_question','portrait_source','promise'):
            if not isinstance(tb.get(key),str) or not tb[key].strip():errors.append(f'Thumbnail missing {key}')
        if tb.get('promise')!=opening.get('packaging',{}).get('thumbnail_promise'):errors.append('Thumbnail promise differs from the reviewed first-answer promise')
        if tb.get('brand')!=profile.get('brand'):errors.append('Thumbnail brand differs from channel profile')
        output=Path(tb['output']) if tb.get('output') else None
        if output and not output.is_absolute():output=root/output
        if not output or not output.is_file():errors.append('Thumbnail output file is missing')
        review=tb.get('review',{})
        for key in ('mobile_legibility','faithful_portrait','promise_matches_first_answer','style_matches_direction','rendered_thumbnail_viewed'):
            if review.get(key) is not True:errors.append(f'Thumbnail review is incomplete: {key}')
        if not review.get('evidence'):errors.append('Thumbnail review needs actual output viewing, mobile readability and direction-comparison evidence')
        thumbnail_review=review
        if not frame_manifest:errors.append('Delivery style check requires rendered edge frame evidence; structure alone is insufficient')
    pixel_checks=[]
    if frame_manifest:
        from PIL import Image
        manifest_path=Path(frame_manifest).resolve();frames=json.loads(manifest_path.read_text(encoding='utf-8-sig'))['frames']
        if not isinstance(frames,list) or not frames:raise ValueError('Rendered frame evidence must contain at least one actual frame')
        for f in frames:
            p=Path(f['path']);p=p if p.is_absolute() else manifest_path.parent/p
            with Image.open(p) as im:
                im=im.convert('RGB');w,h=im.size;band=220 if f.get('narration') else 260;base=round(h*(1080-band)/1080)
                edges=[]
                for sample in range(1,80):
                    x=round(w*sample/80)
                    for y in range(max(0,base-round(h*22/1080)),min(h,base+round(h*8/1080))):
                        if max(abs(a-b) for a,b in zip(im.getpixel((x,y)),(23,24,21)))<=12:
                            # Require a solid run into the band, rather than a dark object in source footage.
                            if all(max(abs(a-b) for a,b in zip(im.getpixel((x,yy)),(23,24,21)))<=12 for yy in range(y,min(h,base+7))):edges.append(y);break
                span=max(edges)-min(edges) if edges else 0;ok=len(edges)>60 and span>=max(3,h*5/1080)
                pixel_checks.append(dict(path=str(p),edge_samples=len(edges),edge_height_variation=span,passed=ok))
                if not ok:errors.append(f'{p.name}: rendered paper edge is flat, obscured or not detected')
    return dict(passed=not errors,scenes=scenes,annotation_review=marker_report,rendered_edge_checks=pixel_checks,thumbnail_review=thumbnail_review,errors=errors,continuous_viewing=False,note='Structure and optional pixel evidence; semantic correctness, portrait safety and motion states require the sampled proof frames to be reviewed.')

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('workdir');ap.add_argument('--project',default='motion');ap.add_argument('--frames');ap.add_argument('--delivery',action='store_true');ap.add_argument('--out');args=ap.parse_args()
    try:report=audit(args.workdir,args.project,args.frames,args.delivery)
    except (ValueError,KeyError,FileNotFoundError) as exc:report=dict(passed=False,errors=[str(exc)])
    out=Path(args.out) if args.out else Path(args.workdir)/'qa/style-check.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,ensure_ascii=False));return 0 if report['passed'] else 2
if __name__=='__main__':raise SystemExit(main())
