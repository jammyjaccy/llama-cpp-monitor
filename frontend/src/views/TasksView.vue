<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useMonitorStore } from '../stores/monitor'
import { useSettingsStore } from '../stores/settings'
import { formatLocalTime } from '../utils/format'

const monitor = useMonitorStore()
const settings = useSettingsStore()

// 顶部「立即执行」+ 间隔设置
const interval = ref<number>(120)
const savingInterval = ref(false)

const statusType = (s: string) =>
  ({ running: 'primary', ok: 'success', partial: 'warning', failed: 'danger' } as Record<string, 'primary' | 'success' | 'warning' | 'danger'>)[s] ?? 'info'

const triggerLabel = (t: string) => (t === 'manual' ? '手动' : '定时')

async function onTrigger() {
  try {
    await monitor.trigger()
    ElMessage.success('已触发任务执行')
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(detail || '触发失败')
  }
}

async function saveInterval() {
  if (!Number.isInteger(interval.value) || interval.value < 1) {
    ElMessage.warning('间隔需为不小于 1 的整数（分钟）')
    return
  }
  savingInterval.value = true
  try {
    await settings.save({ interval_minutes: interval.value })
    ElMessage.success('任务间隔已更新')
  } catch {
    ElMessage.error('更新失败')
  } finally {
    savingInterval.value = false
  }
}

// 有任务在跑时轮询刷新
let timer: ReturnType<typeof setInterval> | null = null

async function refresh() {
  await monitor.fetchRuns()
  if (monitor.busy) {
    if (!timer) timer = setInterval(refresh, 5000)
  } else if (timer) {
    clearInterval(timer)
    timer = null
  }
}

onMounted(async () => {
  await Promise.all([monitor.fetchRuns(), settings.fetch()])
  interval.value = settings.settings?.interval_minutes ?? 120
  if (monitor.busy) await refresh()
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div>
    <div class="toolbar">
      <el-button type="primary" :loading="monitor.triggering" :disabled="monitor.busy" @click="onTrigger">
        立即执行
      </el-button>
      <div class="interval-box">
        <span>任务间隔</span>
        <el-input-number v-model="interval" :min="1" :max="1440" :step="10" size="default" />
        <span>分钟</span>
        <el-button size="default" :loading="savingInterval" @click="saveInterval">保存</el-button>
      </div>
    </div>

    <el-table :data="monitor.runs" v-loading="monitor.loading" stripe>
      <el-table-column prop="id" label="#" width="60" />
      <el-table-column prop="started_at" label="开始时间" width="170">
        <template #default="{ row }">{{ formatLocalTime(row.started_at) }}</template>
      </el-table-column>
      <el-table-column prop="ended_at" label="结束时间" width="170">
        <template #default="{ row }">{{ formatLocalTime(row.ended_at) }}</template>
      </el-table-column>
      <el-table-column label="触发方式" width="100">
        <template #default="{ row }">{{ triggerLabel(row.trigger) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="处理版本" min-width="200">
        <template #default="{ row }">
          <span v-if="row.versions_processed.length">{{ row.versions_processed.join(', ') }}</span>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="错误" min-width="200">
        <template #default="{ row }">
          <span v-if="row.error" class="error-text">{{ row.error }}</span>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-bottom: 16px;
}
.interval-box {
  display: flex;
  align-items: center;
  gap: 8px;
}
.muted {
  color: #c0c4cc;
}
.error-text {
  color: #f56c6c;
}
</style>
