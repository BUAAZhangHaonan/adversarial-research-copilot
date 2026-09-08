"""A lead is understandable before its detailed prerequisite list, without approval."""
import pytest

from arc.prompting import PromptLoader
from arc.reports import render_run
from tests.test_reports import ASSETS, FakeLedger, FakeStore, card


@pytest.mark.parametrize('decisive_findings', [[], [
    {'location': '/minimal_test/intervention', 'reason': '四个条件写成五个。',
     'consequence': '条件数量和总资源量无法确定。', 'required_change': '按四条件重算。'}]])
def test_lead_overview_shows_insight_then_current_risk_before_prerequisites(tmp_path, monkeypatch, decisive_findings):
    monkeypatch.setattr('arc.budget.BudgetLedger', FakeLedger)
    store = FakeStore(tmp_path)
    store.cards = [card('LEAD_ONLY')]
    store.run.update(mode='run', status='COMPLETED', assessment='NEEDS_EVIDENCE', card_id='card-1', card_version=2)
    store.run['state'] = {'final_scientific_card_version': 2, 'final_scientific_review': {
        'action': 'revise', 'value_reason': '旧版本调整的完整过程不该替代核心认识。',
        'decisive_findings': decisive_findings, 'remaining_uncertainty': ['仍需条件校准。']}}
    paths = render_run(store, 'run-1', tmp_path / 'lead', PromptLoader(ASSETS))
    report = paths['overview'].read_text()
    lead = report.split('## 待补证线索', 1)[1].split('## 调查范围与当前状态', 1)[0]
    assert lead.index('区分两个解释') < lead.index('决定下一项研究') < lead.index('主要未决风险')
    assert lead.index('主要未决风险') < lead.index('#### 缺失前提与下一步') < lead.index('需要原始方法章节')
    assert '条件数量和总资源量无法确定。' in lead if decisive_findings else '测量风险' in lead
    assert '旧版本调整的完整过程' not in lead
    assert '缺少判断所需证据' in lead and '值得人类执行最小实验' not in lead
    assert 'cards/card-1/v2.md' in lead
    assert store.run['assessment'] == 'NEEDS_EVIDENCE'
