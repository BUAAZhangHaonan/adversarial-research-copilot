import assert from 'node:assert/strict'
import { build } from 'esbuild'
const result = await build({entryPoints:['src/views/reading.ts'],bundle:true,write:false,platform:'node',format:'cjs'})
const module = {exports:{}}
new Function('module','exports',result.outputFiles[0].text)(module,module.exports)
const reading = module.exports
const original = '# 方案\n\n成功率提高13.2%，仍是待检验设想。[When2Tool](https://example.org/paper)\n\n## 技术分析\n\n线性读出近随机，不证明信号不存在。\n\n## 参考文献\n\n[论文原文](https://example.org/paper)\n'
const parts = reading.organizeMarkdown(original)
assert.ok(parts.main[0].text.includes('13.2%'))
assert.ok(parts.technical[0].text.includes('不证明信号不存在'))
assert.ok(parts.sources[0].text.includes('https://example.org/paper'))
const main = reading.withoutExternalLinks(parts.main[0].text)
assert.ok(main.includes('13.2%') && main.includes('待检验设想') && main.includes('When2Tool'))
assert.ok(!main.includes('https://'))
assert.equal(reading.references(original).length, 1)
assert.equal(reading.references(original)[0].url, 'https://example.org/paper')
assert.equal(reading.explicitOverview('# 卡片一\n\n设想\n\n## 总结\n\n单卡全文'), '')
assert.equal(reading.explicitOverview('## 本轮总结\n\n保留原认识。\n\n## 卡片一\n\n单卡细节'), '保留原认识。')
assert.equal(reading.firstSentence('第一句。第二句。'), '第一句。')
const raw = {mode:'discover',dir:'r',topic:'same',cards:[{idea_id:'a',seed:{title:'t',question:'q'},note:{decision:'drop',reason:'反面结果'}}],files:[{name:'REPORT.md'}]}
const before = JSON.stringify(raw)
const normalized = reading.normalizeRun(raw)
assert.equal(reading.readableDecision(normalized.cards[0]), '暂不推进')
assert.equal(JSON.stringify(raw), before)
assert.equal(normalized.cards[0].note.reason, '反面结果')
console.log('PASS reading: citations retained, primary links removed, hypotheses/negative evidence/percentages unchanged, no duplicate card overview, no record mutation')
