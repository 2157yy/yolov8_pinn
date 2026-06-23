import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import Dashboard from './views/Dashboard.vue'
import Maturity from './views/Maturity.vue'

const routes = [
  { path: '/dashboard', component: Dashboard },
  { path: '/maturity', component: Maturity },
  { path: '/', redirect: '/dashboard' },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

const app = createApp({ template: '<router-view />' })
app.use(router)

app.config.errorHandler = (error) => {
  console.error('Vue application error:', error)
}

app.mount('#app')

document.addEventListener('keydown', (event) => {
  if (event.key !== 'F1') return

  event.preventDefault()
  window.alert(
    [
      '智能温室大棚监控系统快捷键说明：',
      'F1 - 显示帮助',
      'F5 - 刷新数据',
      'Ctrl+R - 刷新数据',
      'Ctrl+H - 显示或隐藏历史记录',
      'Esc - 退出全屏模式'
    ].join('\n')
  )
})
