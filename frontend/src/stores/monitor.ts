import { defineStore } from 'pinia'
import { listRuns, triggerRun } from '../api/client'
import type { RunOut } from '../api/types'

// 任务执行状态（runs 列表 + 轮询）
export const useMonitorStore = defineStore('monitor', {
  state: () => ({
    runs: [] as RunOut[],
    loading: false,
    triggering: false,
    busy: false,
  }),
  getters: {
    hasRunning: (s) => s.runs.some((r) => r.status === 'running'),
  },
  actions: {
    async fetchRuns() {
      this.loading = true
      try {
        this.runs = await listRuns()
        this.busy = this.hasRunning
      } finally {
        this.loading = false
      }
    },
    async trigger() {
      this.triggering = true
      try {
        const run = await triggerRun()
        this.runs.unshift(run)
        this.busy = true
        return run
      } finally {
        this.triggering = false
      }
    },
  },
})
