from pathlib import Path

from arc.scoring.rubric import parse_decision, parse_required_revisions, parse_scorecard, parse_unresolved_blockers


def test_parse_scorecard() -> None:
    text = """
    scorecard
    novelty: 5
    feasibility: 4
    falsifiability: 4
    evaluation_clarity: 5
    resource_fit: 4
    """
    score = parse_scorecard(text)
    assert score.novelty == 5
    assert score.resource_fit == 4
    assert score.average > 4.0


def test_parse_decision() -> None:
    # Structured field only; plain prose is a protocol failure (None).
    assert parse_decision("```yaml\ncontinue_or_stop: STOP\n```") == "STOP"
    assert parse_decision("```yaml\ncontinue_or_stop: CONTINUE\n```") == "CONTINUE"
    assert parse_decision("continue_or_stop\nSTOP") is None


def test_parse_yaml_payload() -> None:
    text = """
        moderator report
        ```yaml
        scorecard:
            novelty: 5
            feasibility: 4
            falsifiability: 4
            evaluation_clarity: 5
            resource_fit: 4
        unresolved_blockers:
            - 缺少对照实验
            - 失败判据不明确
        required_revisions:
            - 增加 baseline A/B 对照
            - 给出失败阈值
        continue_or_stop: CONTINUE
        reason: blockers still open
        ```
        """
    score = parse_scorecard(text)
    assert score.novelty == 5
    assert parse_decision(text) == "CONTINUE"
    assert len(parse_unresolved_blockers(text)) == 2
    assert len(parse_required_revisions(text)) == 2


def test_parse_yaml_payload_accepts_yml_fence() -> None:
    text = """
        ```yml
        scorecard:
          novelty: 4
          feasibility: 4
          falsifiability: 4
          evaluation_clarity: 4
          resource_fit: 4
        unresolved_blockers:
          - blocker
        required_revisions:
          - revision
        continue_or_stop: STOP
        ```
    """
    score = parse_scorecard(text)
    assert score.average == 4.0
    assert parse_decision(text) == "STOP"
    assert parse_unresolved_blockers(text) == ["blocker"]
    assert parse_required_revisions(text) == ["revision"]


def test_moderator_prompt_declares_canonical_runtime_schema() -> None:
    prompt = Path("prompts/latest/default/moderator_en.md").read_text(encoding="utf-8")
    assert "scorecard:" in prompt
    assert "unresolved_blockers:" in prompt
    assert "required_revisions:" in prompt
    assert "continue_or_stop:" in prompt


def test_parse_scorecard_tolerates_invalid_yaml_scores() -> None:
    text = """
        ```yaml
        scorecard:
          novelty: 6
          feasibility: high
          falsifiability: null
          evaluation_clarity: 4.7
          resource_fit: 2
        continue_or_stop: CONTINUE
        ```
        """
    score = parse_scorecard(text)
    assert score.novelty == 3  # out-of-range -> default
    assert score.feasibility == 3  # non-numeric -> default
    assert score.falsifiability == 3  # null -> default
    assert score.evaluation_clarity == 4  # float truncates
    assert score.resource_fit == 2


def test_parse_decision_never_guesses_stop_from_prose() -> None:
    # Review R8: prose containing the word STOP must not control the loop.
    assert parse_decision("Do not STOP; CONTINUE collecting evidence.") is None
    assert parse_decision("We should probably stop here maybe.") is None


def test_parse_decision_reads_structured_field_only() -> None:
    stop_yaml = "```yaml\ncontinue_or_stop: STOP\nreason: converged\n```"
    cont_yaml = "```yaml\ncontinue_or_stop: CONTINUE\n```"
    assert parse_decision(stop_yaml) == "STOP"
    assert parse_decision(cont_yaml) == "CONTINUE"
    # Invalid enum value inside the YAML is still a protocol failure.
    assert parse_decision("```yaml\ncontinue_or_stop: MAYBE\n```") is None
