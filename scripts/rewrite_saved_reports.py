"""Development-only writer replay on a snapshot; never resumes research stages.

A source database, existing account and explicit run IDs are required. The only
live writes are new calls in the existing ledger. Original research/report rows
are read through a SQLite snapshot; writer tasks and outputs live in output_dir.
"""
from __future__ import annotations
import argparse
import asyncio
import json
from pathlib import Path
import shutil
import sqlite3

from arc.budget import BudgetLedger
from arc.config import load_settings
from arc.polishing import StagePolish, build_polish_payload, validate_polish
from arc.pricing import PriceBook
from arc.prompting import PromptLoader
from arc.reports import render_discovery_run
from arc.runtime import Runtime
from arc.schemas import Subject
from arc.store import Store


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def prepare(source_db, source_artifacts, source_reports, output_dir, run_ids):
    source_db, output_dir = Path(source_db).resolve(), Path(output_dir).resolve()
    if source_db == output_dir / 'snapshot.sqlite':
        raise ValueError('OUTPUT_MUST_BE_SEPARATE')
    if output_dir == Path(source_reports).resolve() or output_dir.is_relative_to(Path(source_reports).resolve()):
        raise ValueError('OUTPUT_MUST_NOT_OVERWRITE_SOURCE_REPORTS')
    output_dir.mkdir(parents=True, exist_ok=True)
    identity = {'source_db': str(source_db), 'run_ids': run_ids,
                'source_artifacts': str(Path(source_artifacts).resolve()),
                'source_reports': str(Path(source_reports).resolve())}
    manifest = output_dir / 'INPUTS.json'
    if manifest.exists():
        if json.loads(manifest.read_text()) != identity:
            raise ValueError('REPLAY_INPUTS_CHANGED')
    else:
        dump(manifest, identity)
    snapshot = output_dir / 'snapshot.sqlite'
    if not snapshot.exists():
        temporary = output_dir / 'snapshot.partial.sqlite'
        with sqlite3.connect(source_db.as_uri() + '?mode=ro', uri=True) as source:
            with sqlite3.connect(temporary) as target:
                source.backup(target)
        temporary.replace(snapshot)
    source_view = Store(snapshot, source_artifacts)
    for run_id in run_ids:
        source_view.get_run(run_id)
        folder = output_dir / run_id
        folder.mkdir(exist_ok=True)
        payload_file = folder / 'payload.json'
        if not payload_file.exists():
            dump(payload_file, build_polish_payload(source_view, run_id))
        if not (folder / 'before').exists():
            shutil.copytree(Path(source_reports) / run_id, folder / 'before')
    return source_view, Store(snapshot, output_dir / 'writer_artifacts')


async def replay(args):
    source_view, writer_store = prepare(args.source_db, args.source_artifacts,
        args.source_reports, args.output_dir, args.run_ids)
    root = Path(__file__).resolve().parents[1]
    loader = PromptLoader(root / 'prompts')
    settings = load_settings(root / 'configs/runtime.yaml')
    ledger = BudgetLedger(args.ledger_db)
    summary = ledger.summary(args.account_id)  # Does not create/increase authorization.
    if summary['unknown_calls'] or summary['reserved_micro']:
        raise ValueError('EXISTING_ACCOUNT_HAS_UNSETTLED_CALLS')
    output_dir = Path(args.output_dir).resolve()
    receipt_path = output_dir / 'WRITER_USAGE.json'
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {
        'account_id': args.account_id, 'ledger_db': str(Path(args.ledger_db).resolve()),
        'budget_before': summary, 'research_repeated': False, 'tools': [], 'runs': {}}
    if (receipt['account_id'], receipt['ledger_db']) != (args.account_id, str(Path(args.ledger_db).resolve())):
        raise ValueError('REPLAY_BUDGET_ACCOUNT_CHANGED')
    dump(receipt_path, receipt)
    if args.prepare_only:
        print(json.dumps({'prepared': args.run_ids, 'account': summary}, ensure_ascii=False), flush=True)
        return
    runtime = Runtime(store=writer_store, ledger=ledger, account_id=args.account_id,
        loader=loader, role_models=settings.roles, models=settings.models,
        prices=PriceBook(settings.pricing_path or root / 'configs/pricing.json'), tools={})
    try:
        for run_id in args.run_ids:
            folder = output_dir / run_id
            payload = json.loads((folder / 'payload.json').read_text())
            task_run_id = args.revision_id + '.' + run_id
            with writer_store._connect() as db:
                existing = db.execute('SELECT id FROM runs WHERE id=?', (task_run_id,)).fetchone()
            if not existing:
                writer_store.create_run('evaluation', run_id=task_run_id,
                    budget_account_id=args.account_id, config=settings.model_dump(mode='json'),
                    state={'source_run_id': run_id, 'research_repeated': False})
            task_id = task_run_id + '.polish'
            print(json.dumps({'event': 'writer_started', 'run_id': run_id}), flush=True)
            envelope = await runtime.invoke('writer', 'POLISH', payload, StagePolish,
                Subject(run_id=task_run_id, campaign_id=None, card_id=None, card_version=None), task_id, tool_profile=[])
            if envelope.result is None or envelope.evidence_requests:
                raise ValueError('WRITER_MUST_RETURN_PROSE_WITHOUT_RESEARCH_REQUESTS')
            result = validate_polish(envelope.result, payload)
            dump(folder / 'writer_result.json', result.model_dump(mode='json'))
            writer_store.update_run(task_run_id, status='COMPLETED',
                stop_reason='writer_only_saved_material_revision',
                state={'source_run_id': run_id, 'research_repeated': False, 'polish': result.model_dump(mode='json')})
            render_discovery_run(source_view, run_id, folder / 'after', loader,
                polish_override=result, polish_payload=payload)
            calls = [c for c in ledger.list_calls(args.account_id) if c['run_id'] == task_run_id]
            receipt['runs'][run_id] = {'task_id': task_id, 'calls': calls,
                'candidate_count': len(result.candidates), 'output_dir': str(folder / 'after')}
            receipt['budget_after'] = ledger.summary(args.account_id)
            dump(receipt_path, receipt)
            print(json.dumps({'event': 'writer_completed', 'run_id': run_id,
                'calls': len(calls), 'cost_upper_cny': sum(float(c['cost_estimate_upper'] or 0) for c in calls)}, ensure_ascii=False), flush=True)
    finally:
        receipt['all_writer_calls'] = [c for c in ledger.list_calls(args.account_id)
            if c['run_id'] in {args.revision_id + '.' + rid for rid in args.run_ids}]
        receipt['budget_after'] = ledger.summary(args.account_id)
        dump(receipt_path, receipt)
        await runtime.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['source-db', 'source-artifacts', 'source-reports', 'output-dir', 'ledger-db', 'account-id', 'revision-id']:
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('run_ids', nargs='+')
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    asyncio.run(replay(args))


if __name__ == '__main__':
    main()
