"""Explicit natural discover/develop/run steps using the ordinary ARC engine.

This script executes paid work only when invoked, one stage at a time. Importing
it has no side effects. Human/development selection is required between stages.
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv

from arc.cli import execute, new_run, services
from arc.config import Settings, load_settings
from arc.research_context import build_research_context
from arc.store import StateError

DEFAULT_MATERIAL_RUN = 'functional-20260908-early-stopping-material'
DEFAULT_PARENT = 'arc-vnext-validation-20260907'


def _ready(settings, prefix, stage, parent):
    store, ledger = services(settings)
    summary = ledger.summary(parent)  # Existing account, no new authorization.
    if summary['reserved_micro'] or summary['unknown_calls']:
        raise StateError('PARENT_HAS_UNSETTLED_CALLS: finish/reconcile the active task first')
    run_id = f'{prefix}.{stage}'
    try:
        store.get_run(run_id)
    except StateError as exc:
        if str(exc) != 'run_missing':
            raise
    else:
        raise StateError('RUN_ALREADY_EXISTS: use resume --stage ' + stage)
    return store, run_id


def prepare_discover(settings, *, prefix, parent=DEFAULT_PARENT, material_run=DEFAULT_MATERIAL_RUN):
    store, run_id = _ready(settings, prefix, 'discover', parent)
    material = build_research_context(store, store.get_run(material_run))
    task = material['original_task']
    if not task.get('topic') or not material['evidence']:
        raise StateError('MATERIAL_REQUIRES_ORIGINAL_TOPIC_AND_REGISTERED_EVIDENCE')
    run = new_run(settings, 'discover', topic=task['topic'], boundaries=task['boundaries'],
                  budget='200', parent=parent, run_id=run_id)
    # Share registered originals; never copy the preparation run's completion,
    # draw state, cards, recommendations or task results into generation.
    store.update_run(run_id, state={**run.state,
        'source_ids': [item['source_id'] for item in material['sources']],
        'evidence_ids': [item['evidence_id'] for item in material['evidence']],
        'natural_validation_material_run': material_run,
        'material_is_generation_result': False})
    return store.get_run(run_id)


def prepare_selected_stage(settings, *, prefix, stage, card_id, version, selection_reason, parent=DEFAULT_PARENT):
    if stage not in {'develop', 'run'} or not selection_reason.strip():
        raise ValueError('EXPLICIT_STAGE_AND_SELECTION_REASON_REQUIRED')
    store, run_id = _ready(settings, prefix, stage, parent)
    prior_stage = 'discover' if stage == 'develop' else 'develop'
    prior = store.get_run(f'{prefix}.{prior_stage}')
    if prior.status != 'COMPLETED':
        raise StateError('PREVIOUS_STAGE_NOT_COMPLETED')
    candidates = store.list_cards(run_id=prior.run_id)
    if not any(card.card_id == card_id and card.version == version for card in candidates):
        raise StateError('SELECTED_CARD_NOT_FROM_PREVIOUS_STAGE')
    latest_version = max(card.version for card in candidates if card.card_id == card_id)
    if version != latest_version:
        raise StateError('SELECT_LATEST_REVIEWED_CARD_VERSION')
    card = store.get_card(card_id, version)
    if card.selection == 'NOT_RETAINED' or card.assessment == 'REJECTED':
        raise StateError('REJECTED_CARD_REQUIRES_RESOLUTION: choose another card or resolve its review explicitly')
    if card.selection is None:
        raise StateError('SELECTED_CARD_HAS_NO_RECORDED_REVIEW')
    run = new_run(settings, stage, card_id=card_id, version=version, campaign_id=prior.campaign_id,
                  budget='200', parent=parent, run_id=run_id)
    store.update_run(run_id, state={**run.state, 'development_selection': {
        'source_run_id': prior.run_id, 'card_id': card_id, 'version': version,
        'reason': selection_reason, 'actor': 'development_codex_or_user',
        'production_codex_in_loop': False}})
    return store.get_run(run_id)


def resume_stage(settings, *, prefix, stage, parent=DEFAULT_PARENT):
    store, ledger = services(settings)
    run = store.get_run(f'{prefix}.{stage}')
    if ledger.summary(run.budget_account_id)['parent_id'] != parent:
        raise StateError('RESUME_PARENT_MISMATCH')
    summary = ledger.summary(parent)
    if summary['reserved_micro'] or summary['unknown_calls']:
        raise StateError('PARENT_HAS_UNSETTLED_CALLS')
    return run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--prefix', required=True)
    parser.add_argument('--parent', default=DEFAULT_PARENT)
    parser.add_argument('--env-file', type=Path, default=Path('.env'))
    parser.add_argument('--config', type=Path)
    actions = parser.add_subparsers(dest='action', required=True)
    discover = actions.add_parser('discover')
    discover.add_argument('--material-run', default=DEFAULT_MATERIAL_RUN)
    discover.add_argument('--draws', type=int, choices=range(1, 6), default=5)
    for stage in ('develop', 'run'):
        selected = actions.add_parser(stage)
        selected.add_argument('--card', required=True)
        selected.add_argument('--version', required=True, type=int)
        selected.add_argument('--selection-reason', required=True)
    resume = actions.add_parser('resume')
    resume.add_argument('--stage', choices=('discover', 'develop', 'run'), required=True)
    args = parser.parse_args()
    load_dotenv(args.env_file, override=False)
    settings = load_settings(args.config, data_dir=args.data_dir, budget_cny='200',
                             allow_stage_transition=False, draws=getattr(args, 'draws', 5))
    if args.action == 'discover':
        run = prepare_discover(settings, prefix=args.prefix, parent=args.parent, material_run=args.material_run)
    elif args.action == 'resume':
        run = resume_stage(settings, prefix=args.prefix, stage=args.stage, parent=args.parent)
    else:
        run = prepare_selected_stage(settings, prefix=args.prefix, stage=args.action,
            card_id=args.card, version=args.version, selection_reason=args.selection_reason, parent=args.parent)
    asyncio.run(execute(settings, run.run_id))


if __name__ == '__main__':
    main()
