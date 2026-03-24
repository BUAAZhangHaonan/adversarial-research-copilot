from __future__ import annotations

from pathlib import Path


def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def assert_contains_all(text: str, markers: list[str], *, label: str) -> None:
    for marker in markers:
        assert marker in text, f"missing marker {marker!r} in {label}"


def assert_contains_none(text: str, markers: list[str], *, label: str) -> None:
    for marker in markers:
        assert marker not in text, f"unexpected marker {marker!r} in {label}"
