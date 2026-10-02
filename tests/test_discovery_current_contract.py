from types import SimpleNamespace
import pytest
from arc.discovery_models import CandidateCheck, IdeaNote, TriageResult
from arc.runtime import Runtime


def test_new_check_requires_current_understanding_before_acceptance():
    result = CandidateCheck.model_construct(note=IdeaNote.model_construct(current_understanding=None))
    with pytest.raises(ValueError, match="CURRENT_UNDERSTANDING_REQUIRED"):
        Runtime._validate_output_contracts(None, SimpleNamespace(result=result),
            {"require_current_understanding": True}, {})


def test_new_check_requires_problem_facing_source_briefs_before_writing():
    from arc.discovery_models import NearestWork
    work = NearestWork(source_id='s1', already_established='Full method and result.',
                       remaining_difference='A proposed decision question.')
    result = CandidateCheck.model_construct(note=IdeaNote.model_construct(nearest_work=[work]))
    with pytest.raises(ValueError, match='NEAREST_WORK_BRIEF_RESULT_REQUIRED'):
        Runtime._validate_output_contracts(None, SimpleNamespace(result=result),
            {'require_brief_results': True}, {})


def test_new_editor_requires_explicit_relation_before_acceptance():
    result = TriageResult.model_construct(candidate_relation=None)
    with pytest.raises(ValueError, match="CANDIDATE_RELATION_REQUIRED"):
        Runtime._validate_output_contracts(None, SimpleNamespace(result=result),
            {"require_candidate_relation": True}, {})



def test_writer_cannot_start_another_evidence_investigation():
    from arc.polishing import StagePolish
    result = StagePolish(stage_summary='阶段小结', overview='本轮结论', candidates=[], cited_source_ids=[])
    with pytest.raises(ValueError, match='POLISH_MUST_USE_SUPPLIED_RESEARCH_ONLY'):
        Runtime._validate_output_contracts(None, SimpleNamespace(result=result,
            evidence_requests=[{'question': 'Another investigation'}]),
            {'candidates': [], 'source_directory': []}, {})
