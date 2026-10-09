import axios from 'axios'
import type {
  RunOut,
  SettingsOut,
  SettingsUpdate,
  VersionDetailOut,
  VersionOut,
} from './types'

const http = axios.create({ baseURL: '/api', timeout: 30000 })

export async function listRuns(limit = 50): Promise<RunOut[]> {
  const { data } = await http.get<RunOut[]>('/runs', { params: { limit } })
  return data
}

export async function triggerRun(): Promise<RunOut> {
  const { data } = await http.post<RunOut>('/runs/trigger')
  return data
}

export async function listReports(page: number, pageSize: number): Promise<VersionOut[]> {
  const { data } = await http.get<VersionOut[]>('/reports', {
    params: { page, page_size: pageSize },
  })
  return data
}

export async function reportsTotal(): Promise<number> {
  const { data } = await http.get<{ total: number }>('/reports/total')
  return data.total
}

export async function reportDetail(tag: string): Promise<VersionDetailOut> {
  const { data } = await http.get<VersionDetailOut>(`/reports/${tag}`)
  return data
}

export async function getSettings(): Promise<SettingsOut> {
  const { data } = await http.get<SettingsOut>('/settings')
  return data
}

export async function updateSettings(update: SettingsUpdate): Promise<SettingsOut> {
  const { data } = await http.put<SettingsOut>('/settings', update)
  return data
}
