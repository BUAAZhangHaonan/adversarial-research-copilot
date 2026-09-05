from __future__ import annotations

import json
from pathlib import Path

import pytest

from arc.runners import discover_runner as dr


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_parse_yaml_block_extracts_last_fenced_block() -> None:
    text = (
        "analysis here\n"
        "```yaml\n"
        "gaps:\n"
        "  - id: G1\n"
        "    question: why?\n"
        "```\n"
    )
    payload = dr._parse_yaml_block(text)
    assert payload["gaps"][0]["id"] == "G1"
    assert dr._parse_yaml_block("no yaml here") == {}


def test_taste_score_orders_by_quality() -> None:
    good = {"problem_novelty": 5, "so_what": 4, "decisiveness": 4, "incremental_risk": 1}
    bad = {"problem_novelty": 3, "so_what": 3, "decisiveness": 3, "incremental_risk": 4}
    assert dr._taste_score(good) > dr._taste_score(bad)


def test_stage_taste_gate_enforces_evidence_bound_rules() -> None:
    class FakeClient:
        def chat(self, model, system_prompt, user_prompt, temperature=0.3):
            return (
                "```yaml\n"
                "judgments:\n"
                "  - id: I1\n"
                "    delta_type: rewording\n"
                "    incremental_risk: 4\n"
                "    priority: 1\n"
                "    verdict: KILL\n"
                "    reason: taste-based kill without evidence\n"
                "  - id: I2\n"
                "    delta_type: new_problem\n"
                "    incremental_risk: 2\n"
                "    priority: 4\n"
                "    verdict: KEEP\n"
                "    reason: genuinely new question\n"
                "  - id: I3\n"
                "    delta_type: new_mechanism\n"
                "    incremental_risk: 2\n"
                "    priority: 3\n"
                "    verdict: KILL\n"
                "    kill_evidence_type: duplicate\n"
                "    reason: same question answered in prior work\n"
                "```\n"
            )

    state = dr.DiscoverState(
        topic="t",
        models={"generator": "g", "judge": "j"},
        config=dr.DiscoverConfig(),
    )
    ideas = [{"id": "I1"}, {"id": "I2"}, {"id": "I3"}]
    dedup = [{"idea_id": "I2", "novelty_verdict": "DUPLICATE",
              "duplicate_of": "Prior Work X", "differentiation": ""}]
    judgments = dr._stage_taste_gate(FakeClient(), state, ideas, dedup)
    by_id = {j["id"]: j for j in judgments}
    # Taste-only KILL (no evidence type) is downgraded, never executed.
    assert by_id["I1"]["verdict"] == "PIVOT"
    assert "[hard rule] KILL without valid kill_evidence_type" in by_id["I1"]["reason"]
    # Duplicate-check evidence forces a KILL even when the judge kept it.
    assert by_id["I2"]["verdict"] == "KILL"
    assert by_id["I2"]["kill_evidence_type"] == "duplicate"
    assert "Prior Work X" in by_id["I2"]["reason"]
    # An evidence-backed KILL stands.
    assert by_id["I3"]["verdict"] == "KILL"


# ---------------------------------------------------------------------------
# Full pipeline with mocked MCP services + mocked LLM
# ---------------------------------------------------------------------------

class FakeScholartrace:
    def call_tool(self, name, arguments, timeout=60.0):
        if name == "query":
            papers = [
                {
                    "paper_id": f"theme:paper-{i}",
                    "title": f"Fake Paper {i} on the topic",
                    "year": 2025,
                    "venue": "arXiv",
                    "abstract": "abstract " * 20,
                    "composite_score": 0.5 - i * 0.01,
                    "agent_rank": i,
                    "rationale": "relevant",
                }
                for i in range(1, 8)
            ]
            return json.dumps({"status": "success", "papers": papers})
        if name == "read":
            return json.dumps({"paper_id": arguments["paper_id"], "arxiv_id": "2401.0000" + arguments["paper_id"][-1]})
        raise AssertionError(f"unexpected tool {name}")


class FakeScholaranalysis:
    def call_tool(self, name, arguments, timeout=60.0):
        assert name == "analyze_paper"
        return json.dumps({
            "status": "success",
            "analysis": {"answer": f"Core claim for {arguments['query']}: X. Limitations: Y. Future: Z. Assumptions: W."},
        })


class FakeWebresearch:
    def call_tool(self, name, arguments, timeout=60.0):
        assert name == "web_search"
        return json.dumps({
            "results": [
                {"title": "Practitioners complain", "url": "https://example.com/1", "snippet": "real pain"},
                {"title": "Benchmark at 71%", "url": "https://example.com/2", "snippet": "far from saturated"},
            ]
        })


class FakeServices:
    def __init__(self):
        self.scholartrace = FakeScholartrace()
        self.scholaranalysis = FakeScholaranalysis()
        self.webresearch = FakeWebresearch()

    def close_all(self):
        pass


class FakeDiscoverLLM:
    def chat(self, model, system_prompt, user_prompt, temperature=0.3):
        if "search mandate" in user_prompt:
            return (
                "plan\n```yaml\ntheme:\n  field: fake field\n  subtopics:\n    - sub1\n"
                "  must_include:\n    - k1\n  exclude:\n    - x1\n"
                "  search_queries:\n    - q1\n```\n"
            )
        if "Mine the research gaps" in user_prompt:
            return (
                "```yaml\ngaps:\n"
                "  - id: G1\n    type: recurring_limitation\n"
                "    question: Why does X fail under Y?\n"
                "    evidence_ids: [2401.00001, 2401.00002]\n"
                "    evidence_summary: both admit it\n"
                "    why_unexplored: no metric exists\n"
                "    who_needs_it: builders\n    confidence: 0.8\n"
                "  - id: G2\n    type: contradiction\n"
                "    question: Does A beat B?\n"
                "    evidence_ids: [2401.00003]\n"
                "    evidence_summary: conflicting results\n"
                "    why_unexplored: unreconciled\n"
                "    who_needs_it: everyone\n    confidence: 0.6\n```\n"
            )
        if "Audit this gap" in user_prompt:
            return (
                "```yaml\naudits:\n"
                "  - gap_id: G1\n    pain_saturation: 1\n    community_pain: 5\n"
                "    incremental_risk: 1\n    evidence: loud complaints\n"
                "    verdict: KEEP\n    reason: real pain, unsolved\n```\n"
            )
        if "Compose up to" in user_prompt:
            return (
                "```yaml\nideas:\n"
                "  - id: I1\n    from_gaps: [G1]\n"
                "    one_sentence_problem: When and why does X fail under Y?\n"
                "    gap_evidence: '[2401.00001] both admit'\n"
                "    who_needs_it: builders\n    why_now: new evidence\n"
                "    minimal_falsifiable_test: run Z on 100 cases\n"
                "    anti_scope: not a new benchmark\n```\n"
            )
        if "Check this candidate" in user_prompt:
            return (
                "```yaml\nchecks:\n"
                "  - idea_id: echo\n    closest_works:\n"
                "      - 'Closest Prior Work — same question under narrower conditions'\n"
                "    differentiation: prior work covered C; candidate examines D; delta is Y\n"
                "    novelty_verdict: DISTINCT\n    unchecked: adjacent-field phrasings\n"
                "    reason: substantive delta named\n```\n"
            )
        if "Judge each" in user_prompt:
            return (
                "```yaml\njudgments:\n"
                "  - id: I1\n    delta_type: new_problem\n    incremental_risk: 1\n"
                "    knowledge_gain: first separation of failure loci\n"
                "    decision_changed: memory-system investment decisions\n"
                "    distinguishes_alternatives: true\n    priority: 5\n"
                "    verdict: KEEP\n"
                "    reason: genuinely new question\n```\n"
            )
        raise AssertionError(f"unexpected user prompt: {user_prompt[:80]}")


def test_run_discover_full_pipeline_with_mocks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(dr, "connect_services", lambda: FakeServices())
    monkeypatch.setattr(dr, "LLMClient", lambda: FakeDiscoverLLM())
    monkeypatch.setattr(dr, "_load_config", lambda: dr.DiscoverConfig(
        papers=6, deep_read=3, ideas=2, min_deep_read_ok=1))

    reports = tmp_path / "reports"
    report_file, state_file = dr.run_discover(
        topic="fake topic",
        generator_model="flash",
        judge_model="pro",
        output_dir=str(reports),
    )

    run_dir = report_file.parent
    assert run_dir == state_file.parent
    for artifact in (
        "TOPIC_DISCOVER.txt", "THEME.md", "theme.json",
        "CANDIDATE_POOL.md", "candidate_pool.json",
        "deep_read_notes.json", "GAP_ANALYSIS.md", "gaps.json",
        "SATURATION_AUDIT.md", "audits.json",
        "IDEA_PORTFOLIO.md", "ideas.json", "judgments.json",
        "DISCOVERY_REPORT.md", "OUTPUT_INDEX.md", "discover_state.json",
    ):
        assert (run_dir / artifact).exists(), f"missing {artifact}"

    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["status"] == "completed"
    assert set(state["stage_statuses"].values()) == {"completed"}

    report = report_file.read_text(encoding="utf-8")
    assert "When and why does X fail under Y?" in report
    notes = json.loads((run_dir / "deep_read_notes.json").read_text(encoding="utf-8"))
    assert len(notes) == 3


def test_run_discover_resume_skips_completed_stages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Second call with resume=True must not re-run the (mocked) stages."""
    calls = {"query": 0, "analyze": 0, "llm": 0}

    class CountingScholartrace(FakeScholartrace):
        def call_tool(self, name, arguments, timeout=60.0):
            if name == "query":
                calls["query"] += 1
            return super().call_tool(name, arguments, timeout)

    class CountingScholaranalysis(FakeScholaranalysis):
        def call_tool(self, name, arguments, timeout=60.0):
            calls["analyze"] += 1
            return super().call_tool(name, arguments, timeout)

    class CountingServices(FakeServices):
        def __init__(self):
            self.scholartrace = CountingScholartrace()
            self.scholaranalysis = CountingScholaranalysis()
            self.webresearch = FakeWebresearch()

        def close_all(self):
            pass

    class CountingLLM(FakeDiscoverLLM):
        def chat(self, model, system_prompt, user_prompt, temperature=0.3):
            calls["llm"] += 1
            return super().chat(model, system_prompt, user_prompt, temperature)

    monkeypatch.setattr(dr, "connect_services", lambda: CountingServices())
    monkeypatch.setattr(dr, "LLMClient", lambda: CountingLLM())
    monkeypatch.setattr(dr, "_load_config", lambda: dr.DiscoverConfig(
        papers=6, deep_read=3, ideas=2, min_deep_read_ok=1))

    reports = tmp_path / "reports"
    dr.run_discover(topic="fake topic", generator_model="flash", judge_model="pro",
                    output_dir=str(reports))
    first = dict(calls)
    # 1 wide retrieval + 1 duplicate-check query per candidate (1 idea)
    assert first["query"] == 2 and first["analyze"] == 3

    # Simulate an interrupted rerun: mark stages incomplete but keep artifacts.
    marker = reports / "LATEST_RUN"
    run_name = marker.read_text(encoding="utf-8").strip()
    state_path = reports / run_name / "discover_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["status"] = "in_progress"
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    report_file, _ = dr.run_discover(
        topic="fake topic", generator_model="flash", judge_model="pro",
        output_dir=str(reports), resume=True)
    assert calls["query"] == 2  # no re-retrieval (1 retrieval + 1 dedup, unchanged)
    assert calls["analyze"] == 3  # no re-reading
    assert calls["llm"] == first["llm"]  # no re-generation
    assert "When and why does X fail under Y?" in report_file.read_text(encoding="utf-8")


def test_run_discover_hard_fails_when_mcp_down(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from arc.providers.mcp_bridge import MCPError

    def broken_connect():
        raise MCPError("scholartrace unreachable")

    monkeypatch.setattr(dr, "connect_services", broken_connect)
    monkeypatch.setattr(dr, "_load_config", lambda: dr.DiscoverConfig(
        papers=6, deep_read=3, ideas=2))

    with pytest.raises(MCPError, match="scholartrace unreachable"):
        dr.run_discover(
            topic="t", generator_model="flash", judge_model="pro",
            output_dir=str(tmp_path / "reports"))


def test_run_discover_all_gaps_killed_still_reports(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class KillingLLM(FakeDiscoverLLM):
        def chat(self, model, system_prompt, user_prompt, temperature=0.3):
            if "Audit this gap" in user_prompt:
                return (
                    "```yaml\naudits:\n"
                    "  - gap_id: G1\n    pain_saturation: 5\n    community_pain: 1\n"
                    "    incremental_risk: 4\n    evidence: solved\n"
                    "    verdict: KILL\n    reason: metric saturated at 98%+\n```\n"
                )
            return super().chat(model, system_prompt, user_prompt, temperature)

    monkeypatch.setattr(dr, "connect_services", lambda: FakeServices())
    monkeypatch.setattr(dr, "LLMClient", lambda: KillingLLM())
    monkeypatch.setattr(dr, "_load_config", lambda: dr.DiscoverConfig(
        papers=6, deep_read=3, ideas=2, min_deep_read_ok=1))

    report_file, state_file = dr.run_discover(
        topic="fake topic", generator_model="flash", judge_model="pro",
        output_dir=str(tmp_path / "reports"))

    report = report_file.read_text(encoding="utf-8")
    assert "No surviving problems" in report
    assert "metric saturated" in report
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["status"] == "completed"
    assert state["stop_reason"] == "no_surviving_gaps"


def _many_gap_llm(n_gaps: int):
    """Fake LLM whose gap miner returns n_gaps gaps; audit echoes KEEP for the asked gap."""
    class ManyGapLLM(FakeDiscoverLLM):
        def chat(self, model, system_prompt, user_prompt, temperature=0.3):
            if "Mine the research gaps" in user_prompt:
                entries = "\n".join(
                    f"  - id: G{i}\n    type: recurring_limitation\n"
                    f"    question: q{i}?\n    evidence_ids: [2401.00001]\n"
                    f"    evidence_summary: e\n    why_unexplored: w\n"
                    f"    who_needs_it: builders\n    confidence: 0.7"
                    for i in range(1, n_gaps + 1)
                )
                return f"```yaml\ngaps:\n{entries}\n```\n"
            return super().chat(model, system_prompt, user_prompt, temperature)
    return ManyGapLLM


def test_audit_gaps_beyond_budget_are_not_audited_and_never_pass(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    n = 10  # _MAX_GAPS_TO_AUDIT is 8: G9/G10 must not pass
    captured_ideas_prompt: dict[str, str] = {}

    class CapturingLLM(_many_gap_llm(n)):
        def chat(self, model, system_prompt, user_prompt, temperature=0.3):
            if "Compose up to" in user_prompt:
                captured_ideas_prompt["value"] = user_prompt
            return super().chat(model, system_prompt, user_prompt, temperature)

    monkeypatch.setattr(dr, "connect_services", lambda: FakeServices())
    monkeypatch.setattr(dr, "LLMClient", lambda: CapturingLLM())
    monkeypatch.setattr(dr, "_load_config", lambda: dr.DiscoverConfig(
        papers=6, deep_read=3, ideas=2, min_deep_read_ok=1))

    report_file, state_file = dr.run_discover(
        topic="t", generator_model="flash", judge_model="pro",
        output_dir=str(tmp_path / "reports"))
    run_dir = report_file.parent

    audits = json.loads((run_dir / "audits.json").read_text(encoding="utf-8"))
    by_gap = {a["gap_id"]: a["verdict"] for a in audits}
    assert len(audits) == n, "every gap must carry exactly one audit record"
    assert by_gap["G9"] == "NOT_AUDITED"
    assert by_gap["G10"] == "NOT_AUDITED"
    assert "G9" not in captured_ideas_prompt["value"], "unaudited gap must not reach idea composition"
    assert "G10" not in captured_ideas_prompt["value"]


def test_audit_web_failure_yields_insufficient_evidence_not_keep(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from arc.providers.mcp_bridge import MCPError

    class BrokenWebServices(FakeServices):
        def __init__(self):
            self.scholartrace = FakeScholartrace()
            self.scholaranalysis = FakeScholaranalysis()

            class Broken:
                def call_tool(self, name, arguments, timeout=60.0):
                    raise MCPError("searxng down")

            self.webresearch = Broken()

    class NoAuditCalls:
        calls = {"audit": 0}

    monkeypatch.setattr(dr, "connect_services", lambda: BrokenWebServices())
    monkeypatch.setattr(dr, "LLMClient", lambda: _many_gap_llm(2)())
    monkeypatch.setattr(dr, "_load_config", lambda: dr.DiscoverConfig(
        papers=6, deep_read=3, ideas=2, min_deep_read_ok=1))

    report_file, _ = dr.run_discover(
        topic="t", generator_model="flash", judge_model="pro",
        output_dir=str(tmp_path / "reports"))
    run_dir = report_file.parent
    audits = json.loads((run_dir / "audits.json").read_text(encoding="utf-8"))
    assert all(a["verdict"] == "INSUFFICIENT_EVIDENCE" for a in audits)
    assert all("webresearch unavailable" in a["reason"] for a in audits)
    # No gap survived -> report explains, run still completes.
    report = (run_dir / "DISCOVERY_REPORT.md").read_text(encoding="utf-8")
    assert "No surviving problems" in report


def test_audit_unparseable_output_yields_insufficient_evidence_not_keep(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class GarbageAuditLLM(FakeDiscoverLLM):
        def chat(self, model, system_prompt, user_prompt, temperature=0.3):
            if "Audit this gap" in user_prompt:
                return "I assessed it and it seems fine, no structure today."
            return super().chat(model, system_prompt, user_prompt, temperature)

    monkeypatch.setattr(dr, "connect_services", lambda: FakeServices())
    monkeypatch.setattr(dr, "LLMClient", lambda: GarbageAuditLLM())
    monkeypatch.setattr(dr, "_load_config", lambda: dr.DiscoverConfig(
        papers=6, deep_read=3, ideas=2, min_deep_read_ok=1))

    report_file, _ = dr.run_discover(
        topic="t", generator_model="flash", judge_model="pro",
        output_dir=str(tmp_path / "reports"))
    audits = json.loads(
        (report_file.parent / "audits.json").read_text(encoding="utf-8"))
    assert audits
    assert all(a["verdict"] == "INSUFFICIENT_EVIDENCE" for a in audits)


def test_deep_read_ranking_prefers_agent_ranked_papers(tmp_path: Path) -> None:
    """Mixed pool: agent-ranked papers must be deep-read before unranked ones (review R2)."""
    class Noop:
        def call_tool(self, *a, **kw):
            raise AssertionError("should not be called")

    class NoopServices:
        scholartrace = Noop()
        scholaranalysis = Noop()
        webresearch = Noop()

        def close_all(self):
            pass

    pool = [
        {"paper_id": "t:unranked", "title": "No agent rank", "agent_rank": None,
         "composite_score": 0.9},
        {"paper_id": "t:rank2", "title": "Ranked second", "agent_rank": 2,
         "composite_score": 0.2},
        {"paper_id": "t:rank1", "title": "Ranked first", "agent_rank": 1,
         "composite_score": 0.1},
        {"paper_id": "t:unranked2", "title": "No agent rank either", "agent_rank": None,
         "composite_score": 0.8},
    ]

    # Reuse the ranking logic through _stage_deep_read by pre-seeding cached
    # notes for every paper: the read order is observable via file creation order.
    import contextlib

    calls: list[str] = []

    class RecordingServices:
        def __init__(self):
            self.scholartrace = self
            self.scholaranalysis = self
            self.webresearch = Noop()

        def call_tool(self, name, arguments, timeout=60.0):
            calls.append((name, arguments.get("paper_id") or arguments.get("query")))
            if name == "read":
                pid = arguments["paper_id"]
                return json.dumps({"paper_id": pid, "arxiv_id": "2401.0" + pid[-1]})
            if name == "analyze_paper":
                return json.dumps({"status": "success",
                                   "analysis": {"answer": f"claim for {arguments['query']}"}})
            raise AssertionError(name)

        def close_all(self):
            pass

    notes = dr._stage_deep_read(RecordingServices(), tmp_path, pool,
                                dr.DiscoverConfig(deep_read=2, min_deep_read_ok=1))
    assert [n["title"] for n in notes] == ["Ranked first", "Ranked second"], (
        "deep-read budget must go to agent-ranked papers first; unranked papers "
        "must not consume the budget before them")


def test_zero_gaps_is_first_class_outcome(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`gaps: []` must complete without retry or error (review R6)."""
    calls = {"gap_mining": 0}

    class ZeroGapLLM(FakeDiscoverLLM):
        def chat(self, model, system_prompt, user_prompt, temperature=0.3):
            if "Mine the research gaps" in user_prompt:
                calls["gap_mining"] += 1
                return "Checked all four categories; nothing qualifies.\n```yaml\ngaps: []\n```\n"
            return super().chat(model, system_prompt, user_prompt, temperature)

    monkeypatch.setattr(dr, "connect_services", lambda: FakeServices())
    monkeypatch.setattr(dr, "LLMClient", lambda: ZeroGapLLM())
    monkeypatch.setattr(dr, "_load_config", lambda: dr.DiscoverConfig(
        papers=6, deep_read=3, ideas=2, min_deep_read_ok=1))

    report_file, state_file = dr.run_discover(
        topic="t", generator_model="flash", judge_model="pro",
        output_dir=str(tmp_path / "reports"))

    assert calls["gap_mining"] == 1, "empty list is valid: no retry expected"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["status"] == "completed"
    assert state["stop_reason"] == "zero_gaps_mined"
    assert "No surviving problems" in report_file.read_text(encoding="utf-8")


def test_empty_ideas_is_first_class_outcome(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class NoIdeasLLM(FakeDiscoverLLM):
        def chat(self, model, system_prompt, user_prompt, temperature=0.3):
            if "Compose up to" in user_prompt:
                return "Nothing composable.\n```yaml\nideas: []\n```\n"
            return super().chat(model, system_prompt, user_prompt, temperature)

    monkeypatch.setattr(dr, "connect_services", lambda: FakeServices())
    monkeypatch.setattr(dr, "LLMClient", lambda: NoIdeasLLM())
    monkeypatch.setattr(dr, "_load_config", lambda: dr.DiscoverConfig(
        papers=6, deep_read=3, ideas=2, min_deep_read_ok=1))

    report_file, state_file = dr.run_discover(
        topic="t", generator_model="flash", judge_model="pro",
        output_dir=str(tmp_path / "reports"))

    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["status"] == "completed"
    assert state["stop_reason"] == "no_composable_ideas"
    assert "No surviving problems" in report_file.read_text(encoding="utf-8")


def test_deep_read_restores_cached_notes_without_repaying(
    tmp_path: Path,
) -> None:
    """A note already on disk from an interrupted run is restored, not re-analyzed (review R7b)."""
    deep_dir = tmp_path / "DEEP_READ"
    deep_dir.mkdir(parents=True)
    cached_note = {
        "arxiv_id": "2401.00001", "paper_id": "t:rank1",
        "title": "Ranked first", "year": 2025, "venue": "arXiv",
        "analysis": "cached extraction from previous run",
    }
    (deep_dir / "2401.00001.json").write_text(
        json.dumps(cached_note, ensure_ascii=False), encoding="utf-8")

    analyze_calls = {"count": 0}

    class CountingServices:
        def __init__(self):
            self.scholartrace = self
            self.scholaranalysis = self

        def call_tool(self, name, arguments, timeout=60.0):
            if name == "analyze_paper":
                analyze_calls["count"] += 1
                return json.dumps({"status": "success",
                                   "analysis": {"answer": "fresh analysis"}})
            if name == "read":
                return json.dumps({"paper_id": arguments["paper_id"],
                                   "arxiv_id": "2401.0000" + arguments["paper_id"][-1]})
            raise AssertionError(name)

        def close_all(self):
            pass

    pool = [
        {"paper_id": "t:rank1", "title": "Ranked first", "agent_rank": 1,
         "composite_score": 0.5},
        {"paper_id": "t:rank2", "title": "Ranked second", "agent_rank": 2,
         "composite_score": 0.4},
    ]
    notes = dr._stage_deep_read(CountingServices(), tmp_path, pool,
                                dr.DiscoverConfig(deep_read=2, min_deep_read_ok=1))

    by_id = {n["arxiv_id"]: n for n in notes}
    assert by_id["2401.00001"]["analysis"] == "cached extraction from previous run"
    assert analyze_calls["count"] == 1, "only the uncached paper should be re-analyzed"


def test_duplicate_check_incremental_and_feeds_taste_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Dedup persists per-idea (interrupted rerun skips done ids) and its
    material reaches the taste-gate prompt (review D2)."""
    taste_prompts: list[str] = []
    dedup_llm_calls = {"count": 0}

    class DedupCountingLLM(FakeDiscoverLLM):
        def chat(self, model, system_prompt, user_prompt, temperature=0.3):
            if "Check this candidate" in user_prompt:
                dedup_llm_calls["count"] += 1
                idea_id = "I1" if "I1" in user_prompt else "I2"
                return (
                    f"```yaml\nchecks:\n  - idea_id: echo\n"
                    f"    closest_works:\n      - 'Prior W{idea_id}'\n"
                    f"    differentiation: delta {idea_id}\n"
                    f"    novelty_verdict: DISTINCT\n    unchecked: x\n    reason: r\n```\n"
                )
            if "Judge each" in user_prompt:
                taste_prompts.append(user_prompt)
            return super().chat(model, system_prompt, user_prompt, temperature)

    monkeypatch.setattr(dr, "connect_services", lambda: FakeServices())
    monkeypatch.setattr(dr, "LLMClient", lambda: DedupCountingLLM())
    monkeypatch.setattr(dr, "_load_config", lambda: dr.DiscoverConfig(
        papers=6, deep_read=3, ideas=2, min_deep_read_ok=1))

    report_file, _ = dr.run_discover(
        topic="t", generator_model="flash", judge_model="pro",
        output_dir=str(tmp_path / "reports"))
    run_dir = report_file.parent

    checks = json.loads((run_dir / "duplicate_checks.json").read_text(encoding="utf-8"))
    assert {c["idea_id"] for c in checks} == {"I1"}  # the fake composer emits one idea
    assert dedup_llm_calls["count"] == 1
    report = (run_dir / "DISCOVERY_REPORT.md").read_text(encoding="utf-8")
    assert "delta I1" in report, "dedup delta must surface in the kept-problem section"
    dedup_doc = (run_dir / "DUPLICATE_CHECK.md").read_text(encoding="utf-8")
    assert "Prior WI1" in dedup_doc, "closest prior work must be recorded in DUPLICATE_CHECK.md"

    # Simulate interruption after the dedup stage and rerun: no re-checking.
    state_path = run_dir / "discover_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["status"] = "in_progress"
    state["stage_statuses"] = {k: v for k, v in state["stage_statuses"].items()
                               if k not in ("taste-gate",)}
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    marker = reports = tmp_path / "reports"
    dr.run_discover(topic="t", generator_model="flash", judge_model="pro",
                    output_dir=str(marker), resume=True)
    assert dedup_llm_calls["count"] == 1, "already-checked candidates must be skipped"


def test_rejection_log_records_conditional_kills_with_reopen(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class KillerJudgeLLM(FakeDiscoverLLM):
        def chat(self, model, system_prompt, user_prompt, temperature=0.3):
            if "Audit this gap" in user_prompt:
                gap_id = "G1" if "G1" in user_prompt else "G2"
                if gap_id == "G1":
                    return (f"```yaml\naudits:\n  - gap_id: echo\n"
                            f"    verdict: INSUFFICIENT_EVIDENCE\n"
                            f"    evidence_basis: none\n    evidence: none\n"
                            f"    missing_evidence: deployment failure reports\n"
                            f"    reason: dossier too thin\n```\n")
                return (f"```yaml\naudits:\n  - gap_id: echo\n    verdict: KEEP\n"
                        f"    evidence_basis: scientific_deficit\n"
                        f"    evidence: documented contradiction\n"
                        f"    reason: unresolved contradiction worth probing\n```\n")
            if "Judge each" in user_prompt:
                return ("```yaml\njudgments:\n  - id: I1\n    delta_type: rewording\n"
                        "    incremental_risk: 4\n    priority: 1\n    verdict: KILL\n"
                        "    kill_evidence_type: duplicate\n"
                        "    reason: prior work covers it\n```\n")
            return super().chat(model, system_prompt, user_prompt, temperature)

    monkeypatch.setattr(dr, "connect_services", lambda: FakeServices())
    monkeypatch.setattr(dr, "LLMClient", lambda: KillerJudgeLLM())
    monkeypatch.setattr(dr, "_load_config", lambda: dr.DiscoverConfig(
        papers=6, deep_read=3, ideas=2, min_deep_read_ok=1))

    report_file, _ = dr.run_discover(
        topic="t", generator_model="flash", judge_model="pro",
        output_dir=str(tmp_path / "reports"))
    run_dir = report_file.parent
    log = json.loads((run_dir / "rejection_log.json").read_text(encoding="utf-8"))
    by_key = {(e["object_type"], e["object_id"]): e for e in log}
    insuff = by_key[("gap", "G1")]
    assert insuff["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert "webresearch reachable" in insuff["reopen_condition"]
    # G2 was audited KEEP, so its idea survived to the taste gate, where I1
    # is killed with duplicate evidence -> logged with a reopen condition.
    idea_kill = by_key[("idea", "I1")]
    assert idea_kill["kill_evidence_type"] == "duplicate"
    assert "does not cover the candidate's conditions" in idea_kill["reopen_condition"]
    assert "reopen" in (run_dir / "REJECTION_LOG.md").read_text(encoding="utf-8").lower()


def test_stress_test_passes_full_brief_and_cross_models(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Stress tests receive the full candidate brief and a skeptic from a
    different model than the proposer (review 一.5)."""
    captured: dict[str, Any] = {}

    import arc.runners.chat_mode_runner as cmr

    def fake_run_chat_mode(**kwargs):
        captured.update(kwargs)
        run_dir = Path(kwargs["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "chat_mode_state.json").write_text("{}", encoding="utf-8")
        return run_dir / "CHAT_TRANSCRIPT.md", run_dir / "chat_mode_state.json"

    monkeypatch.setattr("arc.runners.chat_mode_runner.run_chat_mode", fake_run_chat_mode)

    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    ideas = [{"id": "I1", "one_sentence_problem": "Does X fail under Y?",
              "gap_evidence": "[a1] both admit", "who_needs_it": "builders",
              "why_now": "new logs", "minimal_falsifiable_test": "oracle replay on 100 failures",
              "anti_scope": "not a benchmark"}]
    judgments = [{"id": "I1", "verdict": "KEEP", "reason": "new question",
                  "knowledge_gain": "failure attribution"}]
    (run_dir / "ideas.json").write_text(json.dumps(ideas), encoding="utf-8")
    (run_dir / "judgments.json").write_text(json.dumps(judgments), encoding="utf-8")
    (run_dir / "duplicate_checks.json").write_text(json.dumps([
        {"idea_id": "I1", "novelty_verdict": "DISTINCT",
         "closest_works": ["Prior W"], "differentiation": "delta D"}]), encoding="utf-8")

    state = dr.DiscoverState(
        topic="t", models={"generator": "flash", "judge": "pro"},
        config=dr.DiscoverConfig(stress_test=True, stress_rounds=4))

    dr._run_stress_test(run_dir, state)

    assert captured["proposer_model"] == "flash"
    assert captured["skeptic_model"] == "pro", "skeptic must differ from proposer"
    assert captured["moderator_model"] == "pro"
    topic = captured["topic"]
    for marker in ("oracle replay on 100 failures", "not a benchmark", "delta D", "Prior W"):
        assert marker in topic, f"brief lost evidence: {marker}"


def test_llm_client_records_usage(tmp_path: Path) -> None:
    from arc.llm_client import LLMClient

    cfg = tmp_path / "models.yaml"
    cfg.write_text(
        "models:\n  m1:\n    provider: p\n    base_url_env: B\n    api_key_env: K\n"
        "    endpoint: chat_completions\n",
        encoding="utf-8")

    class FakeClient(LLMClient):
        pass

    client = FakeClient(config_path=str(cfg))
    monkey = None
    import arc.llm_client as lc

    def fake_post(url, headers=None, json=None, payload=None, timeout=60.0, **kwargs):
        class R:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"choices": [{"message": {"content": "hello"}}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                                  "total_tokens": 15}}
        return R()

    original = lc.requests.post
    lc.requests.post = fake_post
    try:
        import os
        os.environ.setdefault("B", "http://x")
        os.environ.setdefault("K", "k")
        text = client.chat("m1", "sys", "user")
    finally:
        lc.requests.post = original

    assert text == "hello"
    stats = client.snapshot_usage()["m1"]
    assert stats["calls"] == 1
    assert stats["prompt_tokens"] == 10
    assert stats["total_tokens"] == 15
    assert stats["reports_without_usage"] == 0
