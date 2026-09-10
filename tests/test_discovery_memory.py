from copy import deepcopy
import json
from arc.discovery_memory import current_idea_view
from arc.store import Store


def seed():
    return dict(title='Original gate', question='Can routing be removed?',
        insight='A redundant gate can always be removed.', difference_from_known='Known gate',
        key_unknown='Whether removal is safe.', source_ids=[])


def note(explicit=False):
    result=dict(seed={**seed(), 'title':'Conditioned routing'}, decision='drop',
        reason='The unconditional shortcut duplicates existing work.',
        main_risk='Existing controls cover this distinction.', next_question='Can an earlier signal exist?',
        changes_from_seed=['Zebracorrection: the routing signal is unavailable before retrieval.'])
    if explicit:
        result['current_understanding']=dict(core_insight='Keep the routing dependency explicit.',
            invalidated_premises=['The gate is not redundant.'], decisive_unknown='Can signal be observed earlier?',
            why_existing_insufficient='An earlier observable signal is absent.')
    return result


def environment(tmp_path):
    store=Store(tmp_path/'state.sqlite');campaign=store.create_campaign('Routing scope',[])
    return store,store.create_run('discover',campaign_id=campaign.campaign_id),store.create_run('discover',campaign_id=campaign.campaign_id)


def test_historical_checked_view_does_not_revive_seed_or_investigate():
    record=dict(idea_id='idea',run_id='run',draw_id='draw',seed=seed(),
        triage={'action':'investigate','reason':'Initially novel'},note=note(),status='checked')
    before=deepcopy(record);view=current_idea_view(record)
    assert view['decision']=='drop' and view['status']=='checked' and view['origin']=='historical_note'
    assert view['title']=='Conditioned routing'
    assert view['current_understanding']==dict(core_insight=note()['reason'],
        invalidated_premises=note()['changes_from_seed'],decisive_unknown=note()['next_question'],
        why_existing_insufficient=note()['main_risk'])
    assert 'investigate' not in json.dumps(view) and seed()['insight'] not in json.dumps(view)
    assert not {'seed','note','triage'} & view.keys()
    view['current_understanding']['invalidated_premises'].append('Caller edit')
    assert record==before


def test_explicit_view_and_candidate_relation_are_lossless():
    record=dict(idea_id='idea',seed=seed(),note=note(True),status='checked',
        triage={'action':'investigate','candidate_relation':{'kind':'distinct','reason':'Another question'}})
    view=current_idea_view(record)
    assert view['origin']=='explicit_note' and view['current_understanding']==note(True)['current_understanding']
    assert view['candidate_relation']==record['triage']['candidate_relation']
    view['candidate_relation']['reason']='Changed'
    assert record['triage']['candidate_relation']['reason']=='Another question'


def test_pending_view_keeps_preliminary_reason_and_unknown():
    record=dict(idea_id='idea',seed=seed(),note=None,status='park',triage={'action':'park','reason':'No source available'})
    view=current_idea_view(record)
    assert view['origin']=='pending_seed' and view['decision']=='park'
    assert view['current_understanding']['core_insight']==seed()['insight']
    assert view['current_understanding']['decisive_unknown']==seed()['key_unknown']
    assert view['current_understanding']['why_existing_insufficient']=='No source available'
    assert current_idea_view({'idea_id':'empty','status':'pending'})['decision']=='pending'


def test_latest_corrections_searchable_and_original_record_preserved(tmp_path):
    store,first,second=environment(tmp_path)
    original=store.save_discovery_idea(first.run_id,'draw1',seed=seed(),triage={'action':'investigate'},status='pending')
    assert store.lookup_discovery_ideas('Zebracorrection')==[]
    saved=store.save_discovery_idea(first.run_id,'draw1',note=note(),status='checked',check_material_basis='shared_notes')
    found=store.lookup_discovery_ideas('Zebracorrection',exclude_run_id=second.run_id)
    assert len(found)==1 and found[0]['idea_id']==original['idea_id'] and found[0]['decision']=='drop'
    assert store.lookup_discovery_ideas('Zebracorrection',exclude_run_id=first.run_id)==[]
    assert store.get_record(saved['idea_id'])['seed']==original['seed']==seed()
    assert store.get_record(saved['idea_id'])['check_material_basis']=='shared_notes'
    updated=note(True);updated['current_understanding']['core_insight']='Octopuscorrection is current.'
    store.save_discovery_idea(first.run_id,'draw1',note=updated,status='checked')
    assert store.lookup_discovery_ideas('Octopuscorrection')[0]['origin']=='explicit_note'
    assert store.lookup_discovery_ideas('Zebracorrection')[0]['origin']=='explicit_note'
    updated['changes_from_seed']=['The current corrected statement replaces the prior one.']
    store.save_discovery_idea(first.run_id,'draw1',note=updated,status='checked')
    assert store.lookup_discovery_ideas('Zebracorrection')==[]


def test_explicit_reindex_is_idempotent_and_does_not_rewrite_records(tmp_path):
    store,first,_=environment(tmp_path)
    saved=store.save_discovery_idea(first.run_id,'draw1',seed=seed(),note=note(),status='checked')
    with store._transaction() as db:
        db.execute('DELETE FROM discovery_ideas_fts')
        db.execute('INSERT INTO discovery_ideas_fts VALUES (?,?)',(saved['idea_id'],'obsolete seed'))
    before=store.get_record(saved['idea_id'])
    assert store.lookup_discovery_ideas('Zebracorrection')==[]
    assert store.reindex_discovery_ideas()=={'indexed_ideas':1}
    assert store.lookup_discovery_ideas('Zebracorrection')[0]['decision']=='drop'
    assert store.reindex_discovery_ideas()=={'indexed_ideas':1}
    assert store.get_record(saved['idea_id'])==before
    with store._connect() as db:
        assert db.execute('SELECT COUNT(*) FROM discovery_ideas_fts').fetchone()[0]==1
