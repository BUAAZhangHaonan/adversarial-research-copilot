"""Apply one explicit display selection to all run and job entry points."""
from __future__ import annotations

from .artifacts import ArtifactError
from .run_versions import RunVersions, VersionError, identifier


class VersionedArtifacts:
    def __init__(self, artifacts, versions: RunVersions):
        self.artifacts = artifacts
        self.versions = versions

    def _require_visible(self, run_id: str, snapshot: dict | None = None) -> dict:
        identifier(run_id)
        snapshot = snapshot if snapshot is not None else self.versions.snapshot()
        if not RunVersions.visible(snapshot, run_id):
            raise VersionError("这份结果已有选定版本，旧记录仍保留", 410,
                RunVersions.selected_run(snapshot, run_id))
        return snapshot

    @staticmethod
    def _display_meta(snapshot: dict, run_id: str) -> dict:
        entry = snapshot["runs"].get(run_id)
        return {"version_revision": snapshot["revision"],
            "problem_id": entry["problem_id"] if entry else None,
            "version_run_id": entry["version_run_id"] if entry else None}

    def visibility(self, run_id: str) -> dict:
        identifier(run_id)
        snapshot = self.versions.snapshot()
        return {"visible": RunVersions.visible(snapshot, run_id),
            "current_run_id": RunVersions.selected_run(snapshot, run_id),
            **self._display_meta(snapshot, run_id)}

    def list_runs(self) -> list[dict]:
        # Load once for the entire response; never infer relationships from topics.
        snapshot = self.versions.snapshot()
        return [{**run, **self._display_meta(snapshot, run["dir"])}
            for run in self.artifacts.list_runs() if RunVersions.visible(snapshot, run["dir"])]

    def run_detail(self, run_id: str) -> dict:
        self._require_visible(run_id)
        detail = self.artifacts.run_detail(run_id)
        # A selection may have changed while the underlying files were read.
        snapshot = self._require_visible(run_id)
        return {**detail, **self._display_meta(snapshot, run_id)}

    def read_file(self, run_id: str, name: str) -> dict:
        self._require_visible(run_id)
        content = self.artifacts.read_file(run_id, name)
        self._require_visible(run_id)
        return content

    @staticmethod
    def _job_run(job: dict) -> str | None:
        return job.get("run_dir") or (job.get("params") or {}).get("run_id")

    def visible_jobs(self, jobs: list[dict]) -> list[dict]:
        snapshot = self.versions.snapshot()
        return [job for job in jobs if not self._job_run(job)
            or RunVersions.visible(snapshot, self._job_run(job))]

    def require_visible_job(self, job: dict) -> None:
        run_id = self._job_run(job)
        if run_id:
            self._require_visible(run_id)

    def job_visibility(self, job: dict) -> dict:
        run_id = self._job_run(job)
        if run_id:
            return self.visibility(run_id)
        return {"visible": True, "current_run_id": None,
            "version_revision": self.versions.snapshot()["revision"]}

    def _discover(self, run_id: str) -> dict:
        identifier(run_id)
        detail = self.artifacts.run_detail(run_id)
        if detail.get("mode") != "discover":
            raise VersionError("问题版本必须以 discover 运行作为起点", 400)
        return detail

    def register_current(self, problem_id: str, run_id: str, actor: str) -> dict:
        self._require_visible(run_id)
        self._discover(run_id)
        return self.versions.register_current(problem_id, run_id, actor)

    def register_version(self, problem_id: str, run_id: str, previous_run_id: str, actor: str) -> dict:
        self._discover(run_id)
        return self.versions.register_version(problem_id, run_id, previous_run_id, actor)

    def register_stage(self, run_id: str, parent_run_id: str, actor: str) -> dict:
        identifier(run_id)
        detail = self.artifacts.run_detail(run_id)
        if detail.get("mode") not in ("develop", "debate"):
            raise VersionError("后续阶段必须是 develop 或 run 运行", 400)
        return self.versions.register_stage(run_id, parent_run_id, actor)

    def select_version(self, problem_id: str, run_id: str, expected_selected: str,
                       reviewed: bool, actor: str) -> dict:
        if reviewed is not True:
            raise VersionError("请先审核新结果，再明确选择展示版本", 400)
        detail = self._discover(run_id)
        state = detail.get("run") or detail.get("state") or {}
        status = state.get("status") or detail.get("status")
        if str(status or "").upper() != "COMPLETED":
            raise VersionError("新运行尚未成功完成，继续展示原版本")
        cards = detail.get("cards") or []
        if not cards:
            raise VersionError("新运行尚无可展示的灵感卡，继续展示原版本")
        # Structural readiness is separate from scientific quality. Explicit
        # review is required above; successful execution alone never publishes.
        report_names = {item.get("name") for item in detail.get("files", [])}
        report = "REPORT.md" if "REPORT.md" in report_names else "DISCOVERY_REPORT.md"
        try:
            content = self.artifacts.read_file(run_id, report)
            if not str(content.get("content") or "").strip():
                raise VersionError("新报告尚未写入，继续展示原版本")
            for card in cards:
                name = card.get("idea_md")
                if "idea_id" in card and not name:
                    raise VersionError("新卡片尚未写入，继续展示原版本")
                if name is not None and not str(self.artifacts.read_file(run_id, name).get("content") or "").strip():
                    raise VersionError("新卡片尚未写入，继续展示原版本")
        except VersionError:
            raise
        except (ArtifactError, OSError) as exc:
            raise VersionError("新报告或卡片尚未齐全，继续展示原版本") from exc
        return self.versions.select(problem_id, run_id, expected_selected, actor)
