"""Validated application configuration; behavioral instructions live in Markdown."""
from pathlib import Path
from typing import Literal
import os

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .model_adapters import ModelSpec, default_models, CURRENT_RESEARCH_ALIAS

ModelName = str
DISCOVER_ROLES = ('scout', 'ideator', 'editor', 'writer')
DEFAULT_ROLES = dict.fromkeys((
    'investigator', 'librarian', 'discovery', 'novelty_examiner', 'selector',
    'developer', 'proposer', 'skeptic', 'moderator', 'reporter', 'evaluator',
    'scientific_reviewer',
), CURRENT_RESEARCH_ALIAS)


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    data_dir: Path = Field(default_factory=lambda: Path(os.environ.get('ARC_DATA_DIR', '.arc')))
    models: dict[str, ModelSpec] = Field(default_factory=default_models)
    research_model: str = CURRENT_RESEARCH_ALIAS
    roles: dict[str, ModelName] = Field(default_factory=dict)
    pricing_path: Path | None = None
    reasoning_effort: Literal['max'] = 'max'
    max_rounds: int = Field(default=6, ge=1, le=60)
    draws: int = Field(default=5, ge=1, le=5)
    budget_cny: str = '20'
    archive_window: int = Field(default=8, ge=1, le=50)
    allow_stage_transition: bool = False

    @model_validator(mode='after')
    def resolve_models(self):
        self.models = {**default_models(), **self.models}
        if self.research_model not in self.models:
            raise ValueError('UNKNOWN_MODEL_ALIAS:' + self.research_model)
        unknown_roles = set(self.roles) - set(DEFAULT_ROLES) - set(DISCOVER_ROLES)
        if unknown_roles:
            raise ValueError('UNKNOWN_ROLE:' + ','.join(sorted(unknown_roles)))
        roles = {**DEFAULT_ROLES, **dict.fromkeys(DISCOVER_ROLES, self.research_model), **self.roles}
        for role, alias in roles.items():
            if alias not in self.models:
                raise ValueError('UNKNOWN_MODEL_ALIAS:' + role + ':' + alias)
        self.roles = roles
        return self


def load_settings(path: Path | None = None, **explicit_overrides) -> Settings:
    values = yaml.safe_load(path.read_text(encoding='utf-8')) if path else {}
    if values is None:
        values = {}
    if not isinstance(values, dict):
        raise ValueError('CONFIG_OBJECT_REQUIRED')
    # CLI defaults are None so only explicit options override configuration.
    values.update({key: value for key, value in explicit_overrides.items() if value is not None})
    settings = Settings.model_validate(values)
    return settings
