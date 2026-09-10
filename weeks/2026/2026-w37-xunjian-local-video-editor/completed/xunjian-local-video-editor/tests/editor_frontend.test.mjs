import test from 'node:test';
import assert from 'node:assert/strict';
import {mappedCaptions,clipFade,sampleClipWaveform} from '../local_editor/web/utils.js';

test('word-level captions crop text and timestamps through source trim and speed',()=>{
 const caption={id:'s',media_id:'m',start:0,end:6,text:'刪掉保留文字尾巴',words:[
  {start:0,end:1,text:'刪掉'},{start:1,end:3,text:'保留'},{start:3,end:5,text:'文字'},{start:5,end:6,text:'尾巴'}]};
 const project={captions:[caption],clips:[{id:'c',media_id:'m',track:'video',start:2,end:4,offset:10,speed:2}]};
 const result=mappedCaptions(project);
 assert.equal(result.length,1);
 assert.equal(result[0].id,'s:c');
 assert.equal(result[0].source_caption_id,'s');
 assert.equal(result[0].text,'保留文字');
 assert.equal(result[0].start,10);
 assert.equal(result[0].end,11);
 assert.deepEqual(result[0].words,[{start:10,end:10.5,text:'保留'},{start:10.5,end:11,text:'文字'}]);
 assert.equal(caption.text,'刪掉保留文字尾巴');
});

test('instant words keep left boundary, drop right boundary, and wordless cropped cues disappear',()=>{
 const clip={id:'c',media_id:'m',track:'video',start:2,end:4,offset:0,speed:1};
 const captions=[{id:'s',media_id:'m',start:0,end:6,text:'原文',words:[
  {start:2,end:2,text:'左'},{start:4,end:4,text:'右'}]},
  {id:'empty',media_id:'m',start:0,end:6,text:'已剪除',words:[{start:0,end:1,text:'已剪除'}]}];
 const result=mappedCaptions({clips:[clip,{...clip,id:'audio',track:'audio'}],captions});
 assert.equal(result.length,1);
 assert.equal(result[0].text,'左');
 assert.deepEqual(result[0].words,[{start:0,end:0,text:'左'}]);
});

test('caption placements repeat independently and sort by start, end, then ID like core',()=>{
 const clip={id:'z',media_id:'m',track:'video',start:0,end:2,offset:2,speed:1};
 const captions=[{id:'s',media_id:'m',start:0,end:2,text:'完整字幕'}];
 assert.deepEqual(mappedCaptions({captions,clips:[clip,{...clip,id:'a'}, {...clip,id:'first',offset:0}]}).map(c=>c.id),['s:first','s:a','s:z']);
});

test('visual and audio fade envelopes clamp to clip duration and multiply when overlapping',()=>{
 const clip={start:0,end:4,speed:2,offset:5,fade_in:10,fade_out:10};
 assert.equal(clipFade(clip,4.9),0);
 assert.equal(clipFade(clip,5),0);
 assert.equal(clipFade(clip,6),.25);
 assert.equal(clipFade(clip,7),0);
 assert.equal(clipFade({...clip,fade_in:0,fade_out:0},6),1);
 assert.equal(clipFade({...clip,fade_in:.5,fade_out:.5},5.25),.5);
});

test('waveform samples the trimmed source interval regardless of timeline offset or speed',()=>{
 const media={duration:10,waveform_duration:10,waveform:[0,.1,.2,.3,.4,.5,.6,.7,.8,.9]};
 const clip={start:2,end:4,offset:0,speed:1};
 assert.deepEqual(sampleClipWaveform(media,clip,2),[.2,.3]);
 assert.deepEqual(sampleClipWaveform(media,{...clip,offset:100,speed:2},2),[.2,.3]);
 assert.deepEqual(sampleClipWaveform(media,{...clip,start:0,end:10},2),[.4,.9]);
});

test('bounded waveform coverage leaves unmeasured sections blank instead of implying silence',()=>{
 const media={duration:20,waveform_duration:10,waveform:[0,.1,.2,.3,.4,.5,.6,.7,.8,.9]};
 assert.deepEqual(sampleClipWaveform(media,{start:8,end:12},4),[.8,.9,null,null]);
 assert.deepEqual(sampleClipWaveform(media,{start:11,end:15},4),[]);
 assert.deepEqual(sampleClipWaveform({duration:10,waveform:[]},{start:0,end:2},4),[]);
});
