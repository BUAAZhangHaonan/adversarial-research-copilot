/* 渲染冒烟:SSR 渲染各视图首帧,验证组件树不抛错、关键结构存在(不执行 useEffect) */
import { renderToString } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { createElement as h } from 'react'
import App from './App'
import Login from './views/Login'
import Hall from './views/Hall'
import Summon from './views/Summon'
import Trial from './views/Trial'
import Judgment from './views/Judgment'
import Collection from './views/Collection'
import RunDetail from './views/RunDetail'
import IdeaCardView from './components/IdeaCard'
import BudgetBar from './components/BudgetBar'
import TaskFeed from './components/TaskFeed'
import { RunBadges } from './components/Badge'
import StepTrack from './components/StepTrack'
import type { DiscoveryCard } from './types'

let failures = 0
function check(name: string, fn: () => string) {
  try {
    const html = fn()
    if (!html || html.length < 40) throw new Error(`suspiciously short output (${html.length})`)
    console.log(`✓ ${name} (${html.length} bytes)`)
    return html
  } catch (e) {
    failures++
    console.error(`✗ ${name}: ${e}`)
    return ''
  }
}

const wrap = (el: React.ReactNode) =>
  renderToString(h(MemoryRouter, { initialEntries: ['/'] }, el))

check('Login', () => wrap(h(Login, { onOk: () => {} })))
check('Hall (no health)', () => wrap(h(Hall, { health: null })))
check('Summon form', () => wrap(h(Summon)))
check('Trial form', () => wrap(h(Trial)))
check('Judgment form', () => wrap(h(Judgment)))
check('Collection', () => wrap(h(Collection)))
check('RunDetail loading', () => wrap(h(RunDetail)))

const card: DiscoveryCard = {
  idea_id: 'idea_abc123def456', draw_id: 'idea1', status: 'checked', topic: 't',
  seed: {
    title: '测试灵感标题', question: 'q', insight: 'i', why_it_matters: 'w',
    difference_from_known: 'd', source_ids: [], key_unknown: 'k',
  },
  sketch: { action: 'submit', seed: null, reason: 'r' },
  triage: { action: 'investigate', reason: 'r', strongest_objection: 'o', check_questions: ['q1'] },
  note: {
    seed: null as never, decision: 'lead', reason: 'r', nearest_work: [], feasibility: 'f',
    resources: { gpu_type: '3090', gpu_count: 1, training_hours_estimate: null, inference_hours_estimate: null, basis: 'b' },
    main_risk: 'm', next_question: 'n', source_notes: [], limits: [], changes_from_seed: [],
  },
  idea_md: 'ideas/idea_abc123def456.md',
}
const cardHtml = check('IdeaCardView (lead=SS)', () => wrap(h(IdeaCardView, { card })))
if (!cardHtml.includes('SS')) { failures++; console.error('✗ IdeaCardView missing SS rarity') }
if (!cardHtml.includes('测试灵感标题')) { failures++; console.error('✗ IdeaCardView missing title') }

check('BudgetBar', () => wrap(h(BudgetBar, {
  budget: { limit_cny: 20, spent_lower_cny: 8.2, spent_upper_cny: 8.3, reserved_cny: 2, remaining_cny: 9.7, call_count: 42, unknown_calls: 0 },
})))
check('TaskFeed', () => wrap(h(TaskFeed, {
  tasks: [{ task_id: 'idea1.sketch', status: 'ACCEPTED' }, { task_id: 'survey', status: 'ACCEPTED' }],
  current: 'survey',
})))
check('Badges', () => wrap(h(RunBadges, {
  run: { run_id: 'r', status: 'PAUSED_BUDGET', stop_reason: 'budget_exhausted', assessment: 'PROMISING' } as never,
})))
check('StepTrack', () => wrap(h(StepTrack, {
  steps: [
    { key: 'survey', label: '领域调查', status: 'done' },
    { key: 'idea1', label: '第 1 抽', status: 'active' },
    { key: 'idea2', label: '第 2 抽', status: 'todo' },
  ],
})))

if (failures) {
  throw new Error(`render smoke: ${failures} failure(s)`)
}
console.log('\nall render smoke checks passed')
