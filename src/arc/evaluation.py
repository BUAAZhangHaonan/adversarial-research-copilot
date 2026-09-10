"""Explicit development chaining, frozen evidence and anonymous comparison helpers."""
from __future__ import annotations
import json
import hashlib
import random

VALIDATION_PARENT = 'arc-vnext-validation-20260907'


def anonymous_candidates(candidates, seed=20260907):
    indexed = list(enumerate(candidates))
    random.Random(seed).shuffle(indexed)
    presented, identity = [], {}
    for number, (original, candidate) in enumerate(indexed, 1):
        identifier = f'candidate_{number}'
        # Only the research object is passed. Identity, roles, scores and verdicts
        # belong in the private mapping, not evaluator context.
        presented.append({'candidate_id': identifier, 'research_card': candidate['draft']})
        identity[identifier] = {'index': original, 'system': candidate['system']}
    return presented, identity


async def run_e2e(settings, campaign_name, topic, total_budget):
    from .cli import services, new_run, execute
    from .store import StateError
    store, ledger = services(settings)
    ledger.create_account(VALIDATION_PARENT, total_budget)
    # Stable IDs deliberately resume prior attempts and preserve the same parent.
    prefix = f'{VALIDATION_PARENT}.{campaign_name}'
    discover_id = prefix + '.discover'
    try:
        discovery = store.get_run(discover_id)
    except StateError:
        discovery = new_run(settings, 'discover', topic=topic, budget='20',
            parent=VALIDATION_PARENT, run_id=discover_id)
    if store.get_campaign(discovery.campaign_id).topic != topic:
        raise ValueError('E2E_CAMPAIGN_TOPIC_MISMATCH')
    discovery = await execute(settings, discovery.run_id)
    result = {'L2': {'discover': discovery.status}, 'L3': 'not_completed',
              'selected_card': None, 'parent': VALIDATION_PARENT}
    retained = [d for d in discovery.state.get('draws', {}).values()
                if d.get('selection', {}).get('selection') == 'MAIN_REPORT']
    if discovery.status == 'COMPLETED' and retained:
        chosen = retained[0]
        result['selected_card'] = {'card_id': chosen['card_id'], 'version': chosen['card_version'],
                                   'selection_method': 'explicit_development_first_retained'}
        previous = None
        for mode in ('develop', 'run'):
            run_id = prefix + '.' + mode
            version = chosen['card_version'] if previous is None else previous.card_version
            try:
                stage = store.get_run(run_id)
            except StateError:
                stage = new_run(settings, mode, card_id=chosen['card_id'], version=version,
                    budget='20', parent=VALIDATION_PARENT, run_id=run_id,
                    campaign_id=discovery.campaign_id)
            previous = await execute(settings, stage.run_id)
            result['L2'][mode] = previous.status
            if previous.status != 'COMPLETED' or (mode == 'develop' and previous.assessment != 'PROMISING'):
                result['L3'] = 'stopped_at_' + mode
                break
        else:
            result['L3'] = 'natural_card_chain_completed'
            result['assessment'] = previous.assessment
    result['cost'] = ledger.summary(VALIDATION_PARENT)
    target = settings.data_dir / 'E2E_RESULT.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    return result


async def _frozen_call(store, runtime, run_id, key, role, task='INVOKE', payload=None):
    """Only judge the frozen material; never expand an evidence request online."""
    from .schemas import Envelope, Subject, RESULT_SCHEMAS
    from .workflows import WorkflowPause
    run = store.get_run(run_id)
    schema = RESULT_SCHEMAS[f'{role}.{task}' if role == 'discovery' else role]
    envelopes = dict(run.state.get('comparison_envelopes', {}))
    if key in envelopes:
        envelope = Envelope[schema].model_validate(envelopes[key])
    else:
        physical_key = key
        retries = run.state.get('comparison_task_retries', {}).get(key, [])
        if retries:
            audit = json.loads(store.read_artifact(retries[-1]['audit_path']))
            subject = {'campaign_id': run.campaign_id, 'run_id': run_id,
                       'card_id': run.card_id, 'card_version': run.card_version}
            if audit['subject'] != subject:
                from .validation import ProtocolViolation
                raise ProtocolViolation('COMPARISON_RETRY_SUBJECT_CHANGED')
            physical_key = audit['replacement_key']
            payload = {**(payload or {}), 'protocol_retry': audit['protocol_retry']}
        envelope = await runtime.invoke(role=role, task=task, payload=payload or {},
            result_schema=schema, subject=Subject(campaign_id=run.campaign_id, run_id=run_id,
                card_id=run.card_id, card_version=run.card_version),
            task_id=f'{run_id}.{physical_key}', tool_profile=[])
        envelopes[key] = envelope.model_dump(mode='json')
        state = {**store.get_run(run_id).state, 'comparison_envelopes': envelopes}
        store.update_run(run_id, state=state)
    if envelope.result_status != 'complete':
        raise WorkflowPause('PAUSED_EXTERNAL', f'frozen_material_{envelope.result_status}')
    return envelope.result


def _record_failure(store, run_id, exc):
    from .validation import ProtocolViolation
    status = 'PAUSED_PROTOCOL' if isinstance(exc, ProtocolViolation) else getattr(exc, 'status', 'ERROR')
    if status not in {'PAUSED_PROTOCOL', 'PAUSED_EXTERNAL', 'PAUSED_BUDGET'}:
        status = 'ERROR'
    store.update_run(run_id, status=status, stop_reason=getattr(exc, 'reason', None) or str(exc))


async def run_comparison(settings, source_run_id, *, seed=20260907, include_swapped_order=False):
    from .cli import services, new_run
    from .bootstrap import make_runtime
    from .workflows import data
    from .store import StateError
    from .validation import ProtocolViolation, validate_selection
    store, ledger = services(settings)
    from .budget import BudgetError
    try:
        ledger.summary(VALIDATION_PARENT)
    except BudgetError as exc:
        if str(exc) != 'account_missing':
            raise
        ledger.create_account(VALIDATION_PARENT, '100')
    source_run = store.get_run(source_run_id)
    campaign = store.get_campaign(source_run.campaign_id)
    frozen_path = f'evaluations/{source_run_id}/evidence.json'
    try:
        frozen_text = store.read_artifact(frozen_path)
    except FileNotFoundError:
        source_ids = source_run.state.get('source_ids', [])
        evidence_ids = source_run.state.get('evidence_ids', [])
        sources = [store.get_record(identifier) for identifier in source_ids]
        for source in sources:
            if source.get('content_path'):
                source['content'] = store.read_artifact(source['content_path'])
        material = {'topic': campaign.topic, 'boundaries': campaign.boundaries,
            'mandate': source_run.state.get('frame', {}).get('mandate'), 'sources': sources,
            'evidence': [store.get_record(identifier) for identifier in evidence_ids]}
        material_bytes = json.dumps(material, ensure_ascii=False, sort_keys=True).encode('utf-8')
        frozen_text = json.dumps({'material': material,
            'sha256': hashlib.sha256(material_bytes).hexdigest()}, ensure_ascii=False)
        store.save_artifact(frozen_path, frozen_text)
    manifest = json.loads(frozen_text)
    frozen = manifest['material']
    if 'boundaries' not in frozen:
        raise ProtocolViolation('COMPARISON_MATERIAL_PROTOCOL_MISMATCH_MISSING_BOUNDARIES')
    material_hash = hashlib.sha256(json.dumps(frozen, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
    if material_hash != manifest['sha256']:
        raise ProtocolViolation('COMPARISON_MATERIAL_HASH_MISMATCH')
    if not frozen['evidence']:
        raise ValueError('COMPARISON_REQUIRES_FROZEN_EVIDENCE')
    # Derive shared task context from the immutable material, not a later live
    # campaign or a candidate's self-authored problem anchor.
    original_task = {'topic': frozen['topic'], 'boundaries': frozen['boundaries'],
                     'proposal_details_are_user_constraints': False}
    frozen = {**frozen, 'original_task': original_task, 'mandate': frozen.get('mandate')}
    candidates = []
    for system in ('ARC', 'direct-Pro'):
        config = settings if system == 'ARC' else settings.model_copy(update={
            'roles': {role: settings.research_model for role in settings.roles}})
        run_id = source_run_id + '.comparison.' + system
        try:
            run = store.get_run(run_id)
        except StateError:
            run = new_run(config, 'evaluation', budget=settings.budget_cny, parent=VALIDATION_PARENT, run_id=run_id)
        config = type(settings).model_validate(run.config)
        runtime = await make_runtime(store, ledger, run, config)
        draft = judgments = None
        task_context = dict(frozen)
        store.update_run(run_id, status='RUNNING', stop_reason=None)
        try:
            if system == 'ARC':
                frame = await _frozen_call(store, runtime, run_id, 'frame', 'discovery', 'FRAME', frozen)
                family = await _frozen_call(store, runtime, run_id, 'family', 'discovery', 'NEXT_DRAW',
                    {**frozen, 'mandate': data(frame.mandate), 'previous_draws': {}})
                if family.continue_or_stop == 'STOP':
                    store.update_run(run_id, status='COMPLETED', stop_reason='no_distinct_direction')
                    candidates.append({'system': system, 'draft': None, 'judgment': None,
                        'status': 'COMPLETED', 'stop_reason': 'no_distinct_direction',
                        'cost': ledger.summary(run_id)})
                    continue
                if not family.proposed_family or not family.anchor_evidence_ids:
                    raise ProtocolViolation('COMPARISON_DIRECTION_REQUIRES_EVIDENCE_ANCHOR')
                approved = data(family)
                task_context['mandate'] = data(frame.mandate)
            else:
                approved = {'user_topic': frozen['topic'], 'mode': 'direct_frozen_material_generation'}
            composed = await _frozen_call(store, runtime, run_id, 'compose', 'discovery', 'COMPOSE',
                {**task_context, 'approved_family': approved})
            draft = composed.card_candidate
            judgments = None
            if draft is not None:
                card = store.save_card(draft, creation_key=run_id + '.card')
                store.update_run(run_id, card_id=card.card_id, card_version=card.version)
                novelty = await _frozen_call(store, runtime, run_id, 'novelty', 'novelty_examiner', payload={
                    **task_context, 'card': data(card), 'evaluation_mode': 'frozen_material_only',
                    'claim_evidence_bindings': store.claim_evidence_bindings(card.draft)})
                judgments = await _frozen_call(store, runtime, run_id, 'selection', 'selector', payload={
                    **task_context, 'card': data(card), 'novelty': data(novelty),
                    'claim_evidence_bindings': store.claim_evidence_bindings(card.draft)})
                validate_selection(store, card, judgments, novelty)
                store.record_selection(run_id, card.card_id, card.version, judgments)
            store.update_run(run_id, status='COMPLETED', stop_reason='frozen_material_comparison')
        except Exception as exc:
            _record_failure(store, run_id, exc)
        finally:
            await runtime.close()
        latest = store.get_run(run_id)
        candidates.append({'system': system, 'draft': data(draft),
            'judgment': data(judgments) if latest.status == 'COMPLETED' else None,
            'status': latest.status, 'stop_reason': latest.stop_reason,
            'pending_envelopes': {k: v for k, v in latest.state.get('comparison_envelopes', {}).items()
                                  if v['result_status'] != 'complete'}, 'cost': ledger.summary(run_id)})
    shuffle_seed = seed
    report = {'automatic_screen_only': True, 'material_hash': material_hash, 'shuffle_seed': shuffle_seed,
              'candidates': candidates, 'comparison_status': 'incomplete',
              'evaluation': None, 'evaluations': [],
              'include_swapped_order': include_swapped_order, 'parent_cost': ledger.summary(VALIDATION_PARENT)}
    if any(c['status'] != 'COMPLETED' for c in candidates):
        store.save_artifact(f'evaluations/{source_run_id}/comparison.json', json.dumps(report, ensure_ascii=False, indent=2))
        return report
    anonymous, identity = anonymous_candidates(candidates, seed=shuffle_seed)
    orders = [('forward', anonymous, identity)]
    if include_swapped_order:
        reversed_cards, reversed_identity = [], {}
        for number, candidate in enumerate(reversed(anonymous), 1):
            identifier = f'candidate_{number}'
            reversed_cards.append({'candidate_id': identifier, 'research_card': candidate['research_card']})
            reversed_identity[identifier] = identity[candidate['candidate_id']]
        orders.append(('swapped', reversed_cards, reversed_identity))
    eval_id = source_run_id + '.comparison.evaluator'
    try:
        evaluation = store.get_run(eval_id)
    except StateError:
        evaluation = new_run(settings, 'evaluation', budget=settings.budget_cny, parent=VALIDATION_PARENT, run_id=eval_id)
    runtime = await make_runtime(store, ledger, evaluation, type(settings).model_validate(evaluation.config))
    store.update_run(eval_id, status='RUNNING', stop_reason=None)
    try:
        for order, presented, mapping in orders:
            # Keep the historical default key; new seeds/orderings have separate
            # cached outputs and can never silently reuse another presentation.
            key = 'judge' if seed == 20260907 and order == 'forward' else f'judge.seed{seed}.{order}'
            result = await _frozen_call(store, runtime, eval_id, key, 'evaluator',
                payload={**frozen, 'candidates': presented})
            identifiers = [finding.candidate_id for finding in result.per_candidate_findings]
            if len(identifiers) != len(set(identifiers)) or set(identifiers) != set(mapping):
                raise ProtocolViolation('EVALUATOR_CANDIDATE_COVERAGE')
            item = {'order': order, 'task_key': key, 'identity_map_private': mapping,
                    'evaluation': data(result)}
            report['evaluations'].append(item)
            if order == 'forward':
                report['evaluation'] = data(result)
        report['comparison_status'] = 'completed'
        store.update_run(eval_id, status='COMPLETED', stop_reason='frozen_material_comparison')
    except Exception as exc:
        _record_failure(store, eval_id, exc)
    finally:
        await runtime.close()
    report.update(identity_map_private=identity, evaluator_status=store.get_run(eval_id).status,
                  evaluator_state=store.get_run(eval_id).state, parent_cost=ledger.summary(VALIDATION_PARENT))
    store.save_artifact(f'evaluations/{source_run_id}/comparison.json', json.dumps(report, ensure_ascii=False, indent=2))
    # Separate artifacts retain earlier seeds even when comparison.json points
    # to the latest requested comparison. This does not regenerate candidates.
    suffix = 'both' if include_swapped_order else 'forward'
    store.save_artifact(f'evaluations/{source_run_id}/comparison.seed{seed}.{suffix}.json',
                        json.dumps(report, ensure_ascii=False, indent=2))
    return report
