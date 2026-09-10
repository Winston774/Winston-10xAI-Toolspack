"""Small explicit edit assertions. Unobserved media assertions stay pending."""
from .core import project_duration
from .understanding import _timeline_gaps


def evaluate_checks(project, checks, evidence=()):
    results = []
    duration = project_duration(project)
    for check in checks:
        result = {"check": check, "status": "pending", "evidence_ids": []}
        if check["kind"] == "duration_between":
            result.update(status="passed" if check["min"] <= duration <= check["max"] else "failed", actual=duration)
        elif check["kind"] == "no_timeline_gaps":
            gaps = _timeline_gaps(project, {"start": 0, "end": duration})
            result.update(status="failed" if gaps else "passed", gaps=gaps, basis="main_video_track")
        elif check["kind"] == "no_black_frames":
            span = check["range"]
            if span["end"] > duration:
                result.update(status="failed", reason="驗收區間超過提案時長")
            else:
                for item in evidence:
                    scan = item.get("black_scan", {})
                    window = scan.get("range", {})
                    if scan.get("status") != "completed" or window.get("start", float("inf")) > span["start"] or window.get("end", -1) < span["end"]:
                        continue
                    findings = [f for f in scan["findings"] if f["range"]["start"] < span["end"] and f["range"]["end"] > span["start"]]
                    result.update(status="needs_review" if findings else "pending" if scan.get("truncated") else "passed",
                        evidence_ids=[item["evidence_id"]] if item.get("evidence_id") else [],
                        finding_ids=[f["id"] for f in findings], basis="decoded_dark_pixels_only")
                    break
        results.append(result)
    status = ("not_requested" if not results else "failed" if any(r["status"] == "failed" for r in results)
              else "needs_review" if any(r["status"] == "needs_review" for r in results)
              else "pending" if any(r["status"] == "pending" for r in results) else "passed")
    return {"status": status, "results": results, "audiovisual_naturalness": "unchecked"}
