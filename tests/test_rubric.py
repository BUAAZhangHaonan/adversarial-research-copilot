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
    assert parse_decision("continue_or_stop\nSTOP") == "STOP"
    assert parse_decision("continue_or_stop\nCONTINUE") == "CONTINUE"


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
