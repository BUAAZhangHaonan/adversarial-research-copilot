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
        envelope = await runtime.invoke(role=role, task=task, payload=payload or {},
            result_schema=schema, subject=Subject(campaign_id=run.campaign_id, run_id=run_id,
                card_id=run.card_id, card_version=run.card_version),
            task_id=f'{run_id}.{key}', tool_profile=[])
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


async def run_comparison(settings, source_run_id):
    from .cli import services, new_run
    from .bootstrap import make_runtime
    from .workflows import data
    from .store import StateError
    from .validation import ProtocolViolation, validate_selection
    store, ledger = services(settings)
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
        material = {'topic': campaign.topic, 'sources': sources,
            'evidence': [store.get_record(identifier) for identifier in evidence_ids]}
        material_bytes = json.dumps(material, ensure_ascii=False, sort_keys=True).encode('utf-8')
        frozen_text = json.dumps({'material': material,
            'sha256': hashlib.sha256(material_bytes).hexdigest()}, ensure_ascii=False)
        store.save_artifact(frozen_path, frozen_text)
    manifest = json.loads(frozen_text)
    frozen = manifest['material']
    material_hash = hashlib.sha256(json.dumps(frozen, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
    if material_hash != manifest['sha256']:
        raise ProtocolViolation('COMPARISON_MATERIAL_HASH_MISMATCH')
    if not frozen['evidence']:
        raise ValueError('COMPARISON_REQUIRES_FROZEN_EVIDENCE')
    candidates = []
    for system in ('ARC', 'direct-Pro'):
        config = settings if system == 'ARC' else settings.model_copy(update={
            'roles': {role: 'deepseek-v4-pro' for role in settings.roles}})
        run_id = source_run_id + '.comparison.' + system
        try:
            run = store.get_run(run_id)
        except StateError:
            run = new_run(config, 'evaluation', budget='20', parent=VALIDATION_PARENT, run_id=run_id)
        config = type(settings).model_validate(run.config)
        runtime = await make_runtime(store, ledger, run, config)
        draft = judgments = None
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
            else:
                approved = {'user_topic': frozen['topic'], 'mode': 'direct_frozen_material_generation'}
            composed = await _frozen_call(store, runtime, run_id, 'compose', 'discovery', 'COMPOSE',
                {**frozen, 'approved_family': approved})
            draft = composed.card_candidate
            judgments = None
            if draft is not None:
                card = store.save_card(draft, creation_key=run_id + '.card')
                store.update_run(run_id, card_id=card.card_id, card_version=card.version)
                novelty = await _frozen_call(store, runtime, run_id, 'novelty', 'novelty_examiner', payload={
                    **frozen, 'card': data(card), 'evaluation_mode': 'frozen_material_only',
                    'claim_evidence_bindings': store.claim_evidence_bindings(card.draft)})
                judgments = await _frozen_call(store, runtime, run_id, 'selection', 'selector', payload={
                    **frozen, 'card': data(card), 'novelty': data(novelty),
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
    report = {'automatic_screen_only': True, 'material_hash': material_hash,
              'candidates': candidates, 'comparison_status': 'incomplete',
              'evaluation': None, 'parent_cost': ledger.summary(VALIDATION_PARENT)}
    if any(c['status'] != 'COMPLETED' for c in candidates):
        store.save_artifact(f'evaluations/{source_run_id}/comparison.json', json.dumps(report, ensure_ascii=False, indent=2))
        return report
    anonymous, identity = anonymous_candidates(candidates)
    eval_id = source_run_id + '.comparison.evaluator'
    try:
        evaluation = store.get_run(eval_id)
    except StateError:
        evaluation = new_run(settings, 'evaluation', budget='20', parent=VALIDATION_PARENT, run_id=eval_id)
    runtime = await make_runtime(store, ledger, evaluation, type(settings).model_validate(evaluation.config))
    store.update_run(eval_id, status='RUNNING', stop_reason=None)
    try:
        result = await _frozen_call(store, runtime, eval_id, 'judge', 'evaluator', payload={**frozen, 'candidates': anonymous})
        identifiers = [finding.candidate_id for finding in result.per_candidate_findings]
        if len(identifiers) != len(set(identifiers)) or set(identifiers) != set(identity):
            raise ProtocolViolation('EVALUATOR_CANDIDATE_COVERAGE')
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
    return report
