<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { listReports, reportsTotal, reportDetail } from '../api/client'
import type { VersionDetailOut, VersionOut } from '../api/types'

const route = useRoute()
const router = useRouter()
const tag = computed(() => route.params.tag as string | undefined)

// 列表状态
const rows = ref<VersionOut[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loadingList = ref(false)

// 详情状态
const detail = ref<VersionDetailOut | null>(null)
const loadingDetail = ref(false)

async function loadList() {
  loadingList.value = true
  try {
    const [items, t] = await Promise.all([listReports(page.value, pageSize.value), reportsTotal()])
    rows.value = items
    total.value = t
  } catch {
    ElMessage.error('加载报告列表失败')
  } finally {
    loadingList.value = false
  }
}

async function loadDetail() {
  if (!tag.value) return
  loadingDetail.value = true
  try {
    detail.value = await reportDetail(tag.value)
  } catch {
    ElMessage.error('加载报告详情失败')
    detail.value = null
  } finally {
    loadingDetail.value = false
  }
}

function goList() {
  router.replace({ name: 'reports' })
}

function openDetail(row: VersionOut) {
  router.push({ name: 'report-detail', params: { tag: row.tag } })
}

function onPageChange(p: number) {
  page.value = p
  loadList()
}

const analyzedTag = (v: VersionOut) =>
  v.analyzed ? '已分析' : '待分析'
const analyzedType = (v: VersionOut) => (v.analyzed ? 'success' : 'warning')
const diffTag = (v: VersionOut) => (v.help_diffed ? '已 diff' : '未完成')
const diffType = (v: VersionOut) => (v.help_diffed ? 'success' : 'info')

watch(tag, (t) => (t ? loadDetail() : (detail.value = null)), { immediate: true })

onMounted(loadList)
</script>

<template>
  <!-- 详情视图 -->
  <div v-if="tag" v-loading="loadingDetail">
    <el-page-header @back="goList" class="detail-header">
      <template #content>
        <span class="detail-title">报告 {{ tag }}</span>
      </template>
    </el-page-header>

    <div v-if="detail">
      <el-descriptions :column="4" border class="meta">
        <el-descriptions-item label="发布">{{ detail.published_at ?? '—' }}</el-descriptions-item>
        <el-descriptions-item label="commit 数">{{ detail.commit_count ?? '—' }}</el-descriptions-item>
        <el-descriptions-item label="分析状态">
          <el-tag :type="analyzedType(detail)">{{ analyzedTag(detail) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="help diff">
          <el-tag :type="diffType(detail)">{{ diffTag(detail) }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <el-card shadow="never" class="section">
        <template #header>正提升条目</template>
        <el-empty v-if="!detail.positive_items.length" description="无" :image-size="60" />
        <ul v-else class="list">
          <li v-for="(p, i) in detail.positive_items" :key="i">
            <strong>{{ p.item }}</strong>
            <div v-if="p.reason" class="reason">{{ p.reason }}</div>
          </li>
        </ul>
      </el-card>

      <el-card shadow="never" class="section">
        <template #header>启动命令影响</template>
        <pre v-if="detail.launch_impact && Object.keys(detail.launch_impact).length" class="json">{{ JSON.stringify(detail.launch_impact, null, 2) }}</pre>
        <el-empty v-else description="无" :image-size="60" />
      </el-card>

      <el-card shadow="never" class="section">
        <template #header>建议加上的 flag</template>
        <el-empty v-if="!detail.suggested_flags.length" description="无" :image-size="60" />
        <ul v-else class="list">
          <li v-for="(f, i) in detail.suggested_flags" :key="i">
            <code>{{ f.flag }}</code>
            <span v-if="f.reason" class="reason">{{ f.reason }}</span>
          </li>
        </ul>
      </el-card>

      <el-card shadow="never" class="section">
        <template #header>新增命令</template>
        <el-empty v-if="!detail.new_commands.length" description="无" :image-size="60" />
        <el-table v-else :data="detail.new_commands" size="small">
          <el-table-column prop="flag" label="flag" min-width="160">
            <template #default="{ row }"><code>--{{ row.flag }}</code></template>
          </el-table-column>
          <el-table-column prop="source" label="来源" width="120" />
          <el-table-column prop="description" label="说明" min-width="240">
            <template #default="{ row }">{{ row.description ?? '—' }}</template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never" class="section">
        <template #header>原始 commit 列表（{{ detail.commits_raw.length }}）</template>
        <el-empty v-if="!detail.commits_raw.length" description="无" :image-size="60" />
        <ul v-else class="commits">
          <li v-for="c in detail.commits_raw" :key="c.sha">
            <code class="sha">{{ c.sha?.slice(0, 8) }}</code>
            <span>{{ c.commit?.message }}</span>
          </li>
        </ul>
      </el-card>
    </div>
  </div>

  <!-- 列表视图 -->
  <div v-else>
    <el-table :data="rows" v-loading="loadingList" stripe @row-click="openDetail" class="clickable">
      <el-table-column prop="tag" label="版本" width="120" />
      <el-table-column prop="published_at" label="发布时间" width="180">
        <template #default="{ row }">{{ row.published_at ?? '—' }}</template>
      </el-table-column>
      <el-table-column prop="commit_count" label="commit 数" width="100">
        <template #default="{ row }">{{ row.commit_count ?? '—' }}</template>
      </el-table-column>
      <el-table-column label="分析" width="100">
        <template #default="{ row }">
          <el-tag :type="analyzedType(row)">{{ analyzedTag(row) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="help diff" width="110">
        <template #default="{ row }">
          <el-tag :type="diffType(row)">{{ diffTag(row) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="正提升" min-width="160">
        <template #default="{ row }">
          <span v-if="row.positive_items.length">{{ row.positive_items.length }} 条</span>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pager"
      background
      layout="total, prev, pager, next, sizes"
      :total="total"
      :current-page="page"
      :page-size="pageSize"
      :page-sizes="[10, 20, 50, 100]"
      @current-change="onPageChange"
      @size-change="(s: number) => { pageSize = s; page = 1; loadList() }"
    />
  </div>
</template>

<style scoped>
.detail-header {
  margin-bottom: 16px;
}
.detail-title {
  font-size: 16px;
  font-weight: 600;
}
.meta {
  margin-bottom: 16px;
}
.section {
  margin-bottom: 16px;
}
.list {
  margin: 0;
  padding-left: 18px;
}
.list li {
  margin-bottom: 8px;
}
.reason {
  color: #909399;
  font-size: 13px;
}
.json {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  background: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
}
.commits {
  margin: 0;
  padding-left: 0;
  list-style: none;
}
.commits li {
  padding: 4px 0;
  border-bottom: 1px solid #f0f2f5;
}
.sha {
  color: #409eff;
  margin-right: 8px;
}
.clickable {
  cursor: pointer;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
.muted {
  color: #c0c4cc;
}
</style>
