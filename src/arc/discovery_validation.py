"""Small provenance checks, without claiming semantic scientific verification."""
from .discovery_models import FieldBrief, CandidateCheck


def validate_source_access(store, result):
    if isinstance(result, FieldBrief): notes = result.source_notes
    elif isinstance(result, CandidateCheck): notes = result.note.source_notes + result.field_updates
    else: return
    for note in notes:
        source = store.get_source(note.source_id)
        if note.access in {"passage", "full_text", "code"}:
            if source.access_status != "retrieved" or not source.content_path or source.content_origin != "original":
                raise ValueError(f"source_access_exceeds_retrieved_material:{note.source_id}; use metadata/secondary and state limits")
            try:
                content = store.read_artifact(source.content_path)
            except FileNotFoundError:
                content = ""
            if not content.strip():
                raise ValueError(f"source_retrieved_content_empty:{note.source_id}; use metadata and state limits")
            if note.access == "full_text" and not source.content_complete:
                raise ValueError(f"source_full_text_not_available:{note.source_id}; use passage and state truncation limits")
            # The web reader registers original repository pages as web_unclassified.
            # That transport label does not certify or disprove authorship/code semantics.
            if note.access == "code" and source.source_type not in {"author_code", "web_unclassified", "official_documentation"}:
                raise ValueError(f"source_is_not_original_code:{note.source_id}")
        if note.access == "abstract" and source.content_origin == "secondary_analysis":
            raise ValueError(f"secondary_analysis_is_not_original_abstract:{note.source_id}")


def repeated_exhausted_read(trace):
    """Repeated EOF pauses only while no later material progress supersedes it.

    Scan to the end: a batch can contain both old exhausted reads and a useful
    new fetch/page. Re-reading already seen material does not reset the guard.
    This uses source metadata and ranges, not content hashes or scientific scores.
    """
    exhausted, available, ranges, latest = {}, {}, {}, {}

    def identity(source, fallback=None):
        return (source.get("source_id") or fallback, source.get("version"),
                source.get("representation_id"))

    def observe(key, size):
        if not key[0] or not isinstance(size, int) or size <= 0:
            return False
        changed = size > available.get(key, 0)
        if key[0] in latest and latest[key[0]] != key:
            changed = True
        latest[key[0]] = key
        available[key] = max(size, available.get(key, 0))
        return changed

    def read_new_range(key, start, length):
        end = start + length
        previous = ranges.setdefault(key, [])
        covered = start
        for left, right in sorted(previous):
            if left > covered:
                break
            covered = max(covered, right)
        new = covered < end
        previous.append((start, end))
        return new

    for item in trace:
        result = item.get("result") or {}
        arguments = item.get("arguments") or {}
        if item.get("name") != "read_record":
            if result.get("is_error"):
                continue
            progress = False
            for source in result.get("sources") or []:
                if not isinstance(source, dict) or source.get("content_origin") == "metadata":
                    continue
                progress = observe(identity(source), source.get("content_chars", 0)) or progress
            if progress:
                exhausted.clear()
            continue
        key = identity(result, arguments.get("record_id"))
        if not key[0]:
            continue
        boundary = (*key, result.get("cached_content_chars"), result.get("content_total_chars"))
        is_eof = result.get("error") in {"SOURCE_CACHE_EXHAUSTED", "SOURCE_END_REACHED"}
        if is_eof:
            # A larger cache or changed representation reopens a useful path.
            was_known = key in available or key[0] in latest
            progress = observe(key, result.get("cached_content_chars", 0))
            if was_known and progress:
                exhausted.clear()
            exhausted[boundary] = exhausted.get(boundary, 0) + 1
            continue
        content = result.get("content")
        if result.get("is_error") or not isinstance(content, str) or not content:
            continue
        start = result.get("content_offset", arguments.get("offset", 0))
        size = result.get("cached_content_chars", start + len(content))
        material_progress = observe(key, size)
        range_progress = read_new_range(key, start, len(content))
        if material_progress or range_progress:
            exhausted.clear()
    return any(count >= 2 for count in exhausted.values())
