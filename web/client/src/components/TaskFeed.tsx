import { AnimatePresence, motion } from 'framer-motion'
import type { TaskProgress } from '../types'
import { taskLabel } from '../rarity'

const taskStatus = (status: string) => (({ ACCEPTED: '已完成', RESPONSE_SAVED: '已保存回复', PENDING: '等待执行', PAUSED_EXTERNAL: '暂时无法继续', PAUSED_PROTOCOL: '输出需要修复', UNKNOWN: '状态待确认' } as Record<string,string>)[status] || status)

const STATUS_ICON: Record<string, string> = {
  ACCEPTED: '✓',
  RESPONSE_SAVED: '◔',
  PENDING: '…',
  PAUSED_EXTERNAL: '⏸',
  PAUSED_PROTOCOL: '⏸',
  UNKNOWN: '?',
}

/** 任务流水：最近完成的语义任务（来自 CLI stdout 进度事件） */
export default function TaskFeed({ tasks, current, max = 8 }: {
  tasks: TaskProgress[]
  current?: string
  max?: number
}) {
  const shown = tasks.slice(-max)
  return (
    <div className="task-feed">
      <AnimatePresence initial={false}>
        {shown.map((t) => {
          const handedOff = t.handoff === 'candidate_prestudy' && t.research_verified === false
          const done = t.status === 'ACCEPTED' && !handedOff
          return (
            <motion.div
              key={t.task_id}
              layout
              initial={{ opacity: 0, x: -18 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25 }}
              className={`task-item ${done ? 'task-done' : ''} ${current === t.task_id ? 'task-current' : ''}`}
            >
              <span className={`task-ico ${done ? 'ok' : handedOff ? '' : 'warn'}`}>{handedOff ? '↗' : STATUS_ICON[t.status] ?? '◔'}</span>
              <span className="task-name">{taskLabel(t.task_id)}</span>
              <span className="task-status pixel" title={handedOff ? `原始任务状态：${t.status}；证据仍待核查。` : undefined}>
                {handedOff ? '想法还需要核查' : taskStatus(t.status)}
              </span>
            </motion.div>
          )
        })}
      </AnimatePresence>
      {shown.length === 0 && <div className="muted small" style={{ padding: '6px 2px' }}>正在准备任务，完成的步骤会显示在这里。</div>}
    </div>
  )
}
