"""Default lightweight dispatch and interruption boundaries, entirely offline."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from arc.cli import app, new_run, services
from arc.config import Settings
from arc.discovery_models import FieldBrief, IdeaSeed, SketchResult, TriageResult, CandidateCheck
from arc.prompting import PromptLoader
from arc.schemas import SourceRecord
from arc.workflows import WorkflowEngine


class ScriptedRuntime:
    """The real WorkflowEngine caches inputs/results; this fake replaces only SDK I/O."""
    def __init__(self, results, *, include_polish=False):
        self.results = results
        self.loader = PromptLoader()
        # These fixtures isolate the research path; writer integration is exercised separately.
        if not include_polish:
            self.loader.manifest['prompts'].pop('writer.POLISH', None)
        self.tools = {name: object() for name in ('read_record', 'search_literature')}
        self.calls, self.payloads, self.profiles, self.accepted = [], {}, {}, {}
        self.before, self.after, self.traces = set(), set(), {}

    async def invoke(self, role, task, payload, result_schema, subject, task_id,
                     tool_profile, on_admitted=None):
        key = task_id.split('.', 1)[1]
        if key in self.accepted:
            return self.accepted[key]
        if key in self.before:
            self.before.remove(key)
            raise InterruptedError('before admission')
        if on_admitted:
            # Several requests in one task still consume one draw.
            on_admitted()
            on_admitted()
        self.calls.append((key, role, task))
        self.payloads[key], self.profiles[key] = deepcopy(payload), list(tool_profile)
        result = result_schema.model_validate(self.results[key])
        envelope = SimpleNamespace(result=result, result_status='complete',
            capability_requests=[], evidence_requests=[], note=None)
        self.accepted[key] = envelope
        if key in self.after:
            self.after.remove(key)
            raise InterruptedError('accepted response before workflow checkpoint')
        return envelope

    def tool_trace(self, task_id):
        return self.traces.get(task_id.split('.', 1)[1], [])


def fixture(tmp_path, monkeypatch, draws=1):
    settings = Settings(data_dir=tmp_path, draws=draws)
    run = new_run(settings, 'discover', topic='Independent evidence for memory routing',
                  boundaries=['No large model training'])
    store, ledger = services(settings)
    source = store.register_source(SourceRecord(title='Routing evidence', url='https://example.org/routing',
        source_type='paper', access_status='retrieved', content_origin='original'),
        content='The reported routing failure changes with retrieval conditions.')
    note = dict(source_id=source.source_id, finding='Routing depends on retrieval conditions.',
                relevance='The route comparison constrains a candidate mechanism.', access='passage', limits='One setup.')
    brief = dict(overview='Different routing mechanisms share an untested retrieval assumption.',
        research_lines=['Memory selection and retrieval conditions interact.'],
        openings=['Can an unnecessary routing step be removed?'], source_notes=[note], search_limits=['One local paper.'])
    seed = dict(title='Remove redundant routing', question='When can routing be eliminated?',
        insight='Use the existing retrieval condition to avoid redundant routing.',
        why_it_matters='It could remove an expensive decision rather than add a module.',
        difference_from_known='The existing route always makes this decision.',
        source_ids=[source.source_id], key_unknown='Whether selection changes with the condition.')
    publications = []
    monkeypatch.setattr('arc.discovery_workflow.publish', lambda engine, rid:
        publications.append(deepcopy(engine.store.list_discovery_ideas(rid))))
    return settings, run, store, ledger, brief, seed, publications


def sketch(seed=None, action='submit', next_search=None):
    return dict(action=action, seed=seed, reason='This direction has a concrete question.', next_search=next_search)


def triage(action):
    return dict(action=action, reason='A specific difference merits checking.' if action == 'investigate' else 'Leave this direction here.',
        strongest_objection='The difference may already be known.',
        check_questions=['Does a known method remove the same decision?'] if action == 'investigate' else [])


def checked(seed, note, updates=None):
    return dict(note=dict(seed=seed, decision='discuss', reason='The proposed simplification has a concrete motivation.',
        nearest_work=[], feasibility='Inspect the existing routing interface.', resources={'basis': 'No runtime measured.'},
        main_risk='The existing method may already implement the operation.', next_question='Compare the routing condition.',
        source_notes=[note], limits=['No research experiment performed.'], changes_from_seed=[]), field_updates=updates or [])


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ['drop', 'park'])
async def test_default_new_run_early_editor_decision_never_creates_card_or_check(tmp_path, monkeypatch, action):
    settings, run, store, ledger, brief, seed, publications = fixture(tmp_path, monkeypatch)
    assert run.state['discover_first'] and run.card_id is None
    runtime = ScriptedRuntime({'survey': brief, 'idea1.sketch': sketch(seed), 'idea1.triage': triage(action)})
    result = await WorkflowEngine(store, runtime, settings).execute(run.run_id)
    assert result.status == 'COMPLETED' and result.assessment is None
    assert [(r, t) for _, r, t in runtime.calls] == [('scout', 'SURVEY'), ('ideator', 'SKETCH'), ('editor', 'TRIAGE')]
    assert store.list_cards(run_id=run.run_id) == []
    assert store.list_discovery_ideas(run.run_id)[0]['status'] == action
    assert any(items and items[0]['status'] == 'pending' for items in publications)
    assert runtime.profiles['idea1.sketch'] == runtime.profiles['idea1.triage'] == []
    assert store.get_campaign(run.campaign_id).draws_started == 1
    assert ledger.summary(run.run_id)['call_count'] == 0


@pytest.mark.asyncio
async def test_checked_updates_reach_next_sketch_with_original_task_and_relation_brief(tmp_path, monkeypatch):
    settings, run, store, ledger, brief, seed, publications = fixture(tmp_path, monkeypatch, draws=2)
    extra = store.register_source(SourceRecord(title='New near neighbor', url='https://example.org/neighbor',
        source_type='paper', access_status='retrieved', content_origin='original'), content='An existing method removes the gate.')
    update = dict(source_id=extra.source_id, finding='A neighbor removes the gate.',
        relevance='The next idea must offer a distinct operation.', access='passage', limits='Limited setup.')
    review = checked(seed, brief['source_notes'][0], [update])
    review['field_revision'] = {'overview': 'The gate already exists; the question is its failure boundary.',
        'research_lines': ['Existing routing eliminates the extra gate.'], 'openings': ['When does the existing gate fail?']}
    review['note']['current_understanding'] = {'core_insight': 'The missing piece is a failure boundary, not a new gate.',
        'invalidated_premises': ['The gate has not been studied.'], 'decisive_unknown': 'Whether its boundary matters.',
        'why_existing_insufficient': 'Unknown until the boundary is checked.'}
    runtime = ScriptedRuntime({'survey': brief, 'idea1.sketch': sketch(seed, next_search='Read the missing route.'),
        'idea1.triage': triage('investigate'), 'idea1.check': review, 'idea2.sketch': sketch(action='stop')})
    runtime.traces['idea1.check'] = [{'name': 'read_record', 'status': 'completed',
        'source_ids': [seed['source_ids'][0]], 'result': {'source_id': seed['source_ids'][0], 'content': 'Actual cached passage.'}}]
    final = await WorkflowEngine(store, runtime, settings).execute(run.run_id)
    assert runtime.payloads['idea1.check']['shared_followup_question'] == 'Read the missing route.'
    assert sum(task == 'SURVEY' for _, _, task in runtime.calls) == 1
    assert not final.state.get('survey_refresh_used')
    payload = runtime.payloads['idea2.sketch']
    assert update in payload['field_brief']['source_notes']
    assert payload['field_brief']['overview'] == review['field_revision']['overview']
    assert payload['field_brief']['research_lines'] == review['field_revision']['research_lines']
    assert final.state['field_brief_history'][0]['field_brief'] == brief
    assert payload['previous_directions'][0]['current_understanding'] == review['note']['current_understanding']
    assert 'content_path' not in payload['sources'][0] and 'content_sha256' not in payload['sources'][0]
    assert payload['brief_version'] == 2
    assert payload['original_question'] == store.get_campaign(run.campaign_id).topic
    assert payload['user_boundaries'] == ['No large model training']
    assert payload['previous_directions']
    assert final.status == 'COMPLETED' and final.state['first_seed_at'] and final.state['first_note_at']
    first = store.list_discovery_ideas(run.run_id)[0]
    assert first['note']['decision'] == 'discuss' and first['check_action_observed']
    assert store.list_cards(run_id=run.run_id) == []


@pytest.mark.asyncio
async def test_reusing_supplied_read_notes_does_not_require_a_redundant_tool_call(tmp_path, monkeypatch):
    settings, run, store, ledger, brief, seed, publications = fixture(tmp_path, monkeypatch)
    runtime = ScriptedRuntime({'survey': brief, 'idea1.sketch': sketch(seed), 'idea1.triage': triage('investigate'),
        'idea1.check': checked(seed, brief['source_notes'][0])})
    await WorkflowEngine(store, runtime, settings).execute(run.run_id)
    result = store.list_discovery_ideas(run.run_id)[0]
    assert not result['check_action_observed'] and result['note']['decision'] == 'discuss'
    assert result['check_material_basis'] == 'shared_notes'
    assert len(result['note']['limits']) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('boundary', ['before', 'after'])
async def test_sketch_admission_resume_reuses_survey_and_draw_even_after_response_acceptance(tmp_path, monkeypatch, boundary):
    settings, run, store, ledger, brief, seed, publications = fixture(tmp_path, monkeypatch)
    runtime = ScriptedRuntime({'survey': brief, 'idea1.sketch': sketch(seed), 'idea1.triage': triage('drop')})
    getattr(runtime, boundary).add('idea1.sketch')
    engine = WorkflowEngine(store, runtime, settings)
    with pytest.raises(InterruptedError):
        await engine.execute(run.run_id)
    assert store.get_campaign(run.campaign_id).draws_started == (0 if boundary == 'before' else 1)
    await engine.execute(run.run_id)
    ids = [item['idea_id'] for item in store.list_discovery_ideas(run.run_id)]
    assert len(ids) == 1 and store.get_campaign(run.campaign_id).draws_started == 1
    assert len(runtime.calls) == 3
    await engine.execute(run.run_id)
    assert len(runtime.calls) == 3 and [item['idea_id'] for item in store.list_discovery_ideas(run.run_id)] == ids


@pytest.mark.asyncio
async def test_five_skips_are_five_opportunities_and_stop_does_not_need_full_draw_count(tmp_path, monkeypatch):
    settings, run, store, ledger, brief, seed, publications = fixture(tmp_path, monkeypatch, draws=5)
    runtime = ScriptedRuntime({'survey': brief, **{f'idea{i}.sketch': sketch(action='skip') for i in range(1, 6)}})
    await WorkflowEngine(store, runtime, settings).execute(run.run_id)
    assert store.get_campaign(run.campaign_id).draws_started == 5
    assert len(runtime.calls) == 6 and len(store.list_discovery_ideas(run.run_id)) == 5
    assert all(item['seed'] is None for item in store.list_discovery_ideas(run.run_id))
    assert store.list_cards(run_id=run.run_id) == []


@pytest.mark.asyncio
@pytest.mark.parametrize('boundary', ['before', 'after'])
async def test_pending_refresh_finishes_before_next_sketch_on_resume(tmp_path, monkeypatch, boundary):
    settings, run, store, ledger, brief, seed, publications = fixture(tmp_path, monkeypatch, draws=2)
    refreshed = deepcopy(brief)
    refreshed['openings'] = ['A newly discovered route enables a different operation.']
    runtime = ScriptedRuntime({'survey': brief, 'idea1.sketch': sketch(action='skip', next_search='Read the missing route.'),
        'survey.refresh': refreshed, 'idea2.sketch': sketch(action='stop')})
    getattr(runtime, boundary).add('survey.refresh')
    engine = WorkflowEngine(store, runtime, settings)
    with pytest.raises(InterruptedError):
        await engine.execute(run.run_id)
    await engine.execute(run.run_id)
    assert runtime.payloads['idea2.sketch']['field_brief']['openings'] == refreshed['openings']
    assert [k for k, _, _ in runtime.calls] == ['survey', 'idea1.sketch', 'survey.refresh', 'idea2.sketch']
    assert store.get_campaign(run.campaign_id).draws_started == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('mode, task', [('develop', 'DEVELOP'), ('run', 'PRESSURE')])
async def test_explicit_idea_handoff_routes_directly_to_prestudy_without_carddraft(tmp_path, monkeypatch, mode, task):
    settings, origin, store, ledger, brief, seed, publications = fixture(tmp_path, monkeypatch)
    store.update_run(origin.run_id, state={**origin.state, 'field_brief': brief, 'brief_version': 1})
    idea = store.save_discovery_idea(origin.run_id, 'idea1', seed=seed, note=checked(seed, brief['source_notes'][0])['note'], status='checked')
    run = new_run(settings, mode, idea_id=idea['idea_id'])
    runtime = ScriptedRuntime({'prestudy': checked(seed, brief['source_notes'][0])})
    result = await WorkflowEngine(store, runtime, settings).execute(run.run_id)
    assert runtime.calls == [('prestudy', 'scout', task)]
    assert result.status == 'COMPLETED' and result.card_id is None
    assert runtime.payloads['prestudy']['original_question'] == store.get_campaign(origin.campaign_id).topic
    assert runtime.payloads['prestudy']['seed'] == seed and runtime.payloads['prestudy']['field_brief'] == brief
    assert store.list_cards(run_id=run.run_id) == []


@pytest.mark.parametrize('command', ['develop', 'run'])
def test_idea_cli_flag_creates_explicit_stage_and_rejects_ambiguous_input(tmp_path, monkeypatch, command):
    settings, origin, store, ledger, brief, seed, publications = fixture(tmp_path, monkeypatch)
    store.update_run(origin.run_id, state={**origin.state, 'field_brief': brief})
    idea = store.save_discovery_idea(origin.run_id, 'idea1', seed=seed)
    observed = []
    async def offline(settings, run_id):
        stage = services(settings)[0].get_run(run_id)
        observed.append(stage)
        assert stage.mode == command and stage.state['idea_input']['idea_id'] == idea['idea_id']
        assert stage.card_id is None
    monkeypatch.setattr('arc.cli.execute', offline)
    runner = CliRunner()
    result = runner.invoke(app, ['--data-dir', str(tmp_path), command, '--idea', idea['idea_id']])
    assert result.exit_code == 0, result.output + repr(result.exception)
    assert len(observed) == 1
    invalid = runner.invoke(app, ['--data-dir', str(tmp_path), command, '--idea', idea['idea_id'], '--question', 'Other topic'])
    assert invalid.exit_code != 0 and len(observed) == 1


@pytest.mark.asyncio
async def test_stop_persisted_before_completion_cannot_reopen_next_draw(tmp_path, monkeypatch):
    settings, run, store, ledger, brief, seed, publications = fixture(tmp_path, monkeypatch, draws=2)
    runtime = ScriptedRuntime({'survey': brief, 'idea1.sketch': sketch(action='stop')})
    engine = WorkflowEngine(store, runtime, settings)
    checkpoint = engine.checkpoint
    def interrupt_after_stop(run_id, **updates):
        result = checkpoint(run_id, **updates)
        if updates.get('idea1_done'):
            monkeypatch.setattr(engine, 'checkpoint', checkpoint)
            raise InterruptedError('STOP saved before run completion')
        return result
    monkeypatch.setattr(engine, 'checkpoint', interrupt_after_stop)
    with pytest.raises(InterruptedError):
        await engine.execute(run.run_id)
    final = await engine.execute(run.run_id)
    assert final.status == 'COMPLETED' and final.stop_reason == 'ideator_stopped'
    assert runtime.calls == [('survey', 'scout', 'SURVEY'), ('idea1.sketch', 'ideator', 'SKETCH')]
    assert store.get_campaign(run.campaign_id).draws_started == 1


@pytest.mark.asyncio
async def test_next_direction_sees_actual_check_rejection_and_core_insight(tmp_path, monkeypatch):
    settings, run, store, ledger, brief, seed, publications = fixture(tmp_path, monkeypatch, draws=2)
    check = checked(seed, brief['source_notes'][0])
    check['note'].update(decision='drop', reason='The proposed operation already exists in the cited method.')
    runtime = ScriptedRuntime({'survey': brief, 'idea1.sketch': sketch(seed), 'idea1.triage': triage('investigate'),
        'idea1.check': check, 'idea2.sketch': sketch(action='stop')})
    await WorkflowEngine(store, runtime, settings).execute(run.run_id)
    previous = runtime.payloads['idea2.sketch']['previous_directions'][0]
    assert previous['decision'] == 'drop'
    assert previous['current_understanding']['core_insight'] == check['note']['reason']
    assert 'seed' not in previous and 'triage' not in previous
    assert store.list_discovery_ideas(run.run_id)[0]['seed'] == seed


@pytest.mark.asyncio
async def test_selected_idea_pressure_stage_receives_latest_completed_develop_note(tmp_path, monkeypatch):
    settings, origin, store, ledger, brief, seed, publications = fixture(tmp_path, monkeypatch)
    original_note = checked(seed, brief['source_notes'][0])['note']
    store.update_run(origin.run_id, state={**origin.state, 'field_brief': brief})
    idea = store.save_discovery_idea(origin.run_id, 'idea1', seed=seed, note=original_note, status='checked')
    develop = new_run(settings, 'develop', idea_id=idea['idea_id'])
    developed = deepcopy(original_note)
    developed.update(decision='lead', reason='Development found a specific implementation barrier.')
    store.update_run(develop.run_id, status='COMPLETED',
        state={**develop.state, 'prestudy_note': developed})
    pressure = new_run(settings, 'run', idea_id=idea['idea_id'])
    assert pressure.state['idea_input']['seed'] == seed
    assert pressure.state['idea_input']['latest_note'] == developed


@pytest.mark.asyncio
async def test_completed_same_scope_survey_is_reused_as_material_without_old_verdict(tmp_path, monkeypatch):
    settings, prior, store, ledger, brief, seed, publications = fixture(tmp_path, monkeypatch)
    store.update_run(prior.run_id, status='COMPLETED', assessment='PROMISING',
        state={**prior.state, 'field_brief': brief, 'brief_version': 3,
               'previous_directions': [{'reason': 'Previously approved.'}]})
    topic = store.get_campaign(prior.campaign_id).topic
    run = new_run(settings, 'discover', topic=topic, boundaries=['No large model training'])
    runtime = ScriptedRuntime({'survey': brief, 'idea1.sketch': sketch(action='stop')})
    await WorkflowEngine(store, runtime, settings).execute(run.run_id)
    assert runtime.payloads['survey']['field_brief'] == brief
    assert runtime.payloads['survey']['sources'][0]['source_id'] == brief['source_notes'][0]['source_id']
    assert 'assessment' not in runtime.payloads['survey']
    assert runtime.payloads['idea1.sketch']['previous_directions'] == []
    assert store.get_run(run.run_id).assessment is None
    changed = new_run(settings, 'discover', topic=topic, boundaries=['Different data access'])
    assert 'reusable_survey' not in changed.state
    store.update_run(prior.run_id, status='PAUSED_EXTERNAL')
    # Completed current material remains reusable, but an unfinished unrelated
    # same-topic run cannot displace it merely by being newer.
    assert store.get_run(changed.run_id).state.get('field_brief') is None


@pytest.mark.asyncio
async def test_editor_compares_current_run_latest_verdict_and_excludes_self(tmp_path, monkeypatch):
    settings, run, store, ledger, brief, seed, publications = fixture(tmp_path, monkeypatch, draws=2)
    review = checked(seed, brief['source_notes'][0])
    review['note'].update(decision='drop', reason='The required user preference fields are absent.',
        changes_from_seed=['The proposed dataset has no user preferences.'])
    second = deepcopy(seed);second.update(title='An evaluation route', insight='Test a different observable error.')
    runtime = ScriptedRuntime({'survey': brief, 'idea1.sketch': sketch(seed), 'idea1.triage': triage('investigate'),
        'idea1.check': review, 'idea2.sketch': sketch(second), 'idea2.triage': triage('park')})
    await WorkflowEngine(store, runtime, settings).execute(run.run_id)
    payload = runtime.payloads['idea2.triage']
    assert payload['require_candidate_relation']
    assert [x['draw_id'] for x in payload['previous_directions']] == ['idea1']
    previous = payload['previous_directions'][0]
    assert previous['decision'] == 'drop'
    assert previous['current_understanding']['invalidated_premises'] == review['note']['changes_from_seed']
    assert previous['current_understanding']['core_insight'] == review['note']['reason']
    assert payload['seed'] == second and payload['original_question'] == store.get_campaign(run.campaign_id).topic
    assert 'idea2.check' not in runtime.payloads


@pytest.mark.asyncio
async def test_metadata_only_input_cannot_count_as_reused_reading(tmp_path, monkeypatch):
    settings, run, store, ledger, brief, seed, publications = fixture(tmp_path, monkeypatch)
    brief['source_notes'][0]['access'] = 'metadata'
    runtime = ScriptedRuntime({'survey': brief, 'idea1.sketch': sketch(seed), 'idea1.triage': triage('investigate'),
        'idea1.check': checked(seed, brief['source_notes'][0])})
    await WorkflowEngine(store, runtime, settings).execute(run.run_id)
    result = store.list_discovery_ideas(run.run_id)[0]
    assert result['note']['decision'] == 'lead' and result['check_material_basis'] == 'unverified'
    assert not result['check_action_observed']


def test_brief_correction_replaces_current_reading_but_keeps_old_brief(tmp_path, monkeypatch):
    from arc.discovery_models import SourceNote, FieldRevision
    from arc.discovery_workflow import merge_updates
    settings, run, store, ledger, brief, seed, _ = fixture(tmp_path, monkeypatch)
    store.update_run(run.run_id, state={**run.state, 'field_brief': brief, 'brief_version': 1})
    engine = WorkflowEngine(store, None, settings)
    correction = {**brief['source_notes'][0], 'finding': 'The earlier source interpretation was wrong.'}
    merge_updates(engine, run.run_id, [SourceNote.model_validate(correction)],
        FieldRevision(overview='The current interpretation is narrower.', openings=[]))
    state = store.get_run(run.run_id).state
    assert state['field_brief']['source_notes'] == [correction]
    assert state['field_brief']['openings'] == []
    assert state['field_brief']['research_lines'] == brief['research_lines']
    assert state['field_brief_history'][0]['field_brief'] == brief
    merge_updates(engine, run.run_id, [SourceNote.model_validate(correction)])
    assert store.get_run(run.run_id).state['brief_version'] == 2


@pytest.mark.asyncio
async def test_final_writer_is_once_cached_and_does_not_repeat_research_after_pause(tmp_path, monkeypatch):
    settings, run, store, ledger, brief, seed, _ = fixture(tmp_path, monkeypatch)
    runtime = ScriptedRuntime({'survey': brief, 'idea1.sketch': sketch(seed),
        'idea1.triage': triage('drop')}, include_polish=True)
    # Pause at writer admission so the completed candidate already exists.
    runtime.before.add('polish')
    engine = WorkflowEngine(store, runtime, settings)
    with pytest.raises(InterruptedError):
        await engine.execute(run.run_id)
    current = store.get_run(run.run_id)
    assert current.state['idea1_done'] and current.status != 'COMPLETED'
    idea = store.list_discovery_ideas(run.run_id)[0]
    runtime.results['polish'] = {'stage_summary': '本轮放下该线索。',
        'overview': '现有材料尚不支持独立研究价值。',
        'candidates': [{'idea_id': idea['idea_id'], 'text': '这条路线缺少清楚的差异，先不投入。',
                        'cited_source_ids': seed['source_ids']}],
        'cited_source_ids': seed['source_ids']}
    final = await engine.execute(run.run_id)
    assert final.status == 'COMPLETED' and final.state['polish']['stage_summary']
    assert len(runtime.calls) == 4 and runtime.calls[-1][1:] == ('writer', 'POLISH')
    assert runtime.profiles['polish'] == []
    assert store.list_discovery_ideas(run.run_id)[0] == idea
    await engine.execute(run.run_id)
    assert len(runtime.calls) == 4


@pytest.mark.asyncio
async def test_lightweight_prestudy_also_finishes_with_one_writer(tmp_path, monkeypatch):
    settings, discovery, store, ledger, brief, seed, _ = fixture(tmp_path, monkeypatch)
    note = checked(seed, brief['source_notes'][0])
    note['field_revision'] = {'overview': '开发补查发现原先的空白已被覆盖。'}
    idea = store.save_discovery_idea(discovery.run_id, 'idea1', seed=seed, note=note['note'], status='checked')
    state = dict(discovery.state); state['field_brief'] = brief
    store.update_run(discovery.run_id, state=state)
    stage = new_run(settings, 'develop', idea_id=idea['idea_id'])
    output = {'stage_summary': '补查了一个关键前提。', 'overview': '下一步先确认是否值得投入。',
        'candidates': [{'idea_id': idea['idea_id'], 'text': '已有材料提供起点，但主要风险仍待判断。',
                        'cited_source_ids': seed['source_ids']}], 'cited_source_ids': seed['source_ids']}
    runtime = ScriptedRuntime({'prestudy': note, 'polish': output}, include_polish=True)
    final = await WorkflowEngine(store, runtime, settings).execute(stage.run_id)
    assert final.status == 'COMPLETED'
    assert [task for _, _, task in runtime.calls] == ['DEVELOP', 'POLISH']
    assert final.state['prestudy_note']['decision'] == 'discuss'

    assert final.state['field_brief']['overview'] == note['field_revision']['overview']
    assert store.get_run(discovery.run_id).state['field_brief']['overview'] == brief['overview']
    followup = new_run(settings, 'run', idea_id=idea['idea_id'])
    assert followup.state['idea_input']['field_brief']['overview'] == note['field_revision']['overview']


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ['park', 'drop'])
async def test_unchecked_candidate_keeps_shared_followup(tmp_path, monkeypatch, action):
    settings, run, store, ledger, brief, seed, _ = fixture(tmp_path, monkeypatch, draws=2)
    runtime = ScriptedRuntime({'survey': brief, 'idea1.sketch': sketch(seed, next_search='Read the missing route.'),
        'idea1.triage': triage(action), 'survey.refresh': brief, 'idea2.sketch': sketch(action='stop')})
    await WorkflowEngine(store, runtime, settings).execute(run.run_id)
    assert runtime.payloads['survey.refresh']['refresh_question'] == 'Read the missing route.'
    assert [key for key, _, _ in runtime.calls] == [
        'survey', 'idea1.sketch', 'idea1.triage', 'survey.refresh', 'idea2.sketch']


@pytest.mark.asyncio
@pytest.mark.parametrize('boundary', ['before', 'after'])
async def test_check_followup_handoff_survives_interruption(tmp_path, monkeypatch, boundary):
    settings, run, store, ledger, brief, seed, _ = fixture(tmp_path, monkeypatch, draws=2)
    runtime = ScriptedRuntime({'survey': brief, 'idea1.sketch': sketch(seed, next_search='Read the missing route.'),
        'idea1.triage': triage('investigate'), 'idea1.check': checked(seed, brief['source_notes'][0]),
        'idea2.sketch': sketch(action='stop')})
    getattr(runtime, boundary).add('idea1.check')
    engine = WorkflowEngine(store, runtime, settings)
    with pytest.raises(InterruptedError):
        await engine.execute(run.run_id)
    assert store.get_run(run.run_id).state['task_inputs']['idea1.check']['payload']['shared_followup_question']
    final = await engine.execute(run.run_id)
    assert sum(task == 'SURVEY' for _, _, task in runtime.calls) == 1
    assert not final.state.get('survey_refresh_used')


@pytest.mark.asyncio
async def test_historical_check_without_followup_input_does_not_suppress_refresh(tmp_path, monkeypatch):
    settings, run, store, ledger, brief, seed, _ = fixture(tmp_path, monkeypatch, draws=2)
    runtime = ScriptedRuntime({'survey': brief, 'idea1.sketch': sketch(seed, next_search='Read the missing route.'),
        'idea1.triage': triage('investigate'), 'idea1.check': checked(seed, brief['source_notes'][0]),
        'survey.refresh': brief, 'idea2.sketch': sketch(action='stop')})
    runtime.before.add('idea1.check')
    engine = WorkflowEngine(store, runtime, settings)
    with pytest.raises(InterruptedError):
        await engine.execute(run.run_id)
    state = deepcopy(store.get_run(run.run_id).state)
    state['task_inputs']['idea1.check']['payload'].pop('shared_followup_question')
    store.update_run(run.run_id, state=state)
    await engine.execute(run.run_id)
    assert 'shared_followup_question' not in runtime.payloads['idea1.check']
    assert runtime.payloads['survey.refresh']['refresh_question'] == 'Read the missing route.'


@pytest.mark.asyncio
async def test_fifth_candidate_reviews_can_address_current_draw_without_allowing_unknown_ids(tmp_path, monkeypatch):
    from arc.runtime import Runtime
    from arc.schemas import Envelope
    from arc.store import StateError

    settings, run, store, ledger, brief, seed, _ = fixture(tmp_path, monkeypatch, draws=5)
    results = {'survey': brief}
    for ordinal in range(1, 6):
        results[f'idea{ordinal}.sketch'] = sketch(seed)
        results[f'idea{ordinal}.triage'] = triage('investigate' if ordinal == 5 else 'park')
    results['idea5.check'] = checked(seed, brief['source_notes'][0])
    scripted = ScriptedRuntime(results)
    await WorkflowEngine(store, scripted, settings).execute(run.run_id)
    # Use the actual schema and the runtime's pure target validation on the
    # frozen workflow payloads. No provider, tools, or ledger writes are needed.
    validator = object.__new__(Runtime)
    request = dict(request_local_id='check-premise', claim_id=None, issue_id=None, draw_id='idea5',
        question='Does existing work remove this routing decision?', target_source_ids=[],
        queries=['routing decision removal'], purpose='Resolve the candidate-specific premise.',
        decision_if_supported='Reconsider the claimed difference.',
        decision_if_contradicted='Retain the premise as unresolved.')
    for task, schema in [('triage', TriageResult), ('check', CandidateCheck)]:
        payload = store.get_run(run.run_id).state['task_inputs'][f'idea5.{task}']['payload']
        assert payload['draw_id'] == 'idea5'
        assert [item['draw_id'] for item in payload['previous_directions']] == [
            'idea1', 'idea2', 'idea3', 'idea4']
        envelope = Envelope[schema].model_validate(dict(schema_version='arc.v1',
            task_id=f'{run.run_id}.idea5.{task}',
            subject=dict(run_id=run.run_id, campaign_id=run.campaign_id, card_id=None, card_version=None),
            result_status='needs_evidence', result=None, evidence_requests=[request],
            capability_requests=[], note='The current candidate requires a premise check.'))
        validator._validate_evidence_request_targets(envelope, payload)
        # Reproduce the previous omission: previous candidates alone cannot
        # authorize a request for the current candidate.
        with pytest.raises(StateError, match='evidence_request_draw_id_not_supplied_to_task'):
            validator._validate_evidence_request_targets(envelope, {
                name: value for name, value in payload.items() if name != 'draw_id'})
        envelope.evidence_requests[0].draw_id = 'idea6'
        with pytest.raises(StateError, match='evidence_request_draw_id_not_supplied_to_task'):
            validator._validate_evidence_request_targets(envelope, payload)
    assert ledger.summary(run.run_id)['call_count'] == 0
