"""Presentation-only final writing; immutable research objects remain authoritative."""
from __future__ import annotations

from copy import deepcopy
import re

from pydantic import BaseModel, ConfigDict, Field

from .research_context import SOURCE_KEYS, reference_ids
from .discovery_memory import evidence_limit_summaries


MAX_CITED_SOURCES = 5


class PolishedCandidate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    idea_id: str = Field(min_length=1)
    presentation_title: str | None = Field(default=None, min_length=1)
    text: str = Field(min_length=1)
    cited_source_ids: list[str]
    technical_analysis: str | None = Field(default=None, min_length=1)


class StagePolish(BaseModel):
    model_config = ConfigDict(extra='forbid')
    stage_summary: str = Field(min_length=1)
    overview: str = Field(min_length=1)
    candidates: list[PolishedCandidate]
    cited_source_ids: list[str]


def as_data(value):
    return value.model_dump(mode='json') if hasattr(value, 'model_dump') else value


def build_polish_payload(store, run_id):
    """Only the current scientific content and its registered references, once."""
    run = as_data(store.get_run(run_id))
    state = run.get('state', {})
    selected = state.get('idea_input') or {}
    brief = deepcopy(state.get('field_brief') or selected.get('field_brief') or {})
    records = [as_data(record) for record in store.list_discovery_ideas(run_id=run_id)]
    if selected:
        original = as_data(store.get_discovery_idea(selected['idea_id']))
        records = [{**original, 'seed': selected['seed'], 'triage': None,
                    'note': None if state.get('prestudy_evidence_limited') else state.get('prestudy_note'),
                    'check_material_basis': state.get('check_material_basis'),
                    'status': ('evidence_limited' if state.get('prestudy_evidence_limited') else
                               'checked' if state.get('prestudy_note') else 'pending')}]
    campaign = as_data(store.get_campaign(run['campaign_id'])) if run.get('campaign_id') else {}
    source_notes = list(brief.pop('source_notes', []))
    candidates, skipped = [], []
    for record in records:
        limited = record.get('status') == 'evidence_limited'
        note, seed = (None if limited else deepcopy(record.get('note'))), deepcopy(record.get('seed'))
        if not seed:
            skipped.append({'draw_id': record.get('draw_id'),
                            'reason': (record.get('sketch') or {}).get('reason'), 'status': record.get('status')})
            continue
        triage = record.get('triage') or {}
        ids = sorted(reference_ids(note if note else seed, SOURCE_KEYS))
        if note:
            source_notes.extend(note.pop('source_notes', []))
        candidate = {'idea_id': record['idea_id'], 'title': (note or {}).get('seed', seed)['title'],
                     'status': record['status'], 'decision': ('evidence_limited' if limited else (note or {}).get('decision') or triage.get('action') or record['status']),
                     'source_ids': ids, 'check_material_basis': record.get('check_material_basis')}
        if note:
            candidate['note'] = note
            if triage.get('candidate_relation'):
                candidate['candidate_relation'] = deepcopy(triage['candidate_relation'])
        else:
            candidate.update(seed=seed, triage=deepcopy(triage))
        prefix = 'prestudy' if selected else str(record.get('draw_id', ''))
        if prefix.isdigit():
            prefix = 'idea' + prefix
        limits = evidence_limit_summaries(state, prefix) if prefix else []
        if limits:
            candidate['evidence_limits'] = limits
        candidates.append(candidate)
    source_ids = set(reference_ids([candidates, source_notes], SOURCE_KEYS))
    directory = []
    for source in store.list_sources(ids=sorted(source_ids)):
        source = as_data(source)
        notes = []
        for note in source_notes:
            if note['source_id'] == source['source_id']:
                value = {key: value for key, value in note.items() if key != 'source_id'}
                if value not in notes:
                    notes.append(value)
        directory.append({key: source.get(key) for key in ('source_id', 'title', 'url')} | {'notes': notes})
    return compact_polish_payload({'run_id': run_id, 'stage': run['mode'],
            'original_question': campaign.get('topic') or selected.get('original_question', ''),
            'user_boundaries': campaign.get('boundaries') or selected.get('user_boundaries', []),
            'field_brief': brief, 'candidates': candidates, 'skipped_directions': skipped,
            'source_directory': directory, 'citation_limit': MAX_CITED_SOURCES,
            'evidence_limits': evidence_limit_summaries(state)})


def compact_polish_payload(payload):
    """Separate proposed explanations from source summaries for new writing tasks.

    Full technical notes remain in the store and technical reports. Frozen writer
    inputs are not rebuilt. This view selects fields, never certifies their truth.
    """
    payload = deepcopy(payload)
    for candidate in payload['candidates']:
        if 'writing_brief' in candidate and not candidate.get('note') and not candidate.get('seed'):
            continue
        note = candidate.get('note') or {}
        seed = note.get('seed') or candidate.get('seed') or {}
        current = note.get('current_understanding') or {}
        nearest = note.get('nearest_work') or []
        historical = bool(note) and not current
        if current:
            proposal = {'question': seed.get('question'),
                        'hypothesis': current.get('core_insight'),
                        'expected_value': seed.get('why_it_matters'),
                        'proposed_difference': current.get('why_existing_insufficient')}
        elif note:
            proposal = {'question': seed.get('question'),
                        'review_status': 'historical_note_requires_current_review'}
        else:
            proposal = {'question': seed.get('question'), 'hypothesis': seed.get('insight'),
                        'expected_value': seed.get('why_it_matters'),
                        'proposed_difference': seed.get('difference_from_known'),
                        'review_status': 'unreviewed_candidate'}
        brief = {
            'proposal': proposal,
            'example': current.get('illustrative_example'),
            'source_summaries': [{'source_id': work['source_id'],
                                  'reported_result': work['brief_result']}
                                 for work in nearest if work.get('brief_result') and not historical],
            'comparison_claims': [{key: work[key] for key in
                                  ('source_id', 'remaining_difference', 'uncertainty') if key in work}
                                 for work in nearest if not historical],
            'decisive_unknown': (None if historical else
                                 current.get('decisive_unknown') or note.get('main_risk') or seed.get('key_unknown')),
            'next_question': None if historical else note.get('next_question'),
            'risk_analysis': None if historical else note.get('main_risk'),
            'limits': note.get('limits', []),
            'audit_reference': {'idea_id': candidate['idea_id'], 'record': 'original_scientific_note'},
        }
        if note.get('feasibility') and not historical:
            brief['proposed_entry'] = note['feasibility']
        # The reason for a drop or a pending investigation is essential reading.
        # Long endorsement paragraphs for discuss/lead stay in technical records.
        if candidate.get('decision') not in {'discuss', 'lead'}:
            brief['decision_context'] = (None if historical else
                                         note.get('reason') or (candidate.get('triage') or {}).get('reason'))
        candidate['writing_brief'] = brief
        for key in ('note', 'seed', 'triage'):
            candidate.pop(key, None)
    for candidate in payload['candidates']:
        brief = candidate['writing_brief']
        candidate.setdefault('technical_context', {}).update(
            {key: brief.pop(key) for key in ('comparison_claims', 'risk_analysis', 'audit_reference',
                                            'limits', 'proposed_entry')
             if key in brief})
    payload.pop('writing_limits', None)
    payload.setdefault('citation_limit', MAX_CITED_SOURCES)
    for source in payload['source_directory']:
        # The nearest-work summary above carries the result; do not repeat full
        # findings, relevance, and historical summaries in the reference directory.
        source['notes'] = [{key: note[key] for key in ('access', 'limits') if key in note}
                           for note in source.get('notes', [])]
    if payload['candidates']:
        relevant = {source_id for candidate in payload['candidates'] for source_id in candidate['source_ids']}
        payload['source_directory'] = [source for source in payload['source_directory']
                                       if source['source_id'] in relevant]
    payload.pop('field_brief', None)
    return payload


def validate_polish(result, payload):
    """Check candidate coverage and source ownership, not scientific truth."""
    result = result if isinstance(result, StagePolish) else StagePolish.model_validate(result)
    expected = {item['idea_id']: item for item in payload['candidates']}
    found = [item.idea_id for item in result.candidates]
    if len(set(found)) != len(found) or set(found) != set(expected):
        raise ValueError('POLISH_CANDIDATE_COVERAGE_MISMATCH')
    allowed = {source['source_id'] for source in payload['source_directory']}
    if len(result.cited_source_ids) != len(set(result.cited_source_ids)) or set(result.cited_source_ids) - allowed:
        raise ValueError('POLISH_SOURCE_OUTSIDE_DIRECTORY')
    texts = [result.stage_summary, result.overview]
    for item in result.candidates:
        permitted = set(expected[item.idea_id]['source_ids']) & allowed
        if len(item.cited_source_ids) != len(set(item.cited_source_ids)) or set(item.cited_source_ids) - permitted:
            raise ValueError('POLISH_CANDIDATE_SOURCE_OUTSIDE_DIRECTORY:' + item.idea_id)
        texts.extend([item.text, item.presentation_title or '', item.technical_analysis or ''])
    # URLs belong to the immutable source directory and renderer, not writer prose.
    if any(re.search(r'https?://|www\.', text, re.I) for text in texts):
        raise ValueError('POLISH_INLINE_URL_NOT_ALLOWED_USE_SOURCE_IDS')
    maximum = payload.get('citation_limit', (payload.get('writing_limits') or {}).get('max_cited_sources'))
    if maximum is not None:
        for path, citations in [('cited_source_ids', result.cited_source_ids),
                                *[(f'candidates[{item.idea_id}].cited_source_ids', item.cited_source_ids)
                                  for item in result.candidates]]:
            if len(citations) > maximum:
                raise ValueError(f'POLISH_REFERENCE_LIMIT_EXCEEDED:{path}: {len(citations)} references; maximum {maximum}')
    return result
