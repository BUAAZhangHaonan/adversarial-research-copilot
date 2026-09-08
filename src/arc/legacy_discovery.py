"""Resume the pre-redesign discovery protocol only for existing checkpoints.

New campaigns use scientific.discover. Retained to avoid changing admitted tasks.
"""
from .workflows import data, WorkflowPause
from .validation import validate_selection

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

