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


def test_stage_taste_gate_enforces_hard_rules() -> None:
    class FakeClient:
        def chat(self, model, system_prompt, user_prompt, temperature=0.3):
            return (
                "```yaml\n"
                "judgments:\n"
                "  - id: I1\n"
                "    problem_novelty: 1\n"
                "    incremental_risk: 3\n"
                "    arrow_before_target: false\n"
                "    so_what: 3\n"
                "    decisiveness: 3\n"
                "    verdict: KEEP\n"
                "    reason: llm wrongly keeps it\n"
                "  - id: I2\n"
                "    problem_novelty: 4\n"
                "    incremental_risk: 2\n"
                "    arrow_before_target: true\n"
                "    so_what: 4\n"
                "    decisiveness: 4\n"
                "    verdict: KEEP\n"
                "    reason: arrow-first offender\n"
                "  - id: I3\n"
                "    problem_novelty: 5\n"
                "    incremental_risk: 1\n"
                "    arrow_before_target: false\n"
                "    so_what: 5\n"
                "    decisiveness: 5\n"
                "    verdict: KEEP\n"
                "    reason: genuine new problem\n"
                "```\n"
            )

    state = dr.DiscoverState(
        topic="t",
        models={"generator": "g", "judge": "j"},
        config=dr.DiscoverConfig(),
    )
    ideas = [{"id": "I1"}, {"id": "I2"}, {"id": "I3"}]
    judgments = dr._stage_taste_gate(FakeClient(), state, ideas)
    by_id = {j["id"]: j for j in judgments}
    assert "[hard rule] problem_novelty" in by_id["I1"]["reason"]
    assert by_id["I1"]["verdict"] == "KILL"
    assert by_id["I2"]["verdict"] == "KILL"
    assert by_id["I3"]["verdict"] == "KEEP"


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
        if "Judge each" in user_prompt:
            return (
                "```yaml\njudgments:\n"
                "  - id: I1\n    problem_novelty: 5\n    incremental_risk: 1\n"
                "    arrow_before_target: false\n    so_what: 5\n"
                "    decisiveness: 4\n    verdict: KEEP\n"
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
    assert first["query"] == 1 and first["analyze"] == 3

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
    assert calls["query"] == 1  # no re-retrieval
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
    assert state["stop_reason"] == "all_gaps_killed"
