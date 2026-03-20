from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DebateMemory:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.run_dir / "debate_log.jsonl"

    def append(self, payload: dict[str, Any]) -> None:
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def save_json(self, name: str, payload: dict[str, Any]) -> Path:
        out_file = self.run_dir / name
        out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return out_file

    def load_json(self, name: str) -> dict[str, Any] | None:
        in_file = self.run_dir / name
        if not in_file.exists():
            return None
        return json.loads(in_file.read_text(encoding="utf-8"))
