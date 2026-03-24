from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml
from rich.console import Console

from arc.agents.moderator import ModeratorAgent
from arc.agents.proposer import ProposerAgent
from arc.agents.skeptic import SkepticAgent
from arc.exporters.markdown_report import export_markdown_report
from arc.llm_client import LLMClient
from arc.memory import DebateMemory
from arc.run_paths import resolve_run_dir
from arc.schemas import DebateConfig, ResearchState, RoundRecord
from arc.scoring.rubric import assess_convergence, parse_decision, parse_required_revisions, parse_scorecard, parse_unresolved_blockers
from arc.state import init_state, load_idea_text


class ARCOrchestrator:
    def __init__(self, config_path: str = "configs/debate.yaml") -> None:
        config_data = yaml.safe_load(
            Path(config_path).read_text(encoding="utf-8"))
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
        resume: bool = False,
        run_dir: Path | None = None,
    ) -> tuple[Path, Path]:
        if self.config.require_cross_model_adversary and proposer_model == skeptic_model:
            raise ValueError(
                "Proposer and Skeptic must use different models when require_cross_model_adversary=true")

        idea = load_idea_text(idea_file)
        target_run_dir = run_dir or resolve_run_dir(
            output_dir, resume, "run_state.json")
        memory = DebateMemory(target_run_dir)
        state, start_round, previous_blockers, resumed = self._prepare_state(
            memory, idea, resume)
        if resume and not resumed and run_dir is None and (target_run_dir / "run_state.json").exists():
            target_run_dir = resolve_run_dir(output_dir, False, "run_state.json")
            memory = DebateMemory(target_run_dir)
            state, start_round, previous_blockers, resumed = self._prepare_state(
                memory, idea, False)

        if resumed:
            existing_idea = (target_run_dir / "INPUT_IDEA.txt").read_text(
                encoding="utf-8").strip() if (target_run_dir / "INPUT_IDEA.txt").exists() else ""
            if existing_idea and existing_idea != idea.strip():
                raise ValueError(
                    "Resume requested with a different idea than the in-progress run.")

        (target_run_dir / "INPUT_IDEA.txt").write_text(idea.strip() + "\n", encoding="utf-8")
        previous_required_revisions: list[str] = []
        if state.rounds:
            previous_required_revisions = state.rounds[-1].required_revisions

        proposer = ProposerAgent(self.client, proposer_model)
        skeptic = SkepticAgent(self.client, skeptic_model)
        moderator = ModeratorAgent(self.client, moderator_model)

        for round_id in range(start_round, self.config.max_rounds + 1):
            self.console.rule(f"Round {round_id}")
            proposer_output = proposer.run(
                state.framed_problem,
                previous_blockers,
                previous_required_revisions,
                round_id,
            )
            skeptic_output = skeptic.run(
                state.framed_problem, proposer_output, previous_blockers, round_id)
            moderator_output = moderator.run(
                state.framed_problem,
                proposer_output,
                skeptic_output,
                previous_blockers,
                previous_required_revisions,
                round_id,
            )

            scorecard = parse_scorecard(moderator_output)
            decision = parse_decision(moderator_output)
            unresolved_blockers = parse_unresolved_blockers(moderator_output)
            required_revisions = parse_required_revisions(moderator_output)

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
            previous_required_revisions = required_revisions

            memory.append(record.model_dump())
            memory.save_json("final_state.json", state.model_dump(mode="json"))
            self._save_run_state(memory, round_id, scorecard.average,
                                 decision, unresolved_blockers, "in_progress")

            if self.config.human_checkpoint:
                if not self._human_checkpoint(record):
                    self.console.print(
                        "[yellow]Stopped by human checkpoint.[/yellow]")
                    break

            convergence = assess_convergence(state.rounds, self.config)
            if convergence.should_stop:
                self.console.print(
                    f"[green]Converged:[/green] {convergence.reason}")
                break

        report_file = export_markdown_report(
            state, target_run_dir / "research_decision_memo.md")
        state_file = memory.save_json(
            "final_state.json", state.model_dump(mode="json"))
        self._save_run_state(
            memory,
            round_id=len(state.rounds),
            avg_score=state.rounds[-1].scorecard.average if state.rounds else 0.0,
            decision=state.rounds[-1].decision if state.rounds else "CONTINUE",
            blockers=state.rounds[-1].unresolved_blockers if state.rounds else [],
            status="completed",
        )
        return report_file, state_file

    def _prepare_state(
        self,
        memory: DebateMemory,
        idea: str,
        resume: bool,
    ) -> tuple[ResearchState, int, list[str], bool]:
        if not resume:
            return init_state(idea), 1, [], False

        run_state = memory.load_json("run_state.json")
        final_state = memory.load_json("final_state.json")
        if not run_state or not final_state:
            return init_state(idea), 1, [], False

        if run_state.get("status") != "in_progress":
            return init_state(idea), 1, [], False

        ts_str = str(run_state.get("timestamp", ""))
        try:
            last_ts = datetime.fromisoformat(ts_str)
        except ValueError:
            return init_state(idea), 1, [], False

        now = datetime.now(UTC)
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=UTC)
        age_hours = (now - last_ts).total_seconds() / 3600
        if age_hours > self.config.stale_resume_hours:
            return init_state(idea), 1, [], False

        state = ResearchState.model_validate(final_state)
        next_round = int(run_state.get("round", len(state.rounds))) + 1
        blockers = [str(x) for x in run_state.get("blockers", [])]
        self.console.print(
            f"[cyan]Recovered run state. Resume from round {next_round}.[/cyan]")
        return state, next_round, blockers, True

    def _save_run_state(
        self,
        memory: DebateMemory,
        round_id: int,
        avg_score: float,
        decision: str,
        blockers: list[str],
        status: str,
    ) -> None:
        if not self.config.persist_run_state:
            return
        memory.save_json(
            "run_state.json",
            {
                "round": round_id,
                "status": status,
                "last_score": avg_score,
                "last_decision": decision,
                "blockers": blockers,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    def _human_checkpoint(self, record: RoundRecord) -> bool:
        self.console.print(
            f"[yellow]Checkpoint[/yellow] round={record.round_id} "
            f"avg={record.scorecard.average:.2f} decision={record.decision}"
        )
        answer = input("Continue? [Y/n]: ").strip().lower()
        return answer in {"", "y", "yes"}
