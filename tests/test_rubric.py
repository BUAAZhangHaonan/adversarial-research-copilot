from arc.scoring.rubric import parse_decision, parse_scorecard


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
