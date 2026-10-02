import { useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'

const modalStack: symbol[] = []
let previousOverflow = ''

export default function Modal({
  open,
  onClose,
  title,
  children,
  wide,
}: {
  open: boolean
  onClose: () => void
  title: React.ReactNode
  children: React.ReactNode
  wide?: boolean
}) {
  const titleId = useId()
  const panel = useRef<HTMLDivElement>(null)
  const close = useRef(onClose)
  close.current = onClose
  useEffect(() => {
    if (!open) return
    const key = Symbol('modal')
    const previousFocus = document.activeElement as HTMLElement | null
    if (!modalStack.length) {
      previousOverflow = document.body.style.overflow
      document.body.style.overflow = 'hidden'
    }
    modalStack.push(key)
    const focusable = () => Array.from(panel.current?.querySelectorAll<HTMLElement>(
      'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex="0"]',
    ) ?? []).filter((el) => el.getClientRects().length > 0)
    const focusFirst = () => (focusable()[0] ?? panel.current)?.focus()
    focusFirst()
    const onKey = (e: KeyboardEvent) => {
      if (modalStack[modalStack.length - 1] !== key) return
      if (e.key === 'Escape') { e.preventDefault(); e.stopImmediatePropagation(); close.current() }
      if (e.key === 'Tab') {
        const elements = focusable()
        const first = elements[0]
        const last = elements[elements.length - 1]
        if (!first) { e.preventDefault(); panel.current?.focus() }
        else if (e.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) {
          e.preventDefault(); last.focus()
        } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
      }
    }
    const onFocus = (e: FocusEvent) => {
      if (modalStack[modalStack.length - 1] === key && !panel.current?.contains(e.target as Node)) focusFirst()
    }
    window.addEventListener('keydown', onKey)
    document.addEventListener('focusin', onFocus)
    return () => {
      window.removeEventListener('keydown', onKey)
      document.removeEventListener('focusin', onFocus)
      modalStack.splice(modalStack.indexOf(key), 1)
      if (!modalStack.length) document.body.style.overflow = previousOverflow
      if (previousFocus?.isConnected) previousFocus.focus()
    }
  }, [open])

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          className="modal-backdrop"
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 80,
            background: 'rgba(9, 11, 20, 0.8)', backdropFilter: 'blur(3px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            ref={panel}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            tabIndex={-1}
            className="panel modal-panel"
            style={{ width: wide ? 'min(920px, 96vw)' : 'min(560px, 94vw)' }}
            initial={{ scale: 0.97, y: 12 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.98, y: 6, opacity: 0 }}
            transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-head">
              <h3 id={titleId} className="panel-title" style={{ margin: 0 }}>{title}</h3>
              <span style={{ flex: 1 }} />
              <button className="btn btn-ghost modal-close" title="关闭 (Esc)" onClick={onClose}>
                ✕ 关闭
              </button>
            </div>
            <div className="modal-body">{children}</div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  )
}
