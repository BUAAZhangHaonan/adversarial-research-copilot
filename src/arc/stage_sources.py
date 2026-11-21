"""Recover which source portions were returned to this stage from its saved tool responses."""
from __future__ import annotations

import json


def trace_readings(store, run_id):
    levels: dict[str, set[str]] = {}
    intervals: dict[str, list[tuple[int, int]]] = {}
    totals: dict[str, int] = {}
    incomplete = False
    for task in store.list_tasks(run_id):
        if not task.response_artifact_path:
            continue
        try:
            result = json.loads(store.read_artifact(task.response_artifact_path))
        except (FileNotFoundError,ValueError):
            incomplete = True
            continue
        for item in result.get("tool_trace", []):
            response = item.get("result") or {}
            if item.get("status") != "completed" or response.get("is_error"):
                continue
            name = item.get("name")
            for source in ([response] if name == "read_record" else response.get("sources", [])):
                sid = source.get("source_id")
                if not sid:
                    continue
                seen = levels.setdefault(sid, set())
                if name in {"search_literature", "search_web"}:
                    seen.add("abstract" if source.get("abstract") else "metadata")
                elif name in {"read_record","read_paper","read_web"}:
                    text = source.get("content")
                    if not isinstance(text, str) or not text:
                        continue
                    if source.get("content_origin") == "secondary_analysis":
                        seen.add("secondary")
                        continue
                    seen.add("passage")
                    offset = (source.get("content_start_char") or 0) + (source.get("content_offset") or 0)
                    intervals.setdefault(sid, []).append((offset, offset + len(text)))
                    total = source.get("content_total_chars")
                    if isinstance(total, int) and total > 0 and source.get("content_complete"):
                        totals[sid] = total
    for sid,total in totals.items():
        end = 0
        for start,stop in sorted(intervals.get(sid, [])):
            if start > end:
                break
            end = max(end, stop)
        if end == total:
            levels[sid].add("full_text")
    return levels, incomplete


def public_url(source):
    if source.url:
        return source.url
    if source.arxiv_id:
        ident = source.arxiv_id.removeprefix("arXiv:")
        if source.version and source.version.removeprefix("v").isdigit():
            version = "v"+source.version.removeprefix("v")
            if not ident.endswith(version):
                ident += version
        return "https://arxiv.org/abs/" + ident
    if source.doi:
        return "https://doi.org/" + source.doi.removeprefix("https://doi.org/")
    return None
