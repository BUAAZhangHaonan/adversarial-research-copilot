from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


def resolve_run_dir(
    output_dir: str,
    resume: bool,
    state_file_name: str,
    model_suffix: str = "",
) -> Path:
    root = _normalize_reports_root(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    if resume:
        resumed = _find_resume_dir(root, state_file_name)
        if resumed is not None:
            _write_latest_marker(root, resumed)
            return resumed

    run_dir = _new_timestamp_dir(root, model_suffix)
    run_dir.mkdir(parents=True, exist_ok=False)
    _write_latest_marker(root, run_dir)
    return run_dir


def sanitize_model_suffix(*models: str) -> str:
    """Build a sanitized directory suffix from model names.

    >>> sanitize_model_suffix("gpt-5.4", "glm-5.1", "gpt-5.4")
    'gpt_54_glm_51_gpt_54'
    """
    raw = "_".join(models)
    s = raw.lower().strip()
    s = re.sub(r"[^a-z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:64]


def _find_resume_dir(root: Path, state_file_name: str) -> Path | None:
    marker = root / "LATEST_RUN"
    if marker.exists():
        try:
            name = marker.read_text(encoding="utf-8").strip()
            if name:
                candidate = root / name
                if (candidate / state_file_name).exists():
                    return candidate
        except Exception:
            pass

    legacy = root / "latest"
    if (legacy / state_file_name).exists():
        return legacy

    candidates: list[Path] = []
    for p in root.iterdir():
        if p.is_dir() and (p / state_file_name).exists():
            candidates.append(p)
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _new_timestamp_dir(root: Path, model_suffix: str = "") -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"{ts}_{model_suffix}" if model_suffix else ts
    candidate = root / name
    if not candidate.exists():
        return candidate

    i = 1
    while True:
        c = root / f"{name}_{i:02d}"
        if not c.exists():
            return c
        i += 1


def _write_latest_marker(root: Path, run_dir: Path) -> None:
    marker = root / "LATEST_RUN"
    marker.write_text(run_dir.name, encoding="utf-8")


def ensure_run_dir_within_reports(run_dir: Path, output_dir: str) -> Path:
    root = _normalize_reports_root(output_dir).resolve()
    candidate = run_dir.resolve()
    if candidate == root or root in candidate.parents:
        return candidate
    raise ValueError(
        f"run_dir must be located under '{root}', got '{candidate}'. "
        "All outputs must stay inside reports."
    )


def _normalize_reports_root(output_dir: str) -> Path:
    root = Path(output_dir)
    if root.name != "reports":
        raise ValueError(
            f"output_dir must point to a directory named 'reports', got '{output_dir}'."
        )
    return root
