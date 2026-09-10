import copy
import tempfile
import unittest

from local_editor.core import EditorError, mapped_captions, project_duration
from local_editor.service import EditorService


class TranscriptEditingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.service = EditorService(temp.name)
        self.addCleanup(self.service.close)
        self.store = self.service.store
        self.p = self.store.create_project('字幕編輯測試')
        self.edit('media_add', {'media': {'id':'m','name':'fixture','path':'fixture.mp4','kind':'video','duration':20,'has_audio':True}})
        self.edit('clip_add', {'id':'a','media_id':'m','start':0,'end':4,'offset':0})
        self.edit('clip_add', {'id':'b','media_id':'m','start':0,'end':4,'offset':4})
        self.edit('captions_set', {'media_id':'m','captions':[{'id':'s','start':0,'end':4,'text':'今天呢很好',
            'words':[{'text':'今天呢','start':0,'end':3},{'text':'很好','start':3,'end':4}]}]})

    def edit(self, action, params):
        self.p = self.store.mutate(self.p['id'], self.p['version'], action, params)

    def cut(self, selection=None, **extra):
        params={'caption_id':'s','clip_id':'a','text':'今天呢很好', **extra}
        if selection is not None: params['selection']=selection
        self.p=self.service.edit(self.p['id'], {'expected_version':self.p['version'],'action':'caption_cut','params':params})

    def test_timeline_delete_removes_only_visible_caption_and_undo_restores(self):
        self.edit('clip_delete',{'clip_id':'a','ripple':True})
        self.assertEqual([(c['clip_id'],c['start']) for c in mapped_captions(self.p)],[('b',0)])
        self.edit('undo',{})
        self.assertEqual(len(mapped_captions(self.p)),2)

    def test_character_cut_splits_word_and_keeps_other_copy_text(self):
        before=copy.deepcopy(self.p)
        self.cut({'start':2,'end':3})
        rows=mapped_captions(self.p)
        self.assertEqual(''.join(c['text'] for c in rows if c['clip_id']!='b'),'今天很好')
        self.assertEqual(next(c['text'] for c in rows if c['clip_id']=='b'),'今天呢很好')
        self.assertEqual(project_duration(self.p),7)
        self.edit('undo',{})
        self.assertEqual(self.p['clips'],before['clips'])
        self.assertEqual(self.p['captions'],before['captions'])

    def test_whole_sentence_cut_is_scoped_to_one_copy(self):
        self.cut()
        self.assertEqual([c['clip_id'] for c in mapped_captions(self.p)],['b'])
        self.assertEqual(project_duration(self.p),4)

    def test_selection_uses_timeline_speed(self):
        self.edit('clip_update',{'clip_id':'a','changes':{'speed':2}})
        self.cut({'start':2,'end':3})
        self.assertEqual(next(c['offset'] for c in self.p['clips'] if c['id']=='b'),3.5)

    def test_stale_text_and_missing_alignment_are_rejected_atomically(self):
        before=copy.deepcopy(self.p)
        with self.assertRaises(EditorError): self.cut({'start':2,'end':3},text='changed')
        self.assertEqual(self.store.get_project(self.p['id']),before)
        self.edit('caption_update',{'caption_id':'s','changes':{'text':'今天很好'}})
        with self.assertRaises(EditorError): self.cut({'start':0,'end':1},text='今天很好')

    def test_paste_inserts_at_playhead_splits_existing_and_undo_is_one_step(self):
        before=copy.deepcopy(self.p)
        clip={k:v for k,v in self.p['clips'][0].items() if k!='id'}
        self.p=self.service.edit(self.p['id'], {'expected_version':self.p['version'],'action':'clip_paste',
             'params':{'at':1,'clips':[clip]}})
        self.assertEqual(project_duration(self.p),12)
        pasted=self.p['clips'][-1]
        self.assertEqual((pasted['offset'],pasted['start'],pasted['end']),(1,0,4))
        self.assertEqual(next(c['offset'] for c in self.p['clips'] if c['id']=='b'),8)
        self.assertEqual(next(c['text'] for c in mapped_captions(self.p) if c['clip_id']==pasted['id']),'今天呢很好')
        self.edit('undo',{})
        self.assertEqual(self.p['clips'],before['clips'])

    def test_group_paste_keeps_relative_offsets_and_tracks(self):
        self.edit('clip_paste',{'at':8,'clips':[{'media_id':'m','track':'video','start':0,'end':2,'offset':5},
                                           {'media_id':'m','track':'overlay','start':2,'end':3,'offset':6}]})
        self.assertEqual([(c['offset'],c['track']) for c in self.p['clips'][-2:]],[(8,'video'),(9,'overlay')])

    def test_invalid_paste_does_not_push_existing_clips(self):
        before=copy.deepcopy(self.p)
        with self.assertRaises(EditorError):
            self.edit('clip_paste',{'at':1,'clips':[{'media_id':'m','start':0,'end':2,'offset':0},
                                                 {'media_id':'missing','start':0,'end':2,'offset':2}]})
        self.assertEqual(self.store.get_project(self.p['id']),before)

    def test_trim_before_ripples_subtitles_and_undo_is_atomic(self):
        before = copy.deepcopy(self.p)
        self.p = self.service.edit(self.p['id'], {'expected_version':self.p['version'],
            'action':'clip_trim_at','params':{'clip_id':'b','at':7,'side':'before','ripple':True}})
        self.assertEqual(project_duration(self.p),5)
        self.assertEqual([(c['offset'],c['start'],c['end']) for c in self.p['clips']],[(0,0,4),(4,3,4)])
        self.assertEqual([c['text'] for c in mapped_captions(self.p)],['今天呢很好','很好'])
        self.edit('undo',{})
        self.assertEqual(self.p['clips'],before['clips'])
        self.assertEqual(self.p['captions'],before['captions'])

    def test_trim_after_ripples_other_tracks_with_speed(self):
        self.edit('clip_update',{'clip_id':'a','changes':{'speed':2}})
        self.edit('clip_add',{'id':'audio','media_id':'m','track':'audio','offset':0,'start':0,'end':8})
        self.edit('title_add',{'id':'title','text':'測試','start':4,'end':6})
        self.edit('clip_trim_at',{'clip_id':'a','at':1.5,'side':'after','ripple':True})
        self.assertEqual(next(c for c in self.p['clips'] if c['id']=='a')['end'],3)
        self.assertEqual(next(c for c in self.p['clips'] if c['id']=='b')['offset'],3.5)
        self.assertEqual(self.p['titles'][0]['start'],3.5)
        self.assertEqual(sum((c['end']-c['start'])/c['speed'] for c in self.p['clips'] if c['track']=='audio'),7.5)

    def test_trim_without_ripple_preserves_other_clips_and_gap(self):
        before = copy.deepcopy(self.p['clips'][1])
        self.edit('clip_trim_at',{'clip_id':'a','at':3,'side':'before','ripple':False})
        self.assertEqual((self.p['clips'][0]['start'],self.p['clips'][0]['offset']),(3,3))
        self.assertEqual(self.p['clips'][1],before)
        self.assertEqual(project_duration(self.p),8)
        self.assertEqual(mapped_captions(self.p)[0]['text'],'很好')

    def test_trim_at_boundary_and_invalid_side_leave_project_unchanged(self):
        before=copy.deepcopy(self.p)
        for at in [0,4,8]:
            with self.assertRaises(EditorError):
                self.edit('clip_trim_at',{'clip_id':'a','at':at,'side':'before'})
        with self.assertRaises(ValueError):
            self.edit('clip_trim_at',{'clip_id':'a','at':2,'side':'both'})
        self.assertEqual(self.store.get_project(self.p['id']),before)
