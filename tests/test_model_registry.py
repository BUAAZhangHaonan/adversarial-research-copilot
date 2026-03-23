from __future__ import annotations

from pathlib import Path

import yaml

from arc.model_registry import (
    load_registry,
    load_runtime_roles,
    resolve_role_model,
    role_api_ready,
    set_role_model,
)


def _write_models(path: Path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "models": {
                    "m1": {
                        "provider": "x",
                        "base_url_env": "X_BASE",
                        "api_key_env": "X_KEY",
                        "endpoint": "chat_completions",
                    },
                    "m2": {
                        "provider": "x",
                        "base_url_env": "Y_BASE",
                        "api_key_env": "Y_KEY",
                        "endpoint": "responses",
                    },
                },
                "aliases": {
                    "proposer_default": "m1",
                    "skeptic_default": "m2",
                    "moderator_default": "m2",
                },
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_runtime_roles_default_and_set(tmp_path: Path) -> None:
    models_file = tmp_path / "models.yaml"
    runtime_file = tmp_path / "runtime.yaml"
    _write_models(models_file)

    reg = load_registry(models_file)
    cfg = load_runtime_roles(reg, runtime_file)
    assert cfg.proposer == "m1"
    assert cfg.skeptic == "m2"
    assert cfg.pipeline_writer == "m1"

    cfg2 = set_role_model("pipeline_reviewer", "m1", reg, runtime_file)
    assert cfg2.pipeline_reviewer == "m1"


def test_resolve_role_model_prefers_explicit(tmp_path: Path) -> None:
    models_file = tmp_path / "models.yaml"
    runtime_file = tmp_path / "runtime.yaml"
    _write_models(models_file)
    reg = load_registry(models_file)
    cfg = load_runtime_roles(reg, runtime_file)

    resolved = resolve_role_model("proposer", reg, cfg, explicit_model="m2")
    assert resolved == "m2"


def test_role_api_ready_missing_env(tmp_path: Path) -> None:
    models_file = tmp_path / "models.yaml"
    _write_models(models_file)
    reg = load_registry(models_file)

    ok, reason = role_api_ready("m1", reg)
    assert not ok
    assert reason in {"missing:X_BASE", "missing:X_KEY"}
