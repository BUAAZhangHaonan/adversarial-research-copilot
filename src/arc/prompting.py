from __future__ import annotations

import os
from pathlib import Path


DEFAULT_PROMPT_ROOT = Path("prompts/latest")
SUPPORTED_PROMPT_LANGUAGES = {"en", "zh"}


def normalize_prompt_language(language: str | None, default: str = "en") -> str:
    if language and language.strip().lower() in SUPPORTED_PROMPT_LANGUAGES:
        return language.strip().lower()
    env_value = os.getenv("ARC_PROMPT_LANGUAGE", "").strip().lower()
    if env_value in SUPPORTED_PROMPT_LANGUAGES:
        return env_value
    fallback = default.strip().lower()
    if fallback in SUPPORTED_PROMPT_LANGUAGES:
        return fallback
    return "en"


def resolve_prompt_path(mode: str, prompt_name: str, language: str, prompt_root: Path = DEFAULT_PROMPT_ROOT) -> Path:
    normalized = normalize_prompt_language(language)
    mode_dir = prompt_root / mode
    candidates = [
        mode_dir / f"{prompt_name}.md",
        mode_dir / f"{prompt_name}_{normalized}.md",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Prompt file not found for mode='{mode}', prompt='{prompt_name}', language='{normalized}'. "
        f"Looked in: {', '.join(str(p) for p in candidates)}"
    )


def localized_text(language: str, en_text: str, zh_text: str) -> str:
    return zh_text if normalize_prompt_language(language) == "zh" else en_text
