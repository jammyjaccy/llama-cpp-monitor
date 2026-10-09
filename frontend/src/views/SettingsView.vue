<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useSettingsStore } from '../stores/settings'

const settings = useSettingsStore()

// 表单本地副本，保存时整体提交
const form = reactive({
  interval_minutes: 120,
  baseline_tag: '',
  model_base_url: '',
  model_api_key: '',
  model_name: '',
  proxy: '',
  launch_command: '',
})
const saving = ref(false)

function fill() {
  const s = settings.settings
  if (!s) return
  form.interval_minutes = s.interval_minutes
  form.baseline_tag = s.baseline_tag
  form.model_base_url = s.model_base_url
  form.model_api_key = s.model_api_key
  form.model_name = s.model_name
  form.proxy = s.proxy
  form.launch_command = s.launch_command
}

async function onSave() {
  saving.value = true
  try {
    await settings.save({ ...form })
    ElMessage.success('配置已保存')
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(detail || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await settings.fetch()
  fill()
})
</script>

<template>
  <el-card shadow="never">
    <el-form label-width="120px" label-position="top">
      <el-form-item label="任务间隔（分钟）">
        <el-input-number v-model="form.interval_minutes" :min="1" :max="1440" :step="10" />
      </el-form-item>

      <el-form-item label="基线版本">
        <el-input v-model="form.baseline_tag" placeholder="b11514" />
      </el-form-item>

      <el-divider>模型配置</el-divider>

      <el-form-item label="模型 base_url">
        <el-input v-model="form.model_base_url" placeholder="http://localhost:4000" />
      </el-form-item>

      <el-form-item label="模型 API Key">
        <el-input v-model="form.model_api_key" type="password" show-password placeholder="API Key" />
      </el-form-item>

      <el-form-item label="模型名">
        <el-input v-model="form.model_name" placeholder="Swift-Qwen3.8-27B" />
      </el-form-item>

      <el-divider>网络与启动命令</el-divider>

      <el-form-item label="代理地址">
        <el-input v-model="form.proxy" placeholder="http://127.0.0.1:7981" />
      </el-form-item>

      <el-form-item label="启动命令">
        <el-input
          v-model="form.launch_command"
          type="textarea"
          :rows="6"
          placeholder="llama-server.exe 启动命令"
        />
      </el-form-item>

      <el-form-item>
        <el-button type="primary" :loading="saving" @click="onSave">保存配置</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>
