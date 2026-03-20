from __future__ import annotations

from pathlib import Path

import yaml
from rich.console import Console

from arc.agents.moderator import ModeratorAgent
from arc.agents.proposer import ProposerAgent
from arc.agents.skeptic import SkepticAgent
from arc.exporters.markdown_report import export_markdown_report
from arc.llm_client import LLMClient
from arc.memory import DebateMemory
from arc.schemas import DebateConfig, RoundRecord
from arc.scoring.rubric import assess_convergence, extract_section, parse_bullets, parse_decision, parse_scorecard
from arc.state import init_state, load_idea_text


class ARCOrchestrator:
    def __init__(self, config_path: str = "configs/debate.yaml") -> None:
        config_data = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
        self.config = DebateConfig(**config_data.get("debate", {}))
        self.console = Console()
        self.client = LLMClient()

    def run(
        self,
        idea_file: str,
        proposer_model: str,
        skeptic_model: str,
        moderator_model: str,
        output_dir: str = "reports",
    ) -> tuple[Path, Path]:
        idea = load_idea_text(idea_file)
        state = init_state(idea)
        run_dir = Path(output_dir) / "latest"
        memory = DebateMemory(run_dir)

        proposer = ProposerAgent(self.client, proposer_model)
        skeptic = SkepticAgent(self.client, skeptic_model)
        moderator = ModeratorAgent(self.client, moderator_model)

        previous_blockers: list[str] = []

        for round_id in range(1, self.config.max_rounds + 1):
            self.console.rule(f"Round {round_id}")
            proposer_output = proposer.run(state.framed_problem, previous_blockers, round_id)
            skeptic_output = skeptic.run(state.framed_problem, proposer_output, round_id)
            moderator_output = moderator.run(state.framed_problem, proposer_output, skeptic_output, round_id)

            scorecard = parse_scorecard(moderator_output)
            decision = parse_decision(moderator_output)
            unresolved_blockers = parse_bullets(extract_section(moderator_output, "unresolved blockers"))
            required_revisions = parse_bullets(extract_section(moderator_output, "required revisions"))

            record = RoundRecord(
                round_id=round_id,
                proposer=proposer_output,
                skeptic=skeptic_output,
                moderator=moderator_output,
                scorecard=scorecard,
                unresolved_blockers=unresolved_blockers,
                required_revisions=required_revisions,
                decision=decision,
            )
            state.add_round(record)
            previous_blockers = unresolved_blockers

            memory.append(record.model_dump())

            convergence = assess_convergence(state.rounds, self.config)
            if convergence.should_stop:
                self.console.print(f"[green]Converged:[/green] {convergence.reason}")
                break

        report_file = export_markdown_report(state, run_dir / "research_decision_memo.md")
        state_file = memory.save_json("final_state.json", state.model_dump(mode="json"))
        return report_file, state_file
