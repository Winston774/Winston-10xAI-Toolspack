import test from 'node:test';
import assert from 'node:assert/strict';
import { clipAtPlayhead, playheadShortcut } from '../local_editor/web/playhead-edit.js';
import { Timeline } from '../local_editor/web/timeline.js';

const p = { clips: [
  {id:'a',track:'video',offset:0,start:0,end:4,speed:1},
  {id:'b',track:'video',offset:4,start:0,end:4,speed:2},
  {id:'audio',track:'audio',offset:0,start:0,end:10,speed:1},
] };
test('playhead targets current primary clip regardless of old or multiple selections', () => {
  assert.equal(clipAtPlayhead(p, 5).id, 'b');
  assert.equal(clipAtPlayhead(p, 2).id, 'a');
  for (const time of [0,4,6,8]) assert.equal(clipAtPlayhead(p,time),null);
  assert.equal(clipAtPlayhead({...p, clips:[...p.clips,{...p.clips[0],id:'top'}]},2).id,'top');
});
test('shortcuts work in transcript but protect typing, composition, repeats and modifiers', () => {
  const event = {key:'Q',target:{tagName:'TEXTAREA',matches:()=>true}};
  assert.equal(playheadShortcut(event),'trim-before');
  assert.equal(playheadShortcut({...event,key:'w'}),'trim-after');
  assert.equal(playheadShortcut({...event,key:'s'}),'split');
  assert.equal(playheadShortcut({...event,target:{tagName:'INPUT',matches:selector=>selector.includes('input[type="range"]')}}),'trim-before');
  for (const flag of ['repeat','isComposing','ctrlKey','metaKey','altKey'])
    assert.equal(playheadShortcut({...event,[flag]:true}),null);
  for (const tagName of ['INPUT','TEXTAREA','SELECT'])
    assert.equal(playheadShortcut({...event,target:{tagName,matches:()=>false}}),null);
  assert.equal(playheadShortcut({...event,target:{isContentEditable:true}}),null);
});
test('caption navigation reveals an offscreen playhead without moving a visible viewport', () => {
  const scroller={scrollLeft:0,clientWidth:600};
  const timeline={root:{querySelector:()=>scroller},zoom:50};
  Timeline.prototype.revealTime.call(timeline,20);
  assert.equal(scroller.scrollLeft,918);
  Timeline.prototype.revealTime.call(timeline,22);
  assert.equal(scroller.scrollLeft,918);
  Timeline.prototype.revealTime.call(timeline,0);
  assert.equal(scroller.scrollLeft,0);
});
