from __future__ import annotations

from pathlib import Path

from arc.schemas import ResearchState


def load_idea_text(path: str | Path) -> str:
    idea_path = Path(path)
    return idea_path.read_text(encoding="utf-8").strip()


def frame_problem(raw_idea: str) -> str:
    # Keep framing deterministic in v0.1 so convergence behavior is easy to test.
    return (
        "目标：将科研设想转化为可证伪、可执行、可评估的方案。\n"
        "约束：限定资源、时间、可复现条件，避免概念空转。\n"
        "评价标准：创新性、可行性、可证伪性、评估清晰度、资源匹配度。\n"
        f"输入设想：{raw_idea}"
    )


def init_state(idea: str) -> ResearchState:
    framed = frame_problem(idea)
    return ResearchState(idea=idea, framed_problem=framed)
