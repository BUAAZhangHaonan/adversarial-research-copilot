import { useEffect, useState, type MouseEvent } from 'react'
import Markdown from '../components/Markdown'
import { api } from '../api'
import { organizeMarkdown, references, withoutExternalLinks, type ReadingPart } from './reading'

export function followDocumentLink(event: MouseEvent, file: string, files: string[], onOpenFile: (name: string) => void) {
  const href = (event.target as Element).closest('a')?.getAttribute('href')
  if (!href || /^(?:[a-z][a-z0-9+.-]*:|\/\/|#)/i.test(href)) return
  event.preventDefault()
  try {
    const url = new URL(href, `https://arc.invalid/${file}`)
    const name = decodeURIComponent(url.pathname.slice(1))
    if (url.origin === 'https://arc.invalid' && files.includes(name)) onOpenFile(name)
  } catch { /* Preserve the original link without navigating outside this record. */ }
}

export function ReadingText({ text, heading = true, file = '', files = [], onOpenFile }: {
  text: string; heading?: boolean; file?: string; files?: string[]; onOpenFile?: (name: string) => void
}) {
  const parts = organizeMarkdown(text)
  const render = (items: ReadingPart[], primary = false) => items.map((part, index) => (
    <section className="reading-section" key={index}>
      {heading && part.title && <h3>{part.title}</h3>}
      <Markdown text={primary ? withoutExternalLinks(part.text) : part.text} />
    </section>
  ))
  return <div onClick={(event) => { if (onOpenFile) followDocumentLink(event, file, files, onOpenFile) }}>
    <div className="reading-prose">{render(parts.main, true)}</div>
    {!!parts.technical.length && <details className="reading-disclosure"><summary>技术分析与证据限制</summary>{render(parts.technical)}</details>}
    {!!parts.sources.length && <details className="reading-disclosure reading-sources"><summary>文献与来源记录</summary>{render(parts.sources)}</details>}
  </div>
}

export function SourceLinks({ texts }: { texts: string[] }) {
  const refs = texts.flatMap(references).filter((item, index, all) => all.findIndex((other) => other.url === item.url) === index)
  if (!refs.length) return null
  return <details className="reading-disclosure reading-sources"><summary>关键文献与链接 <span>{refs.length}</span></summary>
    <ol>{refs.map((ref) => <li key={ref.url}><a href={ref.url} target="_blank" rel="noopener noreferrer">{ref.label}</a>
      <span className="reading-source-host">{sourceHost(ref.url)}</span></li>)}</ol>
  </details>
}

function sourceHost(url: string): string {
  try { return new URL(url).hostname } catch { return '原始来源链接' }
}

export function useDocument(dir: string, file: string | null, revision?: string | null) {
  const [content, setContent] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    let alive = true
    setContent(''); setError('')
    if (file) api.runFile(dir, file).then((result) => { if (alive) setContent(result.content) })
      .catch((reason) => { if (alive) setError(String(reason)) })
    return () => { alive = false }
  }, [dir, file, revision])
  return { content, error }
}
