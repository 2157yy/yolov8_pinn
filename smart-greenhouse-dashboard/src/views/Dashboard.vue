<template>
  <div class="dashboard-container">
    <!-- 顶部导航栏 -->
    <div class="dashboard-header">
      <div class="header-left">
        <div class="logo">
          <span class="logo-icon">🌿</span>
          <span class="logo-text">智能温室大棚监控系统</span>
        </div>
        <div class="system-status">
          <span class="status-dot" :class="{ active: systemOnline }"></span>
          <span class="status-text">{{ systemOnline ? '系统在线' : '系统离线' }}</span>
        </div>
      </div>
      
      <div class="header-right">
        <div class="time-display">
          <span class="time-icon">🕒</span>
          <span class="time-text">{{ currentTime }}</span>
        </div>
        <div class="server-info">
          <span class="server-icon">📡</span>
          <span class="server-text">{{ serverIp }}</span>
        </div>
        <button class="refresh-btn" @click="refreshData" :disabled="refreshing">
          {{ refreshing ? '刷新中...' : '🔄 刷新数据' }}
        </button>
      </div>
    </div>
    
    <!-- 主要内容区 -->
    <div class="dashboard-main" ref="mainContent">
      <!-- 第一行：关键指标 -->
      <div class="metrics-row">
        <div 
          v-for="metric in metrics" 
          :key="metric.id"
          class="metric-card" 
          :class="metric.type"
          @click="showMetricDetail(metric)"
        >
          <div class="metric-icon">{{ metric.icon }}</div>
          <div class="metric-label">{{ metric.label }}</div>
          <div class="metric-value">{{ metric.value }}</div>
          <div class="metric-range">{{ metric.range }}</div>
          <div class="metric-trend">
            <span class="trend-icon">{{ metric.trendIcon }}</span>
            <span class="trend-text">{{ metric.trendText }}</span>
          </div>
        </div>
      </div>
      
      <!-- 第二行：图表和控件 -->
      <div class="charts-row">
        <div class="chart-container large">
          <div class="chart-header">
            <h3>📈 温度趋势 (24小时)</h3>
            <div class="chart-actions">
              <button 
                v-for="period in chartPeriods" 
                :key="period"
                class="btn-chart" 
                :class="{ active: selectedPeriod === period }"
                @click="changeChartPeriod(period)"
              >
                {{ period }}
              </button>
            </div>
          </div>
          <div class="chart-placeholder" v-if="!chartDataLoaded">
            <div class="loading-chart">
              <div class="spinner"></div>
              <div>加载图表数据...</div>
            </div>
          </div>
          <div class="chart-real" v-else>
            <!-- 这里可以放置真实的图表，比如使用ECharts -->
            <div class="chart-mock">
              <div 
                v-for="(point, index) in temperatureData" 
                :key="index"
                class="chart-line" 
                :style="getLineStyle(point)"
              ></div>
            </div>
          </div>
        </div>
        
        <div class="chart-container">
          <div class="chart-header">
            <h3>🌡️ 实时温度分布</h3>
          </div>
          <div class="gauge-container">
            <div class="gauge-circle" :style="getGaugeStyle()">
              <div class="gauge-value">{{ currentTemperature }}°C</div>
              <div class="gauge-label">当前温度</div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 第三行：控制和警报 -->
      <div class="controls-row">
        <div class="control-panel">
          <h3>🎛️ 设备控制</h3>
          <div class="control-grid">
            <div 
              v-for="device in devices" 
              :key="device.id"
              class="control-item"
              :class="{ disabled: device.disabled }"
            >
              <div class="control-label">{{ device.name }}</div>
              <div class="control-switch">
                <label class="switch">
                  <input 
                    type="checkbox" 
                    :checked="device.status"
                    :disabled="device.disabled"
                    @change="toggleDevice(device)"
                  >
                  <span class="slider"></span>
                </label>
                <div class="control-status">{{ device.status ? '运行中' : '已关闭' }}</div>
              </div>
              <button 
                v-if="device.hasManual"
                class="btn-manual"
                @click="manualControl(device)"
                :disabled="device.disabled"
              >
                手动调节
              </button>
            </div>
          </div>
        </div>
        
        <div class="alarm-panel">
          <div class="panel-header">
            <h3>🚨 警报通知</h3>
            <button 
              class="btn-clear-alarms" 
              @click="clearAlarms"
              :disabled="alarms.length === 0"
            >
              清空警报
            </button>
          </div>
          <div class="alarm-list" ref="alarmList">
            <div 
              v-for="alarm in alarms" 
              :key="alarm.id"
              class="alarm-item" 
              :class="alarm.type"
              @click="handleAlarmClick(alarm)"
            >
              <div class="alarm-icon">{{ getAlarmIcon(alarm.type) }}</div>
              <div class="alarm-content">
                <div class="alarm-title">{{ alarm.title }}</div>
                <div class="alarm-desc">{{ alarm.description }}</div>
                <div class="alarm-time">{{ formatTime(alarm.time) }}</div>
              </div>
              <button 
                class="btn-acknowledge"
                @click.stop="acknowledgeAlarm(alarm)"
              >
                确认
              </button>
            </div>
            <div v-if="alarms.length === 0" class="no-alarms">
              <div class="no-alarms-icon">✅</div>
              <div class="no-alarms-text">一切正常，暂无警报</div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 第四行：历史数据 -->
      <div class="history-panel" v-if="showHistory">
        <div class="panel-header">
          <h3>📋 历史数据记录</h3>
          <button class="btn-close-history" @click="toggleHistory">收起</button>
        </div>
        <div class="history-table">
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>温度 (°C)</th>
                <th>湿度 (%)</th>
                <th>光照 (LUX)</th>
                <th>CO₂ (PPM)</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="record in historyRecords" :key="record.id">
                <td>{{ record.time }}</td>
                <td :class="getTempClass(record.temperature)">{{ record.temperature }}</td>
                <td :class="getHumidityClass(record.humidity)">{{ record.humidity }}</td>
                <td :class="getLightClass(record.light)">{{ record.light }}</td>
                <td :class="getCO2Class(record.co2)">{{ record.co2 }}</td>
                <td>
                  <span class="status-badge" :class="record.status">
                    {{ record.status === 'normal' ? '正常' : '异常' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      
      <!-- 底部操作栏 -->
      <div class="action-bar">
        <button class="btn-action" @click="toggleHistory">
          {{ showHistory ? '隐藏历史记录' : '显示历史记录' }}
        </button>
        <button class="btn-action" @click="exportData">
          📥 导出数据
        </button>
        <button class="btn-action" @click="showSettings">
          ⚙️ 系统设置
        </button>
        <button class="btn-action" @click="fullScreen">
          🖥️ 全屏显示
        </button>
      </div>
    </div>
    
    <!-- 设置对话框 -->
    <div v-if="showSettingsDialog" class="settings-dialog">
      <div class="dialog-content">
        <div class="dialog-header">
          <h3>系统设置</h3>
          <button class="btn-close" @click="showSettingsDialog = false">×</button>
        </div>
        <div class="dialog-body">
          <!-- 设置内容 -->
          <div class="setting-item">
            <label>数据刷新间隔 (秒):</label>
            <input 
              type="number" 
              v-model.number="refreshInterval" 
              min="5" 
              max="300"
            >
          </div>
          <div class="setting-item">
            <label>温度警报阈值 (°C):</label>
            <div class="range-input">
              <span>最低: </span>
              <input type="number" v-model.number="tempThreshold.min" min="0" max="50">
              <span>最高: </span>
              <input type="number" v-model.number="tempThreshold.max" min="0" max="50">
            </div>
          </div>
          <div class="setting-item">
            <label>启用声音警报:</label>
            <label class="switch">
              <input type="checkbox" v-model="enableSoundAlarm">
              <span class="slider"></span>
            </label>
          </div>
        </div>
        <div class="dialog-footer">
          <button class="btn-cancel" @click="showSettingsDialog = false">取消</button>
          <button class="btn-save" @click="saveSettings">保存设置</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
// 引入API模块（稍后创建）
// import api from '@/api/greenhouse';

export default {
  name: 'Dashboard',
  data() {
    return {
      // 系统状态
      systemOnline: true,
      currentTime: '',
      serverIp: '192.168.211.70:8081',
      refreshing: false,
      
      // 指标数据
      metrics: [
        {
          id: 1,
          type: 'temperature',
          icon: '🌡️',
          label: '温度',
          value: '25.3°C',
          range: '适宜范围: 20-30°C',
          trendIcon: '↗',
          trendText: '+0.5°C'
        },
        {
          id: 2,
          type: 'humidity',
          icon: '💧',
          label: '湿度',
          value: '68%',
          range: '适宜范围: 60-80%',
          trendIcon: '→',
          trendText: '稳定'
        },
        {
          id: 3,
          type: 'light',
          icon: '💡',
          label: '光照强度',
          value: '850 LUX',
          range: '适宜范围: 800-1200 LUX',
          trendIcon: '↘',
          trendText: '-50 LUX'
        },
        {
          id: 4,
          type: 'co2',
          icon: '🌫️',
          label: 'CO₂浓度',
          value: '420 PPM',
          range: '适宜范围: 400-600 PPM',
          trendIcon: '→',
          trendText: '正常'
        }
      ],
      
      // 图表数据
      selectedPeriod: '日',
      chartPeriods: ['时', '日', '周', '月'],
      chartDataLoaded: true,
      temperatureData: [65, 70, 75, 80, 85, 75, 70, 65, 60, 55, 50, 45],
      currentTemperature: 25.3,
      
      // 设备控制
      devices: [
        { id: 1, name: '通风系统', status: true, disabled: false, hasManual: true },
        { id: 2, name: '灌溉系统', status: false, disabled: false, hasManual: true },
        { id: 3, name: '补光系统', status: true, disabled: false, hasManual: false },
        { id: 4, name: '加湿系统', status: false, disabled: false, hasManual: true }
      ],
      
      // 警报系统
      alarms: [
        { 
          id: 1, 
          type: 'normal', 
          title: '温度正常', 
          description: '当前温度处于适宜范围内',
          time: new Date(Date.now() - 10 * 60000) // 10分钟前
        },
        { 
          id: 2, 
          type: 'warning', 
          title: '湿度偏低', 
          description: '湿度已低于设定阈值，建议开启加湿',
          time: new Date(Date.now() - 60 * 60000) // 1小时前
        }
      ],
      
      // 历史数据
      showHistory: false,
      historyRecords: [
        { id: 1, time: '10:30', temperature: 25.3, humidity: 68, light: 850, co2: 420, status: 'normal' },
        { id: 2, time: '10:15', temperature: 24.8, humidity: 65, light: 820, co2: 415, status: 'normal' },
        { id: 3, time: '10:00', temperature: 24.2, humidity: 62, light: 800, co2: 410, status: 'warning' },
        { id: 4, time: '09:45', temperature: 23.8, humidity: 60, light: 780, co2: 405, status: 'warning' },
        { id: 5, time: '09:30', temperature: 23.5, humidity: 58, light: 750, co2: 400, status: 'normal' }
      ],
      
      // 设置
      showSettingsDialog: false,
      refreshInterval: 30,
      tempThreshold: { min: 18, max: 32 },
      enableSoundAlarm: true,
      
      // 定时器
      updateTimer: null,
      dataRefreshTimer: null
    }
  },
  mounted() {
    this.updateTime()
    this.updateTimer = setInterval(this.updateTime, 1000)
    
    // 开始定时获取数据
    this.startDataRefresh()
    
    // 模拟实时数据更新
    this.simulateRealTimeData()
    
    console.log('📊 大屏组件加载完成，开始获取数据...')
    
    // 添加键盘快捷键
    this.setupKeyboardShortcuts()
  },
  beforeUnmount() {
    // 清理定时器
    if (this.updateTimer) clearInterval(this.updateTimer)
    if (this.dataRefreshTimer) clearInterval(this.dataRefreshTimer)
    
    // 移除事件监听
    document.removeEventListener('keydown', this.handleKeydown)
  },
  methods: {
    // 更新时间
    updateTime() {
      const now = new Date()
      this.currentTime = now.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      })
    },
    
    // 刷新数据
    refreshData() {
      this.refreshing = true
      console.log('🔄 正在刷新数据...')
      
      // 模拟API调用
      setTimeout(() => {
        // 这里替换为实际的API调用
        // api.getSensorData().then(data => {
        //   this.updateSensorData(data)
        // })
        
        // 模拟数据更新
        this.metrics.forEach(metric => {
          if (metric.type === 'temperature') {
            const newTemp = 24 + Math.random() * 3
            metric.value = `${newTemp.toFixed(1)}°C`
            this.currentTemperature = newTemp.toFixed(1)
          } else if (metric.type === 'humidity') {
            metric.value = `${Math.floor(60 + Math.random() * 15)}%`
          }
        })
        
        this.refreshing = false
        console.log('✅ 数据刷新完成')
      }, 1000)
    },
    
    // 开始定时刷新数据
    startDataRefresh() {
      this.dataRefreshTimer = setInterval(() => {
        if (this.systemOnline) {
          this.refreshData()
        }
      }, this.refreshInterval * 1000)
    },
    
    // 模拟实时数据
    simulateRealTimeData() {
      setInterval(() => {
        if (this.systemOnline) {
          // 随机更新一些数据
          const randomMetric = this.metrics[Math.floor(Math.random() * this.metrics.length)]
          if (randomMetric.type === 'temperature') {
            const change = (Math.random() - 0.5) * 0.2
            const current = parseFloat(this.currentTemperature)
            this.currentTemperature = (current + change).toFixed(1)
            randomMetric.value = `${this.currentTemperature}°C`
          }
        }
      }, 5000)
    },
    
    // 显示指标详情
    showMetricDetail(metric) {
      console.log(`查看${metric.label}详情:`, metric)
      alert(`${metric.label}: ${metric.value}\n${metric.range}\n趋势: ${metric.trendText}`)
    },
    
    // 切换图表周期
    changeChartPeriod(period) {
      this.selectedPeriod = period
      console.log(`切换到${period}视图`)
      
      // 这里应该根据周期重新加载图表数据
      // api.getChartData({ period }).then(data => {
      //   this.temperatureData = data
      // })
    },
    
    // 获取图表线条样式
    getLineStyle(value) {
      const height = (value / 100) * 80
      const opacity = value / 100
      return {
        height: `${height}%`,
        opacity: opacity
      }
    },
    
    // 获取仪表盘样式
    getGaugeStyle() {
      const temp = parseFloat(this.currentTemperature)
      let color = '#4caf50' // 绿色，正常
      
      if (temp < 20) color = '#2196f3' // 蓝色，偏低
      else if (temp > 30) color = '#f44336' // 红色，偏高
      
      return {
        background: `conic-gradient(${color} 0% ${(temp - 10) * 3.33}%, #eee ${(temp - 10) * 3.33}% 100%)`
      }
    },
    
    // 切换设备状态
    toggleDevice(device) {
      if (device.disabled) return
      
      console.log(`${device.status ? '关闭' : '开启'}${device.name}`)
      
      // 模拟API调用
      // api.controlDevice(device.id, !device.status).then(response => {
      //   device.status = !device.status
      // })
      
      device.status = !device.status
    },
    
    // 手动控制设备
    manualControl(device) {
      if (device.disabled) return
      
      const value = prompt(`请输入${device.name}的设置值:`, '50')
      if (value !== null) {
        console.log(`设置${device.name}为: ${value}`)
        alert(`已将${device.name}设置为: ${value}`)
      }
    },
    
    // 获取警报图标
    getAlarmIcon(type) {
      const icons = {
        normal: '✅',
        warning: '⚠️',
        error: '🚨'
      }
      return icons[type] || 'ℹ️'
    },
    
    // 格式化时间
    formatTime(date) {
      const now = new Date()
      const diff = now - date
      
      if (diff < 60000) return '刚刚'
      if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
      if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
      
      return date.toLocaleDateString('zh-CN')
    },
    
    // 处理警报点击
    handleAlarmClick(alarm) {
      console.log('查看警报详情:', alarm)
      alert(`警报: ${alarm.title}\n描述: ${alarm.description}\n时间: ${this.formatTime(alarm.time)}`)
    },
    
    // 确认警报
    acknowledgeAlarm(alarm) {
      console.log('确认警报:', alarm.id)
      this.alarms = this.alarms.filter(a => a.id !== alarm.id)
    },
    
    // 清空所有警报
    clearAlarms() {
      if (confirm('确定要清空所有警报吗？')) {
        this.alarms = []
      }
    },
    
    // 切换历史记录显示
    toggleHistory() {
      this.showHistory = !this.showHistory
      
      // 滚动到底部
      if (this.showHistory) {
        this.$nextTick(() => {
          const mainContent = this.$refs.mainContent
          mainContent.scrollTop = mainContent.scrollHeight
        })
      }
    },
    
    // 获取温度样式类
    getTempClass(temp) {
      if (temp < 20) return 'low'
      if (temp > 28) return 'high'
      return 'normal'
    },
    
    // 获取湿度样式类
    getHumidityClass(humidity) {
      if (humidity < 60) return 'low'
      if (humidity > 80) return 'high'
      return 'normal'
    },
    
    // 获取光照样式类
    getLightClass(light) {
      if (light < 800) return 'low'
      if (light > 1200) return 'high'
      return 'normal'
    },
    
    // 获取CO2样式类
    getCO2Class(co2) {
      if (co2 < 400) return 'low'
      if (co2 > 600) return 'high'
      return 'normal'
    },
    
    // 导出数据
    exportData() {
      console.log('导出数据...')
      alert('数据导出功能开发中...\n可以联系管理员导出历史数据。')
    },
    
    // 显示设置
    showSettings() {
      this.showSettingsDialog = true
    },
    
    // 保存设置
    saveSettings() {
      console.log('保存设置:', {
        refreshInterval: this.refreshInterval,
        tempThreshold: this.tempThreshold,
        enableSoundAlarm: this.enableSoundAlarm
      })
      
      // 重新设置定时器
      if (this.dataRefreshTimer) {
        clearInterval(this.dataRefreshTimer)
      }
      this.startDataRefresh()
      
      this.showSettingsDialog = false
      alert('设置已保存！')
    },
    
    // 全屏显示
    fullScreen() {
      const elem = document.documentElement
      if (!document.fullscreenElement) {
        if (elem.requestFullscreen) {
          elem.requestFullscreen()
        }
      } else {
        if (document.exitFullscreen) {
          document.exitFullscreen()
        }
      }
    },
    
    // 设置键盘快捷键
    setupKeyboardShortcuts() {
      document.addEventListener('keydown', this.handleKeydown)
    },
    
    // 处理键盘事件
    handleKeydown(event) {
      // F5刷新
      if (event.key === 'F5') {
        event.preventDefault()
        this.refreshData()
      }
      
      // ESC退出全屏
      if (event.key === 'Escape' && document.fullscreenElement) {
        document.exitFullscreen()
      }
      
      // Ctrl+H显示/隐藏历史
      if (event.ctrlKey && event.key === 'h') {
        event.preventDefault()
        this.toggleHistory()
      }
      
      // Ctrl+R刷新
      if (event.ctrlKey && event.key === 'r') {
        event.preventDefault()
        this.refreshData()
      }
    }
  }
}
</script>

<style scoped>
/* 基础样式 - 确保可以滚动 */
.dashboard-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #0f1b35 0%, #1a2b4a 100%);
  color: white;
  font-family: 'Microsoft YaHei', Arial, sans-serif;
  display: flex;
  flex-direction: column;
  /* 确保不会溢出 */
  overflow: hidden;
  height: 100vh; /* 添加固定高度 */
}

.dashboard-main {
  flex: 1; /* 占据剩余空间 */
  padding: 20px;
  max-width: 1800px;
  margin: 0 auto;
  width: 100%;
  overflow-y: auto; /* 垂直滚动 */
  overflow-x: hidden; /* 禁止水平滚动 */
  height: calc(100vh - 70px); /* 计算高度：总高度减去头部高度 */
  min-height: 0; /* 重要：允许内容区域收缩 */
  
  /* 自定义滚动条 */
  scrollbar-width: thin;
  scrollbar-color: #409eff #1a2b4a;
}

.dashboard-main::-webkit-scrollbar {
  width: 10px;
}

.dashboard-main::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 5px;
}

.dashboard-main::-webkit-scrollbar-thumb {
  background: linear-gradient(180deg, #409eff, #1e88e5);
  border-radius: 5px;
  border: 2px solid rgba(0, 0, 0, 0.2);
}

.dashboard-main::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(180deg, #1e88e5, #1565c0);
}

.dashboard-main::-webkit-scrollbar-button {
  display: none;
}

/* 头部样式 */
.dashboard-header {
  background: rgba(16, 28, 52, 0.9);
  backdrop-filter: blur(10px);
  padding: 15px 30px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(64, 158, 255, 0.2);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  flex-shrink: 0; /* 防止被压缩 */
  z-index: 100;
  position: sticky;
  top: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 1.5rem;
  font-weight: bold;
  color: #409eff;
}

.logo-icon {
  font-size: 2rem;
}

.system-status {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(64, 158, 255, 0.1);
  padding: 6px 15px;
  border-radius: 20px;
  border: 1px solid rgba(64, 158, 255, 0.3);
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #f44336;
}

.status-dot.active {
  background: #4caf50;
  animation: pulse 2s infinite;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.time-display, .server-info {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.05);
  padding: 8px 15px;
  border-radius: 8px;
  font-size: 0.9rem;
}

.refresh-btn {
  background: linear-gradient(90deg, #2196f3, #1976d2);
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  gap: 5px;
}

.refresh-btn:hover:not(:disabled) {
  background: linear-gradient(90deg, #1976d2, #1565c0);
  transform: translateY(-2px);
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 指标卡片 - 添加点击效果 */
.metrics-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.metric-card {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 15px;
  padding: 25px;
  text-align: center;
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
  cursor: pointer;
}

.metric-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
  background: rgba(255, 255, 255, 0.08);
}

.metric-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
}

.temperature::before { background: linear-gradient(90deg, #ff6b6b, #ff8e53); }
.humidity::before { background: linear-gradient(90deg, #36d1dc, #5b86e5); }
.light::before { background: linear-gradient(90deg, #ffe347, #ff9a00); }
.co2::before { background: linear-gradient(90deg, #9be15d, #00e3ae); }

.metric-icon {
  font-size: 2.5rem;
  margin-bottom: 10px;
}

.metric-label {
  font-size: 1rem;
  color: #bbdefb;
  margin-bottom: 5px;
}

.metric-value {
  font-size: 2.5rem;
  font-weight: bold;
  margin: 10px 0;
}

.metric-range {
  font-size: 0.9rem;
  color: #90caf9;
  margin-bottom: 10px;
}

.metric-trend {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 5px;
  font-size: 0.9rem;
  margin-top: 10px;
}

.trend-icon {
  font-size: 1.2rem;
}

/* 图表区域 */
.charts-row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 20px;
  margin-bottom: 30px;
}

.chart-container {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 15px;
  padding: 20px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.chart-header h3 {
  margin: 0;
  color: #64b5f6;
}

.chart-actions {
  display: flex;
  gap: 10px;
}

.btn-chart {
  background: rgba(255, 255, 255, 0.1);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.2);
  padding: 5px 15px;
  border-radius: 20px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.3s;
}

.btn-chart.active {
  background: #409eff;
  border-color: #409eff;
}

.btn-chart:hover:not(.active) {
  background: rgba(255, 255, 255, 0.2);
}

.chart-placeholder, .chart-real {
  height: 250px;
  display: flex;
  justify-content: center;
  align-items: center;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 10px;
  position: relative;
}

.loading-chart {
  text-align: center;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(255, 255, 255, 0.1);
  border-top-color: #409eff;
  border-radius: 50%;
  margin: 0 auto 10px;
  animation: spin 1s linear infinite;
}

.chart-mock {
  width: 90%;
  height: 80%;
  position: relative;
  display: flex;
  align-items: flex-end;
  gap: 2%;
}

.chart-line {
  flex: 1;
  background: linear-gradient(to top, #409eff, #64b5f6);
  border-radius: 3px 3px 0 0;
  transition: height 0.5s ease;
}

.gauge-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
}

.gauge-circle {
  width: 150px;
  height: 150px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  position: relative;
}

.gauge-circle::before {
  content: '';
  position: absolute;
  top: 10px;
  left: 10px;
  right: 10px;
  bottom: 10px;
  background: #1a2b4a;
  border-radius: 50%;
  z-index: 1;
}

.gauge-value, .gauge-label {
  position: relative;
  z-index: 2;
}

.gauge-value {
  font-size: 2.5rem;
  font-weight: bold;
  margin-bottom: 5px;
}

.gauge-label {
  font-size: 0.9rem;
  color: #bbdefb;
}

/* 控制面板 */
.controls-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 30px;
}

.control-panel, .alarm-panel {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 15px;
  padding: 20px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.control-panel h3, .alarm-panel h3 {
  color: #64b5f6;
  margin-top: 0;
  margin-bottom: 20px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.btn-clear-alarms {
  background: rgba(244, 67, 54, 0.2);
  color: #ff8a80;
  border: 1px solid rgba(244, 67, 54, 0.3);
  padding: 5px 15px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
}

.btn-clear-alarms:hover:not(:disabled) {
  background: rgba(244, 67, 54, 0.3);
}

.btn-clear-alarms:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.control-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.control-item {
  background: rgba(255, 255, 255, 0.03);
  padding: 15px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.control-item.disabled {
  opacity: 0.5;
}

.control-label {
  font-size: 1rem;
  margin-bottom: 10px;
  color: #bbdefb;
}

.control-switch {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.switch {
  position: relative;
  display: inline-block;
  width: 50px;
  height: 26px;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #ccc;
  transition: .4s;
  border-radius: 34px;
}

.slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 4px;
  bottom: 4px;
  background-color: white;
  transition: .4s;
  border-radius: 50%;
}

input:checked + .slider {
  background-color: #4caf50;
}

input:checked + .slider:before {
  transform: translateX(24px);
}

input:disabled + .slider {
  background-color: #666;
  cursor: not-allowed;
}

.control-status {
  font-size: 0.9rem;
  color: #90caf9;
}

.btn-manual {
  background: rgba(33, 150, 243, 0.2);
  color: #64b5f6;
  border: 1px solid rgba(33, 150, 243, 0.3);
  padding: 5px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.8rem;
  width: 100%;
}

.btn-manual:hover:not(:disabled) {
  background: rgba(33, 150, 243, 0.3);
}

.btn-manual:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 警报列表 */
.alarm-list {
  max-height: 300px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #409eff #1a2b4a;
}

.alarm-list::-webkit-scrollbar {
  width: 6px;
}

.alarm-list::-webkit-scrollbar-track {
  background: #1a2b4a;
  border-radius: 3px;
}

.alarm-list::-webkit-scrollbar-thumb {
  background: #409eff;
  border-radius: 3px;
}

.alarm-item {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 15px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  margin-bottom: 10px;
  cursor: pointer;
  transition: all 0.3s;
}

.alarm-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.alarm-item.normal {
  border-left: 4px solid #4caf50;
}

.alarm-item.warning {
  border-left: 4px solid #ff9800;
}

.alarm-item.error {
  border-left: 4px solid #f44336;
}

.alarm-icon {
  font-size: 1.5rem;
  flex-shrink: 0;
}

.alarm-content {
  flex: 1;
}

.alarm-title {
  font-weight: bold;
  margin-bottom: 5px;
}

.alarm-desc {
  font-size: 0.9rem;
  color: #bbdefb;
  margin-bottom: 5px;
}

.alarm-time {
  font-size: 0.8rem;
  color: #90caf9;
}

.btn-acknowledge {
  background: rgba(76, 175, 80, 0.2);
  color: #81c784;
  border: 1px solid rgba(76, 175, 80, 0.3);
  padding: 5px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.8rem;
  flex-shrink: 0;
}

.btn-acknowledge:hover {
  background: rgba(76, 175, 80, 0.3);
}

.no-alarms {
  text-align: center;
  padding: 40px 20px;
  color: #bbdefb;
}

.no-alarms-icon {
  font-size: 3rem;
  margin-bottom: 10px;
}

/* 历史数据面板 */
.history-panel {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 15px;
  padding: 20px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  margin-bottom: 20px;
}

.btn-close-history {
  background: rgba(255, 255, 255, 0.1);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.2);
  padding: 5px 15px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
}

.btn-close-history:hover {
  background: rgba(255, 255, 255, 0.2);
}

.history-table {
  overflow-x: auto;
  margin-top: 20px;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th, td {
  padding: 12px 15px;
  text-align: left;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

th {
  color: #64b5f6;
  font-weight: bold;
}

td.low { color: #2196f3; }
td.normal { color: #4caf50; }
td.high { color: #ff9800; }

.status-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 0.8rem;
}

.status-badge.normal {
  background: rgba(76, 175, 80, 0.2);
  color: #81c784;
}

.status-badge.warning {
  background: rgba(255, 152, 0, 0.2);
  color: #ffb74d;
}

/* 操作栏 */
.action-bar {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.btn-action {
  background: linear-gradient(90deg, #2196f3, #1976d2);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.3s;
}

.btn-action:hover {
  background: linear-gradient(90deg, #1976d2, #1565c0);
  transform: translateY(-2px);
}

/* 设置对话框 */
.settings-dialog {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.dialog-content {
  background: #1a2b4a;
  border-radius: 15px;
  width: 90%;
  max-width: 500px;
  border: 1px solid rgba(64, 158, 255, 0.3);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.dialog-header h3 {
  margin: 0;
  color: #64b5f6;
}

.btn-close {
  background: none;
  color: white;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  padding: 0;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.btn-close:hover {
  background: rgba(255, 255, 255, 0.1);
}

.dialog-body {
  padding: 20px;
}

.setting-item {
  margin-bottom: 20px;
}

.setting-item label {
  display: block;
  margin-bottom: 8px;
  color: #bbdefb;
}

.setting-item input[type="number"] {
  width: 100%;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: white;
}

.range-input {
  display: flex;
  gap: 10px;
  align-items: center;
}

.range-input input {
  flex: 1;
}

.dialog-footer {
  padding: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.btn-cancel, .btn-save {
  padding: 8px 20px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
}

.btn-cancel {
  background: rgba(255, 255, 255, 0.1);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.btn-save {
  background: #409eff;
  color: white;
  border: none;
}

.btn-cancel:hover {
  background: rgba(255, 255, 255, 0.2);
}

.btn-save:hover {
  background: #1e88e5;
}

/* 动画 */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .charts-row {
    grid-template-columns: 1fr;
  }
  
  .control-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .dashboard-header {
    flex-direction: column;
    gap: 15px;
    padding: 15px;
  }
  
  .header-left, .header-right {
    flex-direction: column;
    gap: 10px;
    width: 100%;
  }
  
  .time-display, .server-info {
    width: 100%;
    justify-content: center;
  }
  
  .metrics-row {
    grid-template-columns: 1fr;
  }
  
  .controls-row {
    grid-template-columns: 1fr;
  }
  
  .action-bar {
    flex-wrap: wrap;
  }
}
</style>