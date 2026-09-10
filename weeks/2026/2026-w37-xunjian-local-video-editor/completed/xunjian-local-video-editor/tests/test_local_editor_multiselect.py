import tempfile
import unittest

from local_editor.core import ProjectStore, EditorError
from local_editor.service import EditorService


class GroupEditingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.service = EditorService(temp.name)
        self.addCleanup(self.service.close)
        self.store = self.service.store
        self.project = self.store.create_project("群組編輯驗收")
        self.edit("media_add", {"media": {"id": "m", "name": "fixture", "kind": "video", "path": "fixture.mp4",
                                           "duration": 30, "width": 320, "height": 180, "has_audio": True}})
        for identifier, offset, track in [("a", 2, "video"), ("b", 4, "overlay"), ("tail", 10, "video")]:
            self.edit("clip_add", {"clip": {"id": identifier, "media_id": "m", "start": 0, "end": 4,
                                           "offset": offset, "track": track}})

    def edit(self, action, params):
        self.project = self.store.mutate(self.project["id"], self.project["version"], action, params)

    def test_group_move_preserves_relative_offsets_and_one_undo(self):
        before = self.project
        self.project = self.service.edit(before["id"], {"expected_version": before["version"],
            "action": "clip_move_many", "params": {"clip_ids": ["a", "b"], "delta": 3}})
        self.assertEqual([c["offset"] for c in self.project["clips"]], [5, 7, 10])
        self.assertEqual([c["track"] for c in self.project["clips"]], ["video", "overlay", "video"])
        self.assertEqual(self.project["version"], before["version"]+1)
        self.edit("undo", {})
        self.assertEqual(self.project["clips"], before["clips"])

    def test_delete_many_preserves_unselected_and_restores_in_one_step(self):
        before = self.project
        self.edit("clip_delete_many", {"clip_ids": ["a", "b"], "ripple": False})
        self.assertEqual([c["id"] for c in self.project["clips"]], ["tail"])
        self.assertEqual(self.project["clips"][0]["offset"], 10)
        self.edit("undo", {})
        self.assertEqual(self.project["clips"], before["clips"])

    def test_ripple_delete_merges_overlapping_windows_once(self):
        self.edit("clip_delete_many", {"clip_ids": ["a", "b"], "ripple": True})
        self.assertEqual([c["id"] for c in self.project["clips"]], ["tail"])
        self.assertEqual(self.project["clips"][0]["offset"], 4)

    def test_invalid_group_and_stale_version_are_atomic(self):
        before = self.project
        for action, params in [("clip_move_many", {"clip_ids": ["a", "missing"], "delta": 1}),
                               ("clip_move_many", {"clip_ids": ["a", "b"], "delta": -3}),
                               ("clip_delete_many", {"clip_ids": ["a", "missing"]}),
                               ("clip_delete_many", {"clip_ids": ["a", "a"]})]:
            with self.subTest(params=params), self.assertRaises((ValueError, EditorError)):
                self.edit(action, params)
            self.assertEqual(self.store.get_project(before["id"]), before)
        with self.assertRaises(EditorError):
            self.store.mutate(before["id"], before["version"]-1, "clip_move_many", {"clip_ids": ["a", "b"], "delta": 1})
        self.assertEqual(self.store.get_project(before["id"]), before)
