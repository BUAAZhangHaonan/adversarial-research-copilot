"""ARC discover mode: mine novel research problems from existing literature.

Pipeline direction is inverted relative to chat mode: instead of defending a
user-supplied idea, discover starts from a broad literature pool (scholartrace),
deep-reads the strongest papers (scholaranalysis), mines problem-level gaps,
audits them against real-world pain (webresearch), composes new problem
statements, and gates them through a taste judge that kills incremental work.

All three MCP services are mandatory: if any is unreachable the run fails
fast (no degraded runs).
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from arc.llm_client import LLMClient
from arc.prompting import resolve_prompt_path
from arc.providers.mcp_bridge import MCPError, MCPServices, connect_services
from arc.run_paths import resolve_run_dir, sanitize_model_suffix

logger = logging.getLogger(__name__)

DISCOVER_STAGES = [
    "theme-framing",
    "wide-retrieval",
    "deep-read",
    "gap-mining",
    "saturation-audit",
    "idea-portfolio",
    "duplicate-check",
    "taste-gate",
]

# Cap prompt growth: per-paper deep-read notes fed to the gap miner.
_NOTE_MAX_CHARS = 4000
# Cap the web dossier per gap fed to the saturation auditor.
_DOSSIER_MAX_CHARS = 3500
# Never audit more gaps than this (cost control).
_MAX_GAPS_TO_AUDIT = 8


class DiscoverError(RuntimeError):
    pass


@dataclass
class DiscoverConfig:
    papers: int = 60
    deep_read: int = 12
    ideas: int = 8
    webresearch_max_results: int = 6
    dedup_web_queries: int = 2
    dedup_scholartrace_enabled: bool = True
    dedup_scholartrace_limit: int = 5
    stress_test: bool = False
    stress_rounds: int = 10
    stress_top_k: int = 3
    prompt_language: str = "en"
    mcp_call_timeout: float = 900.0
    min_deep_read_ok: int = 3
    stale_resume_hours: int = 24


@dataclass
class DiscoverState:
    topic: str
    models: dict[str, str]
    config: DiscoverConfig = field(default_factory=DiscoverConfig)
    stage_statuses: dict[str, str] = field(default_factory=dict)
    status: str = "in_progress"
    stop_reason: str = "running"
    timestamp: str = ""


class _CountingMCP:
    """Counts calls to an MCP client; server-side token spend is invisible to
    ARC, so cost reports record call counts and say so honestly (review 七)."""

    def __init__(self, inner: Any, counter: dict[str, int], name: str) -> None:
        self._inner = inner
        self._counter = counter
        self._name = name

    def call_tool(self, name: str, arguments: dict[str, Any], timeout: float = 600.0) -> str:
        self._counter[self._name] = self._counter.get(self._name, 0) + 1
        return self._inner.call_tool(name, arguments, timeout=timeout)

    def close(self) -> None:
        close = getattr(self._inner, "close", None)
        if close:
            close()

    def __getattr__(self, item: str) -> Any:
        return getattr(self._inner, item)


def _render_cost_report(
    llm_usage: dict[str, dict[str, float]],
    mcp_calls: dict[str, int],
) -> str:
    lines = [
        "# COST_REPORT", "",
        "## ARC-owned LLM calls (billed to the configured DeepSeek key)", "",
        "| model | calls | prompt tok | completion tok | total tok | wall time (s) | reports w/o usage |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for model, stats in llm_usage.items():
        lines.append(
            f"| {model} | {stats.get('calls', 0)} | {stats.get('prompt_tokens', 0)} | "
            f"{stats.get('completion_tokens', 0)} | {stats.get('total_tokens', 0)} | "
            f"{stats.get('duration_ms', 0.0) / 1000.0:.1f} | {stats.get('reports_without_usage', 0)} |")
    if not llm_usage:
        lines.append("| (none) | | | | | | |")
    lines += [
        "",
        "## MCP service calls (billed to each service's own key)", "",
    ]
    for name, count in mcp_calls.items():
        lines.append(f"- {name}: {count} tool calls")
    lines += [
        "",
        "Note: MCP services run their own LLM pipelines internally and do not",
        "report token usage to ARC; their cost is only bounded by these call",
        "counts, not measured. Reports without usage are gateway responses that",
        "omitted the usage field (recorded as zero, flagged in the last column).",
        "",
    ]
    return "\n".join(lines)


def run_discover(
    topic: str,
    generator_model: str,
    judge_model: str,
    output_dir: str = "reports",
    resume: bool = False,
    papers: int | None = None,
    deep_read: int | None = None,
    ideas: int | None = None,
    stress_test: bool | None = None,
    stress_rounds: int | None = None,
    prompt_language: str | None = None,
) -> tuple[Path, Path]:
    """Run the discover pipeline. Returns (report_file, state_file)."""
    cfg = _load_config()
    if papers is not None:
        cfg.papers = max(5, int(papers))
    if deep_read is not None:
        cfg.deep_read = max(1, int(deep_read))
    if cfg.deep_read > cfg.papers:
        cfg.deep_read = cfg.papers
    if ideas is not None:
        cfg.ideas = max(1, int(ideas))
    if stress_test is not None:
        cfg.stress_test = stress_test
    if stress_rounds is not None:
        cfg.stress_rounds = max(1, int(stress_rounds))
    if prompt_language is not None:
        cfg.prompt_language = prompt_language

    models = {"generator": generator_model, "judge": judge_model}
    msuffix = sanitize_model_suffix(generator_model, judge_model)
    run_dir = resolve_run_dir(output_dir, resume, "discover_state.json", model_suffix=msuffix)
    state_file = run_dir / "discover_state.json"

    resumed_state = _load_resume_state(state_file, topic, models, cfg.stale_resume_hours)
    if resume and resumed_state is None and state_file.exists():
        run_dir = resolve_run_dir(output_dir, False, "discover_state.json", model_suffix=msuffix)
        state_file = run_dir / "discover_state.json"
        resumed_state = _load_resume_state(state_file, topic, models, cfg.stale_resume_hours)
    if resumed_state is not None:
        existing_topic = _read_text(run_dir / "TOPIC_DISCOVER.txt")
        if existing_topic and existing_topic != topic.strip():
            raise DiscoverError(
                "Resume requested with a different topic than the in-progress discover run.")

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "TOPIC_DISCOVER.txt").write_text(topic.strip() + "\n", encoding="utf-8")

    client = LLMClient()
    raw_services = connect_services()  # hard-fails with startup hints
    mcp_call_counts: dict[str, int] = {}
    services = MCPServices(
        webresearch=_CountingMCP(raw_services.webresearch, mcp_call_counts, "webresearch"),
        scholartrace=_CountingMCP(raw_services.scholartrace, mcp_call_counts, "scholartrace"),
        scholaranalysis=_CountingMCP(raw_services.scholaranalysis, mcp_call_counts, "scholaranalysis"),
    )
    state = DiscoverState(topic=topic, models=models, config=cfg)
    if resumed_state is not None:
        saved_statuses = resumed_state.get("stage_statuses")
        if isinstance(saved_statuses, dict):
            state.stage_statuses = dict(saved_statuses)

    try:
        _run_stages(run_dir, state_file, client, services, state)
    finally:
        services.close_all()

    if cfg.stress_test:
        _run_stress_test(run_dir, state)

    usage = client.snapshot_usage() if hasattr(client, "snapshot_usage") else {}
    (run_dir / "COST_REPORT.md").write_text(
        _render_cost_report(usage, mcp_call_counts), encoding="utf-8")

    state.status = "completed"
    state.stop_reason = state.stop_reason if state.stop_reason != "running" else "completed"
    _save_state(state_file, state)
    _write_output_index(run_dir, state)
    report_file = run_dir / "DISCOVERY_REPORT.md"
    return report_file, state_file


def _run_stages(
    run_dir: Path,
    state_file: Path,
    client: LLMClient,
    services: MCPServices,
    state: DiscoverState,
) -> None:
    cfg = state.config
    topic = state.topic

    def done(stage: str) -> bool:
        return state.stage_statuses.get(stage) == "completed"

    def mark(stage: str) -> None:
        state.stage_statuses[stage] = "completed"
        # Persist after every stage so an interrupted run is resumable.
        _save_state(state_file, state)

    # --- Stage 1: theme framing (generator model) -----------------------
    if not done("theme-framing"):
        theme = _stage_theme_framing(client, state)
        (run_dir / "THEME.md").write_text(theme["human"] + "\n", encoding="utf-8")
        (run_dir / "theme.json").write_text(
            json.dumps(theme["yaml"], ensure_ascii=False, indent=2), encoding="utf-8")
        mark("theme-framing")

    theme: dict[str, Any] = json.loads(_read_text(run_dir / "theme.json"))

    # --- Stage 2: wide retrieval (scholartrace, server-side rerank) ------
    if not done("wide-retrieval"):
        papers = _stage_wide_retrieval(services, theme, cfg)
        (run_dir / "candidate_pool.json").write_text(
            json.dumps(papers, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "CANDIDATE_POOL.md").write_text(
            _render_candidate_pool(papers), encoding="utf-8")
        mark("wide-retrieval")

    pool: list[dict[str, Any]] = json.loads(_read_text(run_dir / "candidate_pool.json"))

    # --- Stage 3: deep read (scholaranalysis, server-side LLM) -----------
    if not done("deep-read"):
        notes = _stage_deep_read(services, run_dir, pool, cfg)
        (run_dir / "deep_read_notes.json").write_text(
            json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
        mark("deep-read")

    notes: list[dict[str, Any]] = json.loads(_read_text(run_dir / "deep_read_notes.json"))

    # --- Stage 4: gap mining (judge model) --------------------------------
    if not done("gap-mining"):
        gaps = _stage_gap_mining(client, state, notes)
        (run_dir / "gaps.json").write_text(
            json.dumps(gaps, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "GAP_ANALYSIS.md").write_text(
            _render_gaps(gaps, notes), encoding="utf-8")
        mark("gap-mining")

    gaps: list[dict[str, Any]] = json.loads(_read_text(run_dir / "gaps.json"))

    # --- Stage 5: saturation audit (webresearch + judge model) ------------
    if not done("saturation-audit"):
        audits = _stage_saturation_audit(client, services, state, gaps)
        (run_dir / "audits.json").write_text(
            json.dumps(audits, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "SATURATION_AUDIT.md").write_text(
            _render_audits(audits), encoding="utf-8")
        mark("saturation-audit")

    audits: list[dict[str, Any]] = json.loads(_read_text(run_dir / "audits.json"))
    survivors = [g for g in gaps
                 if _audit_verdict(audits, g.get("id", "")) == "KEEP"]

    if not survivors:
        # A fully-killed (or zero-mined) pool is a valid and useful outcome:
        # the report must still explain what was considered and why nothing
        # survived — an empty candidate set is first-class.
        state.stop_reason = "zero_gaps_mined" if not gaps else "no_surviving_gaps"
        (run_dir / "ideas.json").write_text("[]", encoding="utf-8")
        (run_dir / "IDEA_PORTFOLIO.md").write_text(
            "# IDEA_PORTFOLIO\n\nNo gaps survived to idea composition.\n", encoding="utf-8")
        (run_dir / "duplicate_checks.json").write_text("[]", encoding="utf-8")
        (run_dir / "DUPLICATE_CHECK.md").write_text(
            "# DUPLICATE_CHECK\n\nNo ideas to check.\n", encoding="utf-8")
        (run_dir / "judgments.json").write_text("[]", encoding="utf-8")
        state.stage_statuses["idea-portfolio"] = "completed"
        state.stage_statuses["duplicate-check"] = "completed"
        state.stage_statuses["taste-gate"] = "completed"
        ideas: list[dict[str, Any]] = []
        judgments: list[dict[str, Any]] = []
        dedup_checks: list[dict[str, Any]] = []
        _write_rejection_log(run_dir, state, gaps, audits, ideas, judgments, dedup_checks)
        (run_dir / "DISCOVERY_REPORT.md").write_text(
            _render_report(state, theme, notes, gaps, audits, ideas, judgments, dedup_checks),
            encoding="utf-8")
        return

    # --- Stage 6: idea portfolio (generator model) ------------------------
    if not done("idea-portfolio"):
        ideas_out = _stage_idea_portfolio(client, state, survivors, notes)
        (run_dir / "ideas.json").write_text(
            json.dumps(ideas_out, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "IDEA_PORTFOLIO.md").write_text(
            _render_ideas(ideas_out), encoding="utf-8")
        mark("idea-portfolio")

    ideas: list[dict[str, Any]] = json.loads(_read_text(run_dir / "ideas.json"))

    if not ideas:
        # Surviving gaps but the composer produced nothing worth judging.
        state.stop_reason = "no_composable_ideas"
        (run_dir / "duplicate_checks.json").write_text("[]", encoding="utf-8")
        (run_dir / "DUPLICATE_CHECK.md").write_text(
            "# DUPLICATE_CHECK\n\nNo ideas to check.\n", encoding="utf-8")
        (run_dir / "judgments.json").write_text("[]", encoding="utf-8")
        state.stage_statuses["duplicate-check"] = "completed"
        state.stage_statuses["taste-gate"] = "completed"
        judgments: list[dict[str, Any]] = []
        dedup_checks = _as_list_of_dicts(_load_json(run_dir / "duplicate_checks.json"))
        _write_rejection_log(run_dir, state, gaps, audits, ideas, judgments, dedup_checks)
        (run_dir / "DISCOVERY_REPORT.md").write_text(
            _render_report(state, theme, notes, gaps, audits, ideas, judgments, dedup_checks),
            encoding="utf-8")
        return

    # --- Stage 7: duplicate check (targeted novelty forensics) -------------
    if not done("duplicate-check"):
        checks = _stage_duplicate_check(run_dir, client, services, state, ideas)
        (run_dir / "DUPLICATE_CHECK.md").write_text(
            _render_duplicate_checks(checks), encoding="utf-8")
        mark("duplicate-check")

    dedup_checks: list[dict[str, Any]] = json.loads(
        _read_text(run_dir / "duplicate_checks.json") or "[]")

    # --- Stage 8: taste gate (judge model) ---------------------------------
    if not done("taste-gate"):
        judgments = _stage_taste_gate(client, state, ideas, dedup_checks)
        (run_dir / "judgments.json").write_text(
            json.dumps(judgments, ensure_ascii=False, indent=2), encoding="utf-8")
        mark("taste-gate")

    judgments: list[dict[str, Any]] = json.loads(_read_text(run_dir / "judgments.json"))

    _write_rejection_log(run_dir, state, gaps, audits, ideas, judgments, dedup_checks)

    (run_dir / "DISCOVERY_REPORT.md").write_text(
        _render_report(state, theme, notes, gaps, audits, ideas, judgments, dedup_checks),
        encoding="utf-8")


# ---------------------------------------------------------------------------
# Stage implementations
# ---------------------------------------------------------------------------

_DEEP_READ_QUESTION = (
    "For this paper, extract four sections. Label author-stated content vs your "
    "own inference explicitly.\n"
    "(1) VERIFIED CLAIMS: what was actually demonstrated, under which conditions "
    "(data distribution, scale/compute budget, evaluation protocol), with which "
    "variables controlled — and which alternative explanations the evaluation "
    "does NOT rule out. Cite section/figure where possible.\n"
    "(2) AUTHOR-STATED LIMITATIONS: the limitations the authors themselves write "
    "(quote or paraphrase closely, with location).\n"
    "(3) OPENED QUESTIONS: the future work they call for, and — separately — "
    "questions their verified claims leave unanswered but they do not mention.\n"
    "(4) LOAD-BEARING ASSUMPTIONS: assumptions the method or conclusions rely on "
    "that newer evidence could invalidate."
)


def _stage_theme_framing(client: LLMClient, state: DiscoverState) -> dict[str, Any]:
    cfg = state.config
    system = _load_prompt("theme_framer", cfg.prompt_language)
    user = (
        f"User topic (may be rough):\n{state.topic}\n\n"
        "Produce the structured search mandate described in your instructions."
    )
    text = client.chat(state.models["generator"], system, user, temperature=0.3)
    payload = _parse_yaml_block(text)
    theme = payload.get("theme") if isinstance(payload, dict) else None
    if not isinstance(theme, dict) or not theme.get("field"):
        # One retry with a corrective nudge before failing the stage.
        text = client.chat(
            state.models["generator"], system,
            user + "\n\nYour previous output was missing the machine-readable YAML block. "
                   "Output the full analysis again and end with the exact ```yaml theme:``` block.",
            temperature=0.3,
        )
        payload = _parse_yaml_block(text)
        theme = payload.get("theme") if isinstance(payload, dict) else None
    if not isinstance(theme, dict) or not theme.get("field"):
        raise DiscoverError("theme-framing failed: no parseable 'theme:' YAML block")
    theme.setdefault("subtopics", [])
    theme.setdefault("must_include", [])
    theme.setdefault("exclude", [])
    theme.setdefault("search_queries", [])
    return {"human": text.strip(), "yaml": theme}


def _build_theme_document(theme: dict[str, Any]) -> str:
    parts = [f"Field: {theme.get('field', '')}"]
    if theme.get("subtopics"):
        parts.append("Subtopics: " + "; ".join(str(s) for s in theme["subtopics"]))
    if theme.get("must_include"):
        parts.append("Must include: " + "; ".join(str(s) for s in theme["must_include"]))
    if theme.get("exclude"):
        parts.append("Exclude: " + "; ".join(str(s) for s in theme["exclude"]))
    return "\n".join(parts)


def _stage_wide_retrieval(
    services: MCPServices, theme: dict[str, Any], cfg: DiscoverConfig,
) -> list[dict[str, Any]]:
    theme_document = _build_theme_document(theme)
    final_limit = cfg.papers
    raw = services.scholartrace.call_tool("query", {
        "theme_document": theme_document,
        "final_limit": final_limit,
        "agent_candidate_limit": max(20, final_limit),
        "coarse_pool_limit": max(60, final_limit * 2),
        "include_rationale": True,
    }, timeout=cfg.mcp_call_timeout)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DiscoverError(f"scholartrace.query returned unparseable JSON: {exc}") from exc
    papers = data.get("papers", []) if isinstance(data, dict) else []
    if len(papers) < 5:
        raise DiscoverError(
            f"scholartrace.query returned only {len(papers)} papers; broaden the topic")
    slim: list[dict[str, Any]] = []
    for p in papers:
        slim.append({
            "paper_id": p.get("paper_id", ""),
            "title": p.get("title", ""),
            "year": p.get("year"),
            "venue": p.get("venue", ""),
            "abstract": p.get("abstract", ""),
            "composite_score": p.get("composite_score"),
            "agent_rank": p.get("agent_rank"),
            "rationale": p.get("rationale", ""),
        })
    return slim


def _stage_deep_read(
    services: MCPServices,
    run_dir: Path,
    pool: list[dict[str, Any]],
    cfg: DiscoverConfig,
) -> list[dict[str, Any]]:
    deep_dir = run_dir / "DEEP_READ"
    deep_dir.mkdir(parents=True, exist_ok=True)

    ranked = sorted(
        pool,
        key=lambda p: (
            # Papers the agent reranked come first; then by rank, then score.
            p.get("agent_rank") is None,
            p.get("agent_rank") if p.get("agent_rank") is not None else 10**6,
            -(p.get("composite_score") or 0.0),
        ),
    )

    notes: list[dict[str, Any]] = []
    tried = 0
    arxiv_id_map = _load_json(run_dir / "deep_read_ids.json") or {}
    for paper in ranked:
        if len(notes) >= cfg.deep_read or tried >= cfg.deep_read * 3:
            break
        paper_id = paper.get("paper_id", "")
        title = paper.get("title", "")
        if not paper_id or not title:
            continue

        tried += 1
        arxiv_id = arxiv_id_map.get(paper_id) or _resolve_arxiv_id(services, paper_id, cfg)
        if not arxiv_id:
            logger.info("deep-read skip (no arxiv id): %s", title[:80])
            continue
        arxiv_id_map[paper_id] = arxiv_id
        _save_json(run_dir / "deep_read_ids.json", arxiv_id_map)

        # A note already on disk (previous interrupted run) is restored, not
        # re-purchased: deep-read is the most expensive stage per paper.
        cached = _load_cached_note(deep_dir, arxiv_id)
        if cached is not None:
            notes.append(cached)
            continue

        try:
            raw = services.scholaranalysis.call_tool("analyze_paper", {
                "query": arxiv_id,
                "question": _DEEP_READ_QUESTION,
                "language": "en",
            }, timeout=cfg.mcp_call_timeout)
            data = json.loads(raw)
        except (MCPError, json.JSONDecodeError) as exc:
            logger.warning("deep-read failed for %s: %s", arxiv_id, exc)
            continue

        if data.get("status") != "success":
            logger.warning("deep-read status=%s for %s", data.get("status"), arxiv_id)
            continue
        answer = str((data.get("analysis") or {}).get("answer", "")).strip()
        if not answer:
            logger.warning("deep-read empty answer for %s", arxiv_id)
            continue

        note = {
            "arxiv_id": arxiv_id,
            "paper_id": paper_id,
            "title": title,
            "year": paper.get("year"),
            "venue": paper.get("venue", ""),
            "analysis": answer,
        }
        notes.append(note)
        slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:40]
        stem = f"{arxiv_id.replace('/', '_')}_{slug}"
        (deep_dir / f"{stem}.md").write_text(
            f"# {title}\n\n- arxiv: {arxiv_id}\n- venue: {paper.get('venue', '')}\n\n"
            f"## Extraction\n\n{answer}\n",
            encoding="utf-8",
        )
        _save_json(deep_dir / f"{stem}.json", note)

    if len(notes) < cfg.min_deep_read_ok:
        raise DiscoverError(
            f"deep-read produced only {len(notes)} usable notes "
            f"(need >= {cfg.min_deep_read_ok}); check scholaranalysis health")
    return notes


def _resolve_arxiv_id(services: MCPServices, paper_id: str, cfg: DiscoverConfig) -> str:
    try:
        raw = services.scholartrace.call_tool(
            "read", {"paper_id": paper_id, "depth": "summary"},
            timeout=min(120.0, cfg.mcp_call_timeout))
        data = json.loads(raw)
    except (MCPError, json.JSONDecodeError):
        return ""
    arxiv_id = data.get("arxiv_id")
    if isinstance(arxiv_id, str) and arxiv_id.strip():
        return arxiv_id.strip()
    # Last resort: some records only carry an S2/OpenAlex id — unusable for
    # scholaranalysis (arXiv-only), so give up cleanly.
    return ""


def _load_cached_note(deep_dir: Path, arxiv_id: str) -> dict[str, Any] | None:
    """Restore a per-paper deep-read note written by a previous (interrupted) run."""
    stem_prefix = arxiv_id.replace("/", "_")
    sidecar = deep_dir / f"{stem_prefix}.json"
    if sidecar.exists():
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            if isinstance(data, dict) and str(data.get("analysis", "")).strip():
                return data
        except Exception:
            pass
    # Legacy layout: only the .md existed; recover the extraction section.
    for md in sorted(deep_dir.glob(f"{stem_prefix}*.md")):
        try:
            text = md.read_text(encoding="utf-8")
        except Exception:
            continue
        marker = "## Extraction"
        if marker not in text:
            continue
        answer = text.split(marker, 1)[1].strip()
        if not answer:
            continue
        return {"arxiv_id": arxiv_id, "paper_id": "", "title": "",
                "year": None, "venue": "", "analysis": answer}
    return None


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _stage_gap_mining(
    client: LLMClient, state: DiscoverState, notes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cfg = state.config
    system = _load_prompt("gap_miner", cfg.prompt_language)
    digest = "\n\n".join(
        f"[{n['arxiv_id']}] {n['title']} ({n.get('venue', '')}, {n.get('year', '')})\n"
        f"{_clip(n['analysis'], _NOTE_MAX_CHARS)}"
        for n in notes
    )
    user = (
        f"Deep-read notes for {len(notes)} papers in the field:\n\n{digest}\n\n"
        "Mine the research gaps described in your instructions. Cite [arxiv ids]."
    )
    text = _structured_call(client, state.models["judge"], system, user, temperature=0.25, key="gaps")
    gaps = _as_list_of_dicts(text.get("gaps"))
    # Zero gaps is a valid outcome ("nothing worth investigating in this pool");
    # the runner renders it as a first-class empty report.
    for i, gap in enumerate(gaps, 1):
        gap.setdefault("id", f"G{i}")
    return gaps


def _stage_saturation_audit(
    client: LLMClient,
    services: MCPServices,
    state: DiscoverState,
    gaps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Audit each gap. Audit states are tri-state plus unaudited:

    KEEP                  audited, enough evidence to keep investigating
    KILL                  audited, explicit disqualifying evidence
    INSUFFICIENT_EVIDENCE audit could not be completed (web research down,
                          model output unparseable, unknown verdict) —
                          never silently treated as KEEP or KILL
    NOT_AUDITED           beyond the audit budget cap

    No evidence never means automatic passage: every gap ends up with
    exactly one audit record, and only audited KEEP enters the survivor set.
    """
    cfg = state.config
    system = _load_prompt("saturation_auditor", cfg.prompt_language)
    audits: list[dict[str, Any]] = []
    for gap in gaps[:_MAX_GAPS_TO_AUDIT]:
        gap_id = str(gap.get("id", ""))
        question = str(gap.get("question", "")) or str(gap.get("statement", ""))
        query = f"{question} benchmark evidence limitations open problem"
        try:
            raw = services.webresearch.call_tool("web_search", {
                "query": query,
                "max_results": cfg.webresearch_max_results,
            }, timeout=120.0)
            dossier = _digest_web_results(raw, cfg.webresearch_max_results)
        except MCPError as exc:
            logger.warning("webresearch failed for %s: %s", gap_id, exc)
            audits.append({
                "gap_id": gap_id, "verdict": "INSUFFICIENT_EVIDENCE",
                "reason": f"webresearch unavailable: {exc}"})
            continue

        user = (
            f"Candidate gap {gap_id}:\n{json.dumps(gap, ensure_ascii=False, indent=1)}\n\n"
            f"Web-research dossier:\n{_clip(dossier, _DOSSIER_MAX_CHARS)}\n\n"
            "Audit this gap per your instructions."
        )
        try:
            payload = _structured_call(
                client, state.models["judge"], system, user, temperature=0.2, key="audits")
        except DiscoverError as exc:
            audits.append({
                "gap_id": gap_id, "verdict": "INSUFFICIENT_EVIDENCE",
                "reason": f"audit output unparseable: {exc}"})
            continue
        entries = _as_list_of_dicts(payload.get("audits"))
        if not entries:
            audits.append({
                "gap_id": gap_id, "verdict": "INSUFFICIENT_EVIDENCE",
                "reason": "audit returned no entries"})
            continue
        entry = entries[-1]
        # The audited gap id is known from the request; never trust the
        # model's echo (a mismatched id would silently leave the gap unaudited).
        entry["gap_id"] = gap_id
        verdict = str(entry.get("verdict", "")).strip().upper()
        if verdict not in {"KEEP", "KILL", "INSUFFICIENT_EVIDENCE"}:
            entry["reason"] = f"unknown verdict {verdict!r}; {entry.get('reason', '')}"
            verdict = "INSUFFICIENT_EVIDENCE"
        entry["verdict"] = verdict
        audits.append(entry)

    # Gaps beyond the audit budget get explicit NOT_AUDITED records so the
    # report shows exactly which candidates never passed an audit.
    audited_ids = {str(a.get("gap_id", "")) for a in audits}
    for gap in gaps[_MAX_GAPS_TO_AUDIT:]:
        gap_id = str(gap.get("id", ""))
        if gap_id not in audited_ids:
            audits.append({
                "gap_id": gap_id, "verdict": "NOT_AUDITED",
                "reason": f"beyond audit budget ({_MAX_GAPS_TO_AUDIT} audits per run)"})

    # Set completeness: one audit record per gap, no orphans.
    gap_ids = sorted(str(g.get("id", "")) for g in gaps)
    audit_ids = sorted(str(a.get("gap_id", "")) for a in audits)
    if gap_ids != audit_ids:
        raise DiscoverError(
            f"audit set incomplete: {len(gap_ids)} gaps but {len(audit_ids)} audit records")
    return audits


def _stage_idea_portfolio(
    client: LLMClient,
    state: DiscoverState,
    survivors: list[dict[str, Any]],
    notes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not survivors:
        raise DiscoverError(
            "saturation audit killed every gap; nothing to compose ideas from")
    cfg = state.config
    system = _load_prompt("idea_generator", cfg.prompt_language)
    evidence = "\n".join(
        f"[{n['arxiv_id']}] {n['title']}" for n in notes)
    user = (
        "Surviving gaps after the saturation audit:\n\n"
        + "\n\n".join(json.dumps(g, ensure_ascii=False, indent=1) for g in survivors)
        + f"\n\nPaper index for evidence citations:\n{evidence}\n\n"
        f"Compose up to {cfg.ideas} new research problem statements per your instructions."
    )
    payload = _structured_call(
        client, state.models["generator"], system, user, temperature=0.5, key="ideas")
    ideas = _as_list_of_dicts(payload.get("ideas"))
    # Empty portfolio is legal: the generator found nothing worth composing.
    for i, idea in enumerate(ideas[: cfg.ideas], 1):
        idea.setdefault("id", f"I{i}")
    return ideas[: cfg.ideas]


def _stage_duplicate_check(
    run_dir: Path,
    client: LLMClient,
    services: MCPServices,
    state: DiscoverState,
    ideas: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Targeted novelty forensics per candidate (review 二.2).

    After a candidate exists, actively search for the prior work most likely
    to destroy its novelty — synonymous phrasings and mechanism terms via
    webresearch, substance-level matches via a small scholartrace query — and
    produce closest_works + differentiation for the taste gate.
    """
    cfg = state.config
    system = _load_prompt("duplicate_checker", cfg.prompt_language)
    checks_file = run_dir / "duplicate_checks.json"
    checks: list[dict[str, Any]] = _as_list_of_dicts(_load_json(checks_file))
    checked_ids = {str(c.get("idea_id")) for c in checks}

    for idea in ideas:
        idea_id = str(idea.get("id", ""))
        if not idea_id or idea_id in checked_ids:
            continue
        problem = str(idea.get("one_sentence_problem", ""))
        mechanism = str(idea.get("minimal_falsifiable_test", ""))[:160]

        web_parts: list[str] = []
        queries = [problem, f"{problem} mechanism {mechanism}"][: max(1, cfg.dedup_web_queries)]
        for q in queries:
            try:
                raw = services.webresearch.call_tool(
                    "web_search", {"query": q, "max_results": 5}, timeout=120.0)
                web_parts.append(_digest_web_results(raw, 5))
            except MCPError as exc:
                web_parts.append(f"(web search unavailable: {exc})")

        hits_text = "(scholartrace dedup disabled)"
        if cfg.dedup_scholartrace_enabled:
            try:
                raw = services.scholartrace.call_tool("query", {
                    "theme_document": f"Novelty check for candidate: {problem}",
                    "final_limit": cfg.dedup_scholartrace_limit,
                    "agent_candidate_limit": 10,
                    "coarse_pool_limit": 20,
                    "include_rationale": False,
                }, timeout=cfg.mcp_call_timeout)
                hits = _as_list_of_dicts(json.loads(raw).get("papers", []))
                hits_text = "\n".join(
                    f"- {h.get('title', '')} ({h.get('year', '')}): "
                    f"{_clip(str(h.get('abstract', '')), 240)}"
                    for h in hits
                ) or "(no hits)"
            except (MCPError, json.JSONDecodeError) as exc:
                hits_text = f"(scholartrace unavailable: {exc})"

        user = (
            f"Duplicate-check candidate {idea_id}:\n"
            f"{json.dumps(idea, ensure_ascii=False, indent=1)}\n\n"
            f"Web dossier:\n{_clip(chr(10).join(web_parts), _DOSSIER_MAX_CHARS)}\n\n"
            f"Paper-search hits:\n{_clip(hits_text, _DOSSIER_MAX_CHARS)}\n\n"
            "Check this candidate per your instructions."
        )
        try:
            payload = _structured_call(
                client, state.models["judge"], system, user, temperature=0.2, key="checks")
        except DiscoverError as exc:
            checks.append({"idea_id": idea_id, "novelty_verdict": "POSSIBLY_DUPLICATE",
                           "reason": f"duplicate-check unparseable: {exc}",
                           "closest_works": [], "differentiation": "", "unchecked": ""})
            _save_json(checks_file, checks)
            continue
        entries = _as_list_of_dicts(payload.get("checks"))
        entry = entries[-1] if entries else {}
        entry["idea_id"] = idea_id
        verdict = str(entry.get("novelty_verdict", "")).strip().upper()
        if verdict not in {"DISTINCT", "POSSIBLY_DUPLICATE", "DUPLICATE"}:
            entry["reason"] = f"unknown verdict {verdict!r}; {entry.get('reason', '')}"
            verdict = "POSSIBLY_DUPLICATE"
        entry["novelty_verdict"] = verdict
        checks.append(entry)
        checked_ids.add(idea_id)
        _save_json(checks_file, checks)  # incremental: interrupted reruns skip done ids

    return checks


def _dedup_digest(dedup_checks: list[dict[str, Any]]) -> str:
    if not dedup_checks:
        return "(no duplicate-check material)"
    parts: list[str] = []
    for c in dedup_checks:
        works = "; ".join(str(w) for w in (c.get("closest_works") or [])[:3])
        parts.append(
            f"[{c.get('idea_id')}] novelty={c.get('novelty_verdict', '?')} | "
            f"closest: {works or 'none listed'} | "
            f"delta: {_clip(str(c.get('differentiation', '')), 400)} | "
            f"unchecked: {_clip(str(c.get('unchecked', '')), 200)}")
    return "\n".join(parts)


def _render_duplicate_checks(checks: list[dict[str, Any]]) -> str:
    lines = ["# DUPLICATE_CHECK", "", f"candidates checked: {len(checks)}", ""]
    for c in checks:
        lines.append(f"## {c.get('idea_id', '?')} — {c.get('novelty_verdict', '?')}")
        lines.append("")
        for w in c.get("closest_works") or []:
            lines.append(f"- closest: {w}")
        lines.append(f"differentiation: {c.get('differentiation', '')}")
        lines.append(f"unchecked: {c.get('unchecked', '')}")
        lines.append(f"reason: {c.get('reason', '')}")
        lines.append("")
    return "\n".join(lines) + "\n"


def _stage_taste_gate(
    client: LLMClient,
    state: DiscoverState,
    ideas: list[dict[str, Any]],
    dedup_checks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if not ideas:
        return []
    cfg = state.config
    system = _load_prompt("taste_judge", cfg.prompt_language)
    user = (
        "Candidate research problems:\n\n"
        + "\n\n".join(json.dumps(i, ensure_ascii=False, indent=1) for i in ideas)
        + "\n\nDuplicate-check material (novelty forensics per candidate):\n"
        + _dedup_digest(dedup_checks or [])
        + "\n\nJudge each per your instructions; order best first."
    )
    payload = _structured_call(
        client, state.models["judge"], system, user, temperature=0.15, key="judgments")
    judgments = _as_list_of_dicts(payload.get("judgments"))
    dedup_by_id = {str(c.get("idea_id")): c for c in (dedup_checks or [])}
    # Hard rules in code, evidence-bound (review 二.3):
    # 1. A KILL is valid only with one of the three evidence types; otherwise
    #    it is downgraded to PIVOT — an uncalibrated taste score must never
    #    perform irreversible actions.
    # 2. A duplicate-check verdict of DUPLICATE is explicit checkable
    #    evidence: force KILL even if the judge tried to KEEP.
    _valid_kill_types = {"duplicate", "logical_contradiction", "resource_infeasible"}
    for j in judgments:
        verdict = str(j.get("verdict", "KEEP")).upper()
        if verdict not in {"KEEP", "PIVOT", "KILL"}:
            j["verdict"] = "PIVOT"
            j["reason"] = f"unknown verdict; {j.get('reason', '')}"
            verdict = "PIVOT"
        if verdict == "KILL" and str(j.get("kill_evidence_type", "")).strip().lower() not in _valid_kill_types:
            j["verdict"] = "PIVOT"
            j["reason"] = "[hard rule] KILL without valid kill_evidence_type downgraded to PIVOT; " + str(j.get("reason", ""))
            verdict = "PIVOT"
        if verdict in {"KEEP", "PIVOT"}:
            dedup = dedup_by_id.get(str(j.get("id")))
            if dedup and str(dedup.get("novelty_verdict", "")).upper() == "DUPLICATE":
                j["verdict"] = "KILL"
                j["kill_evidence_type"] = "duplicate"
                j["reason"] = (f"[hard rule] duplicate-check found prior work covering this "
                               f"question ({_clip(str(dedup.get('duplicate_of', 'see DUPLICATE_CHECK.md')), 120)})")
    return judgments


def _run_stress_test(run_dir: Path, state: DiscoverState) -> None:
    from arc.runners.chat_mode_runner import run_chat_mode

    cfg = state.config
    judgments = json.loads(_read_text(run_dir / "judgments.json"))
    ideas = {i.get("id"): i for i in json.loads(_read_text(run_dir / "ideas.json"))}
    keeps = [j for j in judgments if str(j.get("verdict", "")).upper() == "KEEP"][: cfg.stress_top_k]
    dedup_by_id = {str(c.get("idea_id")): c for c in
                   _as_list_of_dicts(_load_json(run_dir / "duplicate_checks.json"))}

    def _idea_brief(idea: dict[str, Any], judgment: dict[str, Any]) -> str:
        """Full candidate brief, not a bare sentence: the stress test must start
        from the accumulated evidence and boundaries, and it must NOT re-run a
        literature pipeline from scratch around a one-liner (review 一.5)."""
        dedup = dedup_by_id.get(str(idea.get("id", "")), {})
        parts = [
            f"Research problem to stress-test: {idea.get('one_sentence_problem', '')}",
            f"Gap evidence: {idea.get('gap_evidence', '')}",
            f"Who needs it: {idea.get('who_needs_it', '')}",
            f"Why now: {idea.get('why_now', '')}",
            f"Minimal falsifiable test (proposed): {idea.get('minimal_falsifiable_test', '')}",
            f"Anti-scope (what this is NOT): {idea.get('anti_scope', '')}",
            f"Taste-gate verdict: {judgment.get('verdict', '')} — {judgment.get('reason', '')}",
            f"Knowledge gain claimed: {judgment.get('knowledge_gain', '')}",
        ]
        if dedup:
            parts.append(
                f"Closest prior work: {'; '.join(str(w) for w in (dedup.get('closest_works') or [])[:3])}")
            parts.append(f"Novelty differentiation: {dedup.get('differentiation', '')}")
        return "\n".join(p for p in parts if str(p).strip())

    manifest: list[dict[str, str]] = []
    for j in keeps:
        idea = ideas.get(j.get("id"))
        if not idea:
            continue
        brief = _idea_brief(idea, j)
        if not brief:
            continue
        slug = re.sub(r"[^a-z0-9]+", "_", str(idea.get("one_sentence_problem", "")).lower()).strip("_")[:30] or "idea"
        stress_dir = run_dir / "stress_tests"
        stress_dir.mkdir(parents=True, exist_ok=True)
        target = stress_dir / slug
        target.mkdir(parents=True, exist_ok=True)
        try:
            run_chat_mode(
                topic=brief,
                proposer_model=state.models["generator"],
                # Cross-model adversarial setup (review 一.5): the skeptic is
                # deliberately the judge model — a different model family from
                # the generator whenever the role split is configured.
                skeptic_model=state.models["judge"],
                moderator_model=state.models["judge"],
                output_dir=str(run_dir),
                resume=False,
                min_rounds_before_stop=2,
                max_rounds=cfg.stress_rounds,
                export_best_consensus=True,
                prompt_language=cfg.prompt_language,
                max_review_cycles=1,
                max_inner_debate_rounds=cfg.stress_rounds,
                run_dir=str(target),
            )
            manifest.append({"idea_id": str(j.get("id")),
                             "problem": idea.get("one_sentence_problem", ""),
                             "run_dir": str(target)})
        except Exception as exc:  # stress test is best-effort
            logger.warning("stress test failed for %s: %s", j.get("id"), exc)
            manifest.append({"idea_id": str(j.get("id")),
                             "problem": idea.get("one_sentence_problem", ""),
                             "error": str(exc)})
    (run_dir / "STRESS_TESTS.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _load_config(config_path: str | Path = "configs/discover.yaml") -> DiscoverConfig:
    cfg = DiscoverConfig()
    p = Path(config_path)
    if not p.exists():
        return cfg
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        raw = data.get("discover", {}) if isinstance(data, dict) else {}
        if isinstance(raw, dict):
            for key in ("papers", "deep_read", "ideas", "webresearch_max_results",
                        "dedup_web_queries", "dedup_scholartrace_limit",
                        "stress_rounds", "stress_top_k", "stale_resume_hours",
                        "min_deep_read_ok"):
                if key in raw:
                    setattr(cfg, key, int(raw[key]))
            if "stress_test" in raw:
                cfg.stress_test = bool(raw["stress_test"])
            if "dedup_scholartrace_enabled" in raw:
                cfg.dedup_scholartrace_enabled = bool(raw["dedup_scholartrace_enabled"])
            if "prompt_language" in raw:
                cfg.prompt_language = str(raw["prompt_language"])
            if "mcp_call_timeout" in raw:
                cfg.mcp_call_timeout = float(raw["mcp_call_timeout"])
    except Exception:
        return DiscoverConfig()
    return cfg


def _load_prompt(name: str, language: str) -> str:
    path = resolve_prompt_path("discover", name, language)
    return path.read_text(encoding="utf-8")


def _structured_call(
    client: LLMClient,
    model: str,
    system: str,
    user: str,
    *,
    temperature: float,
    key: str,
) -> dict[str, Any]:
    """Call the model and require a YAML block containing list-valued `key`.

    An explicit empty list (e.g. `gaps: []`) is a valid first-class answer —
    "checked, nothing found" — and must not trigger a retry or an error.
    """
    text = client.chat(model, system, user, temperature=temperature)
    payload = _parse_yaml_block(text)
    if _has_list_key(payload, key):
        return payload
    retry = client.chat(
        model, system,
        user + "\n\nYour previous output was missing or malformed in the "
               f"machine-readable YAML block. Repeat your full analysis and end with "
               f"the exact ```yaml block containing `{key}:` entries.",
        temperature=max(0.0, temperature - 0.1),
    )
    payload = _parse_yaml_block(retry)
    if _has_list_key(payload, key):
        return payload
    raise DiscoverError(f"structured output missing '{key}' after retry")


def _has_list_key(payload: Any, key: str) -> bool:
    return isinstance(payload, dict) and key in payload and isinstance(payload[key], list)


def _parse_yaml_block(text: str) -> dict[str, Any]:
    for fence in ("```yaml", "```yml", "```"):
        idx = text.rfind(fence)
        if idx == -1:
            continue
        after = text[idx + len(fence):]
        end = after.find("```")
        if end == -1:
            continue
        try:
            data = yaml.safe_load(after[:end].strip())
        except yaml.YAMLError:
            continue
        if isinstance(data, dict):
            return data
    return {}


def _as_list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, dict)]


def _audit_verdict(audits: list[dict[str, Any]], gap_id: str) -> str:
    for a in audits:
        if str(a.get("gap_id", "")) == gap_id:
            return str(a.get("verdict", "NOT_AUDITED")).upper()
    return "NOT_AUDITED"


def _digest_web_results(raw: str, max_results: int) -> str:
    try:
        data = json.loads(raw)
        results = data.get("results", []) if isinstance(data, dict) else []
    except json.JSONDecodeError:
        return _clip(raw, _DOSSIER_MAX_CHARS)
    lines: list[str] = []
    for r in results[:max_results]:
        if not isinstance(r, dict):
            continue
        lines.append(
            f"- {r.get('title', '')} | {r.get('url', '')} | snippet: "
            f"{_clip(str(r.get('snippet', '')), 400)}")
    return "\n".join(lines) if lines else "(no results)"


def _clip(text: str, max_chars: int) -> str:
    text = text or ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[clipped]"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def _save_state(state_file: Path, state: DiscoverState) -> None:
    state.timestamp = datetime.now(UTC).isoformat()
    state_file.write_text(
        json.dumps({
            "topic": state.topic,
            "models": state.models,
            "config": {
                "papers": state.config.papers,
                "deep_read": state.config.deep_read,
                "ideas": state.config.ideas,
                "stress_test": state.config.stress_test,
                "stress_rounds": state.config.stress_rounds,
                "prompt_language": state.config.prompt_language,
            },
            "stage_statuses": state.stage_statuses,
            "status": state.status,
            "stop_reason": state.stop_reason,
            "timestamp": state.timestamp,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_resume_state(
    state_file: Path, topic: str, models: dict[str, str], stale_hours: int,
) -> dict[str, Any] | None:
    """Return the persisted state dict if it is a resumable in-progress run."""
    if not state_file.exists():
        return None
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if data.get("status") != "in_progress":
        return None
    if str(data.get("topic", "")).strip() != topic.strip():
        return None
    if data.get("models") != models:
        return None
    ts = str(data.get("timestamp", ""))
    try:
        updated = datetime.fromisoformat(ts)
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=UTC)
        if (datetime.now(UTC) - updated).total_seconds() / 3600 > stale_hours:
            return None
    except ValueError:
        return None
    return data


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def _render_candidate_pool(papers: list[dict[str, Any]]) -> str:
    lines = ["# CANDIDATE_POOL", "",
             f"papers: {len(papers)} (scholartrace rerank)", "",
             "| # | id | year | venue | score | title |", "|---|---|---|---|---|---|"]
    for i, p in enumerate(papers, 1):
        lines.append(
            f"| {i} | {_clip(p.get('paper_id', ''), 20)} | {p.get('year', '')} | "
            f"{_clip(p.get('venue', ''), 24)} | {p.get('composite_score', 0):.3f} | "
            f"{_clip(p.get('title', ''), 90)} |")
    lines += ["", "## Abstracts", ""]
    for i, p in enumerate(papers, 1):
        lines.append(f"### [{i}] {p.get('title', '')}")
        lines.append(str(p.get("rationale", "")).strip() or "")
        lines.append(_clip(p.get("abstract", ""), 1200))
        lines.append("")
    return "\n".join(lines) + "\n"


def _render_gaps(gaps: list[dict[str, Any]], notes: list[dict[str, Any]]) -> str:
    titles = {n["arxiv_id"]: n["title"] for n in notes}
    lines = ["# GAP_ANALYSIS", "", f"gaps: {len(gaps)}", ""]
    for g in gaps:
        lines.append(f"## {g.get('id', '?')} — {g.get('type', '')}")
        lines.append("")
        lines.append(f"**Question:** {g.get('question', '')}")
        lines.append("")
        for eid in g.get("evidence_ids", []) or []:
            lines.append(f"- [{eid}] {titles.get(str(eid), '')}")
        lines.append("")
        lines.append(f"why unexplored: {g.get('why_unexplored', '')}")
        lines.append(f"who needs it: {g.get('who_needs_it', '')}")
        lines.append(f"confidence: {g.get('confidence', '')}")
        lines.append("")
    return "\n".join(lines) + "\n"


def _render_audits(audits: list[dict[str, Any]]) -> str:
    lines = ["# SATURATION_AUDIT", ""]
    for a in audits:
        lines.append(f"## {a.get('gap_id', '?')} — {a.get('verdict', '?')}")
        lines.append("")
        lines.append(f"pain_saturation: {a.get('pain_saturation', '')} | "
                     f"community_pain: {a.get('community_pain', '')} | "
                     f"incremental_risk: {a.get('incremental_risk', '')}")
        lines.append(f"evidence: {a.get('evidence', '')}")
        lines.append(f"reason: {a.get('reason', '')}")
        lines.append("")
    return "\n".join(lines) + "\n"


def _render_ideas(ideas: list[dict[str, Any]]) -> str:
    lines = ["# IDEA_PORTFOLIO", "", f"ideas: {len(ideas)}", ""]
    for idea in ideas:
        lines.append(f"## {idea.get('id', '?')} — {idea.get('one_sentence_problem', '')}")
        lines.append("")
        lines.append(f"- from gaps: {idea.get('from_gaps', [])}")
        lines.append(f"- evidence: {idea.get('gap_evidence', '')}")
        lines.append(f"- who needs it: {idea.get('who_needs_it', '')}")
        lines.append(f"- why now: {idea.get('why_now', '')}")
        lines.append(f"- minimal falsifiable test: {idea.get('minimal_falsifiable_test', '')}")
        lines.append(f"- anti-scope: {idea.get('anti_scope', '')}")
        lines.append("")
    return "\n".join(lines) + "\n"


def _write_rejection_log(
    run_dir: Path,
    state: DiscoverState,
    gaps: list[dict[str, Any]],
    audits: list[dict[str, Any]],
    ideas: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    dedup_checks: list[dict[str, Any]],
) -> None:
    rejection_log = _build_rejection_log(state, gaps, audits, ideas, judgments, dedup_checks)
    (run_dir / "rejection_log.json").write_text(
        json.dumps(rejection_log, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "REJECTION_LOG.md").write_text(
        _render_rejection_log(rejection_log), encoding="utf-8")


def _build_rejection_log(
    state: DiscoverState,
    gaps: list[dict[str, Any]],
    audits: list[dict[str, Any]],
    ideas: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    dedup_checks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Conditional rejection records: object, applicable conditions, evidence,
    and what would reopen the decision (review 三.5)."""
    cfg = state.config
    run_conditions = (
        f"pool={cfg.papers} papers, deep-read={cfg.deep_read}, "
        f"audit budget={_MAX_GAPS_TO_AUDIT}, models={state.models}")
    ideas_by_id = {str(i.get("id")): i for i in ideas}
    dedup_by_id = {str(c.get("idea_id")): c for c in dedup_checks}

    entries: list[dict[str, Any]] = []
    audits_by_gap = {str(a.get("gap_id")): a for a in audits}
    for gap in gaps:
        audit = audits_by_gap.get(str(gap.get("id", "")), {})
        verdict = str(audit.get("verdict", "NOT_AUDITED")).upper()
        if verdict not in {"KILL", "INSUFFICIENT_EVIDENCE", "NOT_AUDITED"}:
            continue
        if verdict == "INSUFFICIENT_EVIDENCE":
            reopen = "re-run the audit with webresearch reachable and the missing evidence collected"
        elif verdict == "NOT_AUDITED":
            reopen = f"raise the audit budget above {_MAX_GAPS_TO_AUDIT} gaps per run"
        else:
            reopen = "new evidence that the disqualifying basis no longer holds"
        entries.append({
            "object_type": "gap",
            "object_id": str(gap.get("id", "")),
            "object": _clip(str(gap.get("question", "")), 200),
            "conditions": run_conditions,
            "verdict": verdict,
            "evidence": _clip(str(audit.get("reason", "")), 300),
            "reopen_condition": reopen,
        })

    judgments_by_id = {str(j.get("id")): j for j in judgments}
    for j in judgments:
        if str(j.get("verdict", "")).upper() != "KILL":
            continue
        kill_type = str(j.get("kill_evidence_type", "")).strip().lower()
        if kill_type == "duplicate":
            dedup = dedup_by_id.get(str(j.get("id")), {})
            reopen = (f"evidence that the cited prior work "
                      f"({_clip(str(dedup.get('duplicate_of', 'see DUPLICATE_CHECK.md')), 120)}) "
                      f"does not cover the candidate's conditions")
        elif kill_type == "resource_infeasible":
            reopen = "obtain the missing access/resource stated in the reason"
        elif kill_type == "logical_contradiction":
            reopen = "revised statement that removes the internal contradiction"
        else:
            reopen = "none recorded (judge KILL without evidence type was downgraded)"
        idea = ideas_by_id.get(str(j.get("id")), {})
        entries.append({
            "object_type": "idea",
            "object_id": str(j.get("id", "")),
            "object": _clip(str(idea.get("one_sentence_problem", "")), 200),
            "conditions": run_conditions,
            "verdict": "KILL",
            "kill_evidence_type": kill_type,
            "evidence": _clip(str(j.get("reason", "")), 300),
            "reopen_condition": reopen,
        })
    return entries


def _render_rejection_log(entries: list[dict[str, Any]]) -> str:
    lines = ["# REJECTION_LOG", "",
             "Conditional rejections: each entry names its object, the conditions",
             "under which it was rejected, the evidence, and what would reopen it.",
             "These are not permanent bans on a direction.", "",
             f"entries: {len(entries)}", ""]
    for e in entries:
        lines.append(f"## [{e['object_type']}] {e['object_id']} — {e['verdict']}")
        lines.append("")
        lines.append(f"- object: {e['object']}")
        lines.append(f"- conditions: {e['conditions']}")
        lines.append(f"- evidence: {e['evidence']}")
        lines.append(f"- reopen when: {e['reopen_condition']}")
        lines.append("")
    return "\n".join(lines) + "\n"


def _render_report(
    state: DiscoverState,
    theme: dict[str, Any],
    notes: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    audits: list[dict[str, Any]],
    ideas: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    dedup_checks: list[dict[str, Any]] | None = None,
) -> str:
    dedup_checks = dedup_checks or []
    by_id = {i.get("id"): i for i in ideas}
    keeps = [j for j in judgments if str(j.get("verdict", "")).upper() == "KEEP"]
    keeps.sort(key=lambda j: _taste_score(j), reverse=True)

    lines = [
        "# DISCOVERY_REPORT", "",
        f"topic: {state.topic}",
        f"field: {theme.get('field', '')}",
        f"generated_at: {datetime.now(UTC).isoformat()}",
        f"models: {state.models}",
        f"pool: {len(gaps)} gaps -> {len([a for a in audits if str(a.get('verdict')).upper() == 'KEEP'])} kept"
        f" -> {len(ideas)} ideas -> {len(keeps)} KEEP", "",
    ]

    if not ideas:
        lines += [
            "## No surviving problems", "",
            "The pipeline ended with an empty candidate set. This is a result,",
            "not a failure — what was considered and why nothing survived:", "",
            "| gap | type | verdict | question | reason |",
            "|---|---|---|---|---|",
        ]
        for g in gaps:
            audit = next(
                (a for a in audits if str(a.get("gap_id", "")) == str(g.get("id", ""))), {})
            lines.append(
                f"| {g.get('id', '?')} | {g.get('type', '')} | "
                f"**{str(audit.get('verdict', 'NOT_AUDITED')).upper()}** | "
                f"{_clip(str(g.get('question', '')), 110)} | "
                f"{_clip(str(audit.get('reason', 'no audit record')), 130)} |")
        lines += [
            "",
            "Suggestions: broaden the field (the theme may be too narrow),",
            "increase --deep-read for more mining surface, or pick a field where",
            "deployment reality has recently shifted.", "",
        ]

    dedup_by_id = {str(c.get("idea_id")): c for c in dedup_checks}

    if ideas:
        lines += [
            "## Verdicts", "",
            "| id | dedup | delta type | incr.risk | separates alt.? | priority | verdict | kill evidence | reason |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
    for j in judgments:
        dedup = dedup_by_id.get(str(j.get("id")), {})
        lines.append(
            f"| {j.get('id', '?')} | {dedup.get('novelty_verdict', '-')} | "
            f"{j.get('delta_type', '?')} | "
            f"{j.get('incremental_risk', '?')} | {j.get('distinguishes_alternatives', '?')} | "
            f"{j.get('priority', '-')} | "
            f"**{str(j.get('verdict', '?')).upper()}** | "
            f"{j.get('kill_evidence_type', '-')} | {_clip(str(j.get('reason', '')), 90)} |")

    lines += ["", f"## Kept problems (ranked, {len(keeps)})", ""]
    for rank, j in enumerate(keeps, 1):
        idea = by_id.get(j.get("id"), {})
        lines.append(f"### #{rank} — {idea.get('one_sentence_problem', '')}")
        lines.append("")
        lines.append(f"- **id**: {j.get('id')} | taste score: {_taste_score(j):.1f} | "
                     f"delta type: {j.get('delta_type', '?')}")
        lines.append(f"- **knowledge gain**: {j.get('knowledge_gain', '')}")
        lines.append(f"- **decision changed**: {j.get('decision_changed', '')}")
        dedup = dedup_by_id.get(str(j.get("id")), {})
        if dedup:
            lines.append(f"- **dedup verdict**: {dedup.get('novelty_verdict', '?')} | "
                         f"delta: {_clip(str(dedup.get('differentiation', '')), 300)}")
        lines.append(f"- **gap evidence**: {idea.get('gap_evidence', '')}")
        lines.append(f"- **who needs it**: {idea.get('who_needs_it', '')}")
        lines.append(f"- **why now**: {idea.get('why_now', '')}")
        lines.append(f"- **minimal falsifiable test**: {idea.get('minimal_falsifiable_test', '')}")
        lines.append(f"- **anti-scope**: {idea.get('anti_scope', '')}")
        lines.append(f"- **judge reason**: {j.get('reason', '')}")
        if str(j.get("verdict", "")).upper() == "PIVOT":
            lines.append(f"- **pivot to**: {j.get('pivot_to', '')}")
        lines.append("")

    lines += ["", "## Killed / pivoted", ""]
    for j in judgments:
        if str(j.get("verdict", "")).upper() in ("KILL", "PIVOT"):
            idea = by_id.get(j.get("id"), {})
            lines.append(
                f"- **{j.get('id')}** ({str(j.get('verdict')).upper()}): "
                f"{idea.get('one_sentence_problem', '')} — {j.get('reason', '')}")
    lines += [
        "", "## Evidence base", "",
        f"deep-read papers: {len(notes)}",
    ]
    for n in notes:
        lines.append(f"- [{n['arxiv_id']}] {n['title']} ({n.get('venue', '')}, {n.get('year', '')})")
    return "\n".join(lines) + "\n"


def _taste_score(j: dict[str, Any]) -> float:
    """Ranking score only (never a kill trigger): judge priority first,
    falling back to inverse incremental risk."""
    def _num(key: str, default: float) -> float:
        try:
            return float(j.get(key, default))
        except (TypeError, ValueError):
            return default
    if j.get("priority") is not None:
        return _num("priority", 3.0)
    return 6.0 - _num("incremental_risk", 3.0)


def _write_output_index(run_dir: Path, state: DiscoverState) -> None:
    entries = [
        ("TOPIC_DISCOVER.txt", "User topic input"),
        ("THEME.md / theme.json", "Structured search mandate"),
        ("CANDIDATE_POOL.md / candidate_pool.json", "scholartrace reranked paper pool"),
        ("DEEP_READ/", "Per-paper extraction notes (scholaranalysis)"),
        ("deep_read_notes.json", "Aggregated deep-read notes"),
        ("GAP_ANALYSIS.md / gaps.json", "Mined problem-level gaps"),
        ("SATURATION_AUDIT.md / audits.json", "Pain saturation audit per gap"),
        ("IDEA_PORTFOLIO.md / ideas.json", "New problem statements"),
        ("DUPLICATE_CHECK.md / duplicate_checks.json", "Targeted novelty forensics per candidate"),
        ("judgments.json", "Taste-gate verdicts"),
        ("REJECTION_LOG.md / rejection_log.json", "Conditional rejections with reopen conditions"),
        ("DISCOVERY_REPORT.md", "Final ranked report"),
        ("STRESS_TESTS.json", "Stress-test run manifest (optional)"),
        ("discover_state.json", "Pipeline state (resume support)"),
    ]
    lines = ["# OUTPUT_INDEX (discover)", "",
             f"- topic: {state.topic}",
             f"- stages: {state.stage_statuses}",
             f"- status: {state.status} ({state.stop_reason})", "",
             "| artifact | purpose |", "|---|---|"]
    for name, purpose in entries:
        lines.append(f"| {name} | {purpose} |")
    (run_dir / "OUTPUT_INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
