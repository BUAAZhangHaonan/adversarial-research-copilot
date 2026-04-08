from __future__ import annotations

from typing import Any

from arc.providers import literature as lp
from arc.runners.pipeline_runner import _format_references


def _base_cfg() -> dict[str, Any]:
    cfg = lp.DEFAULT_REFERENCE_CONFIG.copy()
    cfg["search_pool_size"] = 50
    cfg["final_reference_count"] = 5
    cfg["deepxiv_enabled"] = True
    return cfg


def test_collect_normalizes_reference_schema(monkeypatch) -> None:
    provider = lp.UnifiedLiteratureProvider(_base_cfg())

    monkeypatch.setattr(
        provider,
        "_fetch_arxiv",
        lambda topic, max_results: [
            {
                "source": "arxiv",
                "id": "",
                "year": "2025",
                "citation_count": "7",
                "title": "  Test   Paper  ",
                "abstract": "  Abstract   Text ",
                "url": "https://arxiv.org/abs/2501.00001",
            }
        ],
    )
    monkeypatch.setattr(provider, "_fetch_semantic_scholar", lambda topic, max_results: [])
    monkeypatch.setattr(provider, "_fetch_deepxiv_web", lambda topic, max_results: [])
    monkeypatch.setattr(provider, "_needs_deepxiv_supplement", lambda refs, topic_terms, target_pool: False)

    refs = provider.collect("test topic")
    assert refs
    assert list(refs[0].keys()) == [
        "source",
        "id",
        "year",
        "citation_count",
        "title",
        "abstract",
        "url",
    ]
    assert refs[0]["source"] == "arxiv"
    assert refs[0]["id"] == "2501.00001"
    assert refs[0]["year"] == 2025
    assert refs[0]["citation_count"] == 7
    assert refs[0]["title"] == "Test Paper"
    assert refs[0]["abstract"] == "Abstract Text"


def test_deduplicate_by_title_merges_metadata() -> None:
    provider = lp.UnifiedLiteratureProvider(_base_cfg())
    refs = provider._deduplicate_by_title(
        [
            {
                "source": "semantic_scholar",
                "id": "sem-1",
                "year": 2023,
                "citation_count": 120,
                "title": "Unified Agent Benchmark",
                "abstract": "Short abstract.",
                "url": "https://example.com/sem",
            },
            {
                "source": "arxiv",
                "id": "2501.12345",
                "year": 2024,
                "citation_count": 0,
                "title": "  unified  agent benchmark ",
                "abstract": "Longer abstract with more details for prompt injection.",
                "url": "https://arxiv.org/abs/2501.12345",
            },
        ]
    )

    assert len(refs) == 1
    merged = refs[0]
    assert merged["source"] == "arxiv"
    assert merged["citation_count"] == 120
    assert merged["year"] == 2024
    assert merged["abstract"].startswith("Longer abstract")


def test_source_priority_skips_deepxiv_when_pool_sufficient(monkeypatch) -> None:
    provider = lp.UnifiedLiteratureProvider(_base_cfg())
    deepxiv_calls = {"count": 0}

    def fake_arxiv(topic: str, max_results: int) -> list[dict[str, Any]]:
        out = []
        for idx in range(50):
            out.append(
                {
                    "source": "arxiv",
                    "id": f"2504.{idx:05d}",
                    "year": 2026,
                    "citation_count": idx,
                    "title": f"Agent memory benchmark paper {idx}",
                    "abstract": "agent memory benchmark",
                    "url": f"https://arxiv.org/abs/2504.{idx:05d}",
                }
            )
        return out

    monkeypatch.setattr(provider, "_fetch_arxiv", fake_arxiv)
    monkeypatch.setattr(provider, "_fetch_semantic_scholar", lambda topic, max_results: [])

    def fake_deepxiv(topic: str, max_results: int) -> list[dict[str, Any]]:
        deepxiv_calls["count"] += 1
        return []

    monkeypatch.setattr(provider, "_fetch_deepxiv_web", fake_deepxiv)

    refs = provider.collect("agent memory benchmark")
    assert refs
    assert deepxiv_calls["count"] == 0


def test_collect_fallback_topic_when_primary_query_empty(monkeypatch) -> None:
    provider = lp.UnifiedLiteratureProvider(_base_cfg())
    provider.cfg["deepxiv_enabled"] = False

    seen_topics: list[str] = []

    def fake_arxiv(topic: str, max_results: int) -> list[dict[str, Any]]:
        seen_topics.append(topic)
        if topic == lp.DEFAULT_FALLBACK_TOPIC:
            return [
                {
                    "source": "arxiv",
                    "id": "fallback-1",
                    "year": 2025,
                    "citation_count": 20,
                    "title": "Fallback paper",
                    "abstract": "fallback abstract",
                    "url": "https://arxiv.org/abs/fallback-1",
                }
            ]
        return []

    monkeypatch.setattr(provider, "_fetch_arxiv", fake_arxiv)
    monkeypatch.setattr(provider, "_fetch_semantic_scholar", lambda topic, max_results: [])

    refs = provider.collect("very niche custom topic")
    assert refs
    assert any(topic == lp.DEFAULT_FALLBACK_TOPIC for topic in seen_topics)
    assert refs[0]["title"] == "Fallback paper"


def test_format_references_compatibility_with_provider_schema() -> None:
    refs = [
        {
            "source": "arxiv",
            "id": "2501.00001",
            "year": 2025,
            "citation_count": 42,
            "title": "Paper | Name",
            "abstract": "A" * 500,
            "url": "https://arxiv.org/abs/2501.00001",
        }
    ]
    text = _format_references(refs)
    assert text.startswith("# REFERENCES")
    assert "| source | id | year | citations | title | abstract | url |" in text
    assert "Paper \\| Name" in text
    assert "..." in text
