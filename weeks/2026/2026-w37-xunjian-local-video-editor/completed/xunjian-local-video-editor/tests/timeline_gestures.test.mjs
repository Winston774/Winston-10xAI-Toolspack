import test from 'node:test';
import assert from 'node:assert/strict';
import { selectionBox, intersects, groupDelta } from '../local_editor/web/timeline-gestures.js';

const clips = [
  { id: 'a', offset: 2, start: 0, end: 2, speed: 1 },
  { id: 'b', offset: 5, start: 0, end: 4, speed: 2 },
  { id: 'other', offset: 10, start: 0, end: 2, speed: 1 },
];
test('marquee works in all drag directions and intersects partial clips', () => {
  const bounds = selectionBox({x:300,y:90},{x:100,y:20});
  assert.deepEqual(bounds,{left:100,right:300,top:20,bottom:90});
  assert.equal(intersects(bounds,{left:290,right:350,top:30,bottom:65}),true);
  assert.equal(intersects(bounds,{left:100,right:200,top:100,bottom:135}),false);
});
test('group clamps as a whole and never collapses relative spacing', () => {
  const delta = groupDelta(clips,['a','b'],-10);
  assert.equal(delta,-2);
  assert.equal((clips[1].offset+delta)-(clips[0].offset+delta),3);
});
test('group snaps trailing edge using playback speed and ignores internal edges', () => {
  assert.ok(Math.abs(groupDelta(clips,['a','b'],2.93,{snapping:true,zoom:100,time:0})-3)<1e-8);
  assert.equal(groupDelta(clips,['a','b'],.04,{snapping:true,zoom:100,time:0}),.04);
});
