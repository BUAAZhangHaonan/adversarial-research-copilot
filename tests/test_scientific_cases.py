"""Fixture integrity tests, not a claim about model correction performance."""
from collections import Counter
import json
from arc.schemas import CardDraft
from arc.store import Store
from tests.helpers.scientific_cases import load_scientific_cases,model_payload,register_scientific_case

def test_eight_paired_cases_are_schema_valid_and_expected_is_private():
    cases=load_scientific_cases()
    assert len(cases)==8
    assert Counter(case['pair_id'] for case in cases)=={'scope':2,'attribution':2,'interaction':2,'partition':2}
    for case in cases:
        payload=model_payload(case)
        CardDraft.model_validate(payload['card'])
        serialized=json.dumps(payload,ensure_ascii=False)
        assert 'expected' not in payload and 'case_id' not in payload and 'pair_id' not in payload
        assert 'repair_acceptance' not in serialized and 'has_target_hard_error' not in serialized
        assert case['case_id'] not in serialized
        for evidence in payload['evidence']:
            source=next(source for source in payload['sources'] if source['source_id']==evidence['source_id'])
            assert evidence['excerpt'] in source['content']

def test_pairs_keep_original_question_and_evidence_fixed():
    cases=load_scientific_cases()
    for pair_id in {case['pair_id'] for case in cases}:
        pair=[case for case in cases if case['pair_id']==pair_id]
        assert sum(case['expected']['has_target_hard_error'] for case in pair)==1
        good,bad=[model_payload(case) for case in pair]
        assert good['original_task']==bad['original_task']
        assert good['sources']==bad['sources'] and good['evidence']==bad['evidence']
        assert good['card']!=bad['card']

def test_explicit_registration_does_not_create_runs_or_tasks(tmp_path):
    for case in load_scientific_cases():
        store=Store(tmp_path/(case['case_id']+'.sqlite'))
        card,payload=register_scientific_case(store,case,creation_key=case['case_id'])
        assert card.draft.model_dump(mode='json')==payload['card']
        assert store.get_record(payload['sources'][0]['source_id'])['access_status']=='retrieved'
        assert store.get_record(payload['evidence'][0]['evidence_id'])['verification_status']=='verified'
        with store._connect() as db:
            assert db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]==0
            assert db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]==0
