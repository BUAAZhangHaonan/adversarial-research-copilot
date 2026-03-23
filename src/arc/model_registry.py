from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


Role = Literal[
    "proposer",
    "skeptic",
    "moderator",
    "pipeline_writer",
    "pipeline_reviewer",
    "pipeline_moderator",
]


class ModelEntry(BaseModel):
    provider: str
    base_url_env: str
    api_key_env: str
    endpoint: Literal["chat_completions", "responses"]


class RuntimeRoleConfig(BaseModel):
    proposer: str
    skeptic: str
    moderator: str
    pipeline_writer: str
    pipeline_reviewer: str
    pipeline_moderator: str


class Registry(BaseModel):
    models: dict[str, ModelEntry] = Field(default_factory=dict)
    aliases: dict[str, str] = Field(default_factory=dict)


def load_registry(path: str | Path = "configs/models.yaml") -> Registry:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    models_raw = raw.get("models", {})
    aliases_raw = raw.get("aliases", {})
    models = {name: ModelEntry(**spec) for name, spec in models_raw.items()}
    aliases = {str(k): str(v) for k, v in aliases_raw.items()}
    return Registry(models=models, aliases=aliases)


def default_runtime_roles(registry: Registry) -> RuntimeRoleConfig:
    proposer = registry.aliases.get("proposer_default", _first_model(registry))
    skeptic = registry.aliases.get("skeptic_default", proposer)
    moderator = registry.aliases.get("moderator_default", skeptic)
    return RuntimeRoleConfig(
        proposer=proposer,
        skeptic=skeptic,
        moderator=moderator,
        pipeline_writer=proposer,
        pipeline_reviewer=skeptic,
        pipeline_moderator=moderator,
    )


def load_runtime_roles(
    registry: Registry,
    path: str | Path = "configs/runtime_models.yaml",
) -> RuntimeRoleConfig:
    p = Path(path)
    if not p.exists():
        cfg = default_runtime_roles(registry)
        save_runtime_roles(cfg, path)
        return cfg

    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    try:
        cfg = RuntimeRoleConfig(**raw.get("roles", {}))
    except Exception:
        cfg = default_runtime_roles(registry)
        save_runtime_roles(cfg, path)
        return cfg

    # Ensure referenced models still exist.
    repaired = _repair_roles(cfg, registry)
    if repaired != cfg:
        save_runtime_roles(repaired, path)
    return repaired


def save_runtime_roles(cfg: RuntimeRoleConfig, path: str | Path = "configs/runtime_models.yaml") -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "roles": cfg.model_dump(),
    }
    p.write_text(yaml.safe_dump(payload, allow_unicode=True,
                 sort_keys=False), encoding="utf-8")
    return p


def set_role_model(
    role: Role,
    model_name: str,
    registry: Registry,
    path: str | Path = "configs/runtime_models.yaml",
) -> RuntimeRoleConfig:
    if model_name not in registry.models:
        raise ValueError(f"Unknown model: {model_name}")
    cfg = load_runtime_roles(registry, path)
    setattr(cfg, role, model_name)
    save_runtime_roles(cfg, path)
    return cfg


def resolve_role_model(
    role: Role,
    registry: Registry,
    runtime: RuntimeRoleConfig,
    explicit_model: str | None,
) -> str:
    if explicit_model:
        return explicit_model

    env_map = {
        "proposer": "ARC_DEFAULT_PROPOSER",
        "skeptic": "ARC_DEFAULT_SKEPTIC",
        "moderator": "ARC_DEFAULT_MODERATOR",
        "pipeline_writer": "ARC_DEFAULT_PIPELINE_WRITER",
        "pipeline_reviewer": "ARC_DEFAULT_PIPELINE_REVIEWER",
        "pipeline_moderator": "ARC_DEFAULT_PIPELINE_MODERATOR",
    }
    env_name = env_map[role]
    env_value = os.getenv(env_name)
    if env_value:
        return env_value

    return getattr(runtime, role)


def role_api_ready(role_model: str, registry: Registry) -> tuple[bool, str]:
    entry = registry.models.get(role_model)
    if not entry:
        return False, "model-not-found"
    base_url = os.getenv(entry.base_url_env, "").strip()
    api_key = os.getenv(entry.api_key_env, "").strip()
    if not base_url:
        return False, f"missing:{entry.base_url_env}"
    if not api_key:
        return False, f"missing:{entry.api_key_env}"
    return True, "ready"


def _first_model(registry: Registry) -> str:
    if not registry.models:
        raise ValueError("No models defined in registry")
    return next(iter(registry.models.keys()))


def _repair_roles(cfg: RuntimeRoleConfig, registry: Registry) -> RuntimeRoleConfig:
    fallback = default_runtime_roles(registry)
    data = cfg.model_dump()
    changed = False
    for key, model in data.items():
        if model not in registry.models:
            data[key] = getattr(fallback, key)
            changed = True
    if not changed:
        return cfg
    return RuntimeRoleConfig(**data)
