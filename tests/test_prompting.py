from __future__ import annotations

from pathlib import Path

from arc.prompting import DEFAULT_PROMPT_ROOT, resolve_prompt_path


def test_resolve_prompt_path_prefers_language_variant() -> None:
    path = resolve_prompt_path("default", "proposer", "en")
    assert path == DEFAULT_PROMPT_ROOT / "default" / "proposer_en.md"


def test_resolve_prompt_path_uses_suffixless_as_fallback(tmp_path: Path) -> None:
    mode_dir = tmp_path / "chat"
    mode_dir.mkdir(parents=True, exist_ok=True)
    (mode_dir / "moderator_chat.md").write_text("generic prompt", encoding="utf-8")

    path = resolve_prompt_path("chat", "moderator_chat", "zh", prompt_root=tmp_path)
    assert path == mode_dir / "moderator_chat.md"
