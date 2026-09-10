import test from 'node:test';
import assert from 'node:assert/strict';
import { waveformWindow, waveformChunks, waveformPeak } from '../local_editor/web/waveform.js';
import { Timeline } from '../local_editor/web/timeline.js';

test('trimmed, moved and sped-up video maps scrolled pixels to the original audio', () => {
  const clip = {start: 12, end: 24, offset: 5, speed: 2};
  assert.deepEqual(waveformWindow(clip, 100, 700, 1000), {x:700, width:300, start:16, end:22});
  assert.deepEqual(waveformWindow(clip, 50, 0, 1000), {x:250, width:300, start:12, end:24});
  assert.equal(waveformWindow(clip, 100, 1200, 1800), null);
});

test('chunk boundaries and audio beyond the old 30-minute limit remain addressable', () => {
  assert.deepEqual(waveformChunks(29.5, 30), [0]);
  assert.deepEqual(waveformChunks(29.5, 30.5), [0, 1]);
  assert.deepEqual(waveformChunks(1800, 1801), [60]);
});

test('waveform distinguishes known silence, amplitude differences and missing coverage', () => {
  const data = new Map([[0, {start:0, end:4, bucket_seconds:1, peaks:[0, .1, .8, .2]}]]);
  assert.equal(waveformPeak(data, 0, 1), 0);
  assert.equal(waveformPeak(data, 1, 2), .1);
  assert.equal(waveformPeak(data, 2, 3), .8);
  assert.equal(waveformPeak(data, 0, 4), .8);
  assert.equal(waveformPeak(data, 3, 5), null);
  assert.equal(waveformPeak(data, 30, 31), null);
  data.set(0, {start:0, end:30, bucket_seconds:1, peaks:Array(30).fill(.2)});
  data.set(1, {start:30, end:31, bucket_seconds:1, peaks:[.9]});
  assert.equal(waveformPeak(data, 29.5, 30.5), .9);
});

test('waveform lane follows video cuts only, preserving exact offset and duration', () => {
  const timeline = Object.create(Timeline.prototype);
  timeline.zoom = 100;
  timeline.project = {media:[{id:'m', name:'<voice>', has_audio:true}], clips:[
    {id:'v1', media_id:'m', track:'video', start:0, end:2, speed:1, offset:0},
    {id:'v2', media_id:'m', track:'video', start:4, end:8, speed:2, offset:3},
    {id:'music', media_id:'m', track:'audio', start:0, end:8, speed:1, offset:0},
  ]};
  const html = timeline.waveformHTML(800);
  assert.equal((html.match(/data-waveform-id=/g) || []).length, 2);
  assert.match(html, /left:300px;width:200px/);
  assert.match(html, /&lt;voice&gt;/);
  assert.doesNotMatch(html, /data-waveform-id="music"/);
});
