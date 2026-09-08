from arc.prompting import PromptLoader
from tests.test_prompts import ASSETS, DATA, SCHEMA


def test_scientific_reviewer_receives_concrete_value_reasoning_action():
    rendered=PromptLoader(ASSETS).render('scientific_reviewer.INVOKE',DATA,schema=SCHEMA)
    system=rendered.messages[0]['content']
    role=rendered.sources['roles/scientific_reviewer.md']
    assert role in system
    assert '先暂不接受候选自称的贡献，独立写出价值论证' in role
    assert '不同结果' in role and '具体解释、设计选择或能力边界' in role
    assert '在 value_reason 中简短给出这条论证' in role
    assert '不要求已有论文先宣布这个假设' in role
    assert '没有硬错误就保持正确性结论' in role


def test_calibration_reaches_both_conception_and_review_without_fixture_answers():
    for task in ['discovery.CONCEIVE','scientific_reviewer.INVOKE']:
        rendered=PromptLoader(ASSETS).render(task,DATA,schema=SCHEMA)
        examples=rendered.sources['common/selection_examples.md']
        system=rendered.messages[0]['content']
        assert examples in system
        assert '结果确实未知' in examples
        assert '同样局部，但触及真实瓶颈' in examples
        assert '局部范围与简单实验都不妨碍' in examples
        assert 'interaction_correct' not in system
        assert 'expected_value' not in system
