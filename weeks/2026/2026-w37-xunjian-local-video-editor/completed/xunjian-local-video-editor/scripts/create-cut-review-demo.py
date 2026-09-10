"""Create isolated, synthetic before/after projects for the cut-review experiment."""
from pathlib import Path
import json
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from local_editor.media_engine import _run, _tool, probe
from local_editor.service import EditorService


def main():
    root = Path(__file__).resolve().parents[1]
    data = root / ".editor-test-data" / "cut-review"
    data.mkdir(parents=True, exist_ok=True)
    source = data / "synthetic-two-frame-flash.mp4"
    if not source.exists():
        _run([_tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=640x360:r=20:d=4",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=4",
            "-vf", "drawbox=color=blue:t=fill:enable='gte(n,40)',drawbox=color=black:t=fill:enable='between(n,39,40)'",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source)])
    with_service = EditorService(data)
    try:
        service = with_service
        index = data / "demo.json"
        if index.exists():
            previous = json.loads(index.read_text(encoding="utf-8"))
            project = service.store.get_project(previous["project_id"])
            if all(Path(m["path"]).is_relative_to(service.assets) for m in project["media"] if m["id"] in {c["media_id"] for c in project["clips"]}):
                print(json.dumps({k: v for k, v in previous.items() if k != "evidence"}, ensure_ascii=False, indent=2))
                return
        else:
            project = service.store.create_project("切點實驗 A｜合成兩影格黑閃")
        def edit(action, params):
            nonlocal project
            project = service.store.mutate(project["id"], project["version"], action, params)
        edit("settings", {"width": 640, "height": 360, "fps": 20})
        project = service.import_media(project["id"], {"expected_version": project["version"], "path": str(source)})
        media_id = project["media"][-1]["id"]
        if project["clips"]:
            for clip in list(project["clips"]):
                edit("clip_update", {"clip_id": clip["id"], "changes": {"media_id": media_id}})
        else:
            edit("clip_add", {"clip": {"id": "left", "media_id": media_id, "start": 0, "end": 2}})
            edit("clip_add", {"clip": {"id": "right", "media_id": media_id, "start": 2, "end": 4, "offset": 2}})
        edit("brief_update", {"goal": "合成測試：檢查第 1.95 與 2.00 秒的黑影格；音訊為測試音，不代表口播。"})
        operations = [
            {"action": "clip_update", "params": {"clip_id": "left", "changes": {"end": 1.95}}},
            {"action": "clip_update", "params": {"clip_id": "right", "changes": {"start": 2.05, "offset": 1.95}}}]
        proposal = service.prepare_edit(project["id"], {"expected_version": project["version"],
            "intent": "移除兩個已知合成黑影格，驗證正常紅藍硬切", "operations": operations,
            "checks": [{"kind": "no_timeline_gaps"}, {"kind": "duration_between", "min": 3.89, "max": 3.91},
                       {"kind": "no_black_frames", "range": {"start": 1, "end": 3}}]})
        reports = {}
        for side in ("before", "after"):
            job = service.inspect_range(project["id"], {"expected_version": project["version"],
                "edit_id": proposal["id"], "preview_side": side, "time_space": "timeline",
                "range": {"start": 1, "end": 3}, "include": ["frames", "audio", "video"],
                "sampling": {"strategy": "cut_boundaries"}, "scan_black_frames": True, "max_frames": 8})
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                status = service.job_status(job["id"], 1000)
                if status["status"] == "failed":
                    raise RuntimeError(status)
                if status["status"] == "succeeded":
                    reports[side] = status["result"]
                    break
            else:
                raise TimeoutError("合成證據逾時")
        verification = service.verify_edit(project["id"], {"expected_version": project["version"], "edit_id": proposal["id"]})
        result = {"data_dir": str(data), "project_id": project["id"], "version": project["version"],
            "edit_id": proposal["id"], "before_candidates": reports["before"]["evidence"]["black_scan"]["candidate_count"],
            "after_candidates": reports["after"]["evidence"]["black_scan"]["candidate_count"],
            "acceptance": verification["acceptance"], "evidence": reports}
        index.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in result.items() if k != "evidence"}, ensure_ascii=False, indent=2))
    finally:
        with_service.close()


if __name__ == "__main__":
    main()
