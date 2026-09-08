import json
from pathlib import Path

from arc.prompting import PromptLoader
from arc.schemas import CardDraft
from tests.helpers.scientific_cases import model_payload, scientific_case
from tests.test_prompts import ASSETS,DATA,SCHEMA


def test_value_regression_preserves_previously_seen_candidate_and_hides_expected_judgment():
    fixture=json.loads((Path(__file__).parent/'fixtures/value_calibration_regression.json').read_text())
    assert fixture['unseen_test'] is False and len(fixture['cases'])==1
    case=fixture['cases'][0]
    assert case['expected']['expected_value']=='routine'
    assert case['expected']['has_target_hard_error'] is False
    visible=model_payload(case)
    assert visible==model_payload(scientific_case(case['case_id']))
    CardDraft.model_validate(visible['card'])
    rendered=PromptLoader(ASSETS).render('scientific_reviewer.INVOKE',
        {**DATA,'payload':visible},schema=SCHEMA)
    task=rendered.messages[1]['content']
    assert 'expected_value' not in task and 'has_target_hard_error' not in task
    assert 'unseen_test' not in task and 'not_a_quality_label' not in task
    assert case['case_id'] not in task
