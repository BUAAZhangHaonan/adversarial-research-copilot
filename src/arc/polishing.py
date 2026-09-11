"""Presentation-only final writing; immutable research objects remain authoritative."""
from __future__ import annotations

from copy import deepcopy
import re

from pydantic import BaseModel, ConfigDict, Field

from .research_context import SOURCE_KEYS, reference_ids
from .discovery_memory import evidence_limit_summaries


WRITING_LIMITS = {
    'stage_summary_max_chars': 450,
    'overview_max_chars': 1100,
    'candidate_text_max_chars': 1300,
    'paragraph_max_chars': 260,
    'max_cited_sources': 5,
}


class PolishedCandidate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    idea_id: str = Field(min_length=1)
    presentation_title: str | None = Field(default=None, min_length=1)
    text: str = Field(min_length=1)
    cited_source_ids: list[str]


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
        ids = sorted(reference_ids([note, seed], SOURCE_KEYS))
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
            'source_directory': directory, 'writing_limits': dict(WRITING_LIMITS),
            'evidence_limits': evidence_limit_summaries(state)})


def compact_polish_payload(payload):
    """Select current writing material without rewriting any scientific statements."""
    payload = deepcopy(payload)
    for candidate in payload['candidates']:
        note = candidate.get('note') or {}
        if note.get('current_understanding'):
            # Current understanding includes withdrawn premises; the seed and edit
            # chronology remain available in the separately retained technical draft.
            note.pop('seed', None)
            note.pop('changes_from_seed', None)
    if payload['stage'] in {'develop', 'run'}:
        payload.pop('field_brief', None)
        relevant = {source_id for candidate in payload['candidates'] for source_id in candidate['source_ids']}
        payload['source_directory'] = [source for source in payload['source_directory']
                                       if source['source_id'] in relevant]
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
        texts.extend([item.text, item.presentation_title or ''])
    # URLs belong to the immutable source directory and renderer, not writer prose.
    if any(re.search(r'https?://|www\.', text, re.I) for text in texts):
        raise ValueError('POLISH_INLINE_URL_NOT_ALLOWED_USE_SOURCE_IDS')
    if payload.get('writing_limits'):
        validate_writing_limits(result, payload['writing_limits'])
    return result


def validate_writing_limits(result, limits):
    """Explain all size violations together; the runtime gives one JSON correction."""
    violations = []
    sections = [
        ('stage_summary', result.stage_summary, limits['stage_summary_max_chars']),
        ('overview', result.overview, limits['overview_max_chars']),
        *[(f'candidates[{item.idea_id}].text', item.text, limits['candidate_text_max_chars'])
          for item in result.candidates],
    ]
    for path, text, maximum in sections:
        count = len(text.strip())
        if count > maximum:
            violations.append(f'{path}: {count} characters; maximum {maximum}')
        paragraphs = [part.strip() for part in re.split(r'\n\s*\n', text.strip()) if part.strip()]
        for index, paragraph in enumerate(paragraphs, 1):
            if len(paragraph) > limits['paragraph_max_chars']:
                violations.append(f'{path}.paragraph[{index}]: {len(paragraph)} characters; '
                                  f"maximum {limits['paragraph_max_chars']}")
    for path, citations in [('cited_source_ids', result.cited_source_ids),
                            *[(f'candidates[{item.idea_id}].cited_source_ids', item.cited_source_ids)
                              for item in result.candidates]]:
        if len(citations) > limits['max_cited_sources']:
            violations.append(f'{path}: {len(citations)} references; maximum {limits["max_cited_sources"]}')
    if violations:
        raise ValueError('POLISH_WRITING_LIMITS_EXCEEDED\n' + '\n'.join(violations)
                         + '\n请精简重复内容、选择关键引用并用空行分段；保留决定性适用条件，不截断句子或改写科学判断。')
