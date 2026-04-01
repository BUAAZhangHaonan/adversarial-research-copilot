from arc.state import frame_problem, init_state


def test_frame_problem_contains_core_fields() -> None:
    raw = "test idea"
    framed = frame_problem(raw)
    assert "Goal:" in framed
    assert "Evaluation axes:" in framed
    assert "test idea" in framed


def test_init_state() -> None:
    state = init_state("abc")
    assert state.idea == "abc"
    assert len(state.rounds) == 0
