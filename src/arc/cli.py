from __future__ import annotations

import os
import json
from typing import Optional
from pathlib import Path

import typer
import requests
from rich.console import Console

# Auto-load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()  # project .env
    load_dotenv(Path.home() / ".env", override=False)  # user-wide .env (e.g. DEEPXIV_TOKEN)
except ImportError:
    pass
from rich.table import Table

from arc.llm_client import LLMClient
from arc.model_registry import load_registry, load_runtime_roles, resolve_role_model, role_api_ready, set_role_model
from arc.run_paths import resolve_run_dir, sanitize_model_suffix
from arc.runners.debate_runner import run_debate
from arc.runners.chat_mode_runner import run_chat_mode
from arc.runners.pipeline_runner import run_pipeline
from arc.topic_refiner import build_topic_refine_report, refine_research_topic

app = typer.Typer(help="ARC - Adversarial Research Copilot")
models_app = typer.Typer(help="Model registry and role mapping")
app.add_typer(models_app, name="models")
console = Console()


def _ensure_known_model(role: str, model: str, registry) -> str:
    if model in registry.models:
        return model
    alias_key = f"{role}_default"
    fallback = registry.aliases.get(alias_key)
    if fallback and fallback in registry.models:
        console.print(
            f"[yellow]Warning:[/yellow] unknown model '{model}' for role '{role}', fallback to '{fallback}'."
        )
        return fallback
    if registry.models:
        first = next(iter(registry.models.keys()))
        console.print(
            f"[yellow]Warning:[/yellow] unknown model '{model}' for role '{role}', fallback to '{first}'."
        )
        return first
    raise typer.BadParameter("No model available in registry. Please check configs/models.yaml")


@app.command()
def run(
    idea_file: str = typer.Argument(...,
                                    help="Path to idea markdown/text file"),
    proposer: Optional[str] = typer.Option(None, help="Model for Proposer"),
    skeptic: Optional[str] = typer.Option(None, help="Model for Skeptic"),
    moderator: Optional[str] = typer.Option(None, help="Model for Moderator"),
    output_dir: str = typer.Option("reports", help="Output directory"),
    resume: bool = typer.Option(
        False, help="Resume from most recent run if run_state.json is available"),
    gpt_effort: str = typer.Option(
        "high", help="GPT reasoning effort: none|minimal|low|medium|high|xhigh"),
    gpt_verbosity: str = typer.Option(
        "medium", help="GPT output verbosity: low|medium|high"),
    prompt_language: str = typer.Option(
        "en", help="Prompt language for iterative discussion: en|zh"),
) -> None:
    os.environ["ARC_GPT_REASONING_EFFORT"] = gpt_effort
    os.environ["ARC_GPT_VERBOSITY"] = gpt_verbosity
    os.environ["ARC_PROMPT_LANGUAGE"] = prompt_language

    registry = load_registry()
    runtime = load_runtime_roles(registry)
    proposer_model = resolve_role_model(
        "proposer", registry, runtime, proposer)
    skeptic_model = resolve_role_model("skeptic", registry, runtime, skeptic)
    moderator_model = resolve_role_model(
        "moderator", registry, runtime, moderator)

    report_file, state_file = run_debate(
        idea_file=idea_file,
        proposer_model=proposer_model,
        skeptic_model=skeptic_model,
        moderator_model=moderator_model,
        output_dir=output_dir,
        resume=resume,
    )
    console.print(f"[bold green]Report:[/bold green] {report_file}")
    console.print(f"[bold green]State:[/bold green] {state_file}")


@app.command()
def pipeline(
    topic: str = typer.Argument(..., help="Research topic"),
    proposer: Optional[str] = typer.Option(
        None,
        help="Model for generation stages (default: proposer)",
    ),
    skeptic: Optional[str] = typer.Option(
        None,
        help="Model for novelty check / review (default: skeptic)",
    ),
    moderator: Optional[str] = typer.Option(
        None,
        help="Model for debate moderator",
    ),
    output_dir: str = typer.Option("reports", help="Output directory"),
    resume: bool = typer.Option(
        False, help="Resume from most recent run if pipeline_state.json is available"),
    strict_gates: bool = typer.Option(
        True,
        "--strict-gates/--no-strict-gates",
        help="Enforce mandatory pipeline gates (novelty-check, debate-runner)",
    ),
    checkpoint: bool = typer.Option(
        False, help="Ask for confirmation after each completed stage"),
    gpt_effort: str = typer.Option(
        "high", help="GPT reasoning effort: none|minimal|low|medium|high|xhigh"),
    gpt_verbosity: str = typer.Option(
        "medium", help="GPT output verbosity: low|medium|high"),
) -> None:
    os.environ["ARC_GPT_REASONING_EFFORT"] = gpt_effort
    os.environ["ARC_GPT_VERBOSITY"] = gpt_verbosity

    registry = load_registry()
    runtime = load_runtime_roles(registry)
    writer_model = resolve_role_model(
        "pipeline_writer", registry, runtime, proposer)
    reviewer_model = resolve_role_model(
        "pipeline_reviewer", registry, runtime, skeptic)
    pipeline_moderator_model = resolve_role_model(
        "pipeline_moderator", registry, runtime, moderator)

    state_file, memo_file = run_pipeline(
        topic=topic,
        proposer_model=writer_model,
        skeptic_model=reviewer_model,
        moderator_model=pipeline_moderator_model,
        output_dir=output_dir,
        resume=resume,
        strict_gates=strict_gates,
        human_checkpoint=checkpoint,
    )
    console.print(f"[bold green]Pipeline state:[/bold green] {state_file}")
    console.print(f"[bold green]Final memo:[/bold green] {memo_file}")


@app.command("explain-outputs")
def explain_outputs(
    run_dir: Optional[str] = typer.Option(
        None, help="Run directory path, e.g. reports/20260323_191404"),
    output_dir: str = typer.Option("reports", help="Reports root directory"),
) -> None:
    root = Path(output_dir)
    target: Optional[Path] = None
    if run_dir:
        candidate = Path(run_dir)
        target = candidate if candidate.is_absolute() else Path.cwd() / candidate
    else:
        marker = root / "LATEST_RUN"
        if marker.exists():
            try:
                name = marker.read_text(encoding="utf-8").strip()
                if name:
                    target = root / name
            except Exception:
                target = None

    if target is None or not target.exists() or not target.is_dir():
        raise typer.BadParameter(
            "Cannot find run directory. Provide --run-dir or ensure reports/LATEST_RUN exists.")

    index_file = target / "OUTPUT_INDEX.md"
    if index_file.exists():
        console.print(f"[bold green]Output index:[/bold green] {index_file}")
        console.print(index_file.read_text(encoding="utf-8"))
        return

    files = sorted([p.name for p in target.iterdir() if p.is_file()])
    table = Table(title=f"Artifacts in {target}")
    table.add_column("file")
    table.add_column("purpose")
    purpose_map = {
        "TOPIC.txt": "Input research task",
        "REFERENCES.md": "Unified references with abstracts",
        "LITERATURE_MAP.md": "Literature mapping",
        "IDEA_REPORT.md": "Candidate ideas",
        "FINAL_PROPOSAL.md": "Final proposal",
        "EVIDENCE_TABLE.md": "Claim-evidence table",
        "EXPERIMENT_PLAN.md": "Experiment plan",
        "RESEARCH_DECISION_MEMO.md": "Final discussion memo",
        "AUTO_REVIEW.md": "Auto-review logs",
        "pipeline_state.json": "Pipeline state",
    }
    for f in files:
        table.add_row(f, purpose_map.get(f, "auxiliary artifact"))
    console.print(table)


@app.command("chat-mode")
def chat_mode(
    topic: str = typer.Argument(..., help="Brainstorm topic"),
    proposer: Optional[str] = typer.Option(None, help="Model for Proposer"),
    skeptic: Optional[str] = typer.Option(None, help="Model for Skeptic"),
    moderator: Optional[str] = typer.Option(None, help="Model for Moderator"),
    output_dir: str = typer.Option("reports", help="Output directory"),
    resume: bool = typer.Option(False, help="Resume from latest run directory"),
    min_rounds_before_stop: Optional[int] = typer.Option(
        None,
        help="Minimum rounds before judge is allowed to stop (default: configs/chat_mode.yaml)",
    ),
    max_rounds: Optional[int] = typer.Option(
        None,
        help="Advisory round target; judge decision still controls stop. 0 disables the hint. (default: configs/chat_mode.yaml)",
    ),
    export_best_consensus: Optional[bool] = typer.Option(
        None,
        "--export-best-consensus/--no-export-best-consensus",
        help="Generate BEST_CONSENSUS.md automatically (default: configs/chat_mode.yaml)",
    ),
    gpt_effort: str = typer.Option(
        "medium", help="GPT reasoning effort: none|minimal|low|medium|high|xhigh"),
    gpt_verbosity: str = typer.Option(
        "high", help="GPT output verbosity: low|medium|high"),
    prompt_language: str = typer.Option(
        "en", help="Prompt language for chat iteration: en|zh"),
    max_review_cycles: Optional[int] = typer.Option(
        None, help="Maximum review cycles (outer loop). 0 = unlimited. (default: configs/chat_mode.yaml)"),
    max_inner_rounds: Optional[int] = typer.Option(
        None, help="Maximum inner debate rounds per review cycle. 0 = unlimited. (default: configs/chat_mode.yaml)"),
    drift_interval: Optional[int] = typer.Option(
        None, help="Run drift monitor every N inner rounds. (default: configs/chat_mode.yaml)"),
) -> None:
    os.environ["ARC_GPT_REASONING_EFFORT"] = gpt_effort
    os.environ["ARC_GPT_VERBOSITY"] = gpt_verbosity
    os.environ["ARC_PROMPT_LANGUAGE"] = prompt_language

    registry = load_registry()
    runtime = load_runtime_roles(registry)
    proposer_model = resolve_role_model("proposer", registry, runtime, proposer)
    skeptic_model = resolve_role_model("skeptic", registry, runtime, skeptic)
    moderator_model = resolve_role_model("moderator", registry, runtime, moderator)
    proposer_model = _ensure_known_model("proposer", proposer_model, registry)
    skeptic_model = _ensure_known_model("skeptic", skeptic_model, registry)
    moderator_model = _ensure_known_model("moderator", moderator_model, registry)

    transcript_file, state_file = run_chat_mode(
        topic=topic,
        proposer_model=proposer_model,
        skeptic_model=skeptic_model,
        moderator_model=moderator_model,
        output_dir=output_dir,
        resume=resume,
        min_rounds_before_stop=min_rounds_before_stop,
        max_rounds=max_rounds,
        export_best_consensus=export_best_consensus,
        prompt_language=prompt_language,
        max_review_cycles=max_review_cycles,
        max_inner_debate_rounds=max_inner_rounds,
        drift_check_interval=drift_interval,
    )
    console.print(f"[bold green]Chat transcript:[/bold green] {transcript_file}")
    console.print(f"[bold green]Chat state:[/bold green] {state_file}")
    consensus_file = transcript_file.parent / "BEST_CONSENSUS.md"
    if consensus_file.exists():
        console.print(f"[bold green]Best consensus:[/bold green] {consensus_file}")


@app.command("discover")
def discover(
    topic: str = typer.Argument(..., help="Research field or rough topic to mine for novel problems"),
    proposer: Optional[str] = typer.Option(
        None, help="Generator model (default: proposer role, deepseek-v4-flash)"),
    moderator: Optional[str] = typer.Option(
        None, help="Judge model (default: moderator role, deepseek-v4-pro)"),
    output_dir: str = typer.Option("reports", help="Output directory"),
    resume: bool = typer.Option(False, help="Resume from latest discover run if in progress"),
    papers: Optional[int] = typer.Option(
        None, help="Reranked paper pool size (default: configs/discover.yaml)"),
    deep_read: Optional[int] = typer.Option(
        None, help="Top papers to deep-read (default: configs/discover.yaml)"),
    ideas: Optional[int] = typer.Option(
        None, help="Candidate ideas to compose (default: configs/discover.yaml)"),
    stress_test: bool = typer.Option(
        False, "--stress-test/--no-stress-test",
        help="Run chat-mode stress tests on top KEEP ideas after the report"),
    stress_rounds: Optional[int] = typer.Option(
        None, help="Max rounds per stress-test debate (default: configs/discover.yaml)"),
    prompt_language: str = typer.Option("en", help="Prompt language: en|zh"),
) -> None:
    os.environ["ARC_PROMPT_LANGUAGE"] = prompt_language

    registry = load_registry()
    runtime = load_runtime_roles(registry)
    generator_model = resolve_role_model("proposer", registry, runtime, proposer)
    judge_model = resolve_role_model("moderator", registry, runtime, moderator)
    generator_model = _ensure_known_model("proposer", generator_model, registry)
    judge_model = _ensure_known_model("moderator", judge_model, registry)

    from arc.runners.discover_runner import run_discover

    report_file, state_file = run_discover(
        topic=topic,
        generator_model=generator_model,
        judge_model=judge_model,
        output_dir=output_dir,
        resume=resume,
        papers=papers,
        deep_read=deep_read,
        ideas=ideas,
        stress_test=stress_test,
        stress_rounds=stress_rounds,
        prompt_language=prompt_language,
    )
    console.print(f"[bold green]Discovery report:[/bold green] {report_file}")
    console.print(f"[bold green]Discover state:[/bold green] {state_file}")


@app.command("refine-topic")
def refine_topic_cmd(
    topic: str = typer.Argument(..., help="Raw research problem statement"),
    proposer: Optional[str] = typer.Option(
        None, help="Writer model (default: pipeline_writer role)"),
    skeptic: Optional[str] = typer.Option(
        None, help="Reviewer model (default: pipeline_reviewer role)"),
    output_dir: str = typer.Option("reports", help="Output directory"),
    rounds: int = typer.Option(2, help="Refinement rounds"),
    run_pipeline_after: bool = typer.Option(
        False, help="Start pipeline with refined topic after refinement"),
    gpt_effort: str = typer.Option(
        "high", help="GPT reasoning effort: none|minimal|low|medium|high|xhigh"),
    gpt_verbosity: str = typer.Option(
        "medium", help="GPT output verbosity: low|medium|high"),
    prompt_language: str = typer.Option(
        "en", help="Prompt language for iterative refinement: en|zh"),
) -> None:
    os.environ["ARC_GPT_REASONING_EFFORT"] = gpt_effort
    os.environ["ARC_GPT_VERBOSITY"] = gpt_verbosity
    os.environ["ARC_PROMPT_LANGUAGE"] = prompt_language

    registry = load_registry()
    runtime = load_runtime_roles(registry)
    writer_model = resolve_role_model(
        "pipeline_writer", registry, runtime, proposer)
    reviewer_model = resolve_role_model(
        "pipeline_reviewer", registry, runtime, skeptic)
    moderator_model = resolve_role_model(
        "pipeline_moderator", registry, runtime, None)

    run_dir = resolve_run_dir(output_dir, resume=False,
                              state_file_name="topic_refine_state.json",
                              model_suffix=sanitize_model_suffix(writer_model, reviewer_model))
    client = LLMClient()
    refined, history = refine_research_topic(
        client=client,
        writer_model=writer_model,
        reviewer_model=reviewer_model,
        topic=topic,
        rounds=rounds,
        prompt_language=prompt_language,
    )

    original_file = run_dir / "TOPIC_RAW.md"
    refined_file = run_dir / "TOPIC_REFINED.md"
    report_file = run_dir / "TOPIC_REFINEMENT_REPORT.md"
    state_file = run_dir / "topic_refine_state.json"

    original_file.write_text(topic.strip() + "\n", encoding="utf-8")
    refined_file.write_text(refined.strip() + "\n", encoding="utf-8")
    report_file.write_text(build_topic_refine_report(
        topic, refined, history), encoding="utf-8")
    state_file.write_text(
        json.dumps(
            {
                "status": "completed",
                "writer_model": writer_model,
                "reviewer_model": reviewer_model,
                "rounds": len(history),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    console.print(f"[bold green]Refined topic:[/bold green] {refined}")
    console.print(f"[bold green]Artifacts:[/bold green] {run_dir}")

    if run_pipeline_after:
        pipeline_state, memo = run_pipeline(
            topic=refined,
            proposer_model=writer_model,
            skeptic_model=reviewer_model,
            moderator_model=moderator_model,
            output_dir=output_dir,
            resume=False,
            strict_gates=True,
            human_checkpoint=False,
        )
        console.print(
            f"[bold green]Pipeline state:[/bold green] {pipeline_state}")
        console.print(f"[bold green]Final memo:[/bold green] {memo}")


@models_app.command("list")
def models_list() -> None:
    registry = load_registry()
    runtime = load_runtime_roles(registry)

    table = Table(title="Available models")
    table.add_column("name")
    table.add_column("provider")
    table.add_column("endpoint")
    table.add_column("base_url_env")
    table.add_column("api_key_env")
    for name, spec in registry.models.items():
        table.add_row(name, spec.provider, spec.endpoint,
                      spec.base_url_env, spec.api_key_env)
    console.print(table)

    role_table = Table(title="Current role mapping")
    role_table.add_column("role")
    role_table.add_column("model")
    for role, model in runtime.model_dump().items():
        ready, reason = role_api_ready(model, registry)
        status = "ready" if ready else reason
        role_table.add_row(role, f"{model} ({status})")
    console.print(role_table)


@models_app.command("set")
def models_set(
    role: str = typer.Argument(
        ..., help="Role: proposer|skeptic|moderator|pipeline_writer|pipeline_reviewer|pipeline_moderator"),
    model: str = typer.Argument(..., help="Model name from registry"),
) -> None:
    registry = load_registry()
    valid_roles = {
        "proposer",
        "skeptic",
        "moderator",
        "pipeline_writer",
        "pipeline_reviewer",
        "pipeline_moderator",
    }
    if role not in valid_roles:
        raise typer.BadParameter(f"Unknown role: {role}")

    cfg = set_role_model(role=role, model_name=model, registry=registry)
    console.print(f"[green]Updated[/green] {role} -> {getattr(cfg, role)}")


@models_app.command("doctor")
def models_doctor(
    online: bool = typer.Option(
        False, help="Run real API smoke tests for mapped role models"),
) -> None:
    registry = load_registry()
    runtime = load_runtime_roles(registry)

    table = Table(title="Model doctor")
    table.add_column("role")
    table.add_column("model")
    table.add_column("config")
    table.add_column("online")

    client = LLMClient() if online else None
    for role, model in runtime.model_dump().items():
        ready, reason = role_api_ready(model, registry)
        online_result = "skipped"
        if online and ready and client is not None:
            try:
                _ = client.chat(
                    model=model,
                    system_prompt="You are a concise assistant.",
                    user_prompt="Return exactly: OK",
                    temperature=0.0,
                )
                online_result = "ok"
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else "?"
                body = ""
                if e.response is not None:
                    body = (e.response.text or "").replace("\n", " ")[:80]
                online_result = f"http:{status}:{body}" if body else f"http:{status}"
            except Exception as e:
                online_result = f"fail:{type(e).__name__}"
        elif online and not ready:
            online_result = "not-configured"

        table.add_row(
            role, model, reason if not ready else "ready", online_result)

    console.print(table)


if __name__ == "__main__":
    app()
