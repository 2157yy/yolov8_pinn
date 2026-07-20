<template>
  <div class="page">
    <svg style="display:none" aria-hidden="true">
      <filter id="glass-distortion">
        <feTurbulence type="fractalNoise" baseFrequency="0.03" numOctaves="3" result="noise" />
        <feDisplacementMap in="SourceGraphic" in2="noise" scale="5" xChannelSelector="R" yChannelSelector="G" />
      </filter>
    </svg>
    <div class="bg-decor">
      <div class="bg-orb o1"></div>
      <div class="bg-orb o2"></div>
    </div>

    <header class="topbar">
      <div class="topbar-l">
        <span class="logo-mark"></span>
        <span class="title-cn">草莓智慧温室</span>
        <span class="title-en">Smart Greenhouse</span>
      </div>
      <div class="topbar-r">
        <span class="clock">{{ currentTime }}</span>
        <span class="dot" :class="{ on: systemOnline }"></span>
        <span class="status-text">{{ systemOnline ? 'ONLINE' : 'OFFLINE' }}</span>
      </div>
    </header>

    <main class="bento">

      <!-- 温度 Hero：左 2 列 × 2 行 -->
      <article class="b-card hero-card">
        <div class="hero-inner">
          <div class="hero-top">
            <span class="eyebrow">TEMPERATURE</span>
            <strong class="hero-num">{{ currentTemperature.toFixed(1) }}°</strong>
            <span class="hero-label">温度</span>
          </div>
          <div class="hero-gauge">
            <div class="gauge-ring">
              <svg viewBox="0 0 100 100">
                <circle class="ring-bg" cx="50" cy="50" r="42" />
                <circle class="ring-fill" cx="50" cy="50" r="42"
                  :style="{ strokeDashoffset: 264 - (264 * gaugePct / 100), stroke: gaugeColor }" />
              </svg>
              <div class="gauge-text">{{ gaugeText }}</div>
            </div>
            <div class="gauge-info">
              <span class="gauge-label">状态</span>
              <span class="gauge-val" :style="{ color: gaugeColor }">{{ gaugeText }}</span>
            </div>
          </div>
        </div>
      </article>

      <!-- 湿度 -->
      <article class="b-card stat-card">
        <span class="eyebrow">HUMIDITY</span>
        <strong class="stat-num humid-num">{{ metrics[1].value }}</strong>
        <span class="stat-label">湿度</span>
        <span class="stat-sub">{{ metrics[1].trendText }}</span>
      </article>

      <!-- 光照 -->
      <article class="b-card stat-card">
        <span class="eyebrow">LIGHT</span>
        <strong class="stat-num light-num">{{ metrics[2].value }}</strong>
        <span class="stat-label">光照</span>
        <span class="stat-sub">{{ metrics[2].trendText }}</span>
      </article>

      <!-- CO2 -->
      <article class="b-card stat-card">
        <span class="eyebrow">CO2</span>
        <strong class="stat-num co2-num">{{ metrics[3].value }}</strong>
        <span class="stat-label">二氧化碳</span>
        <span class="stat-sub">{{ metrics[3].trendText }}</span>
      </article>

      <!-- 土壤湿度 -->
      <article class="b-card stat-card">
        <span class="eyebrow">SOIL</span>
        <strong class="stat-num soil-num">45%</strong>
        <span class="stat-label">土壤湿度</span>
        <span class="stat-sub">正常</span>
      </article>

      <!-- 报警 -->
      <article class="b-card alert-card">
        <span class="eyebrow alert-eyebrow">ALERTS</span>
        <div v-if="alarms.length === 0" class="stat-sub" style="margin-top:6px">暂无报警</div>
        <div v-for="a in alarms" :key="a.id" class="alert-row" @click="handleAlarmClick(a)">
          <span class="alert-dot">!</span>
          <div>
            <div class="alert-title">{{ a.title }}</div>
            <div class="stat-sub" style="font-size:.68rem">{{ a.description }}</div>
          </div>
        </div>
      </article>

      <!-- 设备 -->
      <article class="b-card device-card">
        <span class="eyebrow">DEVICES</span>
        <div class="dev-list">
          <div v-for="d in devices" :key="d.id" class="dev-row">
            <span class="dev-name">{{ d.name }}</span>
            <label class="toggle">
              <input type="checkbox" :checked="d.status" @change="toggleDevice(d)" />
              <span class="toggle-track"></span>
            </label>
          </div>
        </div>
      </article>

      <!-- 温度趋势 -->
      <article class="b-card chart-card">
        <div class="chart-head">
          <div>
            <span class="eyebrow">TREND</span>
            <span class="chart-title">温度趋势</span>
          </div>
          <div class="periods">
            <button v-for="p in chartPeriods" :key="p" class="p-btn" :class="{ on: selectedPeriod === p }" @click="selectedPeriod = p">{{ p }}</button>
          </div>
        </div>
        <div class="chart-area">
          <div v-for="(pt, i) in temperatureData" :key="i" class="bar-col">
            <div class="bar-fill" :style="{ height: pt + '%' }"></div>
          </div>
        </div>
      </article>

      <!-- Qwen 对话 -->
      <article class="b-card chat-card">
        <div class="chat-wrap">
          <div class="chat-main">
            <div class="chat-top">
              <span class="eyebrow" style="margin:0">Qwen AI</span>
              <span class="chat-label">草莓咨询助手</span>
              <span class="pill" :class="{ live: qwenLoading }">{{ qwenLoading ? '思考中' : '就绪' }}</span>
            </div>

            <div ref="chatBox" class="chat-list">
              <div v-for="m in qwenMessages" :key="m.id" class="bubble" :class="[m.role, { pending: m.pending }]">
                <div class="bubble-head">
                  <span>{{ m.role === 'user' ? '你' : 'Qwen' }}</span>
                  <span class="stat-sub" style="font-size:.62rem">{{ formatChatTime(m.timestamp) }}</span>
                </div>
                <div v-if="m.pending" class="thinking">
                  <div class="dots"><span></span><span></span><span></span></div>
                  <span class="stat-sub" style="font-size:.7rem">{{ getMessageStatusLabel(m) }}</span>
                  <div v-if="m.contextSummary" class="chips" style="margin-top:3px">
                    <span v-for="ch in getSummaryChips(m.contextSummary)" :key="ch.text" class="chip" :class="ch.tone">{{ ch.text }}</span>
                  </div>
                </div>
                <div v-if="m.reasoning" class="reasoning-text">{{ m.reasoning }}</div>
                <div v-if="m.content" class="msg-text">{{ m.content }}<span v-if="m.pending" class="cursor"></span></div>
                <div v-else-if="m.pending" class="stat-sub" style="margin-top:3px;font-size:.78rem">...</div>
              </div>
            </div>

            <div v-if="qwenError" class="err-msg">{{ qwenError }}</div>

            <div class="chat-input-row">
              <input ref="imageInput" type="file" accept="image/*" hidden @change="handleImageSelect" />
              <button class="ghost-btn" @click="$refs.imageInput.click()" :disabled="qwenLoading">
                {{ selectedImage ? '已选图' : '+ 图片' }}
              </button>
              <input class="chat-input" v-model="qwenInput" placeholder="输入问题..." @keydown="handleQwenKeydown" :disabled="qwenLoading" />
              <button class="send-btn" :disabled="qwenLoading || (!qwenInput.trim() && !selectedImage)" @click="sendQwenMessage">
                {{ qwenLoading ? '...' : '发送' }}
              </button>
            </div>

            <div v-if="selectedImage" class="img-tag">
              <span>{{ selectedImage.name }}</span>
              <button class="ghost-btn" @click="removeImage" :disabled="qwenLoading" style="padding:2px 7px;font-size:.62rem">×</button>
            </div>
          </div>

          <div class="chat-side">
            <span class="eyebrow">QUICK</span>
            <button v-for="q in (selectedImage ? diseaseQuestions : suggestedQuestions)" :key="q" class="quick-btn" :disabled="qwenLoading" @click="useSuggestedQuestion(q)">{{ q }}</button>
          </div>
        </div>
      </article>

    </main>
  </div>
</template>

<script>
function welcomeMessage() {
  return {
    id: 'welcome',
    role: 'assistant',
    content: '你好，我是 Qwen 草莓咨询助手。你可以直接问我采摘、补光、成熟度和风险建议。',
    pending: false, reasoning: '', status: 'done', contextSummary: null, timestamp: new Date()
  }
}

export default {
  name: 'Dashboard',
  data() {
    return {
      systemOnline: true,
      currentTime: '',
      refreshing: false,
      metrics: [
        { id: 1, label: '温度', value: '25.3°C', range: '适宜范围: 20-30°C', trendText: '平稳', tone: 'ok', icon: 'TEMP' },
        { id: 2, label: '湿度', value: '68%', range: '适宜范围: 60-80%', trendText: '稳定', tone: 'ok', icon: 'HUM' },
        { id: 3, label: '光照', value: '850 LUX', range: '适宜范围: 800-1200 LUX', trendText: '正常', tone: 'ok', icon: 'LUX' },
        { id: 4, label: 'CO2', value: '420 PPM', range: '适宜范围: 400-600 PPM', trendText: '正常', tone: 'ok', icon: 'CO2' }
      ],
      chartPeriods: ['日', '周', '月'],
      selectedPeriod: '日',
      temperatureData: [62, 66, 71, 76, 82, 86, 78, 74, 70, 65, 61, 58],
      currentTemperature: 25.3,
      devices: [
        { id: 1, name: '通风系统', status: true, power: 75 },
        { id: 2, name: '灌溉系统', status: false, power: 0 },
        { id: 3, name: '补光系统', status: true, power: 60 },
        { id: 4, name: '加湿系统', status: false, power: 0 }
      ],
      alarms: [
        { id: 1, title: '湿度偏低', description: '当前湿度低于设定阈值，建议检查加湿系统。', time: new Date() }
      ],
      qwenInput: '',
      qwenLoading: false,
      qwenError: '',
      qwenMessages: [welcomeMessage()],
      suggestedQuestions: ['现在适合采摘吗？', '需要补光吗？', '当前最大风险是什么？'],
      diseaseQuestions: ['这是什么病害？', '如何防治？', '需要人工复核吗？'],
      qwenSession: { imageId: 'web_qwen_image_001', plotId: 'plot_demo', plantBatchId: 'batch_demo' },
      qwenLoadingHints: ['正在运行 YOLO 检测', '正在分析结果', '正在整理建议', '正在组织回复'],
      qwenLoadingHintIndex: 0,
      qwenLoadingTimer: null,
      latestContextSummary: null,
      selectedImage: null,
      selectedImagePreview: '',
      detectionCount: 0,
      latestDetections: [],
      detectionMode: false
    }
  },
  computed: {
    gaugeColor() {
      const t = Number(this.currentTemperature)
      return t < 20 ? '#5AC8FA' : t > 30 ? '#FF9500' : '#34C759'
    },
    gaugePct() {
      return Math.max(5, Math.min(95, (Number(this.currentTemperature) - 10) * 3.33))
    },
    currentQwenHint() {
      return this.qwenLoadingHints[this.qwenLoadingHintIndex] || '思考中'
    },
    gaugeText() {
      const t = Number(this.currentTemperature)
      if (t < 20) return '偏低'
      if (t > 30) return '偏高'
      return '适宜'
    }
  },
  mounted() {
    this.updateTime()
    this.refreshData()
    this.timeTimer = setInterval(this.updateTime, 1000)
  },
  beforeUnmount() {
    clearInterval(this.timeTimer)
    this.stopQwenTicker()
  },
  methods: {
    updateTime() {
      this.currentTime = new Date().toLocaleString('zh-CN', { hour12: false })
    },
    async refreshData() {
      this.refreshing = true
      try {
        const [sensorRes, deviceRes, alertRes, historyRes] = await Promise.all([
          fetch('/api/sensors'), fetch('/api/devices'), fetch('/api/alerts'), fetch('/api/history?period=day')
        ])
        const sensor = await sensorRes.json()
        const device = await deviceRes.json()
        const alert = await alertRes.json()
        const history = await historyRes.json()
        if (sensor.success) this.applySensorData(sensor.data)
        if (device.success) this.devices = device.data
        if (alert.success) {
          this.alarms = alert.data.map((item) => ({ id: item.id, title: item.title, description: item.message, time: new Date(item.timestamp) }))
        }
        if (history.success) this.temperatureData = history.data.slice(-14).map((item) => Math.max(28, Math.min(94, item.temperature * 3)))
        this.systemOnline = true
      } catch (error) {
        this.systemOnline = false
      } finally {
        this.refreshing = false
      }
    },
    applySensorData(data) {
      this.currentTemperature = Number(data.temperature)
      this.metrics[0] = { ...this.metrics[0], value: `${data.temperature}°C`, trendText: data.temperature > 30 ? '偏高' : '平稳', tone: data.temperature > 30 ? 'warn' : 'ok' }
      this.metrics[1] = { ...this.metrics[1], value: `${data.humidity}%`, trendText: data.humidity < 60 ? '偏低' : '稳定', tone: data.humidity < 60 ? 'warn' : 'ok' }
      this.metrics[2] = { ...this.metrics[2], value: `${data.light} LUX`, trendText: data.light < 800 ? '偏弱' : '正常', tone: data.light < 800 ? 'warn' : 'ok' }
      this.metrics[3] = { ...this.metrics[3], value: `${data.co2} PPM`, trendText: data.co2 > 600 ? '偏高' : '正常', tone: data.co2 > 600 ? 'warn' : 'ok' }
    },
    toggleDevice(device) {
      device.status = !device.status
      device.power = device.status ? Math.round(55 + Math.random() * 25) : 0
    },
    handleAlarmClick(alarm) {
      window.alert(`${alarm.title}\n${alarm.description}`)
    },
    formatChatTime(timestamp) {
      return new Date(timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    },
    handleQwenKeydown(event) {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault()
        this.sendQwenMessage()
      }
    },
    useSuggestedQuestion(question) {
      this.qwenInput = question
      this.sendQwenMessage()
    },
    startQwenTicker() {
      this.stopQwenTicker()
      this.qwenLoadingHintIndex = 0
      this.qwenLoadingTimer = setInterval(() => {
        this.qwenLoadingHintIndex = (this.qwenLoadingHintIndex + 1) % this.qwenLoadingHints.length
      }, 1400)
    },
    stopQwenTicker() {
      if (this.qwenLoadingTimer) clearInterval(this.qwenLoadingTimer)
      this.qwenLoadingTimer = null
    },
    scrollChat() {
      this.$nextTick(() => {
        const box = this.$refs.chatBox
        if (box) box.scrollTop = box.scrollHeight
      })
    },
    getMessageStatusLabel(m) {
      if (m.status === 'detecting') return '正在 YOLO 检测...'
      if (m.status === 'ready') return '检测完成，分析中'
      if (m.status === 'thinking') return this.currentQwenHint
      if (m.status === 'answering') return '正在组织回复'
      return '准备中'
    },
    getSummaryChips(summary) {
      if (!summary) return []
      if (summary.detections && summary.detections.length > 0) {
        return summary.detections.slice(0, 4).map((d) => ({
          text: `${d.disease_name} ${(d.confidence * 100).toFixed(0)}%`,
          tone: d.confidence > 0.7 ? 'warn' : 'info'
        }))
      }
      if (summary.detection_count !== undefined) {
        return [{ text: `检测: ${summary.detection_count} 处病害`, tone: summary.detection_count > 0 ? 'warn' : 'good' }]
      }
      const chips = []
      if (summary.harvest === true) chips.push({ text: '可采摘', tone: 'good' })
      if (summary.manual_review === true) chips.push({ text: '建议人工复核', tone: 'warn' })
      if (summary.fill_light === true) chips.push({ text: '建议补光', tone: 'info' })
      return chips
    },
    consumeSseBuffer(buffer, msg) {
      const parts = buffer.split('\n\n')
      const remain = parts.pop() || ''
      for (const block of parts) {
        const data = block.split(/\r?\n/).filter((l) => l.startsWith('data: ')).map((l) => l.slice(6)).join('\n')
        if (!data) continue
        const err = this.applyStreamEvent(JSON.parse(data), msg)
        if (err) this.qwenError = err
      }
      return remain
    },
    applyStreamEvent(event, msg) {
      if (event.type === 'status' && event.stage === 'detecting') msg.status = 'detecting'
      if (event.type === 'ready') {
        msg.status = 'ready'
        if (event.detections) {
          this.detectionCount = event.detection_count || 0
          this.latestDetections = event.detections || []
          msg.contextSummary = { detection_count: event.detection_count, detections: event.detections, scene: event.scene }
        } else {
          msg.contextSummary = event.context_summary || null
        }
        this.latestContextSummary = msg.contextSummary || this.latestContextSummary
      }
      if (event.type === 'thinking' && event.delta) { msg.status = 'thinking'; msg.reasoning += event.delta }
      if (event.type === 'answer' && event.delta) { msg.status = 'answering'; msg.content += event.delta }
      if (event.type === 'done') {
        if (!msg.content && event.reply) msg.content = event.reply
        if (!msg.reasoning && event.reasoning) msg.reasoning = event.reasoning
        msg.contextSummary = event.context_summary || msg.contextSummary
        msg.pending = false; msg.status = 'done'
        this.latestContextSummary = msg.contextSummary || this.latestContextSummary
        if (this.detectionMode) this.removeImage()
      }
      if (event.type === 'error') { msg.pending = false; msg.status = 'done'; return event.error || '流式回答失败' }
      return ''
    },
    handleImageSelect(event) {
      const file = event.target.files?.[0]
      if (file) this.setSelectedImage(file)
    },
    setSelectedImage(file) {
      if (!/\.(jpe?g|png|bmp|tiff?|webp)$/i.test(file.name)) { window.alert('不支持该格式'); return }
      this.selectedImage = file; this.detectionCount = 0; this.latestDetections = []; this.detectionMode = true
      const reader = new FileReader()
      reader.onload = (e) => { this.selectedImagePreview = e.target.result }
      reader.readAsDataURL(file)
    },
    removeImage() {
      this.selectedImage = null; this.selectedImagePreview = ''; this.detectionCount = 0; this.latestDetections = []; this.detectionMode = false
      if (this.$refs.imageInput) this.$refs.imageInput.value = ''
    },
    async sendQwenMessage() {
      const content = this.qwenInput.trim()
      if ((!content && !this.selectedImage) || this.qwenLoading) return
      const userContent = content || '请分析这张图片中的草莓病害情况'
      const hasImage = !!this.selectedImage
      const userMsg = { id: `u-${Date.now()}`, role: 'user', content: userContent, pending: false, reasoning: '', status: 'done', contextSummary: null, timestamp: new Date() }
      const asstMsg = { id: `a-${Date.now()}`, role: 'assistant', content: '', pending: true, reasoning: '', status: 'queued', contextSummary: null, timestamp: new Date() }
      const msgs = [...this.qwenMessages, userMsg].map((m) => ({ role: m.role, content: m.content }))
      this.qwenMessages.push(userMsg, asstMsg)
      this.qwenInput = ''; this.qwenLoading = true; this.qwenError = ''
      this.startQwenTicker(); this.scrollChat()
      const apiPath = hasImage ? '/api/detect/chat/stream' : '/api/qwen/chat/stream'
      let body, headers = {}
      if (hasImage) {
        const form = new FormData()
        form.append('image', this.selectedImage); form.append('message', userContent); form.append('messages', JSON.stringify(msgs))
        body = form
      } else {
        headers['Content-Type'] = 'application/json'
        body = JSON.stringify({ message: userContent, messages: msgs, imageId: this.qwenSession.imageId, plotId: this.qwenSession.plotId, plantBatchId: this.qwenSession.plantBatchId })
      }
      try {
        const res = await fetch(apiPath, { method: 'POST', headers, body })
        if (!res.ok || !res.body) throw new Error(hasImage ? '检测服务异常' : 'Qwen 无法响应')
        const reader = res.body.getReader(); const decoder = new TextDecoder('utf-8'); let buf = ''
        while (true) {
          const { value, done } = await reader.read()
          if (done) break
          buf += decoder.decode(value, { stream: true })
          buf = this.consumeSseBuffer(buf, asstMsg)
          this.scrollChat()
        }
        buf += decoder.decode()
        if (buf.trim()) this.consumeSseBuffer(buf, asstMsg)
        asstMsg.pending = false
      } catch (e) {
        asstMsg.pending = false; asstMsg.status = 'done'
        this.qwenError = e.message || '接入失败'
      } finally {
        this.qwenLoading = false; this.stopQwenTicker(); this.scrollChat()
      }
    }
  }
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: url('/photo.jpg') center / cover no-repeat fixed;
  color: #fff;
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  position: relative;
}
.bg-decor { position: fixed; inset: 0; pointer-events: none; z-index: 0; }
.bg-orb { position: absolute; border-radius: 50%; filter: blur(140px); }
.o1 { width: 520px; height: 520px; background: radial-gradient(circle, rgba(0,122,255,.12), transparent); top: -180px; left: -120px; }
.o2 { width: 380px; height: 380px; background: radial-gradient(circle, rgba(52,199,89,.08), transparent); bottom: 5%; right: -80px; }

/* 顶栏 */
.topbar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 11px 30px;
  background: rgba(255,255,255,.04);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border-bottom: 1px solid rgba(255,255,255,.06);
  position: relative; z-index: 2;
}
.topbar-l { display: flex; align-items: center; gap: 10px; }
.logo-mark { width: 9px; height: 9px; border-radius: 3px; background: linear-gradient(180deg, rgba(0,122,255,.9), rgba(0,122,255,.2)); }
.title-cn { font-size: 1.05rem; font-weight: 700; letter-spacing: .05em; }
.title-en { font-size: .62rem; opacity: .4; text-transform: uppercase; letter-spacing: .22em; }
.topbar-r { display: flex; align-items: center; gap: 9px; }
.clock { font-size: .74rem; opacity: .55; }
.dot { width: 6px; height: 6px; border-radius: 50%; background: #FF3B30; }
.dot.on { background: #34C759; box-shadow: 0 0 9px rgba(52,199,89,.5); }
.status-text { font-size: .62rem; opacity: .4; letter-spacing: .16em; }

/* Bento 网格 */
.bento {
  display: grid;
  grid-template-columns: 1.8fr 1fr 1fr 1fr;
  gap: 8px;
  padding: 12px;
  max-width: 1440px;
  margin: 0 auto;
  position: relative; z-index: 1;
}

/* 卡片基底 —— 液态玻璃 */
.b-card {
  position: relative;
  overflow: hidden;
  border-radius: 20px;
  padding: 14px 16px;
  box-shadow: 0 6px 6px rgba(0,0,0,0.2), 0 0 20px rgba(0,0,0,0.1);
}
.b-card::before {
  content: '';
  position: absolute; z-index: 0; inset: 0;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  filter: url(#glass-distortion);
}
.b-card::after {
  content: '';
  position: absolute; z-index: 1; inset: 0;
  background: rgba(255,255,255,0.16);
  box-shadow: inset 2px 2px 1px 0 rgba(255,255,255,0.5),
              inset -1px -1px 1px 1px rgba(255,255,255,0.5);
}
.b-card > * {
  position: relative; z-index: 3;
}

/* ===== Hero 温度 ===== */
.hero-card {
  grid-row: 1 / 3;
  grid-column: 1 / 3;
  border-radius: 22px;
  padding: 20px 22px;
}
.hero-inner {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;
  gap: 12px;
}
.hero-num {
  font-size: 5.4rem;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -.04em;
  background: linear-gradient(180deg, rgba(0,122,255,1) 0%, rgba(0,122,255,.5) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  display: block;
  margin: 6px 0 2px;
}
.hero-label { font-size: .84rem; opacity: .75; font-weight: 500; }
.hero-gauge { display: flex; align-items: center; gap: 14px; margin-top: 4px; }
.gauge-ring { width: 64px; height: 64px; position: relative; flex-shrink: 0; }
.gauge-ring svg { width: 100%; height: 100%; transform: rotate(-90deg); }
.ring-bg { fill: none; stroke: rgba(255,255,255,.05); stroke-width: 5; }
.ring-fill {
  fill: none; stroke-width: 5;
  stroke-linecap: round;
  stroke-dasharray: 264;
  transition: stroke-dashoffset .5s ease, stroke .5s ease;
}
.gauge-text {
  position: absolute; inset: 0;
  display: grid; place-items: center;
  font-size: .66rem; font-weight: 600;
  color: rgba(255,255,255,.75);
}
.gauge-info { display: flex; flex-direction: column; gap: 1px; }
.gauge-label { font-size: .6rem; opacity: .35; text-transform: uppercase; letter-spacing: .15em; }
.gauge-val { font-size: .88rem; font-weight: 600; }

/* ===== 统计卡片 ===== */
.stat-card {
  display: flex; flex-direction: column; gap: 1px;
  padding: 12px 15px;
  border-radius: 18px;
}
.stat-num {
  font-size: 2.2rem; font-weight: 700;
  line-height: 1.1; letter-spacing: -.03em;
  margin: 2px 0;
}
.stat-label { font-size: .74rem; opacity: .7; font-weight: 500; }
.stat-sub { font-size: .64rem; opacity: .32; }

.humid-num {
  background: linear-gradient(180deg, rgba(52,199,89,.95) 0%, rgba(52,199,89,.4) 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.light-num {
  background: linear-gradient(180deg, rgba(255,149,0,.95) 0%, rgba(255,149,0,.4) 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.co2-num {
  background: linear-gradient(180deg, rgba(175,82,222,.9) 0%, rgba(175,82,222,.35) 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.soil-num {
  background: linear-gradient(180deg, rgba(90,200,250,.9) 0%, rgba(90,200,250,.35) 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}

.eyebrow {
  font-size: .55rem; opacity: .35;
  text-transform: uppercase; letter-spacing: .2em;
}

/* ===== 图表 ===== */
.chart-card {
  grid-column: 1 / -1;
  border-radius: 18px;
  padding: 14px 18px;
}
.chart-head { display: flex; justify-content: space-between; align-items: flex-start; }
.chart-title { font-size: .74rem; opacity: .7; display: block; margin-top: 1px; }
.periods { display: flex; gap: 3px; }
.p-btn {
  background: rgba(255,255,255,.025); border: 1px solid rgba(255,255,255,.05);
  color: rgba(255,255,255,.45); padding: 2px 9px; border-radius: 999px;
  font-size: .66rem; cursor: pointer;
}
.p-btn.on { background: rgba(255,255,255,.1); color: #fff; border-color: rgba(255,255,255,.12); }
.chart-area { display: flex; align-items: flex-end; gap: 4px; height: 100px; margin-top: 8px; }
.bar-col { flex: 1; height: 100%; display: flex; align-items: flex-end; }
.bar-fill {
  width: 100%; max-width: 24px; margin: 0 auto;
  border-radius: 4px 4px 2px 2px;
  background: linear-gradient(180deg, rgba(0,122,255,.55), rgba(0,122,255,.06));
  min-height: 2px;
}

/* ===== 报警 ===== */
.alert-card {
  grid-column: span 2;
  border-radius: 16px;
  padding: 12px 15px;
}
.alert-eyebrow { color: rgba(255,59,48,.6); }
.alert-row {
  display: flex; align-items: center; gap: 8px;
  margin-top: 6px; padding: 7px 10px;
  border-radius: 10px;
  background: rgba(255,59,48,.03);
  border: 1px solid rgba(255,59,48,.06);
  cursor: pointer;
}
.alert-row:hover { background: rgba(255,59,48,.06); }
.alert-dot {
  width: 22px; height: 22px; border-radius: 50%;
  background: rgba(255,59,48,.12); color: #FF453A;
  display: grid; place-items: center;
  font-weight: 700; font-size: .7rem; flex-shrink: 0;
}
.alert-title { font-size: .76rem; font-weight: 600; }

/* ===== 设备 ===== */
.device-card {
  grid-column: span 2;
  border-radius: 16px;
  padding: 12px 15px;
}
.dev-list { display: flex; flex-direction: column; gap: 5px; margin-top: 4px; }
.dev-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 5px 10px; border-radius: 8px;
  background: rgba(255,255,255,.012); border: 1px solid rgba(255,255,255,.03);
}
.dev-name { font-size: .72rem; opacity: .75; }

.toggle { position: relative; display: inline-block; width: 40px; height: 23px; }
.toggle input { opacity: 0; width: 0; height: 0; }
.toggle-track {
  position: absolute; inset: 0; border-radius: 999px;
  background: rgba(255,255,255,.08); cursor: pointer; transition: background .2s;
}
.toggle-track::before {
  content: ''; position: absolute; left: 2px; top: 2px;
  width: 19px; height: 19px; border-radius: 50%;
  background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.3);
  transition: transform .2s;
}
input:checked + .toggle-track { background: rgba(52,199,89,.45); }
input:checked + .toggle-track::before { transform: translateX(17px); }

/* ===== 聊天 ===== */
.chat-card {
  grid-column: 1 / -1;
  border-radius: 18px;
  padding: 14px 18px;
}
.chat-wrap { display: grid; grid-template-columns: 1fr 155px; gap: 12px; }
.chat-top { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.chat-label { font-size: .76rem; opacity: .7; font-weight: 500; }
.chat-list { max-height: 180px; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; }
.bubble {
  max-width: 82%; padding: 8px 12px; border-radius: 13px;
  border: 1px solid rgba(255,255,255,.04); background: rgba(255,255,255,.015);
}
.bubble.assistant { align-self: flex-start; border-bottom-left-radius: 4px; }
.bubble.user {
  align-self: flex-end; border-bottom-right-radius: 4px;
  background: rgba(0,122,255,.06); border-color: rgba(0,122,255,.08);
}
.bubble.pending { border-color: rgba(0,122,255,.14); }
.bubble-head { display: flex; justify-content: space-between; font-size: .7rem; margin-bottom: 2px; }
.msg-text { margin-top: 3px; white-space: pre-wrap; line-height: 1.6; font-size: .8rem; }
.reasoning-text {
  margin-top: 4px; padding: 6px 8px; border-left: 2px solid rgba(90,200,250,.45);
  border-radius: 4px; background: rgba(90,200,250,.06); color: rgba(255,255,255,.62);
  white-space: pre-wrap; line-height: 1.45; font-size: .72rem;
}
.cursor { display: inline-block; width: 6px; height: 1em; margin-left: 2px; vertical-align: text-bottom; border-radius: 1px; background: #fff; animation: blink .9s infinite; }
.thinking { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; padding: 4px 8px; margin-top: 2px; border-radius: 6px; background: rgba(255,255,255,.01); }

.chat-input-row { display: flex; gap: 6px; margin-top: 8px; align-items: center; }
.chat-input {
  flex: 1; padding: 7px 12px; border-radius: 999px;
  border: 1px solid rgba(255,255,255,.06); background: rgba(255,255,255,.025);
  color: #fff; font-size: .76rem; outline: none;
}
.chat-input::placeholder { color: rgba(255,255,255,.18); }
.chat-side {
  border-left: 1px solid rgba(255,255,255,.03);
  padding-left: 10px; display: flex; flex-direction: column; gap: 4px;
}
.img-tag {
  display: flex; align-items: center; gap: 5px;
  margin-top: 6px; padding: 3px 9px; border-radius: 6px;
  background: rgba(0,122,255,.04); font-size: .66rem;
}

.pill { padding: 2px 9px; border-radius: 999px; background: rgba(255,255,255,.03); font-size: .64rem; }
.pill.live { background: rgba(0,122,255,.08); color: #7db9ff; }
.ghost-btn {
  background: rgba(255,255,255,.02); border: 1px solid rgba(255,255,255,.04);
  color: #aaa; cursor: pointer; border-radius: 999px;
  padding: 4px 11px; font-size: .66rem;
}
.ghost-btn:hover { background: rgba(255,255,255,.04); }
.ghost-btn:disabled { opacity: .25; cursor: not-allowed; }
.send-btn {
  background: rgba(0,122,255,.65); border: none; color: #fff;
  cursor: pointer; border-radius: 999px; padding: 6px 16px;
  font-size: .72rem; font-weight: 600;
}
.send-btn:hover { background: rgba(0,122,255,.8); }
.send-btn:disabled { opacity: .25; cursor: not-allowed; }
.quick-btn {
  background: transparent; border: 1px solid rgba(255,255,255,.03);
  color: #aaa; cursor: pointer; border-radius: 999px;
  padding: 3px 10px; font-size: .64rem; text-align: left;
}
.quick-btn:hover { border-color: rgba(255,255,255,.08); color: #fff; }
.quick-btn:disabled { opacity: .2; cursor: not-allowed; }

.err-msg {
  padding: 6px 10px; margin-top: 6px; border-radius: 8px;
  background: rgba(255,59,48,.06); color: #ffa098; font-size: .7rem;
}

.dots { display: inline-flex; gap: 2px; }
.dots span { width: 4px; height: 4px; border-radius: 50%; background: rgba(255,255,255,.35); animation: bounce 1.1s infinite ease-in-out; }
.dots span:nth-child(2) { animation-delay: .15s; }
.dots span:nth-child(3) { animation-delay: .3s; }

.chip {
  padding: 2px 7px; border-radius: 999px;
  background: rgba(255,255,255,.02); font-size: .62rem;
  border: 1px solid rgba(255,255,255,.03);
}
.chip.warn { background: rgba(255,149,0,.06); color: #ffb366; border-color: rgba(255,149,0,.08); }
.chip.good { background: rgba(52,199,89,.06); color: #5cdb7e; border-color: rgba(52,199,89,.08); }
.chip.info { background: rgba(0,122,255,.06); color: #7db9ff; border-color: rgba(0,122,255,.08); }

@keyframes bounce {
  0%, 80%, 100% { transform: translateY(0); opacity: .25; }
  40% { transform: translateY(-3px); opacity: 1; }
}
@keyframes blink {
  0%, 45% { opacity: 1; }
  55%, 100% { opacity: .06; }
}

@media (max-width: 1150px) {
  .bento { grid-template-columns: 1fr 1fr; }
  .hero-card { grid-column: 1 / -1; grid-row: auto; }
  .chart-card { grid-column: 1 / -1; }
  .chat-wrap { grid-template-columns: 1fr; }
  .chat-side { display: none; }
}
@media (max-width: 640px) {
  .bento { grid-template-columns: 1fr; gap: 6px; padding: 8px; }
  .hero-num { font-size: 3.6rem; }
  .stat-num { font-size: 1.8rem; }
  .topbar { padding: 9px 14px; }
  .title-cn { font-size: .84rem; }
}
</style>
