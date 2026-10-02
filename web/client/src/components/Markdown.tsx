import { useMemo } from 'react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({ breaks: true, gfm: true })

export default function Markdown({ text, className = '', fileName, files, onOpenFile }: {
  text: string; className?: string; fileName?: string; files?: string[]
  onOpenFile?: (name: string) => void
}) {
  const html = useMemo(() => {
    try {
      return DOMPurify.sanitize(marked.parse(text, { async: false }) as string, {
        USE_PROFILES: { html: true },
        FORBID_TAGS: ['style', 'form', 'input', 'button'],
        FORBID_ATTR: ['style'],
      })
    } catch {
      return null
    }
  }, [text])
  if (html === null) return <pre className={`md-body ${className}`}>{text}</pre>
  return (
    <div
      className={`md-body ${className}`}
      style={{ fontSize: 13.5, lineHeight: 1.7 }}
      onClick={(event) => {
        const link = (event.target as Element).closest('a')
        const href = link?.getAttribute('href')
        if (!href || !fileName || !onOpenFile) return
        if (/^(?:[a-z][a-z0-9+.-]*:|\/\/|#)/i.test(href)) return
        // Resolve report-relative links within the current run's file list.
        // Relative navigation would otherwise reload the SPA at a missing URL.
        event.preventDefault()
        try {
          const target = new URL(href, `https://arc.invalid/${fileName}`)
          const name = decodeURIComponent(target.pathname.slice(1))
          if (target.origin === 'https://arc.invalid' && files?.includes(name)) onOpenFile(name)
        } catch { /* malformed report link */ }
      }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}
