/* 与 server 返回结构一一对应的类型定义（ARC v2 数据模型） */

export interface User { username: string; is_admin: boolean }

export interface Health {
  scholartrace: boolean
  scholaranalysis: boolean
  webresearch: boolean
  running_jobs: number
  max_jobs: number
}

/* ---------------- ARC v2 领域模型 ---------------- */

/** 一次灵感（IdeaSeed）：发现链的最小想法单位 */
export interface IdeaSeed {
  title: string
  question: string
  insight: string
  why_it_matters: string
  difference_from_known: string
  source_ids: string[]
  key_unknown: string
}

/** 抽卡时的快速判定（submit / skip / stop） */
export interface SketchResult {
  action: 'submit' | 'skip' | 'stop'
  seed: IdeaSeed | null
  reason: string
  next_search?: string | null
}

/** 价值分诊（investigate / park / drop） */
export interface TriageResult {
  action: 'investigate' | 'park' | 'drop'
  reason: string
  strongest_objection: string
  check_questions: string[]
}

export interface NearestWork {
  source_id: string
  already_established: string
  remaining_difference: string
  uncertainty?: string
}

export interface ResourceHint {
  gpu_type: string | null
  gpu_count: number | null
  training_hours_estimate: string | null
  inference_hours_estimate: string | null
  basis: string
}

/** 定向预研后的结论卡（discuss / lead / drop） */
export interface IdeaNote {
  seed: IdeaSeed
  decision: 'discuss' | 'lead' | 'drop'
  reason: string
  nearest_work: NearestWork[]
  feasibility: string
  resources: ResourceHint
  main_risk: string
  next_question: string
  source_notes: { source_id: string; finding: string; relevance: string; access: string; limits?: string }[]
  limits: string[]
  changes_from_seed: string[]
}

/** 收藏馆/详情页里的灵感卡（来自 SQLite discovery_ideas） */
export interface DiscoveryCard {
  presentation?: { presentation_title: string; text: string } | null
  idea_id: string
  draw_id: string | null
  /** pending / park / drop / checked */
  status: string
  topic: string | null
  seed: IdeaSeed | null
  sketch: SketchResult | null
  triage: TriageResult | null
  note: IdeaNote | null
  idea_md: string | null
}

export interface RunMeta {
  arc_status?: string | null
  interrupted?: boolean
  run_id: string | null
  status: string | null
  stop_reason: string | null
  assessment: string | null
  card_id: string | null
  card_version: number | null
  rounds_completed: number | null
  created_at: string | null
  updated_at: string | null
}

export interface CostSummary {
  total_cost_complete?: boolean
  unknown_calls?: number | null
  unmetered_calls?: number | null
  cost_scope?: string
  limit_cny?: number
  spent_lower_cny?: number
  spent_upper_cny?: number
  reserved_cny?: number
  remaining_cny?: number
  call_count?: number
}

export interface DiscoveryUsage {
  semantic_tasks: number
  model_requests: number
  tool_actions: number
  input_tokens: number
  completion_tokens: number
  first_seed_at?: string
  first_note_at?: string
}

export interface RunFileEntry { name: string; size: number }

/* ---------------- run 详情（三模式） ---------------- */

export interface PauseRecovery {
  kind: 'budget' | 'retry' | 'defer' | 'evidence' | 'resume'
  action: 'resume' | 'retry-task' | 'defer-evidence'
  actionable: boolean
  task_key?: string | null
  reason?: string | null
}

export interface PauseDiagnostics {
  task_id: string | null
  task_status: string | null
  stop_reason: string | null
  errors: string[]
  evidence_requests: { question: string; source_ids: string[] }[]
  truncated: boolean
  details_available: boolean
  recovery_error?: string
}

export interface DiscoverDetail {
  presentation?: { revised_at: string; label: string } | null
  mode: 'discover'
  dir: string
  pause_recovery?: PauseRecovery | null
  pause_diagnostics?: PauseDiagnostics | null
  run: RunMeta
  topic: string
  cards: DiscoveryCard[]
  usage: DiscoveryUsage | null
  files: RunFileEntry[]
  cost: CostSummary | null
}

export interface StageDoc {
  kind: 'card' | 'idea' | 'technical'
  file: string
  size: number
  /** card 链 */
  card_id?: string
  version?: number
  /** idea 链 */
  idea_id?: string
}

/** develop 与 debate(ARC run)共用结构 */
export interface StageDetail {
  presentation?: { revised_at: string; label: string } | null
  mode: 'develop' | 'debate'
  dir: string
  pause_recovery?: PauseRecovery | null
  pause_diagnostics?: PauseDiagnostics | null
  run: RunMeta
  topic: string
  docs: StageDoc[]
  input_idea: Record<string, unknown> | null
  files: RunFileEntry[]
  cost: CostSummary | null
}

export type RunDetail = DiscoverDetail | StageDetail

export interface RunSummary {
  dir: string
  mode: 'discover' | 'develop' | 'debate'
  status: string
  stop_reason: string | null
  assessment: string | null
  topic: string
  created_at: string | null
  mtime: number
  cost: CostSummary | null
}

/* ---------------- 任务进度 ---------------- */

export interface BudgetProgress {
  total_cost_complete?: boolean
  unmetered_calls?: number | null
  cost_scope?: string
  limit_cny: number | null
  spent_lower_cny: number | null
  spent_upper_cny: number | null
  reserved_cny: number | null
  remaining_cny: number | null
  call_count: number | null
  unknown_calls: number | null
}

export interface TaskProgress {
  task_id: string
  status: string
  handoff?: 'candidate_prestudy'
  research_verified?: false
}

export interface JobProgress {
  arc_status?: string | null
  interrupted?: boolean
  run_id?: string
  status?: string
  stop_reason?: string | null
  assessment?: string | null
  rounds_completed?: number | null
  card_id?: string | null
  card_version?: number | null
  draws?: { started: number | null; max: number | null } | null
  budget?: BudgetProgress | null
  tasks?: TaskProgress[]
  current?: string
}

export interface JobStatus {
  job: {
    id: string
    mode: string
    params: Record<string, unknown>
    username: string
    status: 'running' | 'completed' | 'failed' | 'cancelled' | 'paused'
    run_dir: string | null
    error: string | null
    created_at: string
    finished_at: string | null
  }
  progress: JobProgress | null
  log_tail: string
}

export interface JobListItem {
  id: string
  mode: string
  username: string
  status: string
  run_dir: string | null
  created_at: string
  finished_at: string | null
  params: Record<string, unknown>
}
