"""Validated application configuration; behavioral instructions live in Markdown."""
from pathlib import Path
from typing import Literal
import os

import yaml
from pydantic import BaseModel, ConfigDict, Field

ModelName = Literal['deepseek-v4-flash', 'deepseek-v4-pro']
DEFAULT_ROLES = {
    'investigator': 'deepseek-v4-flash', 'librarian': 'deepseek-v4-flash',
    'discovery': 'deepseek-v4-flash', 'novelty_examiner': 'deepseek-v4-pro',
    'selector': 'deepseek-v4-pro', 'developer': 'deepseek-v4-flash',
    'proposer': 'deepseek-v4-flash', 'skeptic': 'deepseek-v4-pro',
    'moderator': 'deepseek-v4-pro', 'reporter': 'deepseek-v4-flash',
    'evaluator': 'deepseek-v4-pro',
}


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    data_dir: Path = Field(default_factory=lambda: Path(os.environ.get('ARC_DATA_DIR', '.arc')))
    roles: dict[str, ModelName] = Field(default_factory=lambda: DEFAULT_ROLES.copy())
    reasoning_effort: Literal['max'] = 'max'
    max_rounds: int = Field(default=6, ge=1, le=60)
    draws: int = Field(default=5, ge=1, le=5)
    budget_cny: str = '20'
    archive_window: int = Field(default=8, ge=1, le=50)
    allow_stage_transition: bool = False


def load_settings(path: Path | None = None, **explicit_overrides) -> Settings:
    values = yaml.safe_load(path.read_text(encoding='utf-8')) if path else {}
    if values is None:
        values = {}
    if not isinstance(values, dict):
        raise ValueError('CONFIG_OBJECT_REQUIRED')
    # CLI defaults are None so only explicit options override configuration.
    values.update({key: value for key, value in explicit_overrides.items() if value is not None})
    settings = Settings.model_validate(values)
    if set(settings.roles) != set(DEFAULT_ROLES):
        raise ValueError('ROLE_SET_MISMATCH')
    return settings
