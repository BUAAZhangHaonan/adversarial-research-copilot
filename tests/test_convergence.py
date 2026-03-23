from arc.schemas import DebateConfig, RoundRecord, ScoreCard
from arc.scoring.rubric import assess_convergence


def _round(rid: int, avg_high: bool = True) -> RoundRecord:
    score = ScoreCard(
        novelty=4 if avg_high else 3,
        feasibility=4 if avg_high else 3,
        falsifiability=4 if avg_high else 3,
        evaluation_clarity=4 if avg_high else 3,
        resource_fit=4 if avg_high else 3,
    )
    return RoundRecord(
        round_id=rid,
        proposer="p",
        skeptic="s",
        moderator="m",
        scorecard=score,
        unresolved_blockers=[],
        required_revisions=[],
        decision="CONTINUE",
    )


def test_convergence_with_stable_scores() -> None:
    cfg = DebateConfig(max_rounds=6, min_rounds_before_stop=2,
                       score_threshold=4.0, required_stable_rounds=2)
    rounds = [_round(1), _round(2)]
    status = assess_convergence(rounds, cfg)
    assert status.should_stop is True


def test_no_convergence_when_low_score() -> None:
    cfg = DebateConfig(max_rounds=6, min_rounds_before_stop=2,
                       score_threshold=4.0, required_stable_rounds=2)
    rounds = [_round(1), _round(2, avg_high=False)]
    status = assess_convergence(rounds, cfg)
    assert status.should_stop is False
