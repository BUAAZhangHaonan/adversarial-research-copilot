/* Browser regressions with every API request intercepted. No research jobs run.
   BASE_URL=http://127.0.0.1:18211 node scripts/regression-client.mjs */
import assert from 'node:assert/strict'
import { mkdirSync, writeFileSync } from 'node:fs'
import { chromium } from 'playwright'

const base = process.env.BASE_URL || 'http://127.0.0.1:18211'
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const created = '2026-09-12T00:00:00Z'
const seed = { title: '回归验证灵感', question: '问题', insight: '洞见', why_it_matters: '价值', difference_from_known: '区别', source_ids: [], key_unknown: '未知' }
const card = { idea_id: 'idea_test', status: 'pending', seed, note: null, triage: null, sketch: null, idea_md: null, draw_id: null, topic: '测试' }
const detail = (dir, status = 'COMPLETED') => ({ mode: 'discover', dir, run: { status, created_at: created, updated_at: created, stop_reason: null, assessment: null }, topic: `主题 ${dir}`, cards: status === 'RUNNING' ? [] : [card], files: [], cost: null, usage: null })
const job = (id, status = 'running', mode = 'develop', runDir = null) => ({ job: { id, mode, params: {}, username: 'test', status, run_dir: runDir, error: status === 'failed' ? '模拟失败原因' : null, created_at: created, finished_at: status === 'running' ? null : created }, progress: null, log_tail: '' })
const jobList = (status) => ({ jobs: [{ id: 'race-job', mode: 'discover', params: {}, username: 'test', status, run_dir: 'race', created_at: created, finished_at: null }] })
const results = []

async function test(name, handlers, run) {
  const context = await browser.newContext()
  const page = await context.newPage()
  page.setDefaultTimeout(10000)
  const errors = []
  page.on('pageerror', (error) => errors.push(String(error)))
  await context.route('**/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    let response
    try {
      response = await handlers({ path: url.pathname, query: url.searchParams, method: request.method(), body: request.postDataJSON() })
      if (response === undefined) {
        if (url.pathname === '/api/auth/me') response = { username: 'test', is_admin: true }
        else if (url.pathname === '/api/health') response = { scholartrace: true, scholaranalysis: true, webresearch: true, running_jobs: 0, max_jobs: 2 }
        else if (url.pathname === '/api/jobs' && request.method() === 'GET') response = { jobs: [] }
        else if (url.pathname.endsWith('/visibility')) response = { visible: true, current_run_id: url.pathname.split('/')[3], version_revision: 1 }
        else response = { status: 404, json: { detail: `Unexpected API: ${request.method()} ${url.pathname}` } }
      }
      const wrapped = response && typeof response === 'object' && 'json' in response
      await route.fulfill({ status: wrapped ? response.status ?? 200 : 200, contentType: 'application/json', body: JSON.stringify(wrapped ? response.json : response) })
    } catch (error) {
      if (!page.isClosed()) errors.push(`route: ${error}`)
    }
  })
  try {
    await run(page)
    assert.deepEqual(errors, [], 'No browser exceptions')
    results.push({ name, status: 'passed' })
    console.log(`PASS ${name}`)
  } catch (error) {
    results.push({ name, status: 'failed', error: String(error) })
    console.error(`FAIL ${name}: ${error}`)
  } finally { await context.close() }
}

try {
  for (const [mode, path, text, button] of [
    ['develop', '/trial', '测试一个足够长度的研究问题，确保提交入口只提交一次。', '开始试炼'],
    ['debate', '/judgment', '# 测试提案\n研究问题、证据主张、相关近邻、最小验证实验以及预算边界都已经说明。', '开始审判'],
  ]) {
    let submits = 0
    await test(`${mode}: submission lock, URL recovery, cancellation error`, async ({ path: apiPath, method }) => {
      if (apiPath === '/api/jobs' && method === 'POST') { submits++; return { job_id: `${mode}-job` } }
      if (apiPath === `/api/jobs/${mode}-job` && method === 'GET') { await delay(700); return job(`${mode}-job`, 'running', mode) }
      if (apiPath === `/api/jobs/${mode}-job` && method === 'DELETE') return { status: 503, json: { detail: '模拟取消失败' } }
    }, async (page) => {
      await page.goto(`${base}/#${path}`)
      await page.locator('textarea').fill(text)
      await page.getByRole('button', { name: button, exact: true }).evaluate((el) => { el.click(); el.click() })
      await page.waitForSelector('.ritual-stage')
      assert.equal(await page.getByRole('button', { name: button, exact: true }).count(), 0)
      assert.equal(submits, 1)
      assert.ok(page.url().includes(`job=${mode}-job`))
      await page.reload()
      await page.getByRole('button', { name: '终止', exact: true }).waitFor()
      assert.equal(submits, 1, 'Refreshing cannot submit again')
      await page.getByRole('button', { name: '终止', exact: true }).click()
      await page.getByRole('alert').filter({ hasText: '模拟取消失败' }).waitFor()
    })
  }

  let newReads = 0
  await test('job identity isolation and polling error recovery', async ({ path }) => {
    if (path === '/api/jobs/old') return job('old', 'failed')
    if (path === '/api/jobs/new') {
      newReads++
      if (newReads === 1) { await delay(400); return { status: 503, json: { detail: '模拟状态短暂失败' } } }
      return job('new')
    }
  }, async (page) => {
    await page.goto(`${base}/#/trial?job=old`)
    await page.getByText('模拟失败原因', { exact: true }).waitFor()
    await page.evaluate(() => { location.hash = '#/trial?job=new' })
    await page.getByText('正在读取任务状态…', { exact: true }).waitFor()
    assert.equal(await page.getByText('模拟失败原因', { exact: true }).count(), 0)
    await page.getByRole('alert').filter({ hasText: '模拟状态短暂失败' }).waitFor()
    await page.getByRole('button', { name: '终止', exact: true }).waitFor({ timeout: 10000 })
    assert.equal(await page.getByRole('alert').count(), 0, 'Successful poll clears old error')
  })

  let scans = 0
  let statusReads = 0
  let finished = false
  await test('run completion survives jobs/status terminal race', async ({ path }) => {
    if (path === '/api/runs/race') return detail('race', finished ? 'COMPLETED' : 'RUNNING')
    if (path === '/api/jobs') {
      scans++
      if (scans > 1) finished = true
      return jobList(finished ? 'completed' : 'running')
    }
    if (path === '/api/jobs/race-job') {
      statusReads++
      if (statusReads === 1) return job('race-job', 'running', 'discover', 'race')
      await delay(3500)
      return job('race-job', 'completed', 'discover', 'race')
    }
  }, async (page) => {
    await page.goto(`${base}/#/runs/race`)
    await page.getByText('召唤进行中', { exact: true }).waitFor()
    await page.locator('.hero .chip').filter({ hasText: '已完成' }).waitFor({ timeout: 9500 })
    await page.locator('.card-slot').waitFor()
    assert.ok(scans >= 2)
  })

  await test('open all cards and reset same summon route', async ({ path }) => {
    if (path === '/api/jobs/pack') return job('pack', 'completed', 'discover', 'pack')
    if (path === '/api/runs/pack') return { ...detail('pack'), cards: [card, { ...card, idea_id: 'idea_two' }] }
  }, async (page) => {
    await page.goto(`${base}/#/summon?job=pack`)
    await page.getByRole('button', { name: '全部翻开', exact: true }).click()
    await page.waitForFunction(() => [...document.querySelectorAll('.card3d')].every((el) => { const angle = Number(el.style.transform.match(/rotateY\(([-\d.]+)deg\)/)?.[1]); return angle >= 179 && angle <= 181 }))
    assert.equal(await page.locator('.card3d').count(), 2)
    await page.getByRole('button', { name: '再抽', exact: true }).click()
    await page.locator('textarea').waitFor()
    assert.ok(!page.url().includes('job='))
  })

  let resultReads = 0
  await test('summon result fetch error has a working retry', async ({ path }) => {
    if (path === '/api/jobs/result') return job('result', 'completed', 'discover', 'result')
    if (path === '/api/runs/result') {
      resultReads++
      return resultReads === 1 ? { status: 503, json: { detail: '模拟结果失败' } } : detail('result')
    }
  }, async (page) => {
    await page.goto(`${base}/#/summon?job=result`)
    await page.getByRole('alert').filter({ hasText: '模拟结果失败' }).waitFor()
    await page.getByRole('button', { name: '重试读取', exact: true }).click()
    await page.getByRole('button', { name: '全部翻开', exact: true }).waitFor()
  })

  let runReads = 0
  await test('collection read error is distinct from empty and refreshes', async ({ path }) => {
    if (path === '/api/runs') {
      runReads++
      return runReads === 1 ? { status: 503, json: { detail: '模拟列表失败' } } : { runs: [{ dir: 'synced', mode: 'discover', status: 'COMPLETED', stop_reason: null, assessment: null, topic: '同步后的记录', created_at: created, mtime: 0, cost: null }] }
    }
  }, async (page) => {
    await page.goto(`${base}/#/collection`)
    await page.getByRole('alert').filter({ hasText: '模拟列表失败' }).waitFor()
    assert.equal(await page.locator('.reading-empty').count(), 0)
    await page.getByText('同步后的记录', { exact: true }).waitFor({ timeout: 8000 })
    assert.equal(await page.getByRole('alert').count(), 0)
  })

  await test('document requests cannot replace a newer file', async ({ path, query }) => {
    if (path === '/api/runs/files') return { ...detail('files'), files: [{ name: 'FIELD_BRIEF.md', size: 10 }, { name: 'COST_REPORT.md', size: 10 }] }
    if (path === '/api/runs/files/file') {
      const name = query.get('name')
      await delay(name === 'FIELD_BRIEF.md' ? 1200 : 20)
      return { name, content: name === 'FIELD_BRIEF.md' ? '旧文件A的内容' : '新文件B的内容' }
    }
  }, async (page) => {
    await page.goto(`${base}/#/runs/files`)
    await page.locator('#reading-records').getByText(/查看完整文档/).click()
    await page.getByRole('button', { name: /领域简报/ }).click()
    await page.getByRole('button', { name: /关闭/ }).click()
    await page.getByRole('button', { name: /费用明细/ }).click()
    await page.getByText('新文件B的内容', { exact: true }).waitFor()
    await delay(1300)
    assert.equal(await page.getByText('旧文件A的内容', { exact: true }).count(), 0)
    assert.equal(await page.getByText('新文件B的内容', { exact: true }).count(), 1)
  })

  await test('run route changes reject late detail responses and clear errors', async ({ path }) => {
    if (path === '/api/runs/slow') { await delay(1000); return detail('slow') }
    if (path === '/api/runs/fast') return detail('fast')
    if (path === '/api/runs/missing') return { status: 404, json: { detail: '模拟无记录' } }
  }, async (page) => {
    await page.goto(`${base}/#/runs/slow`)
    await delay(150)
    await page.evaluate(() => { location.hash = '#/runs/fast' })
    await page.getByRole('heading', { name: '主题 fast', exact: true }).waitFor()
    await delay(1100)
    assert.equal(await page.getByRole('heading', { name: '主题 slow', exact: true }).count(), 0)
    await page.evaluate(() => { location.hash = '#/runs/missing' })
    await page.getByRole('alert').filter({ hasText: '模拟无记录' }).waitFor()
    await page.evaluate(() => { location.hash = '#/runs/fast' })
    await page.getByRole('heading', { name: '主题 fast', exact: true }).waitFor()
    assert.equal(await page.getByRole('alert').count(), 0)
  })

  let forbiddenSubmits = 0
  await test('research-card handoff carries exact version without starting a job', async ({ path, method }) => {
    if (path === '/api/runs/card') return { ...detail('card'), mode: 'develop', docs: [{ kind: 'card', file: 'card.v2.md', size: 10, card_id: 'card_test', version: 2 }], input_idea: null }
    if (path === '/api/runs/card/file') return { name: 'card.v2.md', content: '研究卡第二版' }
    if (path === '/api/jobs' && method === 'POST') { forbiddenSubmits++; return { status: 400, json: { detail: 'Unexpected job submission' } } }
  }, async (page) => {
    await page.goto(`${base}/#/runs/card`)
    await page.getByRole('button', { name: '研究卡 v2', exact: true }).click()
    await page.getByRole('button', { name: /带入这版研究卡审判/ }).click()
    await page.getByText('card_test · v2', { exact: true }).waitFor()
    assert.equal(forbiddenSubmits, 0)
  })
} finally {
  await browser.close()
  const report = JSON.stringify({ apiMode: 'fully mocked; no production mutation', results }, null, 2)
  mkdirSync('output/playwright', { recursive: true })
  writeFileSync('output/playwright/client-regression.json', report)
  console.log(report)
  if (results.some((r) => r.status === 'failed')) process.exitCode = 1
}
