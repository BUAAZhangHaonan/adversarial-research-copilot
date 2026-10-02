/* Seven synthetic records only. All API requests mocked, no account or model calls. */
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { readFileSync, existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { join, resolve, extname } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
const here = fileURLToPath(new URL('.', import.meta.url))
const { chromium } = await import(pathToFileURL(join(process.cwd(), 'node_modules/playwright/index.mjs')).href)
const output = resolve(process.cwd(), process.env.UI_OUTPUT || 'output/playwright')
mkdirSync(output, { recursive: true })
const results = [], requests = []
const delay = (ms) => new Promise((done) => setTimeout(done, ms))
const created = '2026-10-02T13:07:00Z'
const names = ['让模型判断：这次提问能帮上忙吗？', '在失败之前识别需要补充的信息', '让重复查询留下可复用的判断依据', '复杂场景中的任务目标如何表达', '相似证据能否减少重复检索']
const text = (title, n) => `# ${title}\n\n## 场景与研究问题\n用户心中选定左右红杯之一，却没有告诉模型。可靠的 Yes/No 回答可以补齐目标，这是第 ${n} 个待检验设想。\n\n## 核心想法\n比较收到与未收到合法回答的动作收益标签；目标标注用于评价，不输入提问前读出。原记录示例是 37%，这不是 37 个百分点。\n\n## 与最近工作的差别\n[示例论文](https://example.org/paper)提供文本任务的证据，当前多模态方案仍需检验。\n\n## 为什么能做与研究价值\n已有问答环境可用于构造标签。相同提问预算比较任务表现，这是设想，没有实验结果。\n\n## 技术分析与证据限制\n当前线性读出接近随机，不能据此认定信号不存在。\n[查看完整技术记录](TECHNICAL_REPORT.md)\n\n## 文献与来源\n[示例论文](https://example.org/paper)\n[第二份来源](https://example.org/source-two)\n`
const cardsFor = (d, count) => Array.from({ length: count }, (_, i) => ({
  idea_id: `idea_synthetic_${d}_${i}`, status: i === 4 ? 'park' : 'checked', draw_id: null, topic: `合成话题 ${d}`,
  seed: { title: `${names[i]} · ${d}`, question: '用户没有说出选定的目标时，模型如何判断询问能否帮助行动？', insight: '待检验：以合法回答前后的任务收益构造标签。',
    why_it_matters: '在相同提问预算下比较任务表现。这是研究设想，尚无实验结果。', difference_from_known: '[示例论文](https://example.org/paper)的文本任务证据尚不能推广。', source_ids: ['S1', 'S2'], key_unknown: '读出选择能否改善任务表现仍待检验。' },
  presentation: d === 5 && i === 0 ? null : { presentation_title: `${names[i]} · ${d}`, text: text(names[i], i + 1) },
  sketch: null, triage: { action: i === 4 ? 'park' : 'investigate', reason: '初筛依据保留。', strongest_objection: '标签可能没有区分新增信息收益。', check_questions: [] },
  note: i === 4 ? null : { decision: i === 3 ? 'drop' : 'discuss', reason: i === 3 ? '反面结果：现有证据不足以支持当前比较，暂不推进。' : '当前资源支持实施，但效果仍待检验。',
    feasibility: '现有环境与冻结标注可支持小规模核验。', main_risk: '如果收益标签与允许的问题不匹配，核心比较无法成立。', next_question: '标签匹配是否可靠？', resources: { basis: '已有问答环境可提供合法回答。' },
    nearest_work: [{ source_id: 'S1', already_established: '文本任务中已测试内部信号。', remaining_difference: '多模态任务尚未验证。', uncertainty: '证据不覆盖所有场景。' }],
    source_notes: [{ source_id: 'S1', finding: '保留原来源范围。', relevance: '提供实施起点。', access: 'full', limits: '任务范围不同。' }],
    limits: ['尚未实施科研实验。', '线性探针接近随机不说明信号不存在。', '效果与简单置信度相近不说明新增信息没有价值。', '第四条限制仍完整保留。'], changes_from_seed: [] },
  idea_md: `ideas/idea-${i + 1}.md`,
}))
const data = new Map(), fileData = new Map()
for (let d = 1; d <= 5; d++) {
  const dir = `synthetic-discover-${d}`, cards = cardsFor(d, d <= 3 ? 5 : 3)
  const files = new Map([['REPORT.md', '# 合成整轮报告\n\n' + cards.map((c) => c.presentation?.text || text(c.seed.title, 1)).join('\n')],
    ['TECHNICAL_REPORT.md', '# 完整技术记录\n\n反面结果与证据限制保持原文。\n\n[返回整轮报告](REPORT.md)'], ['FIELD_BRIEF.md', '# 合成领域简报'], ['COST_REPORT.md', '# 合成费用明细：无实际调用']])
  for (const c of cards) files.set(c.idea_md, c.presentation?.text || text(c.seed.title, 1))
  // Root-relative known file for cards in the ideas directory, plus sibling link in original file.
  for (const c of cards) if (c.presentation) c.presentation.text = c.presentation.text.replace('(TECHNICAL_REPORT.md)', '(../TECHNICAL_REPORT.md)')
  data.set(dir, { mode: 'discover', dir, topic: `【合成验收 ${d}】多模态模型何时应主动获取信息\n这是一条完整保留的第二行原始边界。`,
    run: { status: 'COMPLETED', created_at: created, updated_at: created }, cards, files: [...files].map(([name, content]) => ({ name, size: content.length })), cost: null, usage: null })
  fileData.set(dir, files)
}
for (const [mode, version] of [['develop', 2], ['debate', 3]]) {
  const dir = `synthetic-${mode}`, files = new Map([['REPORT.md', `# 合成${mode}报告\n\n## 本轮研究发现\n保留当前判断：收益标签与允许的问答形式需要匹配，效果仍待检验。\n\n## 评审依据\n反面结果保留在技术记录中。\n\n## 文献与来源\n[示例论文](https://example.org/paper)`],
    ['card.v1.md', '# 合成研究卡第一版\n\n尚未实施科研实验。'], [`card.v${version}.md`, text(`合成研究卡第 ${version} 版`, version).replace(`版\n\n`, `版\n\n合成版本 v${version}。\n\n`)], ['technical.md', '# 合成独立技术分析\n\n反面结果完整保留。']])
  data.set(dir, { mode, dir, topic: `【合成验收】${mode === 'develop' ? '展开信息获取方案' : '核验信息获取方案'}`, run: { status: 'COMPLETED', assessment: mode === 'debate' ? 'NEEDS_EVIDENCE' : 'PROMISING', created_at: created, updated_at: created },
    docs: [{ kind: 'card', file: 'card.v1.md', version: 1, card_id: 'card_synthetic' }, { kind: 'card', file: `card.v${version}.md`, version, card_id: 'card_synthetic' }, { kind: 'technical', file: 'technical.md' }],
    files: [...files].map(([name, content]) => ({ name, size: content.length })), cost: null })
  fileData.set(dir, files)
}
const summaries = [...data.values()].map((r) => ({ dir: r.dir, mode: r.mode, topic: r.topic, status: 'COMPLETED', created_at: created, mtime: 1, cost: null }))
const job = (id, dir = 'synthetic-discover-1') => ({ job: { id, mode: 'discover', params: {}, username: 'synthetic', status: 'completed', run_dir: dir, error: null, created_at: created, finished_at: created }, progress: null, log_tail: '' })
function staticServer(directory) {
  const root = resolve(directory)
  const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.woff2': 'font/woff2', '.ttf': 'font/ttf' }
  return createServer((req, res) => {
    const path = resolve(root, '.' + decodeURIComponent(new URL(req.url, 'http://localhost').pathname === '/' ? '/index.html' : new URL(req.url, 'http://localhost').pathname))
    if (!path.startsWith(root + '/') || !existsSync(path)) { res.writeHead(404); res.end(); return }
    res.writeHead(200, { 'Content-Type': types[extname(path)] || 'application/octet-stream' }); res.end(readFileSync(path))
  })
}
const server = staticServer(resolve(process.cwd(), process.env.UI_DIST || 'dist'))
await new Promise((done) => server.listen(0, '127.0.0.1', done))
const base = `http://127.0.0.1:${server.address().port}`
writeFileSync(join(output, 'BROWSER_BASE_URL'), base)
const browser = await chromium.launch({ channel: 'chrome', headless: true })
async function scenario(name, run, options = {}) {
  if (process.env.READING_TEST_FILTER && !name.includes(process.env.READING_TEST_FILTER)) return
  const context = await browser.newContext({ viewport: options.viewport || { width: 1440, height: 1000 }, reducedMotion: options.reducedMotion || 'no-preference' })
  const page = await context.newPage(), errors = [], calls = []
  page.setDefaultTimeout(9000)
  page.on('pageerror', (err) => errors.push(String(err)))
  await context.route('**/api/**', async (route) => {
    const req = route.request(), url = new URL(req.url()), path = url.pathname, method = req.method()
    calls.push({ path, method }); requests.push({ scenario: name, path, method })
    let response = options.handler ? await options.handler({ path, query: url.searchParams, method, calls }) : undefined
    if (response === undefined) {
      if (method !== 'GET') response = { status: 400, json: { detail: 'Synthetic read-only test forbids mutation' } }
      else if (path === '/api/auth/me') response = { username: '合成验收', is_admin: false }
      else if (path === '/api/health') response = { scholartrace: true, scholaranalysis: true, webresearch: true, running_jobs: 0, max_jobs: 2 }
      else if (path === '/api/runs') response = { runs: summaries }
      else if (path === '/api/jobs') response = { jobs: [] }
      else if (/\/visibility$/.test(path)) response = { visible: true, current_run_id: path.split('/')[3], version_revision: 1 }
      else if (path.startsWith('/api/jobs/')) response = job(path.split('/')[3])
      else if (path.endsWith('/file')) { const dir = path.split('/')[3], name = url.searchParams.get('name'); response = { name, content: fileData.get(dir)?.get(name) || '合成文件不存在' } }
      else if (path.startsWith('/api/runs/') && data.has(path.split('/')[3])) response = data.get(path.split('/')[3])
      else response = { status: 404, json: { detail: 'Synthetic missing resource' } }
    }
    const wrapped = response && 'json' in response
    await route.fulfill({ status: wrapped ? response.status || 200 : 200, contentType: 'application/json', body: JSON.stringify(wrapped ? response.json : response) })
  })
  try {
    await run(page, calls)
    assert.deepEqual(errors, [], 'No browser exceptions')
    assert.ok(calls.every((c) => c.method === 'GET'), 'No real or simulated research submission in reading QA')
    results.push({ name, status: 'passed' }); console.log(`PASS ${name}`)
  } catch (error) {
    await page.screenshot({ path: join(output, `FAIL-${results.length}.png`), fullPage: true }).catch(() => {})
    results.push({ name, status: 'failed', error: String(error), errors }); console.error(`FAIL ${name}: ${error}`)
  } finally { await context.close() }
}
const discover = '#/runs/synthetic-discover-1'
const closeModal = async (p) => { await p.keyboard.press('Escape'); await p.getByRole('dialog').waitFor({ state: 'hidden' }) }
const noOverflow = async (p) => assert.ok(await p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'No horizontal page overflow')
async function shot(p, name) {
  await delay(500)
  await p.evaluate(() => document.fonts.ready)
  await p.waitForFunction(() => [...document.querySelectorAll('.page')].every(el => Number(getComputedStyle(el).opacity) >= .99))
  await p.evaluate(() => { const note = document.createElement('div'); note.id = 'qa-label'; note.textContent = '合成七记录 · 隔离浏览器验收 · 非生产私有记录'; Object.assign(note.style, { position: 'fixed', right: '12px', bottom: '12px', zIndex: '200', padding: '8px 12px', background: '#11271d', border: '1px solid #ceb661', color: '#ffe6a8', fontSize: '12px' }); document.body.appendChild(note) })
  await p.screenshot({ path: join(output, name), fullPage: true })
  await p.evaluate(() => document.getElementById('qa-label')?.remove())
}
try {
  await scenario('seven records and 5/1/1 stage filters', async (p) => {
    await p.goto(`${base}/#/collection`); await p.locator('.reading-run-row').first().waitFor(); assert.equal(await p.locator('.reading-run-row').count(), 7)
    for (const [mode, n] of [['召唤', 5], ['试炼', 1], ['审判', 1], ['全部', 7]]) { await p.locator('.reading-filters').getByRole('button', { name: new RegExp(mode) }).click(); assert.equal(await p.locator('.reading-run-row').count(), n) }
    await shot(p, 'synthetic-after-collection-desktop.png')
  })
  await scenario('all five discovery summaries and card counts', async (p) => {
    for (let d = 1; d <= 5; d++) { await p.goto(`${base}/#/runs/synthetic-discover-${d}`); await p.locator('#reading-summary h2').waitFor(); const count = d <= 3 ? 5 : 3
      assert.equal(await p.locator('.reading-idea-row').count(), count); assert.equal(await p.locator('.reading-card-wall .card-slot').count(), count)
      assert.equal(await p.locator('#reading-summary a[href^="http"]').count(), 0)
      assert.equal(await p.locator('#reading-summary').getByText('当前线性读出接近随机，不能据此认定信号不存在。', { exact: true }).count(), 0, 'No duplicated card/report body in overview')
      await p.getByText('查看原始问题', { exact: true }).click(); await p.locator('.reading-context pre').filter({ hasText: '完整保留的第二行' }).waitFor()
    }
    await p.goto(`${base}/${discover}`); await p.locator('.reading-idea-row').first().waitFor(); await shot(p, 'synthetic-after-discover-desktop.png')
  })
  await scenario('card reading, secondary references and full negative evidence', async (p) => {
    await p.goto(`${base}/${discover}`); await p.locator('.reading-idea-row').first().click(); const dialog = p.getByRole('dialog')
    await dialog.getByText('场景与研究问题', { exact: true }).waitFor(); assert.ok((await dialog.innerText()).includes('37%'))
    assert.equal(await dialog.locator('.reading-prose a[href^="http"]').count(), 0)
    await shot(p, 'synthetic-after-card-desktop.png')
    await dialog.getByText(/关键文献与链接/).click(); const refs = dialog.locator('.reading-sources[open] a'); assert.equal(await refs.count(), 2); assert.equal(await refs.first().getAttribute('href'), 'https://example.org/paper')
    await dialog.getByText('技术分析与核查记录', { exact: true }).click(); await dialog.getByText('第四条限制仍完整保留。', { exact: true }).waitFor()
    await shot(p, 'synthetic-after-card-evidence-desktop.png'); await closeModal(p)
    await p.locator('.reading-idea-row').nth(3).click(); await p.getByRole('dialog').getByText('反面结果：现有证据不足以支持当前比较，暂不推进。', { exact: true }).first().waitFor(); await closeModal(p)
    await p.goto(`${base}/#/runs/synthetic-discover-5`); await p.locator('.reading-idea-row').first().click(); await p.getByRole('dialog').getByText('核心想法', { exact: true }).waitFor(); await p.getByRole('dialog').getByText('原始内容与判断依据', { exact: true }).click()
    await p.getByRole('dialog').getByText('待检验：以合法回答前后的任务收益构造标签。', { exact: true }).last().waitFor()
  })
  await scenario('relative file links stay inside record, raw documents remain complete', async (p) => {
    await p.goto(`${base}/${discover}`); await p.locator('.reading-idea-row').first().click(); await p.getByRole('dialog').locator('summary').filter({ hasText: '技术分析与证据限制' }).click()
    await p.getByRole('link', { name: '查看完整技术记录', exact: true }).click(); await p.getByRole('dialog').getByRole('heading', { name: '完整技术记录', exact: true }).waitFor(); assert.ok(p.url().endsWith(discover))
    await p.getByRole('link', { name: '返回整轮报告', exact: true }).click(); await p.getByRole('dialog').getByRole('heading', { name: '合成整轮报告', exact: true }).waitFor(); assert.equal(await p.getByRole('dialog').getByText('场景与研究问题', { exact: true }).count(), 5)
    await closeModal(p); await p.locator('#reading-records').getByText(/查看完整文档/).click(); assert.ok(await p.locator('.reading-files button').count() >= 9)
  })
  await scenario('card handoffs preserve identifiers without submitting', async (p) => {
    await p.goto(`${base}/${discover}`); await p.locator('.reading-idea-row').first().click(); await p.getByRole('button', { name: /送入试炼/ }).click(); await p.locator('.prefill-box').filter({ hasText: names[0] }).waitFor()
    assert.ok(p.url().endsWith('#/trial')); await p.goBack(); await p.locator('.reading-idea-row').first().click(); await p.getByRole('button', { name: /直接审判/ }).click(); await p.locator('.prefill-box').filter({ hasText: names[0] }).waitFor()
  })
  await scenario('develop/debate reading and exact selected card version handoff', async (p) => {
    for (const [mode, version] of [['develop', 2], ['debate', 3]]) {
      await p.goto(`${base}/#/runs/synthetic-${mode}`); await p.getByRole('heading', { name: `合成研究卡第 ${version} 版`, exact: true }).waitFor()
      await p.getByRole('button', { name: '研究卡 v1', exact: true }).click(); await p.getByRole('heading', { name: '合成研究卡第一版', exact: true }).waitFor()
      await p.getByRole('button', { name: `研究卡 v${version}`, exact: true }).click(); await p.getByRole('heading', { name: `合成研究卡第 ${version} 版`, exact: true }).waitFor()
      await shot(p, `synthetic-after-${mode}-desktop.png`)
      await p.getByRole('button', { name: /带入这版研究卡审判/ }).click(); await p.getByText(`card_synthetic · v${version}`, { exact: true }).waitFor()
    }
  })
  await scenario('section links, back and refresh keep route and content', async (p) => {
    await p.goto(`${base}/${discover}`); await p.locator('.reading-nav a[href="#reading-records"]').click(); assert.ok(p.url().endsWith(discover))
    await p.getByRole('button', { name: /收藏馆/ }).click(); await p.locator('.reading-run-row').first().waitFor(); await p.locator('.reading-run-row').first().click()
    await p.reload(); await p.locator('.reading-idea-row').first().waitFor(); assert.equal(await p.locator('.reading-idea-row').count(), 5)
  })
  await scenario('375px collection, discovery card and stage prose have no overflow', async (p) => {
    await p.goto(`${base}/#/collection`); await p.locator('.reading-run-row').first().waitFor(); await noOverflow(p); await shot(p, 'synthetic-after-collection-mobile.png')
    await p.locator('.reading-run-row').first().click(); await p.locator('.reading-idea-row').first().waitFor(); await noOverflow(p); await p.locator('.reading-idea-row').first().click()
    await p.getByRole('dialog').getByText('场景与研究问题', { exact: true }).waitFor(); await noOverflow(p); assert.equal(await p.locator('.reading-card-portrait').isVisible(), false); await shot(p, 'synthetic-after-card-mobile.png'); await closeModal(p)
    await p.goto(`${base}/#/runs/synthetic-develop`); await p.getByRole('heading', { name: '合成研究卡第 2 版', exact: true }).waitFor(); await noOverflow(p)
    const prose = await p.locator('#reading-cards .reading-prose').first().evaluate((el) => { const s = getComputedStyle(el); return { overflow: s.overflowY, font: getComputedStyle(el.querySelector('.md-body')).fontSize } }); assert.notEqual(prose.overflow, 'scroll'); assert.equal(prose.font, '14px')
  }, { viewport: { width: 375, height: 812 } })
  await scenario('old server 404 compatibility for detail and job result', async (p, calls) => {
    await p.goto(`${base}/${discover}`); await p.locator('.reading-idea-row').first().waitFor(); assert.ok(calls.filter((c) => c.path === '/api/runs/synthetic-discover-1').length >= 2)
    await p.goto(`${base}/#/summon?job=synthetic-pack`); await p.getByRole('button', { name: '全部翻开', exact: true }).waitFor(); assert.ok(calls.some((c) => c.path === '/api/jobs/synthetic-pack'))
  }, { handler: ({ path }) => /\/visibility$/.test(path) ? { status: 404, json: { detail: 'Synthetic old server has no visibility API' } } : undefined })
  for (const status of [401, 403, 410, 503]) await scenario(`${status} visibility blocks content without compatibility fallback`, async (p, calls) => {
    await p.goto(`${base}/${discover}`)
    if (status === 401) await p.locator('input[type=password]').waitFor(); else await p.getByRole('alert').filter({ hasText: `Synthetic ${status}` }).waitFor()
    assert.equal(calls.filter((c) => c.path === '/api/runs/synthetic-discover-1').length, 0); assert.equal(await p.locator('.reading-idea-row').count(), 0)
  }, { handler: ({ path }) => /\/visibility$/.test(path) ? { status, json: { detail: `Synthetic ${status}` } } : undefined })
  await scenario('404 capability fallback still requires protected resource permission', async (p, calls) => {
    await p.goto(`${base}/${discover}`); await p.getByRole('alert').filter({ hasText: 'Synthetic protected resource 403' }).waitFor(); assert.equal(await p.locator('.reading-idea-row').count(), 0)
    assert.equal(calls.filter((c) => c.path === '/api/runs/synthetic-discover-1').length, 1)
  }, { handler: ({ path }) => path.endsWith('/visibility') ? { status: 404, json: { detail: 'Missing capability' } } : path === '/api/runs/synthetic-discover-1' ? { status: 403, json: { detail: 'Synthetic protected resource 403' } } : undefined })
  let switched = false
  await scenario('explicit selected version redirects open card without stale content', async (p) => {
    await p.goto(`${base}/${discover}`); await p.locator('.reading-idea-row').first().click(); await p.getByRole('dialog').waitFor(); switched = true
    await p.waitForURL('**/#/runs/synthetic-discover-2', { timeout: 8000 }); await p.locator('.reading-idea-row').first().waitFor(); assert.equal(await p.getByRole('dialog').count(), 0)
    assert.equal(await p.getByRole('heading', { name: /合成验收 1/ }).count(), 0)
  }, { handler: ({ path }) => path === '/api/runs/synthetic-discover-1/visibility' ? { visible: !switched, current_run_id: switched ? 'synthetic-discover-2' : 'synthetic-discover-1', version_revision: switched ? 2 : 1 } : undefined })
  await scenario('late original file response cannot replace a newer modal', async (p) => {
    await p.goto(`${base}/${discover}`); await p.locator('#reading-records').getByText(/查看完整文档/).click(); await p.getByRole('button', { name: '领域简报', exact: true }).click(); await closeModal(p)
    await p.getByRole('button', { name: '费用明细', exact: true }).click(); await p.getByRole('dialog').getByText('合成新文件 B', { exact: true }).waitFor(); await delay(1000); assert.equal(await p.getByText('合成旧文件 A', { exact: true }).count(), 0)
  }, { handler: async ({ path, query }) => { if (path.endsWith('/file') && ['FIELD_BRIEF.md', 'COST_REPORT.md'].includes(query.get('name'))) { const old = query.get('name') === 'FIELD_BRIEF.md'; await delay(old ? 900 : 10); return { name: query.get('name'), content: old ? '合成旧文件 A' : '合成新文件 B' } } } })
  await scenario('individual flip, all flip near 180 degrees and reset', async (p) => {
    await p.goto(`${base}/#/summon?job=synthetic-pack`); await p.getByRole('button', { name: '全部翻开', exact: true }).waitFor(); await p.getByRole('button', { name: '翻开灵感卡', exact: true }).first().click()
    await p.waitForFunction(() => { const e = document.querySelector('.card3d'); const a = Number(e.style.transform.match(/rotateY\(([-\d.]+)deg\)/)?.[1]); return a >= 179 && a <= 181 })
    await p.getByRole('button', { name: '全部翻开', exact: true }).click(); await p.waitForFunction(() => [...document.querySelectorAll('.card3d')].every((e) => { const a = Number(e.style.transform.match(/rotateY\(([-\d.]+)deg\)/)?.[1]); return a >= 179 && a <= 181 }))
    assert.equal(await p.locator('.card3d').count(), 5); await p.getByRole('button', { name: '再抽', exact: true }).click(); await p.locator('textarea').waitFor(); assert.ok(!p.url().includes('job='))
  })
  await scenario('main pages retain the card theme with three distinct stage colors', async (p) => {
    await p.goto(`${base}/#/`); await p.locator('.mode-card').first().waitFor(); await delay(250)
    const colors = await p.locator('.mode-card').evaluateAll((els) => els.map((e) => getComputedStyle(e).backgroundImage))
    assert.equal(new Set(colors).size, 3)
    await shot(p, 'theme-after-hall-desktop.png')
    for (const [route, title] of [['summon','召唤'],['trial','试炼'],['judgment','审判']]) {
      await p.goto(`${base}/#/${route}`); await p.getByRole('heading', { name: new RegExp(title) }).waitFor(); await delay(220)
      await noOverflow(p); await shot(p, `theme-after-${route}-form-desktop.png`)
      const body = await p.locator('body').innerText()
      for (const phrase of ['起阵','法阵预热','阵断了','烧真金白银','开庭','最近的邻居','待上报']) assert.ok(!body.includes(phrase), `UI copy excludes ${phrase}`)
    }
  })
  await scenario('login uses the same theme and readable account/fee copy', async (p) => {
    await p.goto(`${base}/#/login`); await p.locator('input[type=password]').waitFor(); await delay(220); await noOverflow(p)
    await p.getByText('账号由管理员开通，研究任务会按实际调用计费。', { exact: true }).waitFor(); await shot(p, 'theme-after-login-desktop.png')
  }, { handler: ({path}) => path === '/api/auth/me' ? { status:401,json:{detail:'Synthetic no session'} } : undefined })
  await scenario('login at 375px has no horizontal overflow', async (p) => {
    await p.goto(`${base}/#/login`); await p.locator('input[type=password]').waitFor(); await delay(220); await noOverflow(p); await shot(p, 'theme-after-login-mobile.png')
  }, { viewport:{width:375,height:812}, handler: ({path}) => path === '/api/auth/me' ? {status:401,json:{detail:'Synthetic no session'}} : undefined })
  for (const [mode,route] of [['develop','trial'],['debate','judgment'],['discover','summon']]) await scenario(`${mode} running page displays complete natural status text`, async (p) => {
    await p.goto(`${base}/#/${route}?job=visual-${mode}`); await p.locator('.ritual-stage').waitFor(); await delay(220); await noOverflow(p)
    await p.getByText('最近完成的步骤',{exact:true}).waitFor(); assert.ok(!(await p.locator('body').innerText()).includes('法阵预热'))
    await shot(p, `theme-after-${mode}-running-desktop.png`)
  }, { handler: ({path}) => path === `/api/jobs/visual-${mode}` ? {job:{id:`visual-${mode}`,mode,params:{},username:'synthetic',status:'running',run_dir:null,error:null,created_at:created,finished_at:null},
    progress:{current:mode==='discover'?'idea1.check':'proposal.development',draws_started:1,draws_max:3,rounds_completed:1,rounds_max:2,budget:{spent_upper_cny:.12,reserved_cny:.03,limit_cny:10,total_cost_complete:true},tasks:[{task_id:'survey',status:'ACCEPTED'},{task_id:'idea1.sketch',status:'RESPONSE_SAVED',handoff:'candidate_prestudy',research_verified:false}]},log_tail:'仅为合成验收，无实际调用。'} : undefined })
  await scenario('375px forms, running page and stage navigation remain usable', async (p) => {
    for (const route of ['summon','trial','judgment']) { await p.goto(`${base}/#/${route}`); await p.locator('textarea').waitFor(); await noOverflow(p) }
    await p.goto(`${base}/#/trial?job=visual-mobile`); await p.locator('.ritual-stage').waitFor(); await noOverflow(p); await shot(p,'theme-after-running-mobile.png')
  }, {viewport:{width:375,height:812},handler:({path})=>path==='/api/jobs/visual-mobile'?{job:{id:'visual-mobile',mode:'develop',params:{},username:'synthetic',status:'running',run_dir:null,error:null,created_at:created,finished_at:null},progress:{current:'proposal.development',tasks:[]},log_tail:''}:undefined})
  await scenario('rapid card/disclosure actions close cleanly and restore focus', async (p) => {
    await p.goto(`${base}/${discover}`); const trigger=p.locator('.reading-idea-row').first(); await trigger.waitFor()
    for(let i=0;i<4;i++){ await trigger.click(); await p.getByRole('dialog').waitFor(); const disclosure=p.getByRole('dialog').locator('summary').filter({hasText:'技术分析与证据限制'}); for(let k=0;k<6;k++)await disclosure.click(); assert.equal(await disclosure.locator('..').getAttribute('open'),null); await closeModal(p); assert.equal(await trigger.evaluate(el=>document.activeElement===el),true) }
    assert.equal(await p.evaluate(()=>document.body.style.overflow), '')
  })
  await scenario('reduced motion removes decorative animation and keeps flip/reset working', async (p) => {
    await p.goto(`${base}/#/summon?job=synthetic-reduced`); await p.getByRole('button',{name:'全部翻开',exact:true}).waitFor(); await p.getByRole('button',{name:'全部翻开',exact:true}).click()
    await p.waitForFunction(()=>[...document.querySelectorAll('.card3d')].every(el=>el.style.transform.includes('rotateY(180deg)')))
    const styles=await p.locator('.pack-stage').evaluate(el=>({duration:getComputedStyle(el).animationDuration,motion:matchMedia('(prefers-reduced-motion:reduce)').matches}))
    assert.equal(styles.motion,true); await p.getByRole('button',{name:'再抽',exact:true}).click(); await p.locator('textarea').waitFor()
    const duration=await p.locator('.page').evaluate(el=>parseFloat(getComputedStyle(el).animationDuration)); assert.ok(duration<=.001)
  },{reducedMotion:'reduce'})
  await scenario('body and secondary text contrast on reading panels is above 4.5',async(p)=>{
    await p.goto(`${base}/${discover}`);await p.locator('.reading-idea-row').first().waitFor()
    const values=await p.evaluate(()=>{const s=getComputedStyle(document.documentElement);return ['--panel','--cream','--cream-dim'].map(x=>s.getPropertyValue(x).trim())})
    const luminance=(hex)=>{const a=hex.replace('#','').match(/../g).map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return .2126*a[0]+.7152*a[1]+.0722*a[2]}
    for(const fg of values.slice(1)){const contrast=(luminance(fg)+.05)/(luminance(values[0])+.05);assert.ok(contrast>=4.5,`contrast ${contrast}`)}
  })

  await scenario('long desktop and mobile pages retain the dark table background', async (p) => {
    await p.goto(`${base}/#/collection`); await p.locator('.reading-run-row').first().waitFor(); await delay(400)
    const metrics = await p.evaluate(() => ({ height:document.body.getBoundingClientRect().height, full:document.documentElement.scrollHeight, background:getComputedStyle(document.documentElement).backgroundColor }))
    assert.ok(metrics.height >= metrics.full-1); assert.equal(metrics.background,'rgb(17, 19, 28)')
  })

  // Existing regression harness connects to this isolated server; its API route mocks never hit production.
  if (process.env.RUN_EXISTING_REGRESSIONS === '1') {
    const { spawn } = await import('node:child_process')
    const code = await new Promise((done) => { const child = spawn(process.execPath, [join(process.cwd(), 'scripts/regression-client.mjs')], { cwd: process.cwd(), env: { ...process.env, BASE_URL: base }, stdio: 'inherit' }); child.on('exit', done) })
    results.push({ name: 'adapted existing 10 browser regressions', status: code === 0 ? 'passed' : 'failed', exitCode: code })
  }
} finally {
  await browser.close(); await new Promise((done) => server.close(done))
  const report = { dataset: '7 synthetic records: 5 discover, 1 develop, 1 debate; 21 idea cards', apiMode: 'All APIs intercepted; no real login/data/model calls', results, requests, screenshots: 'synthetic-* and theme-* screenshots; synthetic records only' }
  writeFileSync(join(output, process.env.READING_TEST_FILTER ? 'reading-browser-targeted.json' : 'reading-browser.json'), JSON.stringify(report, null, 2)); console.log(JSON.stringify({ passed: results.filter((r) => r.status === 'passed').length, failed: results.filter((r) => r.status === 'failed').length }))
  if (results.some((r) => r.status === 'failed')) process.exitCode = 1
}
