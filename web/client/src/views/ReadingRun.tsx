import { useCallback, useEffect, useState, type ComponentProps, type MouseEvent, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import LegacyRunDetail from './RunDetail'
import IdeaCard from '../components/IdeaCard'
import Modal from '../components/Modal'
import Markdown from '../components/Markdown'
import { followDocumentLink, ReadingText, SourceLinks, useDocument } from './ReadingText'
import { assessmentLabel, cardDecision, cardTitle, explicitOverview, firstSentence, modeLabel,
  normalizeRun, readableDecision, withoutExternalLinks, type ReadingCard, type ReadingRun as ReadingRunData } from './reading'
import './reading.css'

type DisplayCard = ComponentProps<typeof IdeaCard>['card']

function fileLabel(name: string) {
  const known: Record<string, string> = { 'REPORT.md': '本轮完整报告', 'DISCOVERY_REPORT.md': '本轮完整报告',
    'FIELD_BRIEF.md': '领域简报', 'TECHNICAL_REPORT.md': '技术报告', 'SEARCH_SOURCES.md': '检索来源',
    'COST_REPORT.md': '费用明细', 'WRITING_REVISION.md': '文字修改记录' }
  return known[name] || name
}
function docLabel(doc: { kind: string; version?: number }) {
  return doc.kind === 'card' ? `研究卡 v${doc.version}` : doc.kind === 'technical' ? '技术报告' : '灵感卡'
}

export default function ReadingRun() {
  const { dir = '' } = useParams()
  const navigate = useNavigate()
  const [detail, setDetail] = useState<ReadingRunData | null>(null)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<ReadingCard | null>(null)
  const [viewFile, setViewFile] = useState<string | null>(null)
  const reload = useCallback(async () => {
    try { return normalizeRun(await api.runDetail(dir)) }
    catch (reason) { throw reason }
  }, [dir])
  useEffect(() => {
    let alive = true
    setDetail(null); setError(''); setSelected(null); setViewFile(null)
    reload().then((value) => { if (alive) setDetail(value) }).catch((reason) => { if (alive) setError(String(reason)) })
    return () => { alive = false }
  }, [reload])
  const files = (detail?.files || []).map((file) => file.name)
  const reportName = files.includes('REPORT.md') ? 'REPORT.md' : files.includes('DISCOVERY_REPORT.md') ? 'DISCOVERY_REPORT.md' : null
  const report = useDocument(dir, reportName, detail?.presentation?.revised_at || detail?.run?.updated_at)
  const fileDocument = useDocument(dir, viewFile)
  if (error && !detail) return <div className="page"><p role="alert" className="error-text">读取失败：{error}</p><button className="btn" onClick={() => {
    setError(''); reload().then(setDetail).catch((reason) => setError(String(reason)))
  }}>重试</button></div>
  if (!detail) return <div className="page"><p className="muted" role="status">正在读取研究结果…</p></div>
  const status = detail.run?.status || detail.state?.status
  // Preserve all existing progress, interruption and recovery interactions.
  if (status !== 'COMPLETED' && status !== 'completed') return <LegacyRunDetail />
  const originalQuestion = detail.topic || '未命名讨论'
  const heading = originalQuestion.trim().split('\n')[0]
  const onOpenFile = (name: string) => setViewFile(name)
  const jumpTo = (event: MouseEvent, id: string) => {
    event.preventDefault()
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  const documentLinks = (event: MouseEvent, fileName: string) => {
    followDocumentLink(event, fileName, files, onOpenFile)
  }
  return <div className={`page reading-page reading-${detail.mode}`}>
    <header className="panel reading-hero hero">
      <div className="reading-header-line"><span className="reading-eyebrow">{modeLabel[detail.mode]} · 研究记录</span>
        <button className="btn btn-ghost" onClick={() => navigate('/collection')}>← 收藏馆</button></div>
      <h1>{heading}</h1>
      <div className="reading-meta"><span className="reading-status">已有结果</span>
        {detail.run?.assessment && <span>{assessmentLabel[detail.run.assessment] || '原记录的判断'}</span>}
        {detail.mode === 'discover' && <span>{detail.cards?.length || 0} 张灵感卡</span>}
      </div>
      <details className="reading-context"><summary>查看原始问题</summary><pre>{originalQuestion}</pre></details>
    </header>
    <nav className="reading-nav" aria-label="结果阅读路径"><a href="#reading-summary" onClick={(event) => jumpTo(event, 'reading-summary')}>{detail.mode === 'discover' ? '本次研究发现' : detail.mode === 'develop' ? '方案概览' : '核查结论'}</a>
      <a href="#reading-cards" onClick={(event) => jumpTo(event, 'reading-cards')}>{detail.mode === 'discover' ? '灵感卡' : '研究卡与文档'}</a><a href="#reading-records" onClick={(event) => jumpTo(event, 'reading-records')}>资料与原始记录</a></nav>
    <p className="reading-notice">本页展示此前保存的研究记录，原有结论和证据限制均予以保留。</p>
    {detail.mode === 'discover' ? <DiscoveryOverview detail={detail} report={report.content} reportError={report.error} onSelect={setSelected} />
      : <StageReading detail={detail} report={report.content} reportError={report.error} onOpenFile={onOpenFile} />}
    <section className="panel reading-panel" id="reading-records"><h2>资料与原始记录</h2>
      <p>完整报告、文献来源与技术记录保留在这里。</p>
      <SourceLinks texts={[report.content, ...(detail.cards || []).map((card) => card.presentation?.text || '')]} />
      <details className="reading-disclosure"><summary>查看完整文档 <span>{files.length}</span></summary>
        <div className="reading-files">{files.map((name) => <button className="btn btn-ghost" key={name} onClick={() => onOpenFile(name)}>{fileLabel(name)}</button>)}</div>
      </details>
    </section>
    <Modal open={!!selected} onClose={() => setSelected(null)} wide title="灵感卡">
      {selected && <CardReading card={selected} files={files} onOpenFile={(name) => { setSelected(null); onOpenFile(name) }} onTrial={() => navigate('/trial', { state: { idea_id: selected.idea_id, title: cardTitle(selected) } })}
        onJudgment={() => navigate('/judgment', { state: { idea_id: selected.idea_id, title: cardTitle(selected) } })} />}
    </Modal>
    <Modal open={!!viewFile} onClose={() => setViewFile(null)} wide title={viewFile ? fileLabel(viewFile) : ''}>
      <div className="reading-prose" onClick={(event) => { event.stopPropagation(); if (viewFile) documentLinks(event, viewFile) }}>
        {fileDocument.error ? <p className="error-text" role="alert">读取失败：{fileDocument.error}</p> : fileDocument.content ? <Markdown text={fileDocument.content} /> : <p className="muted">正在读取完整记录…</p>}
      </div>
    </Modal>
  </div>
}

function DiscoveryOverview({ detail, report, reportError, onSelect }: { detail: ReadingRunData; report: string; reportError: string; onSelect: (card: ReadingCard) => void }) {
  const cards = detail.cards || []
  const active = cards.filter((card) => ['lead', 'discuss', 'investigate'].includes(cardDecision(card))).length
  const parked = cards.filter((card) => cardDecision(card) === 'park').length
  const dropped = cards.filter((card) => cardDecision(card) === 'drop').length
  const overview = explicitOverview(report)
  return <>
    <section className="panel reading-panel" id="reading-summary"><span className="reading-eyebrow">整轮概览</span><h2>本次研究发现</h2>
      {overview ? <div className="reading-prose"><Markdown text={overview} /></div> : <p>这一轮记录了 {cards.length} 个想法。下表列出各自的研究价值与当前判断，可以打开感兴趣的卡片，查看具体问题和研究方法。</p>}
      {reportError && <p className="error-text" role="alert">原始报告暂时无法读取：{reportError}</p>}
      <div className="reading-summary-counts"><span>{active} 个可继续讨论或待核查</span>{!!parked && <span>{parked} 个暂存线索</span>}{!!dropped && <span>{dropped} 个暂不推进</span>}</div>
      <div className="reading-idea-index">{cards.map((card, index) => <button key={card.idea_id} className="reading-idea-row" onClick={() => onSelect(card)}>
        <span className="reading-index">{String(index + 1).padStart(2, '0')}</span><span><strong>{cardTitle(card)}</strong>
          <p>{firstSentence(card.seed?.why_it_matters || card.seed?.question || '') || '打开单卡查看当前记录。'}</p></span>
        <span className="reading-decision">{readableDecision(card)} ↗</span></button>)}</div>
    </section>
    <section className="panel reading-panel" id="reading-cards"><h2>灵感卡</h2><p>打开卡片后，可以了解它要解决的问题、与已有工作的差别，以及值得继续研究的理由。</p>
      <div className="reading-card-wall">{cards.map((card) => <IdeaCard key={card.idea_id} card={card as unknown as DisplayCard} onClick={() => onSelect(card)} />)}</div>
    </section>
  </>
}

function CardReading({ card, files, onOpenFile, onTrial, onJudgment }: { card: ReadingCard; files: string[]; onOpenFile: (name: string) => void; onTrial: () => void; onJudgment: () => void }) {
  const proposed = card.presentation?.text
  const note = card.note
  const negative = ['drop', 'park'].includes(cardDecision(card))
  return <article className="reading-card-layout" onClick={(event) => event.stopPropagation()}>
    <aside className="reading-card-portrait"><IdeaCard card={card as unknown as DisplayCard} width={136} /></aside>
    <div className="reading-card-main"><h2>{cardTitle(card)}</h2><span className="reading-status">{readableDecision(card)}</span>
      {negative && (note?.reason || card.triage?.reason) && <ContentSection title="当前判断的依据">{note?.reason || card.triage?.reason}</ContentSection>}
      {proposed ? <ReadingText text={proposed} file={card.idea_md || ''} files={files} onOpenFile={onOpenFile} /> : <>
        <ContentSection title="场景与研究问题">{card.seed?.question}</ContentSection>
        <ContentSection title="核心想法">{card.seed?.insight}</ContentSection>
        <ContentSection title="与已有工作的差别">{card.seed?.difference_from_known}</ContentSection>
        <ContentSection title="可行性依据">{note?.resources?.basis ? String(note.resources.basis) : note?.feasibility}</ContentSection>
        <ContentSection title="为什么值得研究">{card.seed?.why_it_matters}</ContentSection>
      </>}
      <SourceLinks texts={[proposed || '', card.seed?.difference_from_known || '', note?.reason || '']} />
      <details className="reading-disclosure"><summary>技术分析与核查记录</summary><div className="reading-raw-fields">
        <ContentSection title="主要风险">{note?.main_risk || card.seed?.key_unknown}</ContentSection>
        <ContentSection title="仍需回答的问题">{note?.next_question || card.triage?.strongest_objection}</ContentSection>
        {!!note?.limits?.length && <section><h3>证据范围与限制</h3><ul>{note.limits.map((limit, index) => <li key={index}>{limit}</li>)}</ul></section>}
        {!!note?.nearest_work?.length && <section><h3>已有工作与差别</h3>{note.nearest_work.map((work, index) => <div className="reading-section" key={index}>
          <p>已有工作：{work.already_established}</p><p>当前想法与它的差别：{work.remaining_difference}</p>{work.uncertainty && <p>尚未确认：{work.uncertainty}</p>}<small>来源编号：{work.source_id}</small></div>)}</section>}
        {!!note?.source_notes?.length && <section><h3>来源核查记录</h3>{note.source_notes.map((source, index) => <div className="reading-section" key={index}>
          <small>{source.source_id}</small><p>{source.finding}</p>{source.relevance && <p>{source.relevance}</p>}{source.limits && <p>范围限制：{source.limits}</p>}</div>)}</section>}
        {!note && <p>这张卡尚无定向核查记录。</p>}
      </div></details>
      <details className="reading-disclosure"><summary>原始内容与判断依据</summary>
        <dl className="reading-raw-fields">{Object.entries({ '研究问题': card.seed?.question, '原始想法': card.seed?.insight, '研究价值': card.seed?.why_it_matters,
          '原始差别描述': card.seed?.difference_from_known, '初筛理由': card.triage?.reason, '核查理由': note?.reason, '原记录可行性': note?.feasibility }).filter(([, value]) => !!value).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
      </details>
      <div className="reading-actions"><button className="btn btn-blue" onClick={onTrial}>⚔️ 送入试炼</button><button className="btn" onClick={onJudgment}>⚖️ 直接审判</button>
        {card.idea_md && <button className="btn btn-ghost" onClick={() => onOpenFile(card.idea_md!)}>查看原始全文</button>}</div>
    </div>
  </article>
}

function ContentSection({ title, children }: { title: string; children?: ReactNode }) {
  if (!children) return null
  return <section className="reading-section reading-prose"><h3>{title}</h3><Markdown text={withoutExternalLinks(String(children))} /></section>
}

function StageReading({ detail, report, reportError, onOpenFile }: { detail: ReadingRunData; report: string; reportError: string; onOpenFile: (name: string) => void }) {
  const navigate = useNavigate()
  const docs = detail.docs || []
  const mainDocs = docs.filter((doc) => doc.kind !== 'technical')
  const latest = [...mainDocs].sort((a, b) => (b.version || 0) - (a.version || 0))[0]
  const [active, setActive] = useState<string | null>(latest?.file || null)
  const selected = docs.find((doc) => doc.file === active)
  const document = useDocument(detail.dir, active, detail.run?.updated_at)
  const files = (detail.files || []).map((file) => file.name)
  const reportFile = files.includes('REPORT.md') ? 'REPORT.md' : 'DISCOVERY_REPORT.md'
  const overview = explicitOverview(report)
  return <>
    <section className="panel reading-panel" id="reading-summary"><span className="reading-eyebrow">{detail.mode === 'develop' ? '方案发展' : '结论核查'}</span>
      <h2>{detail.mode === 'develop' ? '方案概览' : '核查结论'}</h2>
      {detail.run?.assessment && <p className="reading-status">{assessmentLabel[detail.run.assessment] || '原记录的判断'}</p>}
      {overview ? <div className="reading-prose"><Markdown text={overview} /></div> : <p>{detail.mode === 'develop' ? '这里保存了对选定想法的研究方案，可以阅读各版研究卡，并展开查看技术分析和核查记录。' : '这里保存了方案的核查与修订结果，可以先阅读当前结论，再查看支持证据和反面结果。'}</p>}
      {reportError && <p className="error-text" role="alert">原始报告暂时无法读取：{reportError}</p>}
      {report && <details className="reading-disclosure"><summary>查看本轮报告内容</summary><ReadingText text={report} file={reportFile} files={files} onOpenFile={onOpenFile} /></details>}
    </section>
    <section className="panel reading-panel" id="reading-cards"><h2>{detail.mode === 'develop' ? '研究方案卡' : '核查后的研究记录'}</h2>
      <div className="reading-doc-tabs">{mainDocs.map((doc) => <button key={doc.file} className={`btn ${active === doc.file ? '' : 'btn-ghost'}`} onClick={() => setActive(doc.file)}>{docLabel(doc)}</button>)}</div>
      {active && (document.error ? <p className="error-text" role="alert">读取失败：{document.error}</p> : document.content ? <ReadingText text={document.content} file={active} files={files} onOpenFile={onOpenFile} /> : <p className="muted">正在读取研究卡…</p>)}
      {!mainDocs.length && report && <ReadingText text={report} file={reportFile} files={files} onOpenFile={onOpenFile} />}
      {!!docs.filter((doc) => doc.kind === 'technical').length && <details className="reading-disclosure"><summary>独立技术报告</summary>
        <div className="reading-files">{docs.filter((doc) => doc.kind === 'technical').map((doc) => <button key={doc.file} className="btn btn-ghost" onClick={() => onOpenFile(doc.file)}>{docLabel(doc)}</button>)}</div></details>}
      {selected?.card_id && <div className="reading-actions"><button className="btn" onClick={() => navigate('/judgment', { state: { card_id: selected.card_id, card_version: selected.version, title: detail.topic } })}>⚖️ 带入这版研究卡审判</button></div>}
    </section>
  </>
}
