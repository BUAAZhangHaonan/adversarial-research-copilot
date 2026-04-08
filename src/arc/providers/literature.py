from __future__ import annotations

import json
import math
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

import requests
import yaml

DEFAULT_REFERENCE_CONFIG: dict[str, Any] = {
    "search_pool_size": 50,
    "final_reference_count": 20,
    "arxiv_max_results": 35,
    "arxiv_timeout_seconds": 20,
    "semantic_scholar_max_results": 35,
    "semantic_scholar_base_url": "https://api.semanticscholar.org/graph/v1",
    "semantic_scholar_timeout_seconds": 25,
    "deepxiv_enabled": True,
    "deepxiv_web_max_results": 20,
    "deepxiv_web_max_calls": 2,
    "deepxiv_timeout_seconds": 30,
    "request_retry_attempts": 3,
    "request_backoff_seconds": 0.6,
    "recency_years_preferred": 3,
    "influential_citation_threshold": 1000,
    "min_recent_results": 10,
    "min_relevant_results": 14,
    "min_relevance_score": 0.15,
    "semantic_scholar_api_key": "",
    "deepxiv_token": "",
}

SOURCE_PRIORITY: dict[str, int] = {
    "arxiv": 0,
    "semantic_scholar": 1,
    "deepxiv": 2,
}

DEFAULT_FALLBACK_TOPIC = "multimodal large language model hallucination benchmark"


def load_reference_config(config_path: str | Path = "configs/references.yaml") -> dict[str, Any]:
    out = DEFAULT_REFERENCE_CONFIG.copy()
    p = Path(config_path)
    if p.exists():
        try:
            cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            refs_cfg = cfg.get("references", {}) if isinstance(cfg, dict) else {}
            if isinstance(refs_cfg, dict):
                out.update(refs_cfg)
        except Exception:
            pass

    # Optional env overrides keep runtime tuning simple during experiments.
    out["search_pool_size"] = _to_int(
        os.getenv("ARC_REFERENCE_SEARCH_POOL_SIZE", out.get("search_pool_size")),
        out["search_pool_size"],
    )
    out["final_reference_count"] = _to_int(
        os.getenv("ARC_REFERENCE_FINAL_COUNT", out.get("final_reference_count")),
        out["final_reference_count"],
    )
    out["deepxiv_enabled"] = _to_bool(
        os.getenv("ARC_DEEPXIV_ENABLED", out.get("deepxiv_enabled")),
        bool(out.get("deepxiv_enabled", True)),
    )

    out["search_pool_size"] = max(10, min(_to_int(out.get("search_pool_size"), 50), 200))
    out["final_reference_count"] = max(1, min(_to_int(out.get("final_reference_count"), 20), 60))
    out["arxiv_max_results"] = max(1, min(_to_int(out.get("arxiv_max_results"), 35), 100))
    out["semantic_scholar_max_results"] = max(1, min(_to_int(out.get("semantic_scholar_max_results"), 35), 100))
    out["deepxiv_web_max_results"] = max(1, min(_to_int(out.get("deepxiv_web_max_results"), 20), 100))
    out["deepxiv_web_max_calls"] = max(1, min(_to_int(out.get("deepxiv_web_max_calls"), 2), 5))
    out["request_retry_attempts"] = max(1, min(_to_int(out.get("request_retry_attempts"), 3), 8))
    out["request_backoff_seconds"] = max(0.0, min(_to_float(out.get("request_backoff_seconds"), 0.6), 10.0))
    out["min_relevance_score"] = max(0.0, min(_to_float(out.get("min_relevance_score"), 0.15), 1.0))
    out["min_recent_results"] = max(0, min(_to_int(out.get("min_recent_results"), 10), 100))
    out["min_relevant_results"] = max(0, min(_to_int(out.get("min_relevant_results"), 14), 100))

    return out


def collect_references(topic: str, config_path: str | Path = "configs/references.yaml") -> list[dict[str, Any]]:
    cfg = load_reference_config(config_path)
    provider = UnifiedLiteratureProvider(cfg)
    return provider.collect(topic)


class UnifiedLiteratureProvider:
    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg

    def collect(self, topic: str) -> list[dict[str, Any]]:
        q = str(topic or "").strip() or DEFAULT_FALLBACK_TOPIC
        topic_terms = _extract_topic_terms(q)
        target_pool = _to_int(self.cfg.get("search_pool_size"), 50)

        candidates: list[dict[str, Any]] = []
        candidates.extend(self._fetch_arxiv(q, _to_int(self.cfg.get("arxiv_max_results"), 35)))
        candidates.extend(self._fetch_semantic_scholar(q, _to_int(self.cfg.get("semantic_scholar_max_results"), 35)))

        deduped = self._deduplicate_by_title(candidates)
        if self._needs_deepxiv_supplement(deduped, topic_terms, target_pool):
            candidates.extend(self._fetch_deepxiv_web(q, _to_int(self.cfg.get("deepxiv_web_max_results"), 20)))
            deduped = self._deduplicate_by_title(candidates)

        if not deduped and q.lower() != DEFAULT_FALLBACK_TOPIC.lower():
            fallback_candidates: list[dict[str, Any]] = []
            fallback_terms = _extract_topic_terms(DEFAULT_FALLBACK_TOPIC)
            fallback_candidates.extend(
                self._fetch_arxiv(DEFAULT_FALLBACK_TOPIC, _to_int(self.cfg.get("arxiv_max_results"), 35))
            )
            fallback_candidates.extend(
                self._fetch_semantic_scholar(
                    DEFAULT_FALLBACK_TOPIC,
                    _to_int(self.cfg.get("semantic_scholar_max_results"), 35),
                )
            )
            if self._needs_deepxiv_supplement(fallback_candidates, fallback_terms, max(12, target_pool // 2)):
                fallback_candidates.extend(
                    self._fetch_deepxiv_web(
                        DEFAULT_FALLBACK_TOPIC,
                        _to_int(self.cfg.get("deepxiv_web_max_results"), 20),
                    )
                )
            deduped = self._deduplicate_by_title(fallback_candidates)
            topic_terms = fallback_terms

        ranked = self._rank_references(deduped, topic_terms)
        if target_pool > 0:
            ranked = ranked[:target_pool]

        preferred = self._prefer_recent_or_influential(ranked)
        final_count = _to_int(self.cfg.get("final_reference_count"), 20)
        selected = preferred[:final_count]
        if len(selected) < final_count:
            selected = ranked[:final_count]

        return [self._normalize_reference(item) for item in selected]

    def _fetch_arxiv(self, topic: str, max_results: int) -> list[dict[str, Any]]:
        query_words = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", topic)[:12]
        if query_words:
            query = "+AND+".join([f"all:{quote_plus(word)}" for word in query_words])
        else:
            query = "all:multimodal+AND+all:hallucination"

        url = (
            "https://export.arxiv.org/api/query?"
            f"search_query={query}&start=0&max_results={max(1, min(max_results, 100))}"
            "&sortBy=submittedDate&sortOrder=descending"
        )

        text = self._request_text(
            url=url,
            timeout_seconds=_to_int(self.cfg.get("arxiv_timeout_seconds"), 20),
            headers={"User-Agent": "ARC/0.1 (research-pipeline)"},
        )
        if not text:
            return []

        try:
            root = ET.fromstring(text)
        except Exception:
            return []

        ns = {"a": "http://www.w3.org/2005/Atom"}
        out: list[dict[str, Any]] = []
        for entry in root.findall("a:entry", ns):
            id_node = entry.find("a:id", ns)
            title_node = entry.find("a:title", ns)
            summary_node = entry.find("a:summary", ns)
            published_node = entry.find("a:published", ns)
            if id_node is None or title_node is None:
                continue

            arxiv_url = str(id_node.text or "").strip()
            arxiv_id = arxiv_url.rsplit("/", 1)[-1] if arxiv_url else ""
            title = _clean_text(title_node.text or "")
            abstract = _clean_text(summary_node.text or "") if summary_node is not None else ""
            year = _extract_year(published_node.text if published_node is not None else "")

            out.append(
                self._normalize_reference(
                    {
                        "source": "arxiv",
                        "id": arxiv_id,
                        "year": year,
                        "citation_count": 0,
                        "title": title,
                        "abstract": abstract,
                        "url": arxiv_url,
                    }
                )
            )
        return out

    def _fetch_semantic_scholar(self, topic: str, max_results: int) -> list[dict[str, Any]]:
        base_url = str(self.cfg.get("semantic_scholar_base_url", "https://api.semanticscholar.org/graph/v1")).rstrip("/")
        query = quote_plus(topic)
        url = (
            f"{base_url}/paper/search?"
            f"query={query}&limit={max(1, min(max_results, 100))}"
            "&fields=title,abstract,url,year,citationCount,externalIds"
        )

        headers = {"User-Agent": "ARC/0.1 (research-pipeline)"}
        api_key = (
            os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
            or str(self.cfg.get("semantic_scholar_api_key", "")).strip()
        )
        if api_key:
            headers["x-api-key"] = api_key

        payload = self._request_json(
            url=url,
            timeout_seconds=_to_int(self.cfg.get("semantic_scholar_timeout_seconds"), 25),
            headers=headers,
        )
        if not isinstance(payload, dict):
            return []

        out: list[dict[str, Any]] = []
        for item in payload.get("data", []):
            if not isinstance(item, dict):
                continue
            title = _clean_text(item.get("title") or "")
            if not title:
                continue
            external_ids = item.get("externalIds") or {}
            paper_id = str(
                (external_ids.get("ArXiv") if isinstance(external_ids, dict) else "")
                or item.get("paperId")
                or ""
            ).strip()
            out.append(
                self._normalize_reference(
                    {
                        "source": "semantic_scholar",
                        "id": paper_id,
                        "year": _to_int(item.get("year"), 0),
                        "citation_count": _to_int(item.get("citationCount"), 0),
                        "title": title,
                        "abstract": _clean_text(item.get("abstract") or ""),
                        "url": str(item.get("url") or "").strip(),
                    }
                )
            )
        return out

    def _fetch_deepxiv_web(self, topic: str, max_results: int) -> list[dict[str, Any]]:
        if not _to_bool(self.cfg.get("deepxiv_enabled"), True):
            return []

        reader = self._load_deepxiv_reader()
        if reader is None:
            return []

        query_plan = [
            topic,
            f"{topic} survey",
            f"{topic} benchmark recent",
        ]
        max_calls = _to_int(self.cfg.get("deepxiv_web_max_calls"), 2)
        target = max(1, min(max_results, 100))
        out: list[dict[str, Any]] = []
        for query in query_plan[:max_calls]:
            payload = self._deepxiv_websearch(reader, query, target)
            for item in self._extract_items(payload):
                ref = self._normalize_deepxiv_item(item)
                if not ref:
                    continue
                out.append(ref)
                if len(out) >= target:
                    return out
        return out

    def _deepxiv_websearch(self, reader: Any, query: str, limit: int) -> Any:
        for call in (
            lambda: reader.websearch(query=query, size=limit),
            lambda: reader.websearch(query, size=limit),
            lambda: reader.websearch(query=query),
            lambda: reader.websearch(query),
        ):
            try:
                return call()
            except TypeError:
                continue
            except Exception:
                return None
        return None

    def _load_deepxiv_reader(self) -> Any | None:
        try:
            from deepxiv_sdk import Reader
        except Exception:
            return None

        token = os.getenv("DEEPXIV_TOKEN", "").strip() or str(self.cfg.get("deepxiv_token", "")).strip()
        if token and not os.getenv("DEEPXIV_TOKEN", "").strip():
            os.environ["DEEPXIV_TOKEN"] = token

        timeout = _to_int(self.cfg.get("deepxiv_timeout_seconds"), 30)
        retries = _to_int(self.cfg.get("request_retry_attempts"), 3)

        for kwargs in (
            {"timeout": timeout, "max_retries": retries},
            {"timeout": timeout},
            {"max_retries": retries},
            {},
        ):
            try:
                return Reader(**kwargs)
            except TypeError:
                continue
            except Exception:
                return None
        return None

    def _extract_items(self, payload: Any) -> list[dict[str, Any]]:
        if payload is None:
            return []
        if isinstance(payload, str):
            text = payload.strip()
            if not text:
                return []
            try:
                parsed = json.loads(text)
            except Exception:
                return []
            return self._extract_items(parsed)
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("results", "items", "papers", "hits", "data", "web", "web_results"):
                candidate = payload.get(key)
                if isinstance(candidate, list):
                    return [item for item in candidate if isinstance(item, dict)]
                if isinstance(candidate, dict):
                    nested = self._extract_items(candidate)
                    if nested:
                        return nested
            if "title" in payload or "name" in payload:
                return [payload]
        return []

    def _normalize_deepxiv_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        title = _clean_text(
            item.get("title")
            or item.get("paper_title")
            or item.get("name")
            or ""
        )
        if not title:
            return None

        url = str(item.get("url") or item.get("paper_url") or item.get("link") or "").strip()
        arxiv_id = _extract_arxiv_id(url)
        item_id = str(item.get("id") or item.get("paper_id") or item.get("arxiv_id") or arxiv_id or "").strip()
        if not item_id:
            item_id = f"deepxiv:{_safe_id_fragment(title)}"

        return self._normalize_reference(
            {
                "source": "deepxiv",
                "id": item_id,
                "year": _extract_year(item.get("year") or item.get("published") or item.get("date") or ""),
                "citation_count": _to_int(
                    item.get("citation_count") or item.get("citations") or item.get("citationCount"),
                    0,
                ),
                "title": title,
                "abstract": _clean_text(
                    item.get("abstract")
                    or item.get("summary")
                    or item.get("snippet")
                    or item.get("description")
                    or ""
                ),
                "url": url,
            }
        )

    def _request_text(self, url: str, timeout_seconds: int, headers: dict[str, str]) -> str | None:
        attempts = _to_int(self.cfg.get("request_retry_attempts"), 3)
        backoff = _to_float(self.cfg.get("request_backoff_seconds"), 0.6)
        for idx in range(max(1, attempts)):
            try:
                resp = requests.get(url, timeout=timeout_seconds, headers=headers)
                resp.raise_for_status()
                return resp.text
            except Exception:
                if idx >= attempts - 1:
                    return None
                time.sleep(backoff * (2**idx))
        return None

    def _request_json(self, url: str, timeout_seconds: int, headers: dict[str, str]) -> Any:
        attempts = _to_int(self.cfg.get("request_retry_attempts"), 3)
        backoff = _to_float(self.cfg.get("request_backoff_seconds"), 0.6)
        for idx in range(max(1, attempts)):
            try:
                resp = requests.get(url, timeout=timeout_seconds, headers=headers)
                resp.raise_for_status()
                return resp.json()
            except Exception:
                if idx >= attempts - 1:
                    return None
                time.sleep(backoff * (2**idx))
        return None

    def _deduplicate_by_title(self, refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        dedup: dict[str, dict[str, Any]] = {}
        for raw in refs:
            ref = self._normalize_reference(raw)
            title_key = _title_key(ref.get("title", ""))
            if not title_key:
                continue
            prev = dedup.get(title_key)
            if prev is None:
                dedup[title_key] = ref
            else:
                dedup[title_key] = self._merge_reference(prev, ref)
        return list(dedup.values())

    def _merge_reference(self, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        merged = dict(left)

        left_source = str(left.get("source", "")).strip().lower()
        right_source = str(right.get("source", "")).strip().lower()
        if self._source_priority(right_source) < self._source_priority(left_source):
            merged["source"] = right_source

        if not str(merged.get("id", "")).strip() and str(right.get("id", "")).strip():
            merged["id"] = str(right.get("id", "")).strip()
        if _to_int(right.get("year"), 0) > _to_int(merged.get("year"), 0):
            merged["year"] = _to_int(right.get("year"), 0)
        merged["citation_count"] = max(
            _to_int(merged.get("citation_count"), 0),
            _to_int(right.get("citation_count"), 0),
        )

        left_abs = str(merged.get("abstract", "")).strip()
        right_abs = str(right.get("abstract", "")).strip()
        if len(right_abs) > len(left_abs):
            merged["abstract"] = right_abs

        if not str(merged.get("url", "")).strip() and str(right.get("url", "")).strip():
            merged["url"] = str(right.get("url", "")).strip()

        return self._normalize_reference(merged)

    def _needs_deepxiv_supplement(
        self,
        refs: list[dict[str, Any]],
        topic_terms: list[str],
        target_pool: int,
    ) -> bool:
        if not _to_bool(self.cfg.get("deepxiv_enabled"), True):
            return False
        if len(refs) < target_pool:
            return True

        now_year = datetime.now(UTC).year
        recent_years = _to_int(self.cfg.get("recency_years_preferred"), 3)
        recent_count = 0
        relevant_count = 0
        min_rel_score = _to_float(self.cfg.get("min_relevance_score"), 0.15)
        for ref in refs:
            year = _to_int(ref.get("year"), 0)
            if year >= now_year - recent_years:
                recent_count += 1
            rel = self._relevance_score(topic_terms, f"{ref.get('title', '')} {ref.get('abstract', '')}")
            if rel >= min_rel_score:
                relevant_count += 1

        if recent_count < _to_int(self.cfg.get("min_recent_results"), 10):
            return True
        if relevant_count < _to_int(self.cfg.get("min_relevant_results"), 14):
            return True
        return False

    def _prefer_recent_or_influential(self, refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not refs:
            return []
        now_year = datetime.now(UTC).year
        recent_years = _to_int(self.cfg.get("recency_years_preferred"), 3)
        influential_threshold = _to_int(self.cfg.get("influential_citation_threshold"), 1000)
        preferred = [
            ref
            for ref in refs
            if _to_int(ref.get("year"), 0) >= now_year - recent_years
            or _to_int(ref.get("citation_count"), 0) >= influential_threshold
        ]
        if not preferred:
            return refs

        preferred_keys = {_title_key(ref.get("title", "")) for ref in preferred}
        rest = [ref for ref in refs if _title_key(ref.get("title", "")) not in preferred_keys]
        return preferred + rest

    def _rank_references(self, refs: list[dict[str, Any]], topic_terms: list[str]) -> list[dict[str, Any]]:
        return sorted(
            refs,
            key=lambda ref: (
                -self._combined_score(ref, topic_terms),
                -_to_int(ref.get("year"), 0),
                -_to_int(ref.get("citation_count"), 0),
                self._source_priority(str(ref.get("source", ""))),
                str(ref.get("title", "")).lower(),
            ),
        )

    def _combined_score(self, ref: dict[str, Any], topic_terms: list[str]) -> float:
        now_year = datetime.now(UTC).year
        year = _to_int(ref.get("year"), 0)
        citations = max(0, _to_int(ref.get("citation_count"), 0))

        age = max(0, now_year - year) if year > 0 else 15
        recency_score = max(0.0, 1.0 - min(age, 15) / 15.0)

        impact_score = 0.0
        if citations > 0:
            impact_score = min(1.0, math.log1p(citations) / math.log(2000.0))

        relevance_score = self._relevance_score(topic_terms, f"{ref.get('title', '')} {ref.get('abstract', '')}")
        abstract_bonus = 0.08 if str(ref.get("abstract", "")).strip() else 0.0
        source_bonus = {
            "arxiv": 0.03,
            "semantic_scholar": 0.02,
            "deepxiv": 0.01,
        }.get(str(ref.get("source", "")).strip().lower(), 0.0)

        return relevance_score * 0.5 + recency_score * 0.3 + impact_score * 0.2 + abstract_bonus + source_bonus

    def _relevance_score(self, topic_terms: list[str], text: str) -> float:
        if not topic_terms:
            return 0.0
        tokens = set(re.findall(r"[a-z0-9\u4e00-\u9fff]+", text.lower()))
        if not tokens:
            return 0.0
        hits = sum(1 for term in topic_terms if term in tokens)
        return hits / len(topic_terms)

    def _source_priority(self, source: str) -> int:
        return SOURCE_PRIORITY.get(source.strip().lower(), 99)

    def _normalize_reference(self, ref: dict[str, Any]) -> dict[str, Any]:
        source = str(ref.get("source") or "").strip().lower() or "unknown"
        title = _clean_text(ref.get("title") or "")
        abstract = _clean_text(ref.get("abstract") or "")
        url = str(ref.get("url") or "").strip()
        item_id = str(ref.get("id") or "").strip()

        if not item_id and url:
            item_id = _extract_arxiv_id(url) or _safe_id_fragment(url)
        if not item_id and title:
            item_id = _safe_id_fragment(title)

        return {
            "source": source,
            "id": item_id,
            "year": _to_int(ref.get("year"), 0),
            "citation_count": _to_int(ref.get("citation_count"), 0),
            "title": title,
            "abstract": abstract,
            "url": url,
        }


def _extract_topic_terms(topic: str) -> list[str]:
    stop_words = {
        "a",
        "an",
        "and",
        "the",
        "for",
        "with",
        "into",
        "from",
        "that",
        "this",
        "using",
        "based",
        "study",
        "research",
        "approach",
        "method",
    }
    tokens = re.findall(r"[a-z0-9\u4e00-\u9fff]+", topic.lower())
    out: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if len(token) <= 1:
            continue
        if token in stop_words:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out[:16]


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _extract_arxiv_id(url: str) -> str:
    if not url:
        return ""
    m = re.search(r"arxiv\.org/(?:abs|pdf)/([^/?#]+)", url)
    if not m:
        return ""
    return m.group(1).replace(".pdf", "").strip()


def _extract_year(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value if 1900 <= value <= 2100 else 0
    text = str(value).strip()
    m = re.search(r"\b(19\d{2}|20\d{2}|2100)\b", text)
    if not m:
        return 0
    return int(m.group(1))


def _safe_id_fragment(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not cleaned:
        return "ref"
    return cleaned[:64]


def _title_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", _clean_text(value).lower()).strip()


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default
