import test from 'node:test';
import assert from 'node:assert/strict';
import {copyClips, selectedCharacters, transcriptRows} from '../local_editor/web/transcript-edit.js';
import {panelHTML} from '../local_editor/web/panels.js';

const p={id:'p',media:[],titles:[],clips:[{id:'a',media_id:'m',track:'video',start:1,end:3,offset:5,speed:2}],
 captions:[{id:'s',media_id:'m',start:0,end:4,text:'刪保留尾',words:[
  {start:0,end:1,text:'刪'},{start:1,end:3,text:'保留'},{start:3,end:4,text:'尾'}]}]};
test('transcript sidebar follows trimmed timeline and disappears with deleted clips',()=>{
 const row=transcriptRows(p)[0]; assert.equal(row.text,'保留');assert.equal(row.start,5);assert.equal(row.end,6);
 assert.deepEqual(transcriptRows({...p,clips:[]}),[]);
 const html=panelHTML('captions',p,{});
 assert.ok(html.includes('data-caption-text="s:a"'));
 assert.ok(!html.includes('data-caption-save'));
 assert.ok(!html.includes('data-caption-delete'));
 assert.ok(html.includes('readonly'));
});
test('copy freezes properties without ids and without mutating the project',()=>{
 const copied=copyClips(p,['a']);assert.equal(copied.projectId,'p');assert.equal(copied.clips[0].id,undefined);
 copied.clips[0].offset=100;assert.equal(p.clips[0].offset,5);
 assert.equal(copyClips(p,[]),null);
});
test('text selection converts browser UTF-16 indices to API codepoints',()=>{
 assert.deepEqual(selectedCharacters('好😀呢',3,4),{start:2,end:3});
 assert.equal(selectedCharacters('你好',1,1),null);
});
