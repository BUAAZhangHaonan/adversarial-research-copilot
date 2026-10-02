/** Display organization only. Original fields and source documents remain untouched. */
export interface ReadingCard {
  [key: string]: unknown
  idea_id: string
  seed?: { title?: string; question?: string; insight?: string; why_it_matters?: string; difference_from_known?: string; key_unknown?: string } | null
  presentation?: { presentation_title: string; text: string } | null
  triage?: { action?: string; reason?: string; strongest_objection?: string } | null
  note?: { decision?: string; reason?: string; feasibility?: string; main_risk?: string; next_question?: string;
    limits?: string[]; resources?: Record<string, unknown>;
    nearest_work?: { source_id: string; already_established: string; remaining_difference: string; uncertainty?: string }[];
    source_notes?: { source_id: string; finding: string; relevance?: string; limits?: string }[] } | null
  status?: string
  idea_md?: string | null
}
export interface ReadingDoc { kind: string; file: string; version?: number; card_id?: string }
export interface ReadingRun {
  mode: 'discover' | 'develop' | 'debate'
  dir: string
  topic: string
  run?: { status?: string | null; assessment?: string | null; created_at?: string | null; updated_at?: string | null; interrupted?: boolean }
  state?: { status?: string }
  cards?: ReadingCard[]
  docs?: ReadingDoc[]
  files?: { name: string; file?: string; size?: number }[]
  presentation?: { label?: string; revised_at?: string } | null
}

export const modeLabel = { discover: '召唤', develop: '试炼', debate: '审判' }
export const decisionLabel: Record<string, string> = {
  lead: '值得优先讨论', discuss: '可以继续讨论', investigate: '已入围，待核查',
  park: '暂存线索', drop: '暂不推进', pending: '尚待判断', checked: '已完成核查',
}
export const assessmentLabel: Record<string, string> = {
  PROMISING: '可以继续讨论', NEEDS_EVIDENCE: '仍需补充证据', REJECTED: '暂不推进',
  SCOPE_CHANGE_PROPOSED: '需要调整问题范围',
}
export function cardTitle(card: ReadingCard): string {
  return card.presentation?.presentation_title || card.seed?.title || String(card.title || '未命名灵感')
}
export function cardDecision(card: ReadingCard): string {
  return card.note?.decision || card.triage?.action || card.status || 'pending'
}
export function readableDecision(card: ReadingCard): string {
  return decisionLabel[cardDecision(card)] || '原记录的判断'
}
export function normalizeRun(value: unknown): ReadingRun {
  const raw = value as ReadingRun
  return { ...raw, files: (raw.files || []).map((entry) => ({ ...entry, name: entry.file || entry.name })),
    cards: (raw.cards || []).map((card, index) => ({ ...card,
      idea_id: card.idea_id || String(card.id || index),
      seed: card.seed || { title: String(card.title || ''), question: String(card.question || ''),
        insight: String(card.insight || ''), why_it_matters: String(card.why_it_matters || ''),
        difference_from_known: String(card.difference_from_known || '') },
    })) }
}

export interface Reference { label: string; url: string }
export function references(text: string): Reference[] {
  const found: Reference[] = []
  for (const match of text.matchAll(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)(?:\s+"[^"]*")?\)/g)) {
    found.push({ label: match[1], url: match[2] })
  }
  for (const match of text.matchAll(/https?:\/\/[^\s<>)\]]+/g)) {
    if (!found.some((item) => item.url === match[0])) found.push({ label: '原文来源', url: match[0] })
  }
  return found.filter((item, index) => found.findIndex((other) => other.url === item.url) === index)
}
export function withoutExternalLinks(text: string): string {
  return text.replace(/<a\b[^>]*href=["']https?:[^>]*>([\s\S]*?)<\/a>/gi, '$1')
    .replace(/\[([^\]]+)\]\(https?:\/\/[^)]+\)/g, '$1')
    .replace(/<https?:\/\/[^>]+>/g, '〔来源见展开记录〕')
    .replace(/https?:\/\/[^\s<>)\]]+/g, '〔来源见展开记录〕')
}
export function firstSentence(text: string): string {
  const plain = withoutExternalLinks(text).replace(/^#+\s+/gm, '').trim()
  const paragraph = plain.split(/\n\s*\n/)[0] || ''
  const sentence = paragraph.match(/^[\s\S]*?[。！？](?:[”’」』])?/)
  return sentence?.[0] || paragraph
}
export interface ReadingPart { title: string; text: string }
export function organizeMarkdown(text: string): { main: ReadingPart[]; technical: ReadingPart[]; sources: ReadingPart[] } {
  const parts: ReadingPart[] = []
  let current: ReadingPart = { title: '', text: '' }
  for (const line of text.split('\n')) {
    const heading = line.match(/^#{1,6}\s+(.+)$/)
    if (heading) {
      if (current.text.trim()) parts.push(current)
      current = { title: heading[1], text: '' }
    } else current.text += line + '\n'
  }
  if (current.text.trim()) parts.push(current)
  const output = { main: [] as ReadingPart[], technical: [] as ReadingPart[], sources: [] as ReadingPart[] }
  for (const part of parts) {
    if (/文献|参考资料|来源|引用|references|bibliography|sources/i.test(part.title)) output.sources.push(part)
    else if (/技术分析|证据限制|风险|算力|资源|实验|验证计划|审计|原始记录|technical|limitations/i.test(part.title)) output.technical.push(part)
    else output.main.push(part)
  }
  return output
}
export function explicitOverview(text: string): string {
  const parts = organizeMarkdown(text).main.filter((part) => /^(?:本轮总结|本次研究发现|整体认识|共同问题|总体判断|本轮发现|总体结论)$/.test(part.title.trim()))
  return parts.map((part) => withoutExternalLinks(part.text.trim())).join('\n\n')
}
