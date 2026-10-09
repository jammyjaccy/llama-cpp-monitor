import { defineStore } from 'pinia'
import { getSettings, updateSettings } from '../api/client'
import type { SettingsOut, SettingsUpdate } from '../api/types'

// 配置状态（任务间隔在任务页与配置页共用）
export const useSettingsStore = defineStore('settings', {
  state: () => ({
    settings: null as SettingsOut | null,
    loading: false,
  }),
  actions: {
    async fetch() {
      this.loading = true
      try {
        this.settings = await getSettings()
      } finally {
        this.loading = false
      }
    },
    async save(update: SettingsUpdate) {
      this.settings = await updateSettings(update)
      return this.settings
    },
  },
})
