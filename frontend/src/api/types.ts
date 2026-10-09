// 与后端 REST API 响应对应的类型（ADR-0001：前端仅通过 REST 通信）

export interface RunOut {
  id: number
  started_at: string | null
  ended_at: string | null
  trigger: 'scheduled' | 'manual' | string
  status: 'running' | 'ok' | 'partial' | 'failed' | string
  versions_processed: string[]
  error: string | null
}

export interface NewCommandOut {
  id: number
  tag: string
  flag: string
  source: 'text' | 'help-diff' | string
  description: string | null
}

export interface VersionOut {
  id: number
  tag: string
  published_at: string | null
  commit_count: number | null
  positive_items: PositiveItem[]
  launch_impact: Record<string, unknown>
  suggested_flags: SuggestedFlag[]
  help_diffed: number
  analyzed: number
  created_at: string | null
}

export interface VersionDetailOut extends VersionOut {
  commits_raw: Commit[]
  new_commands: NewCommandOut[]
}

export interface PositiveItem {
  item: string
  reason: string
  [key: string]: unknown
}

export interface SuggestedFlag {
  flag: string
  reason?: string
  [key: string]: unknown
}

export interface Commit {
  sha: string
  // GitHub compare：消息在嵌套层 commit.message
  commit?: { message?: string; author?: { name?: string; date?: string } }
  [key: string]: unknown
}

export interface SettingsOut {
  interval_minutes: number
  baseline_tag: string
  model_base_url: string
  model_api_key: string
  model_name: string
  proxy: string
  launch_command: string
}

export type SettingsUpdate = Partial<SettingsOut>
