from pathlib import Path

from arc.memory import DebateMemory


def test_save_and_load_json(tmp_path: Path) -> None:
    memory = DebateMemory(tmp_path)
    memory.save_json("run_state.json", {"status": "in_progress", "round": 2})
    loaded = memory.load_json("run_state.json")
    assert loaded is not None
    assert loaded["status"] == "in_progress"
    assert loaded["round"] == 2
