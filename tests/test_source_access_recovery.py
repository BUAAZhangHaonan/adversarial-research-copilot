"""Regression cases from the Arena survey failure; no paid calls."""
from copy import deepcopy
import json
import pytest
from arc.discovery_validation import validate_source_access, repair_source_catalog
from arc.discovery_models import FieldBrief
from arc.runtime import RuntimePaused
from arc.workflows import WorkflowEngine
from arc.schemas import SourceRecord
from tests.test_discovery_validation import source_store, brief
from tests.test_discovery_workflow import fixture, sketch, triage, checked
from tests.test_evidence_continuation import AccessRuntime


def test_all_bad_source_notes_are_reported_together(tmp_path):
    store, first = source_store(tmp_path, content=None, content_origin='metadata', access_status='metadata_only')
    second = store.register_source(SourceRecord(title='Second', url='https://example.test/second',
        source_type='paper', content_origin='metadata', access_status='metadata_only'))
    value = brief(first, 'full_text')
    value.source_notes.extend(brief(second, 'passage').source_notes)
    with pytest.raises(ValueError) as error:
        validate_source_access(store, value)
    assert first.source_id in str(error.value) and second.source_id in str(error.value)


def test_repair_catalog_retains_originals_from_tool_trace_not_private_sources(tmp_path):
    store, metadata = source_store(tmp_path, content=None, content_origin='metadata', access_status='metadata_only')
    original = store.register_source(SourceRecord(title='Actual paper', url='https://example.test/paper.pdf',
        source_type='paper', content_origin='original', access_status='retrieved', content_complete=False), content='Actual passage')
    private = store.register_source(SourceRecord(title='Other task', url='https://example.test/private', source_type='paper', access_status='metadata_only', content_origin='metadata'))
    catalog = repair_source_catalog(store, {'source_ids':[metadata.source_id]},
        [{'status':'completed', 'source_ids':[original.source_id]}])
    assert catalog['sources'][0]['source_id'] == original.source_id
    assert catalog['sources'][0]['content_complete'] is False
    assert private.source_id not in json.dumps(catalog)
    assert catalog['automatic_replacement'] is False
    retry = repair_source_catalog(store, {'protocol_retry': {'previous_successful_tools': [
        {'source_ids':[original.source_id]}]}}, [])
    assert retry['sources'][0]['source_id'] == original.source_id


