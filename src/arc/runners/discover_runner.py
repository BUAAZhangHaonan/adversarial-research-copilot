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
    services = connect_services()  # hard-fails with startup hints
    state = DiscoverState(topic=topic, models=models, config=cfg)
    if resumed_state is not None:
        saved_statuses = resumed_state.get("stage_statuses")
        if isinstance(saved_statuses, dict):
            state.stage_statuses = dict(saved_statuses)

    try:
        _run_stages(run_dir, client, services, state)
    finally:
        services.close_all()

    if cfg.stress_test:
        _run_stress_test(run_dir, state)

    state.status = "completed"
    state.stop_reason = state.stop_reason if state.stop_reason != "running" else "completed"
    _save_state(state_file, state)
    _write_output_index(run_dir, state)
    report_file = run_dir / "DISCOVERY_REPORT.md"
    return report_file, state_file


def _run_stages(
    run_dir: Path,
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
        state.timestamp = datetime.now(UTC).isoformat()

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
        # A fully-killed pool is a valid (and useful) outcome: the report must
        # still explain what was considered and why nothing survived.
        state.stop_reason = "all_gaps_killed"
        (run_dir / "ideas.json").write_text("[]", encoding="utf-8")
        (run_dir / "IDEA_PORTFOLIO.md").write_text(
            "# IDEA_PORTFOLIO\n\nNo gaps survived the saturation audit.\n", encoding="utf-8")
        (run_dir / "judgments.json").write_text("[]", encoding="utf-8")
        state.stage_statuses["idea-portfolio"] = "completed"
        state.stage_statuses["taste-gate"] = "completed"
        ideas: list[dict[str, Any]] = []
        judgments: list[dict[str, Any]] = []
        (run_dir / "DISCOVERY_REPORT.md").write_text(
            _render_report(state, theme, notes, gaps, audits, ideas, judgments),
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

    # --- Stage 7: taste gate (judge model) ---------------------------------
    if not done("taste-gate"):
        judgments = _stage_taste_gate(client, state, ideas)
        (run_dir / "judgments.json").write_text(
            json.dumps(judgments, ensure_ascii=False, indent=2), encoding="utf-8")
        mark("taste-gate")

    judgments: list[dict[str, Any]] = json.loads(_read_text(run_dir / "judgments.json"))
    (run_dir / "DISCOVERY_REPORT.md").write_text(
        _render_report(state, theme, notes, gaps, audits, ideas, judgments),
        encoding="utf-8")


# ---------------------------------------------------------------------------
# Stage implementations
# ---------------------------------------------------------------------------

_DEEP_READ_QUESTION = (
    "For this paper, extract: (1) core claim/contribution in 3 sentences; "
    "(2) the limitations the authors themselves state (quote or paraphrase closely); "
    "(3) the future work they call for; (4) the key assumptions their method or "
    "conclusions rely on. Be specific; include section references where possible."
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
            p.get("agent_rank") is not None,
            p.get("agent_rank") if p.get("agent_rank") is not None else 10**6,
            -(p.get("composite_score") or 0.0),
        ),
    )

    notes: list[dict[str, Any]] = []
    tried = 0
    for paper in ranked:
        if len(notes) >= cfg.deep_read or tried >= cfg.deep_read * 3:
            break
        paper_id = paper.get("paper_id", "")
        title = paper.get("title", "")
        if not paper_id or not title:
            continue

        tried += 1
        arxiv_id = _resolve_arxiv_id(services, paper_id, cfg)
        if not arxiv_id:
            logger.info("deep-read skip (no arxiv id): %s", title[:80])
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
        (deep_dir / f"{arxiv_id.replace('/', '_')}_{slug}.md").write_text(
            f"# {title}\n\n- arxiv: {arxiv_id}\n- venue: {paper.get('venue', '')}\n\n"
            f"## Extraction\n\n{answer}\n",
            encoding="utf-8",
        )

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
    if not gaps:
        raise DiscoverError("gap-mining produced no gaps")
    for i, gap in enumerate(gaps, 1):
        gap.setdefault("id", f"G{i}")
    return gaps


def _stage_saturation_audit(
    client: LLMClient,
    services: MCPServices,
    state: DiscoverState,
    gaps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cfg = state.config
    system = _load_prompt("saturation_auditor", cfg.prompt_language)
    audits: list[dict[str, Any]] = []
    for gap in gaps[:_MAX_GAPS_TO_AUDIT]:
        gap_id = str(gap.get("id", ""))
        question = str(gap.get("question", "")) or str(gap.get("statement", ""))
        query = f"{question} benchmark state of the art limitation pain point"
        try:
            raw = services.webresearch.call_tool("web_search", {
                "query": query,
                "max_results": cfg.webresearch_max_results,
            }, timeout=120.0)
            dossier = _digest_web_results(raw, cfg.webresearch_max_results)
        except MCPError as exc:
            logger.warning("webresearch failed for %s: %s", gap_id, exc)
            dossier = "(web research unavailable for this gap)"
        user = (
            f"Candidate gap {gap_id}:\n{json.dumps(gap, ensure_ascii=False, indent=1)}\n\n"
            f"Web-research dossier:\n{_clip(dossier, _DOSSIER_MAX_CHARS)}\n\n"
            "Audit this gap per your instructions."
        )
        payload = _structured_call(
            client, state.models["judge"], system, user, temperature=0.2, key="audits")
        entries = _as_list_of_dicts(payload.get("audits"))
        if entries:
            entry = entries[-1]
            # The audited gap id is known from the request; never trust the
            # model's echo (a mismatched id would silently leave the gap unaudited).
            entry["gap_id"] = gap_id
            audits.append(entry)
        else:
            audits.append({"gap_id": gap_id, "verdict": "KEEP",
                           "reason": "audit unparseable; conservative keep"})
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
    if not ideas:
        raise DiscoverError("idea-portfolio produced no ideas")
    for i, idea in enumerate(ideas[: cfg.ideas], 1):
        idea.setdefault("id", f"I{i}")
    return ideas[: cfg.ideas]


def _stage_taste_gate(
    client: LLMClient, state: DiscoverState, ideas: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cfg = state.config
    system = _load_prompt("taste_judge", cfg.prompt_language)
    user = (
        "Candidate research problems:\n\n"
        + "\n\n".join(json.dumps(i, ensure_ascii=False, indent=1) for i in ideas)
        + "\n\nJudge each per your instructions; order best first."
    )
    payload = _structured_call(
        client, state.models["judge"], system, user, temperature=0.15, key="judgments")
    judgments = _as_list_of_dicts(payload.get("judgments"))
    if not judgments:
        raise DiscoverError("taste-gate produced no judgments")
    # Enforce the hard rules in code, independent of LLM compliance.
    for j in judgments:
        try:
            novelty = int(j.get("problem_novelty", 3))
        except (TypeError, ValueError):
            novelty = 3
        j["problem_novelty"] = novelty
        if novelty <= 2 and str(j.get("verdict", "KEEP")).upper() == "KEEP":
            j["verdict"] = "KILL"
            j["reason"] = f"[hard rule] problem_novelty={novelty} <= 2; " + str(j.get("reason", ""))
        if str(j.get("arrow_before_target", "false")).strip().lower() == "true" \
                and str(j.get("verdict", "KEEP")).upper() == "KEEP":
            j["verdict"] = "KILL"
            j["reason"] = "[hard rule] arrow_before_target=true; " + str(j.get("reason", ""))
    return judgments


def _run_stress_test(run_dir: Path, state: DiscoverState) -> None:
    from arc.runners.chat_mode_runner import run_chat_mode

    cfg = state.config
    judgments = json.loads(_read_text(run_dir / "judgments.json"))
    ideas = {i.get("id"): i for i in json.loads(_read_text(run_dir / "ideas.json"))}
    keeps = [j for j in judgments if str(j.get("verdict", "")).upper() == "KEEP"][: cfg.stress_top_k]
    manifest: list[dict[str, str]] = []
    for j in keeps:
        idea = ideas.get(j.get("id"))
        if not idea:
            continue
        problem = str(idea.get("one_sentence_problem", "")).strip()
        if not problem:
            continue
        slug = re.sub(r"[^a-z0-9]+", "_", problem.lower()).strip("_")[:30] or "idea"
        stress_dir = run_dir / "stress_tests"
        stress_dir.mkdir(parents=True, exist_ok=True)
        target = stress_dir / slug
        target.mkdir(parents=True, exist_ok=True)
        try:
            run_chat_mode(
                topic=problem,
                proposer_model=state.models["generator"],
                skeptic_model=state.models["generator"],
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
            manifest.append({"idea_id": str(j.get("id")), "problem": problem,
                             "run_dir": str(target)})
        except Exception as exc:  # stress test is best-effort
            logger.warning("stress test failed for %s: %s", j.get("id"), exc)
            manifest.append({"idea_id": str(j.get("id")), "problem": problem,
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
                        "stress_rounds", "stress_top_k", "stale_resume_hours",
                        "min_deep_read_ok"):
                if key in raw:
                    setattr(cfg, key, int(raw[key]))
            if "stress_test" in raw:
                cfg.stress_test = bool(raw["stress_test"])
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
    """Call the model and require a YAML block containing `key`; retry once."""
    text = client.chat(model, system, user, temperature=temperature)
    payload = _parse_yaml_block(text)
    if isinstance(payload, dict) and payload.get(key):
        return payload
    retry = client.chat(
        model, system,
        user + "\n\nYour previous output was missing or malformed in the "
               f"machine-readable YAML block. Repeat your full analysis and end with "
               f"the exact ```yaml block containing `{key}:` entries.",
        temperature=max(0.0, temperature - 0.1),
    )
    payload = _parse_yaml_block(retry)
    if isinstance(payload, dict) and payload.get(key):
        return payload
    raise DiscoverError(f"structured output missing '{key}' after retry")


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
            return str(a.get("verdict", "KEEP")).upper()
    return "KEEP"


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


def _render_report(
    state: DiscoverState,
    theme: dict[str, Any],
    notes: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    audits: list[dict[str, Any]],
    ideas: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
) -> str:
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

    if not ideas and gaps:
        lines += [
            "## No surviving problems", "",
            "The saturation audit killed every mined gap. This is a result, not a",
            "failure: it says this pool offers no unsaturated, real-pain problem", "",
            "| gap | type | question | kill reason |",
            "|---|---|---|---|",
        ]
        for g in gaps:
            verdict = next(
                (a for a in audits if str(a.get("gap_id", "")) == str(g.get("id", ""))), {})
            lines.append(
                f"| {g.get('id', '?')} | {g.get('type', '')} | "
                f"{_clip(str(g.get('question', '')), 110)} | "
                f"{_clip(str(verdict.get('reason', 'no audit')), 130)} |")
        lines += [
            "",
            "Suggestions: broaden the field (the theme may be too narrow),",
            "increase --deep-read for more mining surface, or pick a field where",
            "deployment reality has recently shifted.", "",
        ]

    if ideas:
        lines += [
            "## Verdicts", "",
            "| id | novelty | incr.risk | arrow-first | so-what | decisive | verdict | reason |",
            "|---|---|---|---|---|---|---|---|",
        ]
    for j in judgments:
        lines.append(
            f"| {j.get('id', '?')} | {j.get('problem_novelty', '?')} | "
            f"{j.get('incremental_risk', '?')} | {j.get('arrow_before_target', '?')} | "
            f"{j.get('so_what', '?')} | {j.get('decisiveness', '?')} | "
            f"**{str(j.get('verdict', '?')).upper()}** | {_clip(str(j.get('reason', '')), 90)} |")

    lines += ["", f"## Kept problems (ranked, {len(keeps)})", ""]
    for rank, j in enumerate(keeps, 1):
        idea = by_id.get(j.get("id"), {})
        lines.append(f"### #{rank} — {idea.get('one_sentence_problem', '')}")
        lines.append("")
        lines.append(f"- **id**: {j.get('id')} | taste score: {_taste_score(j):.1f}")
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
    def _num(key: str, default: float) -> float:
        try:
            return float(j.get(key, default))
        except (TypeError, ValueError):
            return default
    return (
        _num("problem_novelty", 3.0)
        + _num("so_what", 3.0)
        + _num("decisiveness", 3.0)
        - _num("incremental_risk", 3.0)
    )


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
        ("judgments.json", "Taste-gate verdicts"),
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
