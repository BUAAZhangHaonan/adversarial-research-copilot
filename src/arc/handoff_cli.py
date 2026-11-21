"""Structured CLI for selected external research ideas. All inputs are data."""
from __future__ import annotations

import asyncio
import json
import sys
from contextlib import redirect_stdout

import typer

from .external_idea import SelectedIdea
from .handoff import handoff_lock, handoff_record, import_selected
from .handoff_result import export_result
from .schemas import utc_now

commands = typer.Typer(no_args_is_help=True, help="导入一个选定的研究想法并执行单个轻量预研阶段。")


def output(value):
    typer.echo(json.dumps(value, ensure_ascii=False, default=str))


@commands.command(name="import")
def import_idea(ctx: typer.Context):
    """Read a frozen radar.arc.selected-idea.v1 object from standard input."""
    from .cli import services
    from pydantic import ValidationError
    try:
        request = SelectedIdea.model_validate_json(sys.stdin.read())
    except ValidationError as exc:
        # Report field paths; input text or credentials do not belong in diagnostics.
        failures = [{"field":e["loc"], "type":e["type"]} for e in exc.errors(include_input=False)]
        raise typer.BadParameter(json.dumps(failures,ensure_ascii=False)) from None
    body = import_selected(ctx.obj, request)
    store, ledger = services(ctx.obj)
    output(export_result(store, ledger, body["handoff_id"]))


@commands.command(name="result")
def result(ctx: typer.Context, handoff_id: str):
    """Return status, current scientific note, original Chinese presentation and sources."""
    from .cli import services
    store, ledger = services(ctx.obj)
    output(export_result(store, ledger, handoff_id))


@commands.command(name="execute")
def execute_stage(ctx: typer.Context, handoff_id: str):
    """Execute or recover this exact stage. A concurrent invocation only returns status."""
    from .cli import services, execute
    store, ledger = services(ctx.obj)
    body = handoff_record(store, handoff_id)
    try:
        with handoff_lock(store, handoff_id, wait=False):
            run = store.get_run(body["run_id"])
            if run.status in {"RUNNING","PAUSED_EXTERNAL"}:
                with store._transaction() as db:
                    db.execute("INSERT OR IGNORE INTO handoff_executions VALUES(?,?)", (handoff_id, utc_now()))
                # The regular CLI prints progress; the final stdout frame stays machine-readable.
                with redirect_stdout(sys.stderr):
                    try:
                        asyncio.run(execute(ctx.obj, run.run_id))
                    except Exception:
                        if store.get_run(run.run_id).status != "ERROR":
                            raise
    except BlockingIOError:
        pass
    output(export_result(store, ledger, handoff_id))
