<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<template>
  <el-container class="layout">
    <el-header class="header">
      <div class="brand">llama-cpp-monitor</div>
      <el-menu
        mode="horizontal"
        :default-active="route.path"
        router
        class="nav"
        background-color="transparent"
        text-color="#999"
        active-text-color="#409eff"
      >
        <el-menu-item index="/tasks">任务执行</el-menu-item>
        <el-menu-item index="/reports">报告</el-menu-item>
        <el-menu-item index="/settings">配置</el-menu-item>
      </el-menu>
    </el-header>
    <el-main class="main">
      <router-view />
    </el-main>
  </el-container>
</template>

<style scoped>
.layout {
  min-height: 100vh;
}
.header {
  display: flex;
  align-items: center;
  gap: 24px;
  border-bottom: 1px solid #ebeef5;
}
.brand {
  font-weight: 600;
  font-size: 16px;
  white-space: nowrap;
}
.nav {
  flex: 1;
  border-bottom: none;
}
.main {
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
}
</style>
