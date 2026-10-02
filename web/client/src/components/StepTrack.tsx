export interface Step { key: string; label: string; status: 'done' | 'active' | 'todo' | 'failed' }

/** 通用阶段轨道：done ✓ / active 旋转呼吸 / failed ✗ / todo 暗 */
export default function StepTrack({ steps, size = 'md' }: { steps: Step[]; size?: 'sm' | 'md' }) {
  return (
    <div className={`ritual-track ${size === 'sm' ? 'track-sm' : ''}`}>
      {steps.map((s) => (
        <div key={s.key} className={`ritual-node ${s.status}`}>
          {s.label}
        </div>
      ))}
    </div>
  )
}
