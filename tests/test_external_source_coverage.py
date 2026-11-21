import json
from types import SimpleNamespace

from arc.stage_sources import trace_readings


def test_scattered_stage_reads_are_not_promoted_to_full_text():
    offsets = [(0, "abc"), (6, "ghi")]

    class TraceStore:
        def list_tasks(self, run_id):
            return [SimpleNamespace(response_artifact_path="saved")]

        def read_artifact(self, path):
            trace = [
                {
                    "name": "read_record",
                    "status": "completed",
                    "result": {
                        "source_id": "source",
                        "content": text,
                        "content_offset": offset,
                        "content_start_char": 0,
                        "content_origin": "original",
                        "content_complete": True,
                        "content_total_chars": 9,
                    },
                }
                for offset, text in offsets
            ]
            return json.dumps({"tool_trace": trace})

    store = TraceStore()
    levels, incomplete = trace_readings(store, "run")
    assert not incomplete
    assert levels["source"] == {"passage"}
    offsets.append((3, "def"))
    assert trace_readings(store, "run")[0]["source"] == {"passage", "full_text"}


def test_unavailable_tool_trace_is_reported_without_inventing_coverage():
    class TraceStore:
        def list_tasks(self, run_id):
            return [SimpleNamespace(response_artifact_path="missing")]

        def read_artifact(self, path):
            raise FileNotFoundError(path)

    assert trace_readings(TraceStore(), "run") == ({}, True)
