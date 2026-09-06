from __future__ import annotations

from pathlib import Path

from arc.prompting import DEFAULT_PROMPT_ROOT, resolve_prompt_path


def test_resolve_prompt_path_prefers_language_variant() -> None:
    path = resolve_prompt_path("debate", "proposer", "en")
    assert path == DEFAULT_PROMPT_ROOT / "debate" / "proposer_en.md"


def test_resolve_prompt_path_uses_suffixless_as_fallback(tmp_path: Path) -> None:
    mode_dir = tmp_path / "develop"
    mode_dir.mkdir(parents=True, exist_ok=True)
    (mode_dir / "moderator.md").write_text("generic prompt", encoding="utf-8")

    path = resolve_prompt_path("develop", "moderator", "zh", prompt_root=tmp_path)
    assert path == mode_dir / "moderator.md"
