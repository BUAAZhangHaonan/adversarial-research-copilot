"""扫描 ARC v2 data-dir（arc.sqlite + reports/<run_id>/）并解析为前端友好结构。

ARC 0.2 报告布局：
- discover: REPORT.md / FIELD_BRIEF.md / ideas/<idea_id>.md / accepted/*.json /
  DISCOVERY_USAGE.json / COST_REPORT.md / SEARCH_SOURCES.md
- develop|run: REPORT.md / cards/<card_id>/v<N>.md / accepted/*.json /
  INPUT_IDEA.json / COST_REPORT.md / SEARCH_SOURCES.md
元数据（status/stop_reason/assessment/topic/灵感卡）以 arc.sqlite 为权威。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .arcstore import ArcStore

_ALLOWED_EXTS = {".md", ".json", ".txt", ".jsonl", ".yaml"}
_MAX_FILE_BYTES = 2 * 1024 * 1024

# 目录内允许下钻的子目录（文件查看器可达）
_SUBDIRS = ("ideas", "cards", "accepted")

_COST_KEYS = {
    "授权上限（元）": "limit_cny",
    "已结算下界（元）": "spent_lower_cny",
    "已结算上界（元）": "spent_upper_cny",
    "预留（元）": "reserved_cny",
    "剩余额度（元）": "remaining_cny",
}


class ArtifactError(Exception):
    def __init__(self, message: str, status: int = 404):
        super().__init__(message)
        self.message = message
        self.status = status


class Artifacts:
    def __init__(self, store: ArcStore, reports_root: Path, jobs=None):
        self.store = store
        self.reports = Path(reports_root)
        self.jobs = jobs

    # ------------------------------------------------------------- helpers
    def _run_path(self, run_dir: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_\-][A-Za-z0-9_.\-]*", run_dir):
            raise ArtifactError("非法 run 目录名")
        p = self.reports / run_dir
        if not p.is_dir():
            raise ArtifactError(f"run 目录不存在: {run_dir}")
        return p

    @staticmethod
    def _read_json(path: Path):
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _run_meta(self, run_dir: str) -> dict:
        run = self.store.get_run(run_dir)
        if run is None:
            return {}
        if self.jobs:
            job = self.jobs.run_lifecycle(run_dir)
            run.update(self.jobs.effective_run_state(run, job))
            if job and job.get("mode") == "resume" and job.get("status") == "failed":
                run["recovery_error"] = str(job.get("error") or "恢复命令失败，未取得详细诊断。")[:2500]
        return run

    def _cost(self, run: Path, meta: dict) -> dict | None:
        return self.store.budget_summary(meta.get('budget_account_id') or run.name) or self._parse_cost(run)

    def _file_entries(self, run: Path) -> list[dict]:
        out: list[dict] = []
        for p in sorted(run.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in _ALLOWED_EXTS:
                continue
            rel = p.relative_to(run).as_posix()
            parts = rel.split('/')
            depth_ok = len(parts) == 1 or (parts[0] in _SUBDIRS and
                (len(parts) == 2 or (parts[0] == 'cards' and len(parts) == 3)))
            if not depth_ok:
                continue
            try:
                size = p.stat().st_size
            except OSError:
                size = 0
            out.append({"name": rel, "size": size})
        return out

    def _parse_cost(self, run: Path) -> dict | None:
        p = run / "COST_REPORT.md"
        if not p.exists():
            return None
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        cost: dict = {}
        for line in text.splitlines():
            for zh, key in _COST_KEYS.items():
                if line.startswith(zh):
                    try:
                        cost[key] = round(float(line.split("：", 1)[1]), 4)
                    except (ValueError, IndexError):
                        pass
            if line.startswith("call_count"):
                try:
                    cost["call_count"] = int(line.split("：", 1)[1])
                except (ValueError, IndexError):
                    pass
        if cost:
            # A report without its original ledger cannot establish complete
            # accounting, even if it records an apparently precise upper bound.
            cost.update(total_cost_complete=False, cost_scope='report_snapshot')
        return cost or None

    # ------------------------------------------------------------- listing
    def list_runs(self) -> list[dict]:
        out = []
        for run in self.store.list_runs():
            run_id = run.get("run_id")
            if self.jobs:
                run.update(self.jobs.effective_run_state(run, self.jobs.run_lifecycle(run_id)))
            d = self.reports / str(run_id)
            try:
                mtime = d.stat().st_mtime if d.is_dir() else 0
            except OSError:
                continue
            out.append({
                "dir": run_id,
                "mode": {"discover": "discover", "develop": "develop", "run": "debate"}.get(
                    run.get("mode"), run.get("mode")),
                "status": run.get("status") or "unknown",
                "arc_status": run.get('arc_status', run.get('status')),
                "interrupted": run.get('interrupted', False),
                "stop_reason": run.get("stop_reason"),
                "assessment": run.get("assessment"),
                "topic": run.get("topic") or "",
                "created_at": run.get("created_at"),
                "mtime": mtime,
                "cost": self._cost(d, run),
            })
        out.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        return out

    # ------------------------------------------------------------ discover
    def _presentation(self, run: Path) -> dict | None:
        """Display-only writing revision; never replaces SQLite research fields."""
        value = self._read_json(run / "PRESENTATION.json")
        if not isinstance(value, dict) or value.get("run_id") != run.name:
            return None
        candidates = value.get("candidates")
        if not isinstance(candidates, list) or not all(
            isinstance(c, dict) and isinstance(c.get("idea_id"), str)
            and isinstance(c.get("presentation_title"), str)
            and isinstance(c.get("text"), str) for c in candidates
        ):
            return None
        return value

    def discover_detail(self, run: Path, meta: dict) -> dict:
        ideas = self.store.discovery_ideas(run.name)
        presentation = self._presentation(run)
        prose = {c["idea_id"]: c for c in (presentation or {}).get("candidates", [])}
        cards = []
        for idea in ideas:
            idea_id = idea.get("idea_id") or ""
            card = {
                "idea_id": idea_id,
                "draw_id": idea.get("draw_id"),
                "status": idea.get("status"),          # pending/park/drop/checked
                "topic": idea.get("topic"),
                "seed": idea.get("seed"),
                "sketch": idea.get("sketch"),
                "triage": idea.get("triage"),
                "note": idea.get("note"),
                "presentation": prose.get(idea_id),
                "idea_md": f"ideas/{idea_id}.md" if (run / "ideas" / f"{idea_id}.md").exists() else None,
            }
            cards.append(card)

        return {
            "mode": "discover",
            "dir": run.name,
            "pause_recovery": self._pause_recovery(meta),
            "pause_diagnostics": self._pause_diagnostics(meta),
            "run": _public_run(meta),
            "topic": meta_topic(meta, self.store),
            "cards": cards,
            "presentation": presentation,
            "usage": self._read_json(run / "DISCOVERY_USAGE.json"),
            "files": self._file_entries(run),
            "cost": self._cost(run, meta),
        }

    # ---------------------------------------------------- develop / debate
    def _stage_detail(self, run: Path, meta: dict, mode: str) -> dict:
        docs = []
        # 卡版本链(develop --card / 老链):cards/<id>/v<N>.md
        cards_root = run / "cards"
        if cards_root.is_dir():
            for card_dir in sorted(cards_root.iterdir()):
                if not card_dir.is_dir():
                    continue
                for md in sorted(card_dir.glob("v*.md")):
                    docs.append({
                        "kind": "card",
                        "card_id": card_dir.name,
                        "version": _version_of(md.stem),
                        "file": f"cards/{card_dir.name}/{md.name}",
                        "size": _size(md),
                    })
        # 灵感预研链(develop/run --idea):ideas/<idea_id>.md 与 .technical.md
        ideas_root = run / "ideas"
        if ideas_root.is_dir():
            for md in sorted(ideas_root.glob("*.md")):
                stem = md.stem
                technical = stem.endswith(".technical")
                docs.append({
                    "kind": "technical" if technical else "idea",
                    "idea_id": stem.removesuffix(".technical"),
                    "file": f"ideas/{md.name}",
                    "size": _size(md),
                })
        input_idea = self._read_json(run / "INPUT_IDEA.json")

        state = meta.get("state") or {}
        idea_input = state.get("idea_input") or {}
        topic = ""
        if input_idea and isinstance(input_idea, dict):
            seed = input_idea.get("seed") or {}
            topic = seed.get("title") or idea_input.get("original_question") or ""
        elif state.get("imported_input"):
            topic = str(state["imported_input"]).strip().split("\n", 1)[0][:200]
        elif idea_input:
            seed = idea_input.get("seed") or {}
            topic = seed.get("title") or idea_input.get("original_question") or ""

        return {
            "mode": mode,
            "dir": run.name,
            "pause_recovery": self._pause_recovery(meta),
            "pause_diagnostics": self._pause_diagnostics(meta),
            "run": _public_run(meta),
            "topic": topic or meta_topic(meta, self.store),
            "docs": docs,
            "presentation": self._presentation(run),
            "input_idea": input_idea,
            "files": self._file_entries(run),
            "cost": self._cost(run, meta),
        }

    # -------------------------------------------------------------- router
    def _pause_recovery(self, meta: dict) -> dict | None:
        return self.store.pause_recovery(meta)

    def _pause_diagnostics(self, meta: dict) -> dict | None:
        diagnostics = self.store.pause_diagnostics(meta)
        if diagnostics is not None and meta.get("recovery_error"):
            diagnostics["recovery_error"] = meta["recovery_error"]
        return diagnostics

    def run_detail(self, run_dir: str) -> dict:
        meta = self._run_meta(run_dir)
        if not re.fullmatch(r"[A-Za-z0-9_\-][A-Za-z0-9_.\-]*", run_dir):
            raise ArtifactError('非法 run 目录名')
        # ARC can create its SQLite run before publishing the first report.
        run = self.reports / run_dir if meta else self._run_path(run_dir)
        mode = meta.get("mode")
        if not mode:
            mode = "discover" if (run / "ideas").is_dir() else "develop"
        if mode == "discover":
            return self.discover_detail(run, meta)
        if mode == "develop":
            return self._stage_detail(run, meta, "develop")
        if mode == "run":
            return self._stage_detail(run, meta, "debate")
        raise ArtifactError(f"不支持的 run 类型: {mode}")

    def read_file(self, run_dir: str, name: str) -> dict:
        run = self._run_path(run_dir)
        if not re.fullmatch(r"[A-Za-z0-9_./\-]+", name) or ".." in name or name.startswith("/"):
            raise ArtifactError("非法文件名")
        p = (run / name).resolve()
        if not p.is_relative_to(run.resolve()):
            raise ArtifactError("路径越界")
        if not p.is_file():
            raise ArtifactError(f"文件不存在: {name}")
        if p.suffix.lower() not in _ALLOWED_EXTS:
            raise ArtifactError("仅支持文本文件")
        data = p.read_text(encoding="utf-8", errors="replace")
        if len(data.encode("utf-8")) > _MAX_FILE_BYTES:
            data = data[: _MAX_FILE_BYTES // 2] + "\n\n... (truncated)"
        return {"name": name, "content": data}


def _public_run(meta: dict) -> dict:
    """前端需要的 run 元数据子集。"""
    state = meta.get("state") or {}
    return {
        "run_id": meta.get("run_id"),
        "status": meta.get("status"),
        "arc_status": meta.get('arc_status', meta.get('status')),
        "arc_stop_reason": meta.get('arc_stop_reason'),
        "interrupted": meta.get('interrupted', False),
        "stop_reason": meta.get("stop_reason"),
        "assessment": meta.get("assessment"),
        "card_id": meta.get("card_id"),
        "card_version": meta.get("card_version"),
        "rounds_completed": state.get("rounds_completed"),
        "created_at": meta.get("created_at"),
        "updated_at": meta.get("updated_at"),
    }


def meta_topic(meta: dict, store: ArcStore) -> str:
    return store.run_topic(meta) if meta else ""


def _version_of(stem: str) -> int:
    try:
        return int(stem.lstrip("v"))
    except ValueError:
        return 0


def _size(p: Path) -> int:
    try:
        return p.stat().st_size
    except OSError:
        return 0
