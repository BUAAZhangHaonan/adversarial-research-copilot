"""Sequential A–E development ablation on one frozen, explicitly scoped material set.

No account authorization is created here: the caller supplies an existing parent.
Model invocations use the ordinary Runtime, ledger, prompt and response artifacts.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
from importlib.resources import files

from .evaluation import _frozen_call, _record_failure, anonymous_candidates
from .research_context import build_research_context, as_data
from .schemas import ScientificReview
from .scientific import review_and_revise
from .store import StateError
from .validation import ProtocolViolation, validate_selection


def freeze_research_material(store, source_run_id):
    """Freeze only registered working evidence and its explicitly referenced sources."""
    context = build_research_context(store, store.get_run(source_run_id))
    sources = []
    for item in context['sources']:
        source = store.get_source(item['source_id'])
        sources.append({**item, 'content': store.read_artifact(source.content_path)
                        if source.content_path else None})
    return {'original_task': context['original_task'], 'topic': context['original_task']['topic'],
            'boundaries': context['original_task']['boundaries'], 'mandate': context['mandate'],
            'sources': sources, 'evidence': context['evidence'],
            'provenance_verification': context['provenance_verification']}


def _stable_artifact(store, path, value):
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    try:
        previous = store.read_artifact(path)
    except FileNotFoundError:
        store.save_artifact(path, text)
    else:
        if json.loads(previous) != value:
            raise ProtocolViolation('FUNCTIONAL_EVALUATION_INPUT_CHANGED_USE_NEW_EXPERIMENT_ID')


def _review_reuse(store, source_run_id, target_payload, candidate_origin):
    """Borrow an accepted observation only for an identical candidate and material."""
    source = store.get_run(source_run_id)
    origin = store.get_run(candidate_origin)
    if (source.state.get('condition') != 'D' or origin.state.get('condition') != 'A'
            or source.state.get('functional_experiment') != origin.state.get('functional_experiment')):
        raise ProtocolViolation('ABLATION_REUSED_REVIEW_ORIGIN_MISMATCH')
    frozen = source.state.get('task_inputs', {}).get('science.review', {})
    envelope = source.state.get('comparison_envelopes', {}).get('science.review', {})
    task = store.get_task(envelope.get('task_id', ''))
    if (task is None or task.status != 'ACCEPTED' or task.run_id != source_run_id
            or task.accepted_result != envelope or envelope.get('result_status') != 'complete'
            or envelope.get('subject') != frozen.get('subject')):
        raise ProtocolViolation('ABLATION_REUSED_REVIEW_ACCEPTED_TASK_MISMATCH')
    prompt = json.loads(store.read_artifact(task.rendered_prompt_path)) if task.rendered_prompt_path else {}
    if prompt.get('prompt_id') != 'scientific_reviewer.INVOKE':
        raise ProtocolViolation('ABLATION_REUSED_REVIEW_ROLE_MISMATCH')
    payload = frozen['payload']
    subject = frozen['subject']
    original = store.get_card(subject['card_id'], subject['card_version'])
    origin_card = store.get_card(origin.card_id, origin.card_version)
    if (original.draft != origin_card.draft
            or original.draft.model_dump(mode='json') != payload.get('review_target')
            or any(payload.get(key) != target_payload.get(key) for key in (
                'review_target', 'original_task', 'mandate', 'sources', 'evidence'))):
        raise ProtocolViolation('ABLATION_REUSED_REVIEW_INPUT_MISMATCH')
    review = ScientificReview.model_validate(envelope['result'])
    if source.state.get('scientific_cycles', {}).get('science', {}).get('review') != review.model_dump(mode='json'):
        raise ProtocolViolation('ABLATION_REUSED_REVIEW_CYCLE_MISMATCH')
    return {'source_task_id': task.task_id, 'source_run_id': source_run_id,
            'source_subject': subject, 'review': review.model_dump(mode='json'),
            'candidate_origin': candidate_origin}


class FrozenEngine:
    def __init__(self, store, ledger, settings, material, runtime_factory):
        self.store, self.ledger, self.settings = store, ledger, settings
        self.material, self.runtime_factory = material, runtime_factory

    def checkpoint(self, run_id, **updates):
        state = dict(self.store.get_run(run_id).state)
        state.update(updates)
        self.store.update_run(run_id, state=state)
        return state

    def context(self, run_id):
        run = self.store.get_run(run_id)
        card = self.store.get_card(run.card_id, run.card_version) if run.card_id else None
        # Registered revisions may add evidence bindings from the same frozen sources.
        evidence_ids = set(e['evidence_id'] for e in self.material['evidence']) | set(run.state.get('evidence_ids', []))
        return {**self.material, 'subject': {'run_id': run_id, 'campaign_id': None,
            'card_id': run.card_id, 'card_version': run.card_version}, 'card': as_data(card),
            'mandate': run.state.get('functional_mandate', self.material.get('mandate')),
            'issues': [], 'evidence': as_data(self.store.list_evidence(ids=sorted(evidence_ids))),
            'claim_evidence_bindings': self.store.claim_evidence_bindings(card.draft) if card else [],
            'evaluation_mode': 'frozen_material_only_no_online_tools'}

    async def call(self, run_id, key, role, task='INVOKE', payload=None,
                   tool_profile=None, on_admitted=None, *, phase='current'):
        if on_admitted:
            raise ValueError('ABLATION_DOES_NOT_CONSUME_DISCOVERY_DRAW_QUOTA')
        run = self.store.get_run(run_id)
        inputs = dict(run.state.get('task_inputs', {}))
        if key not in inputs:
            inputs[key] = {'subject': {'campaign_id': run.campaign_id, 'run_id': run_id,
                'card_id': run.card_id, 'card_version': run.card_version}, 'payload': payload or {}}
            self.checkpoint(run_id, task_inputs=inputs)
        reused = run.state.get('reused_reviews', {}).get(key)
        if reused:
            expected_origin = run.state['functional_experiment'] + '.A'
            verified = _review_reuse(self.store, run.state['functional_experiment'] + '.D',
                                     inputs[key]['payload'], expected_origin)
            if reused != verified:
                raise ProtocolViolation('ABLATION_REUSED_REVIEW_BINDING_CHANGED')
            return ScientificReview.model_validate(reused['review'])
        runtime = await self.runtime_factory(run, phase, self.settings)
        try:
            return await _frozen_call(self.store, runtime, run_id, key, role, task, inputs[key]['payload'])
        finally:
            await runtime.close()

    def trace_tasks(self, run_id, key):
        reused = self.store.get_run(run_id).state.get('reused_reviews', {}).get(key)
        envelope = self.store.get_run(run_id).state.get('comparison_envelopes', {}).get(key, {})
        return [reused['source_task_id'] if reused else envelope.get('task_id', f'{run_id}.{key}')]

    async def investigate(self, run_id, key, questions, *, fresh=False, extra=None):
        result = await self.call(run_id, key, 'investigator', payload={
            **self.context(run_id), 'questions': questions,
            'fresh_verification': False, **(extra or {})}, tool_profile=[])
        run = self.store.get_run(run_id)
        card = self.store.get_card(run.card_id, run.card_version)
        evidence = self.store.register_findings(result.findings + result.contrary_findings,
            task_id=f'{run_id}.{key}', allowed_claims=card.draft.claims)
        self.checkpoint(run_id, evidence_ids=sorted(set(run.state.get('evidence_ids', [])) |
                                                  {e.evidence_id for e in evidence}))
        return result


def _prompt_factory(store, ledger, experiment_id, legacy_prompt_root):
    from .prompting import PromptLoader
    from .pricing import PriceBook
    from .runtime import Runtime
    roots = {}
    for phase, origin in [('current', Path(str(files('arc_prompt_assets')))),
                           ('legacy', Path(legacy_prompt_root))]:
        target = Path(store.artifact_root) / 'functional-evaluations' / experiment_id / 'prompts' / phase
        if not target.exists():
            if not (origin / 'manifest.json').is_file():
                raise ValueError('ABLATION_PROMPT_SNAPSHOT_MISSING')
            shutil.copytree(origin, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        roots[phase] = target
    prices = PriceBook(Path(str(files('arc_config_assets').joinpath('pricing.json'))))

    async def create(run, phase, settings):
        def progress(event):
            print(json.dumps(event, ensure_ascii=False, default=str), flush=True)
        return Runtime(store=store, ledger=ledger, account_id=run.budget_account_id,
            loader=PromptLoader(roots[phase]), role_models=settings.roles, prices=prices,
            api_key=os.environ.get('DEEPSEEK_API_KEY'),
            base_url=os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com'),
            tools={}, on_progress=progress)
    return create


async def run_ablation(settings, source_run_id, *, experiment_id, parent_id, budget_cny,
                       seed, legacy_prompt_root, runtime_factory=None):
    """Run/resume A–E and two anonymous orders. Failures remain explicit results.

    A: Pro CONCEIVE + old review; B: Pro split generation + old review;
    C: Flash split generation + old Pro review; D: A candidate + new review;
    E: same A candidate and D initial review + one revision/recheck when warranted.
    All A/B/C generation uses the same current prompt snapshot and shared
    scientific rules/examples. Only their novelty/selector review uses legacy.
    """
    from .cli import services
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', experiment_id) or '..' in experiment_id:
        raise ValueError('INVALID_ABLATION_EXPERIMENT_ID')
    store, ledger = services(settings)
    parent = ledger.summary(parent_id)  # Existing authorization is mandatory.
    if parent['reserved_micro'] or parent.get('unknown_calls', 0):
        raise ValueError('ABLATION_PARENT_HAS_PENDING_CALLS')
    manifest_path = f'functional-evaluations/{experiment_id}/manifest.json'
    try:
        saved = json.loads(store.read_artifact(manifest_path))
    except FileNotFoundError:
        saved = None
    material = saved['material'] if saved else freeze_research_material(store, source_run_id)
    if not material['topic'] or not material['evidence']:
        raise ValueError('ABLATION_REQUIRES_ORIGINAL_TOPIC_AND_REGISTERED_EVIDENCE')
    specification = {'source_run_id': source_run_id, 'experiment_id': experiment_id,
        'parent_id': parent_id, 'budget_cny': str(budget_cny), 'seed': seed,
        'legacy_prompt_root': str(Path(legacy_prompt_root).resolve()), 'material': material,
        'conditions': {'A': 'Pro coherent, current generation prompts, old Pro review',
            'B': 'Pro split, current generation prompts, old Pro review',
            'C': 'Flash split, current generation prompts, old Pro review',
            'D': 'A candidate, scientific review only',
            'E': 'A candidate, reused D review, bounded revision and recheck'}}
    _stable_artifact(store, manifest_path, specification)
    factory = runtime_factory or _prompt_factory(store, ledger, experiment_id, legacy_prompt_root)
    report = {'experiment_id': experiment_id, 'source_run_id': source_run_id,
        'material_path': manifest_path, 'automatic_screen_only': True,
        'conditions': {}, 'evaluations': [], 'status': 'incomplete'}

    def get_run(condition, config):
        run_id = f'{experiment_id}.{condition}'
        try:
            run = store.get_run(run_id)
        except StateError as exc:
            if str(exc) != 'run_missing':
                raise
            ledger.create_account(run_id, budget_cny, parent_id=parent_id)
            run = store.create_run('evaluation', run_id=run_id, budget_account_id=run_id,
                config=config.model_dump(mode='json'), state={'functional_experiment': experiment_id,
                    'condition': condition, 'material_path': manifest_path})
        if run.config != config.model_dump(mode='json') or ledger.summary(run.budget_account_id)['parent_id'] != parent_id:
            raise ProtocolViolation('ABLATION_CONDITION_CONFIG_CHANGED')
        return run

    def save_report():
        report['parent_cost'] = ledger.summary(parent_id)
        store.save_artifact(f'functional-evaluations/{experiment_id}/report.json',
                           json.dumps(report, ensure_ascii=False, indent=2, default=str))

    for condition in 'ABCDE':
        config = settings.model_copy(update={'roles': {role: 'deepseek-v4-pro' for role in settings.roles}})
        if condition == 'C':
            config.roles['discovery'] = 'deepseek-v4-flash'
        run = get_run(condition, config)
        engine = FrozenEngine(store, ledger, config, material, factory)
        try:
            store.update_run(run.run_id, status='RUNNING', stop_reason=None)
            result = run.state.get('functional_result')
            if result and result.get('not_run_reason'):
                # Missing prerequisites are checked again after an upstream recovery.
                result = None
            if result is None:
                if condition in 'ABC':
                    if condition == 'A':
                        conceived = await engine.call(run.run_id, 'conception', 'discovery', 'CONCEIVE',
                            payload={**engine.context(run.run_id), 'previous_draws': {},
                                'opportunities_remaining': 1})
                        draft = conceived.card_candidate
                    else:
                        frame = await engine.call(run.run_id, 'frame', 'discovery', 'FRAME',
                            payload=engine.context(run.run_id), phase='current')
                        engine.checkpoint(run.run_id, functional_mandate=as_data(frame.mandate))
                        task_context = {**engine.context(run.run_id), 'mandate': as_data(frame.mandate)}
                        family = await engine.call(run.run_id, 'family', 'discovery', 'NEXT_DRAW',
                            payload={**task_context, 'previous_draws': {}}, phase='current')
                        if family.continue_or_stop == 'STOP':
                            draft = None
                        else:
                            composed = await engine.call(run.run_id, 'compose', 'discovery', 'COMPOSE',
                                payload={**task_context, 'approved_family': as_data(family)}, phase='current')
                            draft = composed.card_candidate
                    judgment = None
                    if draft is not None:
                        card = store.save_card(draft, creation_key=run.run_id + '.candidate', run_id=run.run_id)
                        store.update_run(run.run_id, card_id=card.card_id, card_version=card.version)
                        # The original task is present in all three legacy review arms.
                        context = {**engine.context(run.run_id), 'card': as_data(card)}
                        novelty = await engine.call(run.run_id, 'novelty', 'novelty_examiner',
                            payload=context, phase='legacy')
                        judgment = await engine.call(run.run_id, 'selection', 'selector',
                            payload={**context, 'novelty': as_data(novelty)}, phase='legacy')
                        validate_selection(store, card, judgment, novelty)
                    result = {'draft': as_data(draft), 'judgment': as_data(judgment),
                              'candidate_origin': run.run_id}
                else:
                    a = report['conditions'].get('A', {})
                    if not a.get('draft'):
                        result = {'draft': None, 'judgment': None, 'candidate_origin': f'{experiment_id}.A',
                                  'not_run_reason': 'A_has_no_candidate'}
                    elif condition == 'E' and not report['conditions'].get('D', {}).get('judgment'):
                        result = {'draft': a['draft'], 'judgment': None, 'candidate_origin': f'{experiment_id}.A',
                                  'not_run_reason': 'D_has_no_complete_initial_review'}
                    else:
                        card = store.save_card(a['draft'], creation_key=run.run_id + '.candidate', run_id=run.run_id)
                        store.update_run(run.run_id, card_id=card.card_id, card_version=card.version)
                        if condition == 'E':
                            saved_initial = store.get_run(run.run_id).state.get('task_inputs', {}).get('science.review')
                            initial_payload = (saved_initial['payload'] if saved_initial else
                                {**engine.context(run.run_id), 'review_target': as_data(card.draft)})
                            reuse = _review_reuse(store, f'{experiment_id}.D',
                                initial_payload, f'{experiment_id}.A')
                            engine.checkpoint(run.run_id, reused_reviews={'science.review': reuse})
                        card, scientific_review = await review_and_revise(engine, run.run_id,
                            'science', allow_revision=condition == 'E', tool_profile=[])
                        result = {'draft': as_data(card.draft), 'judgment': as_data(scientific_review),
                            'candidate_origin': f'{experiment_id}.A', 'card_version': card.version,
                            'initial_review_origin': engine.trace_tasks(run.run_id, 'science.review')[-1]}
                if not result.get('not_run_reason'):
                    engine.checkpoint(run.run_id, functional_result=result)
            dependency = 'D' if result.get('not_run_reason') == 'D_has_no_complete_initial_review' else 'A'
            waiting = bool(result.get('not_run_reason') and
                           report['conditions'].get(dependency, {}).get('status') != 'COMPLETED')
            store.update_run(run.run_id, status='PAUSED_EXTERNAL' if waiting else 'COMPLETED',
                stop_reason=result['not_run_reason'] if waiting else 'frozen_ablation_condition_complete')
        except Exception as exc:
            _record_failure(store, run.run_id, exc)
            current = store.get_run(run.run_id)
            card = store.get_card(current.card_id, current.card_version) if current.card_id else None
            result = {'draft': as_data(card.draft) if card else None, 'judgment': None}
        latest = store.get_run(run.run_id)
        report['conditions'][condition] = {**result, 'system': condition, 'run_id': run.run_id,
            'status': latest.status, 'stop_reason': latest.stop_reason, 'cost': ledger.summary(run.run_id)}
        save_report()
        # A timed-out provider request may still be active. Preserve the pause
        # and never overlap a later condition with an unsettled paid call.
        outstanding = ledger.summary(parent_id)
        if outstanding['reserved_micro'] or outstanding.get('unknown_calls', 0):
            report['blocked_remaining_conditions'] = list('ABCDE'['ABCDE'.index(condition) + 1:])
            report['stop_reason'] = 'parent_has_unsettled_model_call'
            save_report()
            return report

    if any(value['status'] != 'COMPLETED' for value in report['conditions'].values()):
        return report
    run = get_run('judge', settings.model_copy(update={'roles': {r: 'deepseek-v4-pro' for r in settings.roles}}))
    engine = FrozenEngine(store, ledger, settings.model_copy(update={'roles': {r: 'deepseek-v4-pro' for r in settings.roles}}), material, factory)
    candidates, identity = anonymous_candidates(list(report['conditions'].values()), seed=seed)
    try:
        for order, ordered in [('forward', candidates), ('swapped', list(reversed(candidates)))]:
            presented, mapping = [], {}
            for number, item in enumerate(ordered, 1):
                identifier = f'candidate_{number}'
                presented.append({'candidate_id': identifier, 'research_card': item['research_card']})
                mapping[identifier] = identity[item['candidate_id']]
            judgment = await engine.call(run.run_id, f'judge.{order}', 'evaluator',
                payload={**material, 'candidates': presented})
            ids = [item.candidate_id for item in judgment.per_candidate_findings]
            if len(ids) != len(set(ids)) or set(ids) != set(mapping):
                raise ProtocolViolation('EVALUATOR_CANDIDATE_COVERAGE')
            report['evaluations'].append({'order': order, 'identity_map_private': mapping,
                                           'evaluation': as_data(judgment)})
        store.update_run(run.run_id, status='COMPLETED', stop_reason='paired_anonymous_orders_complete')
        report['status'] = 'completed'
    except Exception as exc:
        _record_failure(store, run.run_id, exc)
    report['judge_status'] = store.get_run(run.run_id).status
    report['judge_cost'] = ledger.summary(run.run_id)
    save_report()
    return report
