import concurrent.futures
import tempfile
import unittest

from local_editor.captions import export_captions, parse_captions
from local_editor.core import EditorError, ProjectStore, mapped_captions, project_duration


class ProjectStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = ProjectStore(self.tmp.name)
        self.project = self.store.create_project("繁體中文剪輯")

    def edit(self, action, **params):
        self.project = self.store.mutate(self.project["id"], self.project["version"], action, params)
        return self.project

    def add_video(self, duration=10, **clip):
        self.edit("media_add", media={"id": "video-1", "name": "口播.mp4", "path": "D:/口播.mp4",
                                      "kind": "video", "duration": duration, "width": 1920,
                                      "height": 1080, "has_audio": True})
        self.edit("clip_add", clip={"id": "clip-1", "media_id": "video-1", **clip})

    def test_persistence_and_monotonic_undo_redo(self):
        self.edit("rename", name="第一次命名")
        self.edit("rename", name="第二次命名")
        self.assertEqual(self.project["version"], 3)
        self.store = ProjectStore(self.tmp.name)
        undone = self.edit("undo")
        self.assertEqual((undone["name"], undone["version"]), ("第一次命名", 4))
        redone = self.edit("redo")
        self.assertEqual((redone["name"], redone["version"]), ("第二次命名", 5))
        self.edit("undo")
        self.edit("rename", name="新分支")
        with self.assertRaises(EditorError) as error:
            self.edit("redo")
        self.assertEqual(error.exception.code, "nothing_to_redo")
        self.assertEqual(self.store.get_project(self.project["id"])["version"], 7)

    def test_version_conflict_is_atomic(self):
        version = self.project["version"]
        self.edit("rename", name="新名稱")
        with self.assertRaises(EditorError) as error:
            self.store.mutate(self.project["id"], version, "rename", {"name": "舊操作"})
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(self.store.get_project(self.project["id"])["name"], "新名稱")

    def test_concurrent_same_version_allows_exactly_one_writer(self):
        project_id, version = self.project["id"], self.project["version"]
        def writer(index):
            try:
                ProjectStore(self.tmp.name).mutate(project_id, version, "rename", {"name": f"Writer {index}"})
                return "ok"
            except EditorError as error:
                return error.code
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(writer, range(4)))
        self.assertEqual(results.count("ok"), 1)
        self.assertEqual(results.count("version_conflict"), 3)
        self.assertEqual(self.store.get_project(project_id)["version"], version + 1)

    def test_failed_edit_rolls_back_and_preserves_undo_history(self):
        self.add_video()
        before = self.store.get_project(self.project["id"])
        for changes in ({"end": 20}, {"start": 8, "end": 4}, {"speed": 0}, {"muted": "false"},
                        {"offset": float("nan")}, {"volume": float("inf")}, {"offset": -1},
                        {"media_id": "unknown"}, {"offset": 10**500}):
            with self.subTest(changes=changes), self.assertRaises(EditorError):
                self.edit("clip_update", clip_id="clip-1", changes=changes)
            self.assertEqual(self.store.get_project(self.project["id"]), before)

    def test_invalid_canvas_create_is_not_persisted(self):
        with self.assertRaises(EditorError):
            self.store.create_project("錯誤畫布", width=2)
        self.assertEqual(len(self.store.list_projects()), 1)

    def test_split_uses_timeline_seconds_with_speed(self):
        self.add_video(duration=20, start=4, end=16, offset=3, speed=2)
        self.edit("clip_split", clip_id="clip-1", at=5)
        left, right = self.project["clips"]
        self.assertEqual((left["start"], left["end"], left["offset"]), (4, 8, 3))
        self.assertEqual((right["start"], right["end"], right["offset"]), (8, 16, 5))
        self.assertEqual(project_duration(self.project), 9)

    def test_source_captions_follow_trim_speed_and_duplicate_placements(self):
        self.add_video(duration=20, start=4, end=12, offset=3, speed=2)
        self.edit("captions_set", media_id="video-1", captions=[{"id": "caption-1", "start": 2, "end": 8, "text": "繁體字幕"}])
        self.edit("clip_add", clip={"media_id": "video-1", "start": 2, "end": 4, "offset": 10})
        mapped = mapped_captions(self.project)
        self.assertEqual([(c["start"], c["end"]) for c in mapped], [(3, 5), (10, 12)])
        self.assertEqual(self.project["captions"][0]["start"], 2)
        self.assertNotEqual(mapped[0]["id"], mapped[1]["id"])

    def test_word_aligned_captions_remove_cut_words_and_map_word_times(self):
        self.add_video(duration=10, speed=2, offset=1)
        self.edit("captions_set", media_id="video-1", captions=[{
            "id": "sentence", "start": 0, "end": 10, "text": "保留贅詞繼續",
            "words": [{"start": 0, "end": 2, "text": "保留"},
                      {"start": 2, "end": 4, "text": "贅詞"},
                      {"start": 4, "end": 10, "text": "繼續"}]}])
        plan = self.store.prepare_plan(self.project["id"], self.project["version"],
                                      [{"id": "filler", "media_id": "video-1", "start": 2, "end": 4}])
        project = self.store.apply_plan(self.project["id"], self.project["version"], plan["id"], ["filler"])
        mapped = mapped_captions(project)
        self.assertEqual([c["text"] for c in mapped], ["保留", "繼續"])
        self.assertEqual([(c["start"], c["end"]) for c in mapped], [(1, 2), (2, 5)])
        self.assertEqual([(w["start"], w["end"]) for c in mapped for w in c["words"]], [(1, 2), (2, 5)])
        self.assertEqual(project["captions"][0]["text"], "保留贅詞繼續")
        self.assertNotIn("贅詞", export_captions(project, "srt"))

    def test_manual_caption_changes_discard_stale_word_alignment(self):
        self.add_video()
        original = {"id": "c1", "start": 0, "end": 2, "text": "原文",
                    "words": [{"start": 0, "end": 2, "text": "原文"}]}
        self.edit("captions_set", media_id="video-1", captions=[original])
        self.edit("caption_update", caption_id="c1", changes={"text": "修正文字"})
        self.assertNotIn("words", self.project["captions"][0])
        self.assertEqual(mapped_captions(self.project)[0]["text"], "修正文字")
        self.edit("captions_set", media_id="video-1", captions=[{**original, "text": "批次取代文字"}])
        self.assertNotIn("words", self.project["captions"][0])

    def test_invalid_word_alignment_is_rejected(self):
        self.add_video()
        for words in ([{"start": 0, "end": 3, "text": "原文"}],
                      [{"start": -1, "end": 2, "text": "原文"}],
                      [{"start": 0, "end": float("nan"), "text": "原文"}]):
            with self.subTest(words=words), self.assertRaises(EditorError):
                self.edit("captions_set", media_id="video-1", captions=[
                    {"start": 0, "end": 2, "text": "原文", "words": words}])

    def test_caption_replace_is_scoped_to_one_media(self):
        self.add_video()
        self.edit("media_add", media={"id": "video-2", "name": "第二段", "path": "second.mp4", "kind": "video", "duration": 10})
        self.edit("captions_set", media_id="video-1", captions=[{"start": 0, "end": 1, "text": "一"}])
        self.edit("captions_set", media_id="video-2", captions=[{"start": 0, "end": 1, "text": "二"}])
        self.edit("captions_set", media_id="video-1", captions=[{"start": 0, "end": 1, "text": "新一"}])
        self.assertEqual({c["text"] for c in self.project["captions"]}, {"新一", "二"})

    def test_smart_cut_splits_and_ripples_all_tracks_and_titles(self):
        self.add_video()
        self.edit("media_add", media={"id": "music", "name": "配樂", "path": "music.wav", "kind": "audio", "duration": 10})
        self.edit("clip_add", clip={"id": "music-clip", "media_id": "music", "track": "audio"})
        self.edit("title_add", text="文字", start=1, end=9)
        self.edit("captions_set", media_id="video-1", captions=[{"start": 6, "end": 8, "text": "剪後字幕"}])
        original_version = self.project["version"]
        plan = self.store.prepare_plan(self.project["id"], original_version,
            [{"id": "gap", "media_id": "video-1", "start": 2, "end": 4, "reason": "停頓"}])
        self.assertEqual(plan["removed_duration"], 2)
        self.assertEqual(self.store.get_project(self.project["id"])["version"], original_version)
        self.project = self.store.apply_plan(self.project["id"], original_version, plan["id"], ["gap"])
        self.assertEqual(project_duration(self.project), 8)
        for track in ("video", "audio"):
            clips = [c for c in self.project["clips"] if c["track"] == track]
            self.assertEqual([(c["start"], c["end"], c["offset"]) for c in clips], [(0, 2, 0), (4, 10, 2)])
        self.assertEqual([(t["start"], t["end"]) for t in self.project["titles"]], [(1, 2), (2, 7)])
        mapped = mapped_captions(self.project)
        self.assertEqual((mapped[0]["start"], mapped[0]["end"]), (4, 6))
        self.edit("undo")
        self.assertEqual(project_duration(self.project), 10)
        self.assertEqual(len(self.project["clips"]), 2)

    def test_overlapping_candidates_removed_once(self):
        self.add_video()
        plan = self.store.prepare_plan(self.project["id"], self.project["version"], [
            {"id": "a", "media_id": "video-1", "start": 2, "end": 4},
            {"id": "b", "media_id": "video-1", "start": 3, "end": 5}])
        self.assertEqual(plan["removed_duration"], 3)
        project = self.store.apply_plan(self.project["id"], self.project["version"], plan["id"], ["a", "b"])
        self.assertEqual(project_duration(project), 7)

    def test_plan_cannot_be_reused_after_edit_or_undo(self):
        self.add_video()
        plan = self.store.prepare_plan(self.project["id"], self.project["version"],
                                      [{"id": "gap", "media_id": "video-1", "start": 2, "end": 4}])
        self.edit("rename", name="變更")
        self.edit("undo")
        with self.assertRaises(EditorError) as error:
            self.store.apply_plan(self.project["id"], self.project["version"], plan["id"], ["gap"])
        self.assertEqual(error.exception.code, "version_conflict")

    def test_plan_rejects_unknown_ids_and_invalid_source_ranges(self):
        self.add_video()
        for start, end in ((-1, 1), (1, 11), (4, 2), (0, float("inf"))):
            with self.subTest(start=start, end=end), self.assertRaises(EditorError):
                self.store.prepare_plan(self.project["id"], self.project["version"],
                                        [{"media_id": "video-1", "start": start, "end": end}])
        plan = self.store.prepare_plan(self.project["id"], self.project["version"],
                                      [{"id": "gap", "media_id": "video-1", "start": 2, "end": 4}])
        for ids in ([], ["gap", "gap"], ["unknown"]):
            with self.subTest(ids=ids), self.assertRaises(EditorError):
                self.store.apply_plan(self.project["id"], self.project["version"], plan["id"], ids)

    def test_smart_cut_rejects_removing_entire_timeline(self):
        self.add_video()
        plan = self.store.prepare_plan(self.project["id"], self.project["version"],
                                      [{"id": "all", "media_id": "video-1", "start": 0, "end": 10}])
        with self.assertRaises(EditorError):
            self.store.apply_plan(self.project["id"], self.project["version"], plan["id"], ["all"])
        self.assertEqual(project_duration(self.store.get_project(self.project["id"])), 10)

    def test_long_music_does_not_allow_smart_cut_to_erase_all_video(self):
        self.add_video()
        self.edit("media_add", media={"id": "music", "name": "配樂", "path": "music.wav", "kind": "audio", "duration": 100})
        self.edit("clip_add", clip={"media_id": "music", "track": "audio"})
        plan = self.store.prepare_plan(self.project["id"], self.project["version"],
                                      [{"id": "all", "media_id": "video-1", "start": 0, "end": 10}])
        before = self.store.get_project(self.project["id"])
        with self.assertRaises(EditorError):
            self.store.apply_plan(self.project["id"], self.project["version"], plan["id"], ["all"])
        self.assertEqual(self.store.get_project(self.project["id"]), before)

    def test_ripple_delete_keeps_other_tracks_in_sync(self):
        self.add_video()
        self.edit("clip_split", clip_id="clip-1", at=4)
        self.edit("clip_delete", clip_id="clip-1", ripple=True)
        self.assertEqual([(c["start"], c["end"], c["offset"]) for c in self.project["clips"]], [(4, 10, 0)])


class CaptionTests(unittest.TestCase):
    def test_bom_crlf_and_srt_round_trip(self):
        captions = parse_captions("\ufeff1\r\n00:00:01,250 --> 00:00:03,000\r\n繁體中文\r\n第二行\r\n", "srt", "video")
        self.assertEqual((captions[0]["start"], captions[0]["end"]), (1.25, 3))
        self.assertEqual(captions[0]["media_id"], "video")
        exported = export_captions(captions, "srt")
        self.assertIn("00:00:01,250 --> 00:00:03,000", exported)
        self.assertEqual(parse_captions(exported)[0]["text"], "繁體中文\n第二行")

    def test_vtt_comments_settings_and_markup(self):
        content = "WEBVTT\n\nNOTE 備註\n不要顯示\n\ncue-1\n00:01.000 --> 00:02.500 align:start\n<b>中文</b> &amp; 字幕\n"
        captions = parse_captions(content, "vtt")
        self.assertEqual(captions[0]["text"], "中文 & 字幕")
        self.assertEqual(captions[0]["start"], 1)
        exported = export_captions(captions, "vtt")
        self.assertTrue(exported.startswith("WEBVTT\n\n"))
        self.assertIn("中文 &amp; 字幕", exported)
        self.assertEqual(export_captions(captions, "txt"), "中文 & 字幕\n")

    def test_invalid_captions_raise_actionable_errors(self):
        for content in ("no timing", "1\n00:00:02,000 --> 00:00:01,000\n錯誤",
                        "1\n00:90:00,000 --> 00:91:00,000\n錯誤", "1\nNaN --> Infinity\n錯誤"):
            with self.subTest(content=content), self.assertRaises(EditorError):
                parse_captions(content)


if __name__ == "__main__":
    unittest.main()
