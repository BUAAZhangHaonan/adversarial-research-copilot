"""Explicit run relationships and display selections, separate from ARC research data."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


class VersionError(Exception):
    def __init__(self, message: str, status: int = 409, current_run_id: str | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.current_run_id = current_run_id


def identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_\-][A-Za-z0-9_.\-]*", value):
        raise VersionError("非法版本或问题编号", 400)
    return value


def empty_snapshot() -> dict:
    return {"schema_version": 1, "revision": 0, "problems": {}, "runs": {}, "events": []}


class RunVersions:
    """Reading never creates files. Mutations back up metadata then replace atomically.

    Relationships are supplied explicitly. Topics, research fields, run timestamps,
    and model judgments are never used to infer a problem or select a version.
    """
    def __init__(self, path: Path):
        self.path = Path(path)

    def snapshot(self) -> dict:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return empty_snapshot()
        except (OSError, ValueError) as exc:
            raise VersionError("运行版本记录无法读取，展示选择未变更", 503) from exc
        try:
            self._validate(value)
        except (KeyError, TypeError, ValueError, VersionError) as exc:
            raise VersionError("运行版本记录无效，展示选择未变更", 503) from exc
        return value

    @staticmethod
    def _validate(value: dict) -> None:
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise ValueError("schema")
        revision = value["revision"]
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            raise ValueError("revision")
        problems, runs, events = value["problems"], value["runs"], value["events"]
        if not isinstance(problems, dict) or not isinstance(runs, dict) or not isinstance(events, list):
            raise ValueError("collections")
        for problem_id, problem in problems.items():
            identifier(problem_id)
            selected = identifier(problem["selected_version"])
            root = runs[selected]
            if root["problem_id"] != problem_id or root["version_run_id"] != selected:
                raise ValueError("selected version")
        for run_id, entry in runs.items():
            identifier(run_id)
            problem_id = identifier(entry["problem_id"])
            version_id = identifier(entry["version_run_id"])
            if problem_id not in problems:
                raise ValueError("problem")
            root = runs[version_id]
            if root["problem_id"] != problem_id or root["version_run_id"] != version_id:
                raise ValueError("root")
            previous = entry.get("previous_version_id")
            parent = entry.get("parent_run_id")
            if run_id == version_id:
                if parent is not None:
                    raise ValueError("root parent")
                if previous is not None:
                    identifier(previous)
                    prior = runs[previous]
                    if previous == run_id or prior["problem_id"] != problem_id or prior["version_run_id"] != previous:
                        raise ValueError("previous version")
                seen = {run_id}
                while previous is not None:
                    if previous in seen:
                        raise ValueError("version cycle")
                    seen.add(previous)
                    previous = runs[previous].get("previous_version_id")
            else:
                identifier(parent)
                if previous is not None or runs[parent]["version_run_id"] != version_id:
                    raise ValueError("stage parent")
                seen = {run_id}
                while parent is not None:
                    if parent in seen or runs[parent]["version_run_id"] != version_id:
                        raise ValueError("stage cycle")
                    seen.add(parent)
                    parent = runs[parent].get("parent_run_id")

    @staticmethod
    def visible(snapshot: dict, run_id: str) -> bool:
        entry = snapshot["runs"].get(run_id)
        return entry is None or snapshot["problems"][entry["problem_id"]]["selected_version"] == entry["version_run_id"]

    @staticmethod
    def selected_run(snapshot: dict, run_id: str) -> str:
        entry = snapshot["runs"].get(run_id)
        return run_id if entry is None else snapshot["problems"][entry["problem_id"]]["selected_version"]

    @contextmanager
    def _lock(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix(self.path.suffix + ".lock").open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def _persist(self, before: dict, after: dict) -> None:
        self._validate(after)
        history = self.path.parent / (self.path.name + ".backups")
        history.mkdir(exist_ok=True)
        try:
            raw = self.path.read_bytes()
        except FileNotFoundError:
            raw = (json.dumps(before, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        backup = history / f"revision-{before['revision']}-{hashlib.sha256(raw).hexdigest()[:16]}.json"
        try:
            with backup.open("xb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            if backup.read_bytes() != raw:
                raise VersionError("版本备份校验失败，展示选择未变更", 503)
        fd, temporary = tempfile.mkstemp(prefix=self.path.name + ".", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(after, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _change(self, actor: str, action: str, operation) -> dict:
        with self._lock():
            before = self.snapshot()
            after = json.loads(json.dumps(before))
            event = operation(after)
            after["revision"] += 1
            after["events"].append({"action": action, "actor": actor,
                "at": datetime.now(timezone.utc).isoformat(), "revision": after["revision"], **event})
            self._persist(before, after)
            return after

    def register_current(self, problem_id: str, run_id: str, actor: str) -> dict:
        identifier(problem_id)
        identifier(run_id)
        def operation(value):
            if problem_id in value["problems"] or run_id in value["runs"]:
                raise VersionError("问题或运行已登记，不会覆盖既有关系")
            value["problems"][problem_id] = {"selected_version": run_id}
            value["runs"][run_id] = {"problem_id": problem_id, "version_run_id": run_id,
                "previous_version_id": None, "parent_run_id": None}
            return {"problem_id": problem_id, "run_id": run_id}
        return self._change(actor, "register_current", operation)

    def register_version(self, problem_id: str, run_id: str, previous_run_id: str, actor: str) -> dict:
        for value in (problem_id, run_id, previous_run_id):
            identifier(value)
        def operation(value):
            if run_id in value["runs"]:
                raise VersionError("运行已登记，不会覆盖既有关系")
            previous = value["runs"].get(previous_run_id)
            if previous is None or previous["problem_id"] != problem_id or previous["version_run_id"] != previous_run_id:
                raise VersionError("前一版本必须是同一问题已登记的 discover 运行")
            value["runs"][run_id] = {"problem_id": problem_id, "version_run_id": run_id,
                "previous_version_id": previous_run_id, "parent_run_id": None}
            return {"problem_id": problem_id, "run_id": run_id, "previous_version_id": previous_run_id}
        return self._change(actor, "register_version", operation)

    def register_stage(self, run_id: str, parent_run_id: str, actor: str) -> dict:
        identifier(run_id)
        identifier(parent_run_id)
        def operation(value):
            if run_id in value["runs"]:
                raise VersionError("运行已登记，不会覆盖既有关系")
            parent = value["runs"].get(parent_run_id)
            if parent is None:
                raise VersionError("先登记该后续阶段所属的版本")
            value["runs"][run_id] = {"problem_id": parent["problem_id"],
                "version_run_id": parent["version_run_id"], "previous_version_id": None,
                "parent_run_id": parent_run_id}
            return {"run_id": run_id, "parent_run_id": parent_run_id}
        return self._change(actor, "register_stage", operation)

    def select(self, problem_id: str, run_id: str, expected_selected: str, actor: str) -> dict:
        for value in (problem_id, run_id, expected_selected):
            identifier(value)
        def operation(value):
            problem = value["problems"].get(problem_id)
            entry = value["runs"].get(run_id)
            if problem is None or entry is None or entry["problem_id"] != problem_id or entry["version_run_id"] != run_id:
                raise VersionError("只能选择同一问题已登记的 discover 版本")
            if problem["selected_version"] != expected_selected:
                raise VersionError("展示版本已被其他操作更新，请重新核对后选择")
            problem["selected_version"] = run_id
            return {"problem_id": problem_id, "selected_version": run_id,
                "previous_selected_version": expected_selected, "reviewed": True}
        return self._change(actor, "select", operation)
