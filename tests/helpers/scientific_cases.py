"""Synthetic semantic controls; expected labels never enter model payloads."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path

FIXTURE=Path(__file__).resolve().parents[1]/'fixtures/scientific_error_pairs.json'

def load_scientific_cases():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))['cases']

def scientific_case(case_id):
    return next(case for case in load_scientific_cases() if case['case_id']==case_id)

def model_payload(case):
    """Return only model-visible material, never pair IDs or expected labels."""
    if isinstance(case,str):
        case=scientific_case(case)
    return deepcopy(case['model_visible'])

def register_scientific_case(store,case,*,creation_key):
    """Register originals/evidence and the initial card for an explicit runner.

    This creates no run, task or budget and makes no model call. Use one isolated
    test store per case or unique creation keys; model_payload excludes labels.
    """
    from arc.schemas import CardDraft,SourceRecord,EvidenceRecord
    payload=model_payload(case)
    for item in payload['sources']:
        record={key:value for key,value in item.items() if key!='content'}
        record.setdefault('url',None)
        store.register_source(SourceRecord.model_validate(record),content=item['content'])
    for item in payload['evidence']:
        store.register_evidence(EvidenceRecord.model_validate(item))
    card=store.save_card(CardDraft.model_validate(payload['card']),creation_key=creation_key)
    return card,payload
