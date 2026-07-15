<template>
  <div id="app-root">
    <nav class="nav-bar">
      <router-link to="/dashboard" class="nav-btn" :class="{ active: $route.path === '/dashboard' }">温室监控台</router-link>
      <router-link to="/maturity" class="nav-btn" :class="{ active: $route.path === '/maturity' }">草莓成熟度检测</router-link>
      <router-link to="/datasets" class="nav-btn" :class="{ active: $route.path === '/datasets' }">成熟度数据集管理</router-link>
    </nav>
    <router-view />
  </div>
</template>

<script>
export default { name: 'App' }
</script>

<style>
#app-root {
  min-height: 100vh;
}

.nav-bar {
  display: flex;
  gap: 8px;
  padding: 12px 24px;
  background: rgba(7, 18, 32, 0.92);
  border-bottom: 1px solid rgba(140, 194, 255, 0.14);
  position: sticky;
  top: 0;
  z-index: 100;
  backdrop-filter: blur(12px);
}

.nav-btn {
  padding: 8px 18px;
  border-radius: 999px;
  text-decoration: none;
  color: #a7c7e5;
  font-size: 0.9rem;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition: all 0.2s ease;
}

.nav-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #eef8ff;
}

.nav-btn.active {
  background: rgba(80, 177, 255, 0.2);
  color: #a6deff;
  border-color: rgba(80, 177, 255, 0.35);
}
</style>
