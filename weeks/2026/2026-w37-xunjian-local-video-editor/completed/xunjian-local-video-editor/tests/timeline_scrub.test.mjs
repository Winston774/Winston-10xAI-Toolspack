import test from 'node:test';
import assert from 'node:assert/strict';
import { Timeline } from '../local_editor/web/timeline.js';

function fixture(t) {
  const oldWindow = globalThis.window, oldDocument = globalThis.document;
  globalThis.window = new EventTarget();
  globalThis.document = { body:{classList:{contains:()=>false}}, querySelector:()=>null };
  class Root extends EventTarget {
    constructor() { super(); this.classList={toggle(){}}; this.captures=new Set(); this.innerHTML=''; }
    setAttribute() {}
    focus() {}
    set innerHTML(value) {
      this.html=value;
      this.nodes=Object.fromEntries(['.ruler','.playhead','.timeline-inner','.timeline-scroll'].map(key=>
        [key,Object.assign(new EventTarget(),{style:{},scrollLeft:0,clientWidth:600,
          getBoundingClientRect:()=>({left:118-this.nodes['.timeline-scroll'].scrollLeft})})]));
    }
    querySelector(key) { return this.nodes[key] || null; }
    querySelectorAll() { return []; }
    setPointerCapture(id) { this.captures.add(id); }
    hasPointerCapture(id) { return this.captures.has(id); }
    releasePointerCapture(id) { this.captures.delete(id); }
  }
  const root=new Root(), seeks=[];
  const timeline=new Timeline(root,{onSeek:time=>{seeks.push(time);timeline.setTime(time);}});
  const project=(end=10,id='p')=>({id,media:[],captions:[],titles:[],clips:[
    {id:'a',media_id:'m',track:'video',offset:0,start:0,end,speed:1}]});
  timeline.setProject(project(),null);
  timeline.zoom=50;
  function send(type,x,{pointerId=1,buttons=1,key}={}) {
    const event=Object.assign(new Event(type,{cancelable:true}),{clientX:x,pointerId,buttons,key});
    window.dispatchEvent(event);
  }
  const down=()=>timeline.scrub({button:0,pointerId:1,clientX:318,preventDefault(){}});
  t.after(()=>{timeline.cancelGesture?.();globalThis.window=oldWindow;globalThis.document=oldDocument;});
  return {root,timeline,seeks,project,send,down};
}

test('held scrub survives repeated Q/W redraws and follows movement until release',t=>{
  const {root,timeline,project,send,down}=fixture(t);
  down(); assert.equal(timeline.time,4);
  const oldRuler=root.querySelector('.ruler');
  timeline.setProject(project(8),null);
  timeline.setTime(2); // Q/W chooses the cut position after accepting the edit.
  timeline.rebaseScrub();
  assert.notEqual(root.querySelector('.ruler'),oldRuler);
  assert.equal(root.hasPointerCapture(1),true);
  send('pointermove',368);
  assert.equal(timeline.time,3); // +50px is +1s, without snapping back to old coordinates.
  timeline.setProject(project(6),null);
  timeline.setTime(1); timeline.rebaseScrub();
  send('pointermove',418); assert.equal(timeline.time,2);
  send('pointerup',418,{buttons:0});
  assert.equal(root.hasPointerCapture(1),false);
  send('pointermove',468); assert.equal(timeline.time,2);
  assert.equal(timeline.cancelGesture,null);
});

test('scroll changes rebase the held pointer and different pointers are ignored',t=>{
  const {root,timeline,send,down}=fixture(t);
  down(); root.querySelector('.timeline-scroll').scrollLeft=200;
  timeline.rebaseScrub();
  send('pointermove',418,{pointerId:2}); assert.equal(timeline.time,4);
  send('pointermove',368); assert.equal(timeline.time,5);
  send('pointermove',418,{buttons:0}); // Recover a release missed outside the window.
  assert.equal(timeline.cancelGesture,null);
  assert.equal(root.hasPointerCapture(1),false);
});

test('Escape and blur stop dragging without restoring a stale pre-cut position',t=>{
  const {timeline,project,send,down}=fixture(t);
  for (const event of ['keydown','blur','pointercancel']) {
    down(); timeline.setProject(project(6),null);
    timeline.setTime(1);timeline.rebaseScrub();
    send('pointermove',368); assert.equal(timeline.time,2);
    send(event,368,{key:'Escape'});
    assert.equal(timeline.time,1);
    assert.equal(timeline.cancelGesture,null);
  }
});

test('project switching and clip gestures still cancel instead of leaking into new state',t=>{
  const {timeline,project,down}=fixture(t);
  down(); timeline.setProject(project(10,'other'),null);
  assert.equal(timeline.cancelGesture,null);
  let cancelled=0;
  timeline.trackPointer({pointerId:1},()=>{},()=>{},()=>cancelled++);
  timeline.render(); assert.equal(cancelled,1);
  assert.equal(timeline.cancelGesture,null);
});
