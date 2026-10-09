import { createRouter, createWebHashHistory } from 'vue-router'
import TasksView from '../views/TasksView.vue'
import ReportsView from '../views/ReportsView.vue'
import SettingsView from '../views/SettingsView.vue'

// hash 模式：静态托管下无需服务端路由回退
const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/tasks' },
    { path: '/tasks', name: 'tasks', component: TasksView },
    { path: '/reports', name: 'reports', component: ReportsView },
    { path: '/reports/:tag', name: 'report-detail', component: ReportsView, props: true },
    { path: '/settings', name: 'settings', component: SettingsView },
  ],
})

export default router
