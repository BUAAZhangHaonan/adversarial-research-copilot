"""Three bounded research workflows sharing typed state and one issue kernel."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import json

from .config import Settings
from .schemas import RESULT_SCHEMAS, Subject, CardDraft, ProblemAnchor
from .store import StateError
from .runtime import RuntimePaused
from .validation import ProtocolViolation, validate_archive_comparisons, validate_selection, validate_revision


@dataclass
class WorkflowPause(Exception):
    status: str
    reason: str


RESEARCH_TOOLS = ('search_literature', 'read_paper', 'search_web', 'read_web',
                  'lookup_archive', 'read_record', 'request_capability')


def data(value):
    if hasattr(value, 'model_dump'):
        return value.model_dump(mode='json')
    if isinstance(value, list):
        return [data(item) for item in value]
    return value


class WorkflowEngine:
    def __init__(self, store, runtime, settings: Settings):
        self.store, self.runtime, self.settings = store, runtime, settings

    def checkpoint(self, run_id, **updates):
        run = self.store.get_run(run_id)
        state = dict(run.state)
        state.update(updates)
        self.store.update_run(run_id, state=state)
        return state

    def context(self, run_id):
        run = self.store.get_run(run_id)
        card = self.store.get_card(run.card_id, run.card_version) if run.card_id else None
        evidence_ids = set(run.state.get('evidence_ids', []))
        source_ids = set(run.state.get('source_ids', []))
        if card:
            evidence_ids.update(card.draft.motivation.evidence_ids)
            source_ids.update(card.draft.closest_work_delta.source_ids)
            for claim in card.draft.claims:
                evidence_ids.update(claim.evidence_ids)
        evidence = self.store.list_evidence(ids=sorted(evidence_ids))
        source_ids.update(e.source_id for e in evidence)
        return {
            'subject': data(Subject(campaign_id=run.campaign_id, run_id=run.run_id,
                                    card_id=run.card_id, card_version=run.card_version)),
            'card': data(card), 'issues': data(self.store.get_issues(run_id)),
            'claim_evidence_bindings': self.store.claim_evidence_bindings(card.draft) if card else [],
            'evidence': data(evidence),
            'sources': data(self.store.list_sources(ids=sorted(source_ids))),
            'constraints': run.config.get('constraints', {}),
            'input_provenance': run.state.get('input_provenance'),
        }

    async def call(self, run_id, key, role, task='INVOKE', payload=None,
                   on_admitted: Callable | None = None, tool_profile=None, request_depth=0):
        run = self.store.get_run(run_id)
        schema_key = f'{role}.{task}' if role == 'discovery' else role
        if key in run.state:
            return RESULT_SCHEMAS[schema_key].model_validate(run.state[key])
        subject = Subject(campaign_id=run.campaign_id, run_id=run_id,
                          card_id=run.card_id, card_version=run.card_version)
        task_id = f'{run_id}.{key}'
        inputs = dict(run.state.get('task_inputs', {}))
        if key not in inputs:
            inputs[key] = {'payload': payload or {}, 'subject': data(subject)}
            self.checkpoint(run_id, task_inputs=inputs)
        payload = inputs[key]['payload']
        subject = Subject.model_validate(inputs[key]['subject'])
        allowed_tools = self.runtime.loader.manifest['prompts'][f'{role}.{task}']['tools']
        envelope = await self.runtime.invoke(
            role=role, task=task, payload=payload or {},
            result_schema=RESULT_SCHEMAS[schema_key], subject=subject,
            task_id=task_id,
            tool_profile=[name for name in dict.fromkeys((*(RESEARCH_TOOLS if tool_profile is None else tool_profile), 'request_capability'))
                          if name in self.runtime.tools and name in allowed_tools],
            on_admitted=on_admitted,
        )
        for index, request in enumerate(envelope.capability_requests):
            self.store.save_capability_request(run_id, data(request), task_id=task_id,
                                              request_key=f'{task_id}.envelope.{index}')
        if envelope.result_status != 'complete':
            self.checkpoint(run_id, pending_task=key,
                            pending_evidence_requests=data(envelope.evidence_requests),
                            pending_capability_requests=data(envelope.capability_requests),
                            pending_note=envelope.note)
            if envelope.result_status == 'needs_evidence' and role != 'investigator':
                if request_depth >= self.settings.max_rounds:
                    raise WorkflowPause('PAUSED_EXTERNAL', 'evidence_action_exhausted')
                request_key = key + '.requested_evidence'
                await self.investigate(run_id, request_key,
                    [r.question for r in envelope.evidence_requests], fresh=True,
                    extra={'evidence_requests': data(envelope.evidence_requests),
                           'decision_subject': data(subject)})
                result = await self.call(run_id, key + '.after_evidence', role, task,
                    payload={**payload, **self.context(run_id),
                             'completed_evidence_requests': data(envelope.evidence_requests)},
                    tool_profile=tool_profile, request_depth=request_depth + 1)
                self.checkpoint(run_id, **{key: data(result), key + '_trace_tasks': list(dict.fromkeys(
                    [task_id] + self.trace_tasks(run_id, request_key) +
                    self.trace_tasks(run_id, key + '.after_evidence')))})
                return result
            # A blocked object is never accepted as a scientific judgment.
            raise WorkflowPause('PAUSED_EXTERNAL', 'critical_source_unavailable')
        result = envelope.result
        latest = self.store.get_run(run_id)
        trace = self.runtime.tool_trace(task_id)
        source_ids = set(latest.state.get('source_ids', []))
        evidence_ids = set(latest.state.get('evidence_ids', []))
        for item in trace:
            if item.get('status') == 'completed':
                source_ids.update(item.get('source_ids', []))
                evidence_ids.update(item.get('evidence_ids', []))
        self.checkpoint(run_id, **{key: data(result), key + '_trace_tasks': [task_id]}, source_ids=sorted(source_ids),
                        evidence_ids=sorted(evidence_ids))
        return result

    def trace_tasks(self, run_id, key):
        return self.store.get_run(run_id).state.get(key + '_trace_tasks', [f'{run_id}.{key}'])

    def task_trace(self, run_id, key):
        return [item for task_id in self.trace_tasks(run_id, key)
                for item in self.runtime.tool_trace(task_id)]

    def has_external_evidence_action(self, trace):
        for item in trace:
            result = item.get('result')
            if (item.get('status') != 'completed' or not isinstance(result, dict)
                    or result.get('is_error') is not False):
                continue
            sources, source_ids = result.get('sources'), result.get('source_ids')
            if not isinstance(sources, list) or not isinstance(source_ids, list):
                continue
            if item.get('name') in {'search_literature', 'search_web'}:
                # A successful empty search establishes an attempted search only.
                return True
            if item.get('name') not in {'read_paper', 'read_web'}:
                continue
            for coverage in sources:
                if not isinstance(coverage, dict):
                    continue
                source_id = coverage.get('source_id')
                count, total = coverage.get('content_chars'), coverage.get('content_total_chars')
                complete = coverage.get('content_complete')
                if (source_id not in source_ids or source_id not in item.get('source_ids', [])
                        or type(count) is not int or count <= 0 or type(complete) is not bool
                        or (total is not None and (type(total) is not int or total < count))
                        or (complete and total != count)):
                    continue
                try:
                    source = self.store.get_source(source_id)
                    if (source.access_status != 'retrieved' or source.content_origin == 'metadata'
                            or not source.content_path):
                        continue
                    body = self.store.read_artifact(source.content_path)
                except (StateError, OSError):
                    continue
                inline = coverage.get('content')
                if (len(body) >= count and body[:count].strip()
                        and (inline is None or inline == body[:count])):
                    return True
        return False

    async def execute(self, run_id):
        run = self.store.get_run(run_id)
        if run.status in ('COMPLETED', 'PAUSED_SCOPE_CHANGE', 'CANCELLED'):
            return run
        self.store.update_run(run_id, status='RUNNING', stop_reason=None)
        try:
            if run.mode in ('develop', 'run') and not run.card_id and run.state.get('imported_input'):
                await self.import_input(run_id)
            if run.mode == 'discover':
                await self.discover(run_id)
            elif run.mode == 'develop':
                await self.develop(run_id)
            elif run.mode == 'run':
                await self.debate(run_id)
            else:
                raise ValueError('UNKNOWN_MODE')
        except WorkflowPause as exc:
            self.store.update_run(run_id, status=exc.status, stop_reason=exc.reason)
        except (ProtocolViolation, StateError) as exc:
            self.store.update_run(run_id, status='PAUSED_PROTOCOL', stop_reason=str(exc))
        return self.store.get_run(run_id)

    async def import_input(self, run_id):
        run = self.store.get_run(run_id)
        original_text = run.state['imported_input']
        anchor = ProblemAnchor(question=original_text, research_object=original_text,
                               conditions=[], anti_scope=[])
        imported = await self.call(run_id, 'import', 'developer', 'IMPORT', payload={
            **self.context(run_id), 'user_proposal': original_text, 'problem_anchor': data(anchor),
            'input_origin': 'user_proposal_not_external_verification',
        })
        if imported.proposed_revision is None or imported.proposed_revision.problem_anchor != anchor:
            raise WorkflowPause('PAUSED_PROTOCOL', 'import_must_preserve_user_question')
        card = self.store.save_card(imported.proposed_revision, creation_key=f'{run_id}.import.card',
                                    run_id=run_id, state_patch={'imported_card': True})
        self.store.update_run(run_id, card_id=card.card_id, card_version=card.version)

    def complete(self, run_id, reason, assessment=None):
        fields = {'status': 'COMPLETED', 'stop_reason': reason}
        if assessment is not None:
            fields['assessment'] = assessment
        self.store.update_run(run_id, **fields)

    def _validate_source_recheck(self, recheck):
        targets = recheck.get('target_source_ids')
        if targets is None:
            saved = json.loads(self.store.read_artifact(recheck['rejected_response_path']))
            draft = json.loads(saved['response']['message']['content'])
            targets = set()
            for finding in draft['result']['findings'] + draft['result']['contrary_findings']:
                try:
                    self.store.validate_finding_sources([finding])
                except StateError:
                    targets.add(finding['source_id'])
        if not targets:
            raise WorkflowPause('PAUSED_PROTOCOL', 'source_recheck_has_no_failed_source')
        reread = {item['result']['source_id']
                  for item in self.runtime.tool_trace(recheck['replacement_task_id'])
                  if item.get('status') == 'completed' and item.get('name') == 'read_record'
                  and item.get('result', {}).get('content')
                  and item['result'].get('source_id') == item.get('arguments', {}).get('record_id')}
        if not set(targets).issubset(reread):
            raise WorkflowPause('PAUSED_EXTERNAL', 'source_recheck_original_not_read')

    async def investigate(self, run_id, key, questions, *, fresh=False, extra=None):
        payload = {**self.context(run_id), 'questions': questions,
                   'fresh_verification_required': fresh, **(extra or {})}
        result_key = key
        try:
            result = await self.call(run_id, key, 'investigator', payload=payload)
        except RuntimePaused as exc:
            # A failed quote is an evidence question, not a formatting repair.
            # Keep the rejected task intact and allow exactly one separately
            # budgeted source-reading task. Its failure propagates unchanged.
            if exc.reason != 'excerpt_not_in_returned_source':
                raise
            rejected = self.store.get_task(f'{run_id}.{key}')
            if rejected is None or rejected.accepted_result is not None:
                raise
            saved = json.loads(self.store.read_artifact(rejected.response_artifact_path))
            draft = json.loads(saved['response']['message']['content'])
            failed_sources = set()
            for finding in draft['result']['findings'] + draft['result']['contrary_findings']:
                try:
                    self.store.validate_finding_sources([finding])
                except StateError:
                    failed_sources.add(finding['source_id'])
            if not failed_sources:
                raise WorkflowPause('PAUSED_PROTOCOL', 'source_recheck_has_no_failed_source')
            trace = self.runtime.tool_trace(rejected.task_id)
            source_ids = sorted({sid for item in trace if item.get('status') == 'completed'
                                 for sid in item.get('source_ids', [])})
            original = self.store.get_run(run_id).state['task_inputs'][key]['payload']
            result_key = key + '.source_recheck'
            self.checkpoint(run_id, **{key + '_source_recheck': {
                'rejected_task_id': rejected.task_id,
                'reason': exc.reason, 'replacement_task_id': f'{run_id}.{result_key}',
                'rejected_response_path': rejected.response_artifact_path,
                'target_source_ids': sorted(failed_sources),
                'maximum_rechecks': 1}})
            result = await self.call(run_id, result_key, 'investigator', payload={
                **original, 'sources_from_rejected_task': data(self.store.list_sources(ids=source_ids)),
                'target_source_ids': sorted(failed_sources),
                'rejected_unverified_result': draft['result'],
                'questions': questions,
                'source_validation_failure': {'reason': exc.reason, 'task_id': rejected.task_id},
            }, tool_profile=['read_record', 'request_capability'])
            self._validate_source_recheck(self.store.get_run(run_id).state[key + '_source_recheck'])
            self.checkpoint(run_id, **{key: data(result), key + '_trace_tasks':
                [rejected.task_id] + self.trace_tasks(run_id, result_key)})
        recheck = self.store.get_run(run_id).state.get(key + '_source_recheck')
        if recheck:
            self._validate_source_recheck(recheck)
        trace = self.task_trace(run_id, key)
        if fresh and not self.has_external_evidence_action(trace):
            self.checkpoint(run_id, missing_fresh_verification=key)
            raise WorkflowPause('PAUSED_EXTERNAL', 'fresh_verification_not_executed')
        # Findings receive registry IDs only after the actual source passage exists.
        # On resume the result still belongs to the independently accepted
        # recheck task, never to the rejected source task.
        if recheck:
            result_key = key + '.source_recheck'
        frozen = self.store.get_run(run_id).state['task_inputs'][result_key]['payload']
        frozen_card = frozen.get('card') or frozen.get('original_card') or {}
        allowed_claims = frozen_card.get('draft', {}).get('claims', [])
        registered = self.store.register_findings(result.findings + result.contrary_findings,
            task_id=f'{run_id}.{result_key}', allowed_claims=allowed_claims)
        run = self.store.get_run(run_id)
        self.checkpoint(run_id,
            evidence_ids=sorted(set(run.state.get('evidence_ids', [])) | {e.evidence_id for e in registered}),
            source_ids=sorted(set(run.state.get('source_ids', [])) | {e.source_id for e in registered}))
        return result

    async def archive_compare(self, run_id, key, query, candidate, on_admitted=None):
        run = self.store.get_run(run_id)
        recall_key = f'{key}_recall'
        if recall_key in run.state:
            window = run.state[recall_key]
        else:
            window = self.store.lookup_archive(query, limit=self.settings.archive_window)
            if isinstance(candidate, dict) and candidate.get('card_id'):
                window['records'] = [r for r in window['records'] if
                                     (r['card_id'], r['version']) != (candidate['card_id'], candidate.get('version'))]
            self.checkpoint(run_id, **{recall_key: window})
        if not window['records']:
            return {'comparisons': [], 'retrieval_scope': window,
                    'unsearched_limits': window.get('unsearched_limits', [])}
        result = await self.call(run_id, key, 'librarian', payload={
            'candidate': candidate, 'retrieval': window,
            'records_to_compare': window['records'],
        }, tool_profile=['lookup_archive', 'read_record'], on_admitted=on_admitted)
        validate_archive_comparisons(result, window['records'], self.store)
        return data(result)

    async def discover(self, run_id):
        run = self.store.get_run(run_id)
        campaign = self.store.get_campaign(run.campaign_id)
        frame = await self.call(run_id, 'frame', 'discovery', 'FRAME', {
            **self.context(run_id),
            'topic': campaign.topic, 'boundaries': campaign.boundaries,
            'resources': run.config.get('constraints', {}),
        })
        await self.investigate(run_id, 'shared_investigation', frame.initial_search_questions,
                               extra={'mandate': data(frame.mandate)})
        for number in range(1, campaign.max_draws + 1):
            run = self.store.get_run(run_id)
            draws = dict(run.state.get('draws', {}))
            draw_id = f'{campaign.campaign_id}.draw{number}'
            current = dict(draws.get(draw_id, {}))
            if current.get('finished'):
                self.store.update_run(run_id, card_id=None, card_version=None)
                continue
            history = await self.archive_compare(run_id, f'draw{number}.archive',
                                                  campaign.topic, data(frame.mandate),
                                                  on_admitted=lambda: self.store.claim_draw(campaign.campaign_id, draw_id))
            plan = await self.call(run_id, f'draw{number}.next', 'discovery', 'NEXT_DRAW', {
                **self.context(run_id), 'mandate': data(frame.mandate),
                'previous_draws': draws, 'archive_relations': history,
                'draw_id': draw_id, 'opportunities_remaining': campaign.max_draws - number + 1,
            }, on_admitted=lambda: self.store.claim_draw(campaign.campaign_id, draw_id))
            current['plan'] = data(plan)
            draws[draw_id] = current
            self.checkpoint(run_id, draws=draws)
            if plan.continue_or_stop == 'STOP':
                self.complete(run_id, 'no_distinct_direction')
                return
            if not plan.anchor_evidence_ids:
                self.checkpoint(run_id, pending_draw=draw_id)
                raise WorkflowPause('PAUSED_EXTERNAL', 'direction_missing_evidence_anchor')
            composed = await self.call(run_id, f'draw{number}.compose', 'discovery', 'COMPOSE', {
                **self.context(run_id), 'mandate': data(frame.mandate),
                'approved_family': data(plan), 'draw_id': draw_id,
            })
            if composed.card_candidate is None:
                current.update(finished=True, reason=composed.composition_reason,
                               unresolved_prerequisites=composed.unresolved_prerequisites)
                draws[draw_id] = current
                self.checkpoint(run_id, draws=draws)
                continue
            if 'card_id' in current:
                card = self.store.get_card(current['card_id'], current['card_version'])
            else:
                card = self.store.save_card(composed.card_candidate, creation_key=f'{run_id}.draw{number}.card')
                current.update(card_id=card.card_id, card_version=card.version)
                draws[draw_id] = current
                self.checkpoint(run_id, draws=draws)
            self.store.update_run(run_id, card_id=card.card_id, card_version=card.version)
            relations = await self.archive_compare(run_id, f'draw{number}.card_archive',
                                                    card.draft.problem_anchor.question,
                                                    data(card))
            duplicates = [r for r in relations.get('comparisons', []) if
                          r['relation'] == 'same_contribution' or
                          (r['relation'] == 'reopening_candidate' and not r['reopening_condition_met'])]
            if duplicates:
                current.update(finished=True, reason='historical_contribution_requires_new_evidence',
                               archive_relations=relations)
                draws[draw_id] = current
                self.checkpoint(run_id, draws=draws)
                self.store.update_run(run_id, card_id=None, card_version=None)
                continue
            novelty = await self.call(run_id, f'draw{number}.novelty', 'novelty_examiner',
                                      payload={**self.context(run_id), 'archive_relations': relations})
            trace = self.task_trace(run_id, f'draw{number}.novelty')
            if not self.has_external_evidence_action(trace):
                raise WorkflowPause('PAUSED_EXTERNAL', 'closest_work_check_not_executed')
            judgment = await self.call(run_id, f'draw{number}.selection', 'selector', payload={
                **self.context(run_id), 'novelty': data(novelty), 'archive_relations': relations,
            })
            validate_selection(self.store, card, judgment, novelty)
            current.update(finished=True, selection=data(judgment), novelty=data(novelty),
                           archive_relations=relations)
            draws[draw_id] = current
            self.store.record_selection(run_id, card.card_id, card.version, judgment,
                                         state_patch={'draws': draws})
            # The next draw sees every retained and failed family; remaining quota
            # alone never supplies an instruction to continue.
            self.store.update_run(run_id, card_id=None, card_version=None)
        self.complete(run_id, 'draw_quota_exhausted')

    async def develop(self, run_id):
        run = self.store.get_run(run_id)
        if not run.card_id:
            raise WorkflowPause('PAUSED_PROTOCOL', 'card_required')
        original = self.store.get_card(run.card_id, run.state.get('input_version', run.card_version))
        self.checkpoint(run_id, input_version=original.version)
        await self.investigate(run_id, 'fresh_verification', [], fresh=True, extra={
            'verification_target': 'strongest_counterexample_or_unchecked_original_condition',
            'original_card': data(original),
        })
        run = self.store.get_run(run_id)
        if not run.state.get('developed_version'):
            revision = await self.call(run_id, 'development', 'developer', payload={
                **self.context(run_id), 'original_card': data(original),
                'fresh_verification': run.state['fresh_verification'],
            })
            if revision.direction_change is not None:
                await self.scope_change(run_id, revision.direction_change)
                return
            if revision.proposed_revision is None:
                raise WorkflowPause('PAUSED_PROTOCOL', 'revision_required')
            if revision.proposed_revision.problem_anchor != original.draft.problem_anchor:
                raise WorkflowPause('PAUSED_PROTOCOL', 'problem_anchor_changed_without_scope_audit')
            validate_revision(self.store, original, revision)
            card = self.store.save_card(revision.proposed_revision, card_id=original.card_id,
                                        parent_version=original.version, creation_key=f'{run_id}.development.card')
            self.store.update_run(run_id, card_version=card.version)
            self.checkpoint(run_id, developed_version=card.version,
                            change_summary=revision.change_summary)
        await self.debate(run_id)

    async def scope_change(self, run_id, change):
        audit = await self.investigate(run_id, 'scope_original_audit', [], extra={
            'scope_change_proposal': data(change), 'verification_target': 'original_source_reinspection',
        })
        if not audit.findings or not change.trigger_evidence_ids:
            raise WorkflowPause('PAUSED_PROTOCOL', 'scope_change_without_original_evidence')
        opened = set()
        for item in self.task_trace(run_id, 'scope_original_audit'):
            if item.get('status') == 'completed' and item.get('name') in {'read_record', 'read_paper', 'read_web'}:
                opened.update(item.get('source_ids', []))
                if item.get('result', {}).get('source_id'):
                    opened.add(item['result']['source_id'])
        if not set(change.original_sources_revisited).issubset(opened):
            raise WorkflowPause('PAUSED_EXTERNAL', 'scope_original_sources_not_revisited')
        self.store.save_direction_change(run_id, change, original_audit=data(audit))
        self.store.update_run(run_id, assessment='SCOPE_CHANGE_PROPOSED')
        raise WorkflowPause('PAUSED_SCOPE_CHANGE', 'scope_change_requires_user')

    async def debate(self, run_id):
        run = self.store.get_run(run_id)
        if not run.card_id:
            raise WorkflowPause('PAUSED_PROTOCOL', 'card_required')
        # Every accepted round is checkpointed; completed roles in an interrupted
        # round are restored by Runtime using their stable task identifiers.
        completed_round = int(run.state.get('rounds_completed', 0))
        if completed_round > run.state.get('last_action_handled', 0) and run.state.get('final_ruling'):
            ruling = RESULT_SCHEMAS['moderator'].model_validate(run.state['final_ruling'])
            if await self.process_ruling(run_id, completed_round, ruling):
                return
        next_round = int(run.state.get('rounds_completed', 0)) + 1
        for number in range(next_round, self.settings.max_rounds + 1):
            context = self.context(run_id)
            proposer = await self.call(run_id, f'round{number}.proposer', 'proposer', payload=context)
            skeptic = await self.call(run_id, f'round{number}.skeptic', 'skeptic', payload={
                **self.context(run_id), 'proposer': data(proposer),
            })
            ruling = await self.call(run_id, f'round{number}.moderator', 'moderator', payload={
                **self.context(run_id), 'proposer': data(proposer), 'skeptic': data(skeptic),
            })
            if ruling.proposed_card_revision is not None:
                run = self.store.get_run(run_id)
                original_subject = run.state['task_inputs'][f'round{number}.moderator']['subject']
                card = self.store.get_card(original_subject['card_id'], original_subject['card_version'])
                if ruling.proposed_card_revision.problem_anchor != card.draft.problem_anchor:
                    raise WorkflowPause('PAUSED_PROTOCOL', 'problem_anchor_changed')
                self.store.validate_claim_dependencies(card, ruling.proposed_card_revision)
                revised = self.store.save_card(ruling.proposed_card_revision,
                                                card_id=card.card_id, parent_version=card.version,
                                                creation_key=f'{run_id}.round{number}.revision')
                self.store.update_run(run_id, card_version=revised.version)
            self.store.apply_issues(run_id, ruling.updated_issues, ruling.issue_transitions,
                event_key=f'{run_id}.round{number}',
                state_patch={'rounds_completed': number, 'final_ruling': data(ruling)})
            self.store.update_run(run_id, assessment=ruling.assessment)
            if await self.process_ruling(run_id, number, ruling):
                return
        self.complete(run_id, 'max_rounds_reached')

    async def process_ruling(self, run_id, number, ruling):
        self.store.update_run(run_id, assessment=ruling.assessment)
        action = ruling.next_action
        if action == 'PROPOSE_SCOPE_CHANGE':
            if ruling.direction_change is None:
                raise WorkflowPause('PAUSED_PROTOCOL', 'scope_change_missing')
            await self.scope_change(run_id, ruling.direction_change)
        if action in ('STOP', 'HANDOFF_EXPERIMENT'):
            self.complete(run_id, 'experiment_required' if action == 'HANDOFF_EXPERIMENT'
                          else ruling.stop_reason, ruling.assessment)
            return True
        issues = self.store.get_issues(run_id)
        if action == 'REASON':
            if not any(i.status == 'open' and i.next_action == 'REASON' and i.change_this_round for i in issues):
                raise WorkflowPause('PAUSED_PROTOCOL', 'reason_without_new_action')
        elif action == 'RETRIEVE':
            targets = [data(i) for i in issues if i.status == 'needs_retrieval']
            if not targets:
                raise WorkflowPause('PAUSED_PROTOCOL', 'retrieval_without_issue')
            await self.investigate(run_id, f'round{number}.retrieval', [], fresh=True,
                                   extra={'issue_targets': targets})
        else:
            raise WorkflowPause('PAUSED_PROTOCOL', 'invalid_next_action')
        self.checkpoint(run_id, last_action_handled=number)
        return False
