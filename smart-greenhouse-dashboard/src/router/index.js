import { createRouter, createWebHashHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import DatasetManager from '../views/DatasetManager.vue'
import Maturity from '../views/Maturity.vue'

const routes = [
  { path: '/dashboard', name: 'Dashboard', component: Dashboard },
  { path: '/datasets', name: 'DatasetManager', component: DatasetManager },
  { path: '/maturity', name: 'Maturity', component: Maturity },
  { path: '/', redirect: '/dashboard' },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
