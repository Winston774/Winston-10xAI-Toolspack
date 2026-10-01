import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import vh_plan as vh


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'frame.jpg').write_bytes(b'fixture')
        self.project = dict(schema_version=1, source=dict(path=str(self.root/'source.mp4'), sha256='a'*64,
                            duration=3600, width=1920, height=1080, has_audio=True, clock='zero_based_media'),
                            transcript=dict(segments=[dict(id='S001', start=10, end=50, text='保留條件才能做出正確判斷。'),
                                                      dict(id='S002', start=120, end=160, text='具體方法從觀察開始。'),
                                                      dict(id='S003', start=3540, end=3590, text='最後要驗證結果。')]))
        self.path = self.root/'project.json'
        vh.write_json(self.path, self.project)
        self.candidate = dict(id='H001', title='如何做判斷', topic='判斷', start=10, end=50,
             summary='條件很重要', hook='如何判斷', reason='有完整方法',
             quotes=[dict(segment_id='S001', text='保留條件')], scores={key:4 for key in vh.WEIGHTS}, confidence='medium',
             gates={key:True for key in vh.GATES}, review=dict(visual='sampled', audio='transcript_only', evidence=['frame.jpg'], notes='尚未聆聽'),
             framing=dict(mode='pad'), unresolved=['未聆聽'])
        self.data = dict(schema_version=1, source_sha256='a'*64,
                         coverage=[dict(start=0, end=3600, kind='speech', summary='完整逐段閱讀的測試資料')], candidates=[self.candidate])

    def pick(self, **kwargs):
        return vh.select(self.data, self.path, **kwargs)

    def test_scores_and_partial_status_roundtrip(self):
        plan = self.pick()
        self.assertEqual(plan['selected'][0]['score'], 80)
        self.assertEqual(plan['status'], 'partial')
        vh.write_json(self.root/'plan.json', plan)
        self.assertEqual(vh.validate_plan(self.root/'plan.json')[0], plan)

    def test_high_score_cannot_override_context_gate(self):
        self.candidate['gates']['context_preserved'] = False
        plan = self.pick()
        self.assertEqual(plan['selected'], [])
        self.assertIn('gate_context_preserved', plan['rejected'][0]['reasons'])

    def test_duration_is_hard_constraint_no_arbitrary_trim(self):
        plan = self.pick(max_seconds=35)
        self.assertEqual(plan['selected'], [])
        self.assertEqual(self.candidate['end'], 50)

    def test_quote_must_exist_and_overlap(self):
        for change in ({'text':'不存在的金句'}, {'segment_id':'S002', 'text':'具體方法'}):
            with self.subTest(change=change):
                previous = self.candidate['quotes']
                self.candidate['quotes'] = [dict(segment_id='S001', text='保留條件', **{}) | change]
                with self.assertRaises(ValueError):
                    self.pick()
                self.candidate['quotes'] = previous

    def test_overlapping_duplicate_rejected(self):
        duplicate = copy.deepcopy(self.candidate)
        duplicate.update(id='H002', start=15, end=55)
        self.data['candidates'].append(duplicate)
        plan = self.pick()
        self.assertEqual(len(plan['selected']), 1)
        self.assertIn('duplicate_time_range', plan['rejected'][0]['reasons'])

    def test_topics_and_late_hour_candidate(self):
        duplicate = copy.deepcopy(self.candidate)
        duplicate.update(id='H002', start=3540, end=3590, quotes=[dict(segment_id='S003', text='最後要驗證')])
        self.data['candidates'].append(duplicate)
        self.assertEqual(len(self.pick(per_topic=1)['selected']), 1)
        duplicate['topic'] = '結果驗證'
        self.assertEqual(len(self.pick(per_topic=1)['selected']), 2)

    def test_coverage_requires_entire_hour(self):
        self.data['coverage'][0]['end'] = 3599
        with self.assertRaisesRegex(ValueError, 'source end'):
            self.pick()

    def test_unreviewed_ranges_not_selected(self):
        self.data['coverage'] = [dict(start=0,end=60,kind='unreviewed',summary='未讀'),
                                 dict(start=60,end=3600,kind='speech',summary='已讀')]
        self.assertEqual(self.pick()['selected'], [])

    def test_numeric_tricks_fail(self):
        for value in (True, float('nan'), float('inf'), -1):
            with self.subTest(value=value):
                self.candidate['start'] = value
                with self.assertRaises(ValueError):
                    self.pick()

    def test_no_fabricated_review_or_crop(self):
        self.candidate['review']['evidence'] = []
        with self.assertRaises(ValueError):
            self.pick()
        self.candidate['review']['visual'] = 'unreviewed'
        self.candidate['scores']['audiovisual'] = 2
        self.candidate['framing'] = dict(mode='crop', x=.5, y=.5, reason='test')
        with self.assertRaisesRegex(ValueError, 'crop requires'):
            self.pick()

    def test_missing_external_or_traversal_evidence_fails(self):
        for name in ('missing.jpg', '../frame.jpg', str(self.root/'frame.jpg')):
            self.candidate['review']['evidence'] = [name]
            with self.assertRaises(ValueError):
                self.pick()

    def test_hash_mismatch_fails(self):
        self.data['source_sha256'] = 'b'*64
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.pick()

    def test_no_top_k_fallback_below_threshold(self):
        self.assertEqual(self.pick(min_score=90)['selected'], [])

    def test_edited_plan_cannot_bypass_validation(self):
        plan = self.pick()
        plan['selected'][0]['score'] = 100
        vh.write_json(self.root/'plan.json', plan)
        with self.assertRaisesRegex(ValueError, 'score/review'):
            vh.validate_plan(self.root/'plan.json')

    def test_export_human_readable_report_and_csv(self):
        plan = self.pick()
        vh.report(plan, self.root)
        self.assertIn('保留條件', (self.root/'HIGHLIGHTS.md').read_text(encoding='utf-8'))
        self.assertIn('80.0', (self.root/'scores.csv').read_text(encoding='utf-8-sig'))


if __name__ == '__main__':
    unittest.main()
