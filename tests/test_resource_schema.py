"""The advertised resource contract matches its standard-schema-expressible invariants."""
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from arc.schemas import DeveloperResult, Envelope, ResourceEstimate
from .test_contracts import card_payload


def envelope_with_resources(resources):
    card = card_payload()
    card['resources'] = deepcopy(resources)
    return {'schema_version': 'arc.v1', 'task_id': 'synthetic.import',
        'subject': {'campaign_id': None, 'run_id': 'synthetic', 'card_id': None, 'card_version': None},
        'result_status': 'complete', 'result': {
            'proposed_revision': card, 'direction_change': None,
            'unchanged_problem_anchor': card['problem_anchor'],
            'change_summary': [], 'affected_claims': [], 'evidence_review': [],
            'minimal_test': card['minimal_test'], 'resources': deepcopy(resources),
            'remaining_issues': [], 'next_action': 'REASON'},
        'evidence_requests': [], 'capability_requests': [], 'note': None}


def resource_case(**updates):
    result = card_payload()['resources']
    result.update(updates)
    return result


ZERO_GPU = {'lower': 0, 'upper': 0, 'unit': 'GPU-hours'}


def detailed_errors(errors):
    for error in errors:
        if error.context:
            yield from detailed_errors(error.context)
        else:
            yield error


@pytest.mark.parametrize('resources', [
    resource_case(),
    resource_case(gpu_count=0, gpu_type=None, gpu_memory_gb_assumption=None,
                  training_gpu_hours_range=None, inference_gpu_hours_range=None),
    resource_case(gpu_count=0, gpu_type='', gpu_memory_gb_assumption=0,
                  training_gpu_hours_range=ZERO_GPU, inference_gpu_hours_range=ZERO_GPU),
    resource_case(gpu_count=1, gpu_type=' ', gpu_memory_gb_assumption=0.01),
    resource_case(gpu_count=2, training_gpu_hours_range=ZERO_GPU, inference_gpu_hours_range=None),
])
def test_valid_resources_preserve_current_runtime_semantics_in_advertised_envelope(resources):
    value = envelope_with_resources(resources)
    schema = Envelope[DeveloperResult].model_json_schema()
    Draft202012Validator.check_schema(schema)
    assert list(Draft202012Validator(schema).iter_errors(value)) == []
    assert Envelope[DeveloperResult].model_validate(value).model_dump() == value
    assert ResourceEstimate.model_json_schema()['additionalProperties'] is False


@pytest.mark.parametrize('updates,error', [
    ({'gpu_type': None}, 'gpu_configuration_required'),
    ({'gpu_type': ''}, 'gpu_configuration_required'),
    ({'gpu_memory_gb_assumption': None}, 'gpu_configuration_required'),
    ({'gpu_memory_gb_assumption': 0}, 'gpu_configuration_required'),
    ({'gpu_count': 0}, 'positive_gpu_hours_require_gpu'),
    ({'gpu_count': 0, 'inference_gpu_hours_range': None,
      'training_gpu_hours_range': {'lower': 0, 'upper': 0.01, 'unit': 'GPU-hours'}},
     'positive_gpu_hours_require_gpu'),
    ({'wall_hours_range': {'lower': 0, 'upper': 1, 'unit': 'GPU-hours'}}, 'wall_time_unit'),
    ({'training_gpu_hours_range': {'lower': 0, 'upper': 1, 'unit': 'hours'}}, 'gpu_time_unit'),
    ({'inference_gpu_hours_range': {'lower': 0, 'upper': 1, 'unit': 'hours'}}, 'gpu_time_unit'),
])
def test_advertised_envelope_rejects_same_resource_invariant_as_pydantic(updates, error):
    value = envelope_with_resources(resource_case(**updates))
    errors = list(Draft202012Validator(Envelope[DeveloperResult].model_json_schema()).iter_errors(value))
    paths = [list(item.absolute_path) for item in detailed_errors(errors)]
    assert any(path[:3] == ['result', 'proposed_revision', 'resources'] for path in paths)
    assert any(path[:2] == ['result', 'resources'] for path in paths)
    with pytest.raises(ValidationError, match=error):
        Envelope[DeveloperResult].model_validate(value)


def test_real_import_zero_gpu_optional_inference_range_is_explicitly_rejected_by_schema():
    # Exact numeric/configuration shape of the saved 2026-09-07 import first response.
    # Its prose described a CPU main path and an optional single-GPU inference path;
    # the single ResourceEstimate object still has to satisfy its declared invariant.
    resources = resource_case(gpu_count=0,
        gpu_type='RTX 3090 24GB', gpu_memory_gb_assumption=24,
        training_gpu_hours_range={'lower': 0, 'upper': 0, 'unit': 'GPU-hours'},
        inference_gpu_hours_range={'lower': 0, 'upper': 12, 'unit': 'GPU-hours'})
    value = envelope_with_resources(resources)
    before = deepcopy(value)
    errors = list(Draft202012Validator(Envelope[DeveloperResult].model_json_schema()).iter_errors(value))
    assert sorted((list(error.absolute_path), error.validator, error.validator_value)
                  for error in detailed_errors(errors) if error.validator == 'maximum') == [
        (['result', 'proposed_revision', 'resources', 'inference_gpu_hours_range', 'upper'], 'maximum', 0),
        (['result', 'resources', 'inference_gpu_hours_range', 'upper'], 'maximum', 0),
    ]
    with pytest.raises(ValidationError, match='positive_gpu_hours_require_gpu'):
        Envelope[DeveloperResult].model_validate(value)
    assert value == before
