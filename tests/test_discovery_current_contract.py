from types import SimpleNamespace
import pytest
from arc.discovery_models import CandidateCheck, IdeaNote, TriageResult
from arc.runtime import Runtime


def test_new_check_requires_current_understanding_before_acceptance():
    result = CandidateCheck.model_construct(note=IdeaNote.model_construct(current_understanding=None))
    with pytest.raises(ValueError, match="CURRENT_UNDERSTANDING_REQUIRED"):
        Runtime._validate_output_contracts(None, SimpleNamespace(result=result),
            {"require_current_understanding": True}, {})


def test_new_editor_requires_explicit_relation_before_acceptance():
    result = TriageResult.model_construct(candidate_relation=None)
    with pytest.raises(ValueError, match="CANDIDATE_RELATION_REQUIRED"):
        Runtime._validate_output_contracts(None, SimpleNamespace(result=result),
            {"require_candidate_relation": True}, {})
