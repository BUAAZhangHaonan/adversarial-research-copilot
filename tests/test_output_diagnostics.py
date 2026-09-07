"""Trailing material remains invalid even when its complete JSON prefix is useful feedback."""
import json

import pytest
from pydantic import ValidationError

from arc.schemas import Envelope, ModeratorResult
from arc.validation import output_validation_errors
from .test_contracts import card_payload


ENVELOPE = Envelope[ModeratorResult]


def moderator_output(*, wrong_fields=False):
    card = card_payload()
    result = {'assessment': 'NEEDS_EVIDENCE', 'next_action': 'STOP',
              'stop_reason': 'Synthetic unresolved condition.', 'concise_ruling': '合成审查：缺少依据。',
              'issue_transitions': [], 'updated_issues': [], 'decisive_evidence_ids': [],
              'proposed_card_revision': card, 'external_test_requirements': [], 'direction_change': None}
    if wrong_fields:
        result['claims'] = result['proposed_card_revision'].pop('claims')
        del result['external_test_requirements']
        del result['direction_change']
    return {'schema_version': 'arc.v1', 'task_id': 'synthetic.moderator',
            'subject': {'campaign_id': None, 'run_id': 'synthetic', 'card_id': 'card1', 'card_version': 1},
            'result_status': 'complete', 'result': result,
            'evidence_requests': [], 'capability_requests': [], 'note': None}


def failed(raw):
    with pytest.raises(ValidationError) as caught:
        ENVELOPE.model_validate_json(raw)
    return caught.value


@pytest.mark.parametrize('suffix', [' trailing output', '\n{"second": "object"}'])
def test_complete_prefix_reports_syntax_wrong_level_and_missing_fields_together(suffix):
    leading = ' \n\t'
    prefix = json.dumps(moderator_output(wrong_fields=True), ensure_ascii=False)
    raw = leading + prefix + suffix
    original_raw = raw[:]
    original = failed(raw)
    before = original.errors(include_url=False, include_input=False)
    errors = output_validation_errors(raw, ENVELOPE, original)
    assert errors[:len(before)] == before and before[0]['type'] == 'json_invalid'
    supplemental = errors[len(before):]
    locations = {(tuple(error['loc']), error['type']) for error in supplemental}
    assert (('result', 'claims'), 'extra_forbidden') in locations
    assert (('result', 'proposed_card_revision', 'claims'), 'missing') in locations
    assert (('result', 'external_test_requirements'), 'missing') in locations
    assert (('result', 'direction_change'), 'missing') in locations
    assert all(error['diagnostic_source'] == 'complete_json_prefix' and error['feedback_only'] is True
               for error in supplemental)
    assert all(error['diagnostic_range'] == {'start': len(leading), 'end': len(leading + prefix),
                                           'unit': 'unicode_codepoints'} for error in supplemental)
    assert original.errors(include_url=False, include_input=False) == before and raw == original_raw
    assert failed(raw).errors(include_url=False, include_input=False) == before


def test_valid_complete_prefix_with_garbage_still_has_original_syntax_failure():
    raw = json.dumps(moderator_output()) + ' trailing garbage'
    original = failed(raw)
    errors = output_validation_errors(raw, ENVELOPE, original)
    assert errors == original.errors(include_url=False, include_input=False)
    assert len(errors) == 1 and errors[0]['type'] == 'json_invalid'
    assert not any(error.get('feedback_only') for error in errors)
    failed(raw)


@pytest.mark.parametrize('raw', [
    json.dumps(moderator_output(wrong_fields=True))[:-1],
    '{"result": {"claims": [',
    'not JSON ' + json.dumps(moderator_output(wrong_fields=True)),
    '[{"not": "an envelope"}] garbage',
])
def test_truncated_leading_garbage_or_nonobject_does_not_get_guessed_schema_errors(raw):
    original = failed(raw)
    assert output_validation_errors(raw, ENVELOPE, original) == original.errors(include_url=False, include_input=False)


@pytest.mark.parametrize('constant', ['NaN', 'Infinity', '-Infinity'])
def test_non_json_numeric_constants_are_not_used_for_prefix_diagnostics(constant):
    raw = '{"unexpected": ' + constant + '} garbage'
    original = failed(raw)
    assert output_validation_errors(raw, ENVELOPE, original) == original.errors(include_url=False, include_input=False)


def test_valid_json_schema_errors_remain_exactly_the_original_errors():
    raw = json.dumps(moderator_output(wrong_fields=True))
    original = failed(raw)
    before = original.errors(include_url=False, include_input=False)
    assert all(error['type'] != 'json_invalid' for error in before)
    assert output_validation_errors(raw, ENVELOPE, original) == before
    assert original.errors(include_url=False, include_input=False) == before
