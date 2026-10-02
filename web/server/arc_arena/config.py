from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

SERVER_DIR = Path(__file__).resolve().parent.parent


@dataclass
class DiscoverDefaults:
    draws: int = 5
    budget_cny: float = 20.0


@dataclass
class DevelopDefaults:
    budget_cny: float = 20.0


@dataclass
class DebateDefaults:
    budget_cny: float = 20.0


@dataclass
class Limits:
    discover_draws_max: int = 5
    discover_budget_cny_max: float = 100.0
    develop_budget_cny_max: float = 200.0
    develop_question_max_chars: int = 4000
    debate_budget_cny_max: float = 200.0
    debate_proposal_max_chars: int = 20000
    resume_budget_cny_max: float = 200.0


@dataclass
class Config:
    host: str = "0.0.0.0"
    port: int = 8210
    # ARC v2 仓库（adversarial-research-copilot master 工作区），零修改引用
    backend_root: Path = field(
        default_factory=lambda: SERVER_DIR.parent.parent)
    data_dir: Path = field(default_factory=lambda: SERVER_DIR / "data")
    max_concurrent_jobs: int = 2
    session_days: int = 7
    job_detect_seconds: int = 90
    limits: Limits = field(default_factory=Limits)
    discover: DiscoverDefaults = field(default_factory=DiscoverDefaults)
    develop: DevelopDefaults = field(default_factory=DevelopDefaults)
    debate: DebateDefaults = field(default_factory=DebateDefaults)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def jobs_log_dir(self) -> Path:
        return self.data_dir / "jobs"

    @property
    def arc_data_dir(self) -> Path:
        """ARC v2 的 --data-dir：arc.sqlite 与 reports/<run_id>/ 都在这里。"""
        return self.data_dir / "arc"

    @property
    def arc_bin(self) -> Path:
        return self.backend_root / ".venv" / "bin" / "arc"

    @property
    def arc_env_file(self) -> Path:
        return self.backend_root / ".env"

    @property
    def arc_db(self) -> Path:
        return self.arc_data_dir / "arc.sqlite"

    @property
    def arc_reports(self) -> Path:
        return self.arc_data_dir / "reports"


def load_config(path: str | Path | None = None) -> Config:
    cfg = Config()
    p = Path(path) if path else SERVER_DIR / "config.yaml"
    if p.exists():
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}

        cfg.host = str(raw.get("host", cfg.host))
        cfg.port = int(raw.get("port", cfg.port))
        cfg.max_concurrent_jobs = int(raw.get("max_concurrent_jobs", cfg.max_concurrent_jobs))
        cfg.session_days = int(raw.get("session_days", cfg.session_days))
        cfg.job_detect_seconds = int(raw.get("job_detect_seconds", cfg.job_detect_seconds))

        backend = raw.get("backend_root")
        if backend:
            b = Path(str(backend))
            cfg.backend_root = b if b.is_absolute() else (p.parent / b).resolve()

        data = raw.get("data_dir")
        if data:
            d = Path(str(data))
            cfg.data_dir = d if d.is_absolute() else (p.parent / d).resolve()

        limits = raw.get("limits") or {}
        cfg.limits.discover_draws_max = int(
            limits.get("discover", {}).get("draws_max", cfg.limits.discover_draws_max))
        cfg.limits.discover_budget_cny_max = float(
            limits.get("discover", {}).get("budget_cny_max", cfg.limits.discover_budget_cny_max))
        cfg.limits.develop_budget_cny_max = float(
            limits.get("develop", {}).get("budget_cny_max", cfg.limits.develop_budget_cny_max))
        cfg.limits.develop_question_max_chars = int(
            limits.get("develop", {}).get("question_max_chars", cfg.limits.develop_question_max_chars))
        cfg.limits.debate_budget_cny_max = float(
            limits.get("debate", {}).get("budget_cny_max", cfg.limits.debate_budget_cny_max))
        cfg.limits.debate_proposal_max_chars = int(
            limits.get("debate", {}).get("proposal_max_chars", cfg.limits.debate_proposal_max_chars))
        cfg.limits.resume_budget_cny_max = float(
            limits.get("resume", {}).get("budget_cny_max", cfg.limits.resume_budget_cny_max))

        disc = raw.get("defaults", {}).get("discover", {})
        if "draws" in disc:
            cfg.discover.draws = int(disc["draws"])
        if "budget_cny" in disc:
            cfg.discover.budget_cny = float(disc["budget_cny"])

        dev = raw.get("defaults", {}).get("develop", {})
        if "budget_cny" in dev:
            cfg.develop.budget_cny = float(dev["budget_cny"])

        deb = raw.get("defaults", {}).get("debate", {})
        if "budget_cny" in deb:
            cfg.debate.budget_cny = float(deb["budget_cny"])

    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.uploads_dir.mkdir(parents=True, exist_ok=True)
    cfg.jobs_log_dir.mkdir(parents=True, exist_ok=True)
    cfg.arc_data_dir.mkdir(parents=True, exist_ok=True)

    if not cfg.arc_bin.exists():
        raise RuntimeError(
            f"ARC v2 CLI not found at {cfg.arc_bin}; expected adversarial-research-copilot "
            "repository with .venv (uv sync)"
        )
    if not cfg.arc_env_file.exists():
        raise RuntimeError(f"ARC env file not found at {cfg.arc_env_file}")
    return cfg
