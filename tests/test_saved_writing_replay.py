"""The development replay must not write through to saved research or budgets."""
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest
from arc.store import Store

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('rewrite_saved_reports', ROOT / 'scripts/rewrite_saved_reports.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def source(tmp_path):
    store = Store(tmp_path / 'source.sqlite', tmp_path / 'source_artifacts')
    store.create_run('discover', run_id='r1', state={'discover_first': True})
    reports = tmp_path / 'reports'
    (reports / 'r1').mkdir(parents=True)
    (reports / 'r1/REPORT.md').write_text('Saved report with its original limits.')
    return store, reports


def test_prepare_isolates_new_tasks_and_preserves_frozen_material(tmp_path):
    original, reports = source(tmp_path)
    old_run = original.get_run('r1').model_dump()
    out = tmp_path / 'rewrite'
    view, writer = replay.prepare(original.db_path, original.artifact_root, reports, out, ['r1'])
    assert view.get_run('r1').model_dump() == old_run
    writer.create_run('evaluation', run_id='new-writing')
    writer.save_artifact('new.txt', 'New writer response')
    assert not (original.artifact_root / 'new.txt').exists()
    with original._connect() as db:
        assert db.execute('SELECT id FROM runs').fetchall()[0][0] == 'r1'
        assert db.execute('SELECT COUNT(*) FROM runs').fetchone()[0] == 1
    payload = (out / 'r1/payload.json').read_text()
    original.update_run('r1', stop_reason='subsequent state must not replace frozen material')
    replay.prepare(original.db_path, original.artifact_root, reports, out, ['r1'])
    assert (out / 'r1/payload.json').read_text() == payload
    assert (out / 'r1/before/REPORT.md').read_text() == (reports / 'r1/REPORT.md').read_text()
    assert view.get_run('r1').model_dump() == old_run


def test_prepare_rejects_original_report_output_and_changed_run_set(tmp_path):
    original, reports = source(tmp_path)
    with pytest.raises(ValueError, match='OVERWRITE_SOURCE_REPORTS'):
        replay.prepare(original.db_path, original.artifact_root, reports, reports, ['r1'])
    out = tmp_path / 'rewrite'
    replay.prepare(original.db_path, original.artifact_root, reports, out, ['r1'])
    with pytest.raises(ValueError, match='REPLAY_INPUTS_CHANGED'):
        replay.prepare(original.db_path, original.artifact_root, reports, out, ['another-run'])

def test_writer_replay_has_no_research_tools_or_new_budget_authorization(tmp_path, monkeypatch):
    import argparse
    import asyncio
    from types import SimpleNamespace
    from arc.budget import BudgetLedger
    from arc.polishing import StagePolish
    original, reports = source(tmp_path)
    ledger = BudgetLedger(original.db_path)
    ledger.create_account('existing-authorization', '20')
    invocations = []

    class WriterOnlyRuntime:
        def __init__(self, **kwargs):
            assert kwargs['tools'] == {}
            assert kwargs['account_id'] == 'existing-authorization'
        async def invoke(self, role, task, payload, schema, subject, task_id, tool_profile):
            assert (role, task, schema, tool_profile) == ('writer', 'POLISH', StagePolish, [])
            assert subject.run_id == 'revision.r1' and subject.campaign_id is None
            invocations.append(task_id)
            return SimpleNamespace(result=StagePolish(stage_summary='Saved conclusion.', overview='Saved context.',
                candidates=[], cited_source_ids=[]), evidence_requests=[])
        async def close(self):
            pass

    monkeypatch.setattr(replay, 'Runtime', WriterOnlyRuntime)
    args = argparse.Namespace(source_db=original.db_path, source_artifacts=original.artifact_root,
        source_reports=reports, output_dir=tmp_path / 'rewrite', ledger_db=original.db_path,
        account_id='existing-authorization', revision_id='revision', run_ids=['r1'], prepare_only=False)
    asyncio.run(replay.replay(args))
    assert invocations == ['revision.r1.polish']
    assert original.get_run('r1').status == 'RUNNING'
    receipt = json.loads((args.output_dir / 'WRITER_USAGE.json').read_text())
    assert receipt['research_repeated'] is False and receipt['all_writer_calls'] == []
    assert 'Saved conclusion.' in (args.output_dir / 'r1/after/REPORT.md').read_text()
    with original._connect() as db:
        assert db.execute('SELECT COUNT(*) FROM budget_accounts').fetchone()[0] == 1
        assert db.execute('SELECT COUNT(*) FROM budget_authorizations').fetchone()[0] == 1

def test_one_protocol_failure_does_not_repeat_or_abort_independent_writing(tmp_path, monkeypatch):
    import argparse
    import asyncio
    from types import SimpleNamespace
    from arc.budget import BudgetLedger
    from arc.polishing import StagePolish
    from arc.runtime import RuntimePaused
    original, reports = source(tmp_path)
    original.create_run('discover', run_id='r2', state={'discover_first': True})
    (reports / 'r2').mkdir()
    (reports / 'r2/REPORT.md').write_text('Second saved report.')
    BudgetLedger(original.db_path).create_account('existing', '20')
    attempted = []

    class OneFailureRuntime:
        def __init__(self, **kwargs):
            pass
        async def invoke(self, role, task, payload, schema, subject, task_id, tool_profile):
            attempted.append(subject.run_id)
            if subject.run_id == 'revision.r1':
                raise RuntimePaused('PAUSED_PROTOCOL', 'SUBJECT_OR_TASK_MISMATCH')
            return SimpleNamespace(result=StagePolish(stage_summary='Saved conclusion.', overview='Context.',
                candidates=[], cited_source_ids=[]), evidence_requests=[])
        async def close(self):
            pass

    monkeypatch.setattr(replay, 'Runtime', OneFailureRuntime)
    args = argparse.Namespace(source_db=original.db_path, source_artifacts=original.artifact_root,
        source_reports=reports, output_dir=tmp_path / 'rewrite', ledger_db=original.db_path,
        account_id='existing', revision_id='revision', run_ids=['r1', 'r2'], prepare_only=False)
    asyncio.run(replay.replay(args))
    assert attempted == ['revision.r1', 'revision.r2']
    receipt = json.loads((args.output_dir / 'WRITER_USAGE.json').read_text())
    assert receipt['runs']['r1']['status'] == 'PAUSED_PROTOCOL'
    assert receipt['runs']['r1']['reason'] == 'SUBJECT_OR_TASK_MISMATCH'
    assert (args.output_dir / 'r2/after/REPORT.md').exists()
    assert Store(args.output_dir / 'snapshot.sqlite').get_run('revision.r1').status == 'PAUSED_PROTOCOL'
    assert original.get_run('r1').status == original.get_run('r2').status == 'RUNNING'
