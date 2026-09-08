"""Run synthetic semantic controls against the real model, sequentially.

Expected answers stay in the fixture and are never passed to Runtime.
The caller supplies an existing parent account; no authorization is created.
"""
import argparse
import asyncio
import json
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv
from arc.cli import new_run, services
from arc.config import Settings
from arc.prompting import PromptLoader
from arc.pricing import PriceBook
from arc.runtime import Runtime, build_tools
from arc.scientific import review_and_revise
from arc.schemas import CardDraft, SourceRecord, EvidenceRecord
from arc.workflows import WorkflowEngine
from arc.reports import render_run


async def main(args):
    load_dotenv(args.env_file)
    settings = Settings(data_dir=args.data_dir, budget_cny=args.child_budget)
    store, ledger = services(settings)
    parent = ledger.summary(args.parent)
    if parent['reserved_micro'] or parent['unknown_calls']:
        raise RuntimeError('Parent has an in-flight or unsettled request; do not run concurrently.')
    cases = json.loads(args.fixture.read_text())['cases']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    prompt_root = args.data_dir/'artifacts'/'functional-pairs'/args.prefix/'prompts'
    if not prompt_root.exists():
        from importlib.resources import files
        shutil.copytree(Path(str(files('arc_prompt_assets'))), prompt_root,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    loader = PromptLoader(resource_root=prompt_root)
    prices = PriceBook(Path('configs/pricing.json'))
    results = []
    for index, case in enumerate(cases, 1):
        run_id = f'{args.prefix}.case{index}'
        # Pair identity and expected verdict are not model-visible.
        visible = json.loads(json.dumps(case['model_visible'], ensure_ascii=False))
        replacements = {x['source_id']: f'{run_id}.source{i}' for i, x in enumerate(visible['sources'])}
        replacements.update({x['evidence_id']: f'{run_id}.evidence{i}' for i, x in enumerate(visible['evidence'])})
        def rename(x):
            if isinstance(x, str): return replacements.get(x, x)
            if isinstance(x, list): return [rename(v) for v in x]
            if isinstance(x, dict): return {k: rename(v) for k, v in x.items()}
            return x
        visible = rename(visible)
        try:
            run = store.get_run(run_id)
        except Exception as exc:
            if str(exc) != 'run_missing': raise
            for source in visible['sources']:
                raw = dict(source)
                content = raw.pop('content')
                raw.setdefault('url', None)
                store.register_source(SourceRecord.model_validate(raw), content=content)
            for evidence in visible['evidence']:
                store.register_evidence(EvidenceRecord.model_validate(evidence))
            card = store.save_card(CardDraft.model_validate(visible['card']), creation_key=run_id+'.input')
            campaign = store.create_campaign(visible['original_task']['topic'],
                boundaries=visible['original_task']['boundaries'], max_draws=1, campaign_id=run_id+'.topic')
            run = new_run(settings, 'run', card_id=card.card_id, version=card.version,
                campaign_id=campaign.campaign_id, budget=args.child_budget, parent=args.parent, run_id=run_id)
        if run.status == 'COMPLETED':
            results.append({'case_id': case['case_id'], 'run_id': run_id, 'review': run.state['final_scientific_review'], 'cost': ledger.summary(run_id)})
            continue
        runtime = Runtime(store=store, ledger=ledger, account_id=run_id,
            loader=loader, role_models=settings.roles, prices=prices,
            api_key=os.environ['DEEPSEEK_API_KEY'], base_url=os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com'),
            tools={key: value for key, value in build_tools(store).items() if key in {'read_record', 'request_capability'}},
            on_progress=lambda event: print(json.dumps(event, ensure_ascii=False), flush=True))
        engine = WorkflowEngine(store, runtime, settings)
        try:
            store.update_run(run_id, status='RUNNING', stop_reason=None)
            card, review = await review_and_revise(engine, run_id, 'science', tool_profile=['read_record'])
            store.record_selection(run_id, card.card_id, card.version, review)
            engine.checkpoint(run_id, final_scientific_review=review.model_dump(mode='json'), final_scientific_card_version=card.version)
            engine.complete(run_id, 'synthetic_semantic_control', review.assessment)
            results.append({'case_id': case['case_id'], 'run_id': run_id, 'review': review.model_dump(mode='json'), 'cost': ledger.summary(run_id)})
        except Exception as exc:
            store.update_run(run_id, status=getattr(exc, 'status', 'PAUSED_PROTOCOL'), stop_reason=getattr(exc, 'reason', str(exc)))
            results.append({'case_id': case['case_id'], 'run_id': run_id, 'failure': str(exc), 'cost': ledger.summary(run_id)})
        finally:
            await runtime.close()
            render_run(store, run_id, args.data_dir/'reports'/run_id)
            args.output.write_text(json.dumps({'synthetic': True, 'results': results, 'parent': ledger.summary(args.parent)}, ensure_ascii=False, indent=2))
            print(json.dumps({'case_finished': case['case_id'], 'status': store.get_run(run_id).status, 'cost': ledger.summary(run_id)}, ensure_ascii=False), flush=True)
        if ledger.summary(args.parent)['unknown_calls']:
            break


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--parent', required=True)
    parser.add_argument('--prefix', required=True)
    parser.add_argument('--child-budget', default='200')
    parser.add_argument('--fixture', type=Path, default=Path('tests/fixtures/scientific_error_pairs.json'))
    parser.add_argument('--env-file', type=Path, default=Path('.env'))
    parser.add_argument('--output', type=Path, required=True)
    asyncio.run(main(parser.parse_args()))
