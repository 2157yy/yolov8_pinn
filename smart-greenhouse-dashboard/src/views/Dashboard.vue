<template>
  <div class="page">
    <header class="topbar">
      <div>
        <p class="eyebrow">Smart Greenhouse</p>
        <h1>智能温室草莓监控台</h1>
        <p class="muted">环境监测、设备状态与 Qwen 流式咨询</p>
      </div>
      <div class="topbar-right">
        <span class="pill" :class="{ off: !systemOnline }">{{ systemOnline ? '系统在线' : '系统离线' }}</span>
        <span class="muted">{{ currentTime }}</span>
        <button class="primary" :disabled="refreshing" @click="refreshData">{{ refreshing ? '刷新中...' : '刷新数据' }}</button>
        <button class="primary nav-btn" @click="goToMaturity">跳转至成熟度检测</button>
      </div>
    </header>

    <main class="content">
      <section class="metrics">
        <article v-for="metric in metrics" :key="metric.id" class="card metric" @click="showMetricDetail(metric)">
          <div class="metric-head">
            <span>{{ metric.label }}</span>
            <span class="muted">{{ metric.icon }}</span>
          </div>
          <strong class="metric-value">{{ metric.value }}</strong>
          <div class="muted">{{ metric.range }}</div>
          <div class="trend" :class="metric.tone">{{ metric.trendText }}</div>
        </article>
      </section>

      <section class="grid">
        <article class="card">
          <div class="section-head">
            <div>
              <p class="eyebrow">Trend</p>
              <h2>温度趋势</h2>
            </div>
            <div class="periods">
              <button v-for="period in chartPeriods" :key="period" class="ghost" :class="{ active: selectedPeriod === period }" @click="selectedPeriod = period">{{ period }}</button>
            </div>
          </div>
          <div class="chart">
            <div v-for="(point, index) in temperatureData" :key="index" class="bar" :style="{ height: `${point}%` }"></div>
          </div>
        </article>

        <article class="card">
          <div class="section-head">
            <div>
              <p class="eyebrow">Gauge</p>
              <h2>实时温度</h2>
            </div>
            <span class="pill">{{ gaugeText }}</span>
          </div>
          <div class="gauge">
            <div class="gauge-ring" :style="gaugeStyle">
              <div class="gauge-core">
                <strong>{{ currentTemperature.toFixed(1) }}°C</strong>
                <span class="muted">当前温度</span>
              </div>
            </div>
          </div>
        </article>
      </section>

      <section class="grid">
        <article class="card">
          <div class="section-head">
            <div>
              <p class="eyebrow">Devices</p>
              <h2>设备控制</h2>
            </div>
          </div>
          <div class="stack">
            <div v-for="device in devices" :key="device.id" class="row">
              <div>
                <div>{{ device.name }}</div>
                <div class="muted">{{ device.status ? `运行中 · ${device.power || 0}%` : '已关闭' }}</div>
              </div>
              <label class="switch">
                <input type="checkbox" :checked="device.status" @change="toggleDevice(device)" />
                <span class="slider"></span>
              </label>
            </div>
          </div>
        </article>

        <article class="card">
          <div class="section-head">
            <div>
              <p class="eyebrow">Alerts</p>
              <h2>报警通知</h2>
            </div>
            <button class="ghost" :disabled="alarms.length === 0" @click="clearAlarms">清空</button>
          </div>
          <div class="stack">
            <div v-if="alarms.length === 0" class="empty">暂无报警</div>
            <div v-for="alarm in alarms" :key="alarm.id" class="row alarm" @click="handleAlarmClick(alarm)">
              <div>
                <div>{{ alarm.title }}</div>
                <div class="muted">{{ alarm.description }}</div>
              </div>
              <button class="ghost small" @click.stop="acknowledgeAlarm(alarm)">确认</button>
            </div>
          </div>
        </article>
      </section>

      <section class="card">
        <div class="section-head">
          <div>
            <p class="eyebrow">Streaming Chat</p>
            <h2>Qwen 草莓咨询助手</h2>
          </div>
          <span class="pill" :class="{ live: qwenLoading }">{{ qwenLoading ? currentQwenHint : '等待提问' }}</span>
        </div>

        <div class="chat-layout">
          <div ref="chatBox" class="chat">
            <div v-for="message in qwenMessages" :key="message.id" class="bubble" :class="[message.role, { pending: message.pending }]">
              <div class="bubble-head">
                <span>{{ message.role === 'user' ? '你' : 'Qwen' }}</span>
                <span class="muted">{{ formatChatTime(message.timestamp) }}</span>
              </div>

              <div v-if="message.pending" class="thinking">
                <div class="thinking-title">
                  <span class="dots"><span></span><span></span><span></span></span>
                  <span>{{ getMessageStatusLabel(message) }}</span>
                </div>
                <div class="chips">
                  <span v-for="stage in getThinkingStages(message)" :key="stage.label" class="chip" :class="stage.state">{{ stage.label }}</span>
                </div>
                <div v-if="message.contextSummary" class="chips">
                  <span v-for="chip in getSummaryChips(message.contextSummary)" :key="chip.text" class="chip" :class="chip.tone">{{ chip.text }}</span>
                </div>
                <div class="muted">{{ getThinkingPreview(message.reasoning, message.contextSummary) }}</div>
              </div>

              <div v-if="message.content" class="message">{{ message.content }}<span v-if="message.pending" class="cursor"></span></div>
              <div v-else-if="message.pending" class="message muted">正在生成回复...</div>
            </div>
          </div>

          <aside class="card side">
            <p class="eyebrow">Quick Ask</p>
            <h3>{{ selectedImage ? '成熟度分析问题' : '推荐问题' }}</h3>
            <div class="stack">
              <button v-for="question in (selectedImage ? diseaseQuestions : suggestedQuestions)" :key="question" class="ghost block" :disabled="qwenLoading" @click="useSuggestedQuestion(question)">{{ question }}</button>
            </div>
            <div class="divider"></div>
            <p class="eyebrow">Live Hints</p>
            <div class="muted">{{ selectedImage && !qwenLoading ? '点击发送将上传图片进行 YOLO 成熟度检测 + Qwen 分析' : qwenLoading ? currentThinkingMessage : latestSummaryText }}</div>
          </aside>
        </div>

        <div v-if="qwenError" class="error">{{ qwenError }}</div>

        <div class="upload-section">
          <input ref="imageInput" type="file" accept="image/*" hidden @change="handleImageSelect" />
          <div
            v-if="!selectedImagePreview"
            class="upload-zone"
            @click="$refs.imageInput.click()"
            @dragover.prevent
            @dragenter.prevent
            @drop.prevent="handleImageDrop"
          >
            <span class="upload-icon">+</span>
            <span class="muted">上传草莓图片进行成熟度分析（点击或拖拽）</span>
          </div>
          <div v-else class="image-preview-row">
            <div class="image-thumb" :style="{ backgroundImage: `url(${selectedImagePreview})` }"></div>
            <div class="image-info">
              <span class="upload-label">{{ selectedImage ? selectedImage.name : '已选择图片' }}</span>
              <span v-if="detectionCount > 0" class="pill">{{ detectionCount }} 个目标</span>
              <div class="detection-chips" v-if="latestDetections.length > 0">
                <span v-for="(d, idx) in latestDetections" :key="idx" class="chip" :class="d.confidence > 0.7 ? 'good' : 'warn'">
                  {{ d.class_name || d.disease_name }} {{ (d.confidence * 100).toFixed(0) }}%
                </span>
              </div>
            </div>
            <button class="ghost small" :disabled="qwenLoading" @click.stop="removeImage">移除</button>
          </div>
        </div>

        <div class="composer">
          <textarea v-model="qwenInput" rows="4" placeholder="例如：现在适合采摘吗？还需要补光吗？" @keydown="handleQwenKeydown"></textarea>
          <div class="composer-row">
            <span class="muted">{{ qwenLoading ? 'Qwen 正在流式输出中' : 'Enter 发送，Shift + Enter 换行' }}</span>
            <button class="primary" :disabled="qwenLoading" @click="sendQwenMessage">{{ qwenLoading ? '生成中...' : '发送问题' }}</button>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script>
function welcomeMessage() {
  return {
    id: 'welcome',
    role: 'assistant',
    content: '你好，我是 Qwen 草莓咨询助手。你可以直接问我采摘、补光、成熟度和风险建议。',
    pending: false,
    reasoning: '',
    status: 'done',
    contextSummary: null,
    timestamp: new Date()
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
        { id: 3, label: '光照', value: '850 LUX', range: '适宜范围: 800-1200 LUX', trendText: '略偏弱', tone: 'warn', icon: 'LUX' },
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
      diseaseQuestions: ['这张图里的草莓成熟度怎么样？', '现在适合采摘吗？', '成熟和未熟分别有多少？', '是否建议人工复核？'],
      qwenSession: { imageId: 'web_qwen_image_001', plotId: 'plot_demo', plantBatchId: 'batch_demo' },
      qwenLoadingHints: ['正在运行 YOLO 成熟度检测', '正在分析检测结果', '正在整理采摘建议', '正在组织自然语言回复'],
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
    currentQwenHint() {
      return this.qwenLoadingHints[this.qwenLoadingHintIndex] || 'Qwen 正在思考中'
    },
    gaugeText() {
      if (this.currentTemperature < 20) return '温度偏低'
      if (this.currentTemperature > 30) return '温度偏高'
      return '温度适宜'
    },
    gaugeStyle() {
      const temp = Number(this.currentTemperature)
      const color = temp < 20 ? '#38bdf8' : temp > 30 ? '#fb923c' : '#4ade80'
      const progress = Math.max(0, Math.min(100, (temp - 10) * 3.33))
      return { background: `conic-gradient(${color} 0% ${progress}%, rgba(255,255,255,0.08) ${progress}% 100%)` }
    },
    latestSummaryText() {
      const summary = this.latestContextSummary
      if (!summary) return '提问后会先显示分析阶段，再逐步输出答案。'
      if (summary.detection_count !== undefined) {
        return summary.detection_count === 0
          ? '最近检测：未识别到有效草莓目标。'
          : `最近检测：识别到 ${summary.detection_count} 个草莓目标。`
      }
      if (summary.harvest === true) return '最近结论：可考虑采摘，建议结合人工复核。'
      if (summary.harvest === false) return '最近结论：暂不建议采摘，建议继续观察。'
      return summary.decision_message || '最近已经生成新的分析结论。'
    },
    currentThinkingMessage() {
      const pending = [...this.qwenMessages].reverse().find((item) => item.pending)
      if (!pending) return this.latestSummaryText
      return this.getThinkingPreview(pending.reasoning, pending.contextSummary)
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
    goToMaturity() {
      this.$router.push('/maturity')
    },
    async refreshData() {
      this.refreshing = true
      try {
        const [sensorRes, deviceRes, alertRes, historyRes] = await Promise.all([
          fetch('/api/sensors'),
          fetch('/api/devices'),
          fetch('/api/alerts'),
          fetch('/api/history?period=day')
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
        if (history.success) this.temperatureData = history.data.slice(-12).map((item) => Math.max(36, Math.min(92, item.temperature * 3)))
        this.systemOnline = true
      } catch (error) {
        console.error(error)
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
    showMetricDetail(metric) {
      window.alert(`${metric.label}\n当前值: ${metric.value}\n${metric.range}\n趋势: ${metric.trendText}`)
    },
    handleAlarmClick(alarm) {
      window.alert(`${alarm.title}\n${alarm.description}`)
    },
    acknowledgeAlarm(alarm) {
      this.alarms = this.alarms.filter((item) => item.id !== alarm.id)
    },
    clearAlarms() {
      this.alarms = []
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
    getThinkingPreview(reasoning, summary) {
      const compact = String(reasoning || '').replace(/\s+/g, ' ').trim()
      if (compact) return compact.length > 90 ? compact.slice(-90) : compact
      if (summary?.detections && summary.detections.length > 0) {
        const names = summary.detections.map((d) => d.class_name || d.disease_name).join('、')
        return `检测到: ${names}`
      }
      if (summary?.detection_count === 0) return '未检测到有效草莓目标'
      if (summary?.decision_message) return `初步结论：${summary.decision_message}`
      return 'Qwen 正在结合检测结果进行推理...'
    },
    getThinkingStages(message) {
      const status = message.status || 'queued'
      const hasDetections = this.detectionMode || (message.contextSummary && message.contextSummary.detections)
      if (hasDetections) {
        return [
          { label: 'YOLO检测', state: status === 'detecting' ? 'active' : ['ready', 'thinking', 'answering', 'done'].includes(status) ? 'done' : 'todo' },
          { label: '分析成熟度', state: status === 'thinking' ? 'active' : ['answering', 'done'].includes(status) ? 'done' : 'todo' },
          { label: '生成回复', state: status === 'answering' ? 'active' : status === 'done' ? 'done' : 'todo' }
        ]
      }
      return [
        { label: '读取上下文', state: ['ready', 'thinking', 'answering', 'done'].includes(status) ? 'done' : 'todo' },
        { label: '分析线索', state: status === 'thinking' ? 'active' : ['answering', 'done'].includes(status) ? 'done' : 'todo' },
        { label: '生成回复', state: status === 'answering' ? 'active' : status === 'done' ? 'done' : 'todo' }
      ]
    },
    getMessageStatusLabel(message) {
      if (message.status === 'detecting') return '正在运行 YOLO 成熟度检测...'
      if (message.status === 'ready') return '检测完成，正在分析成熟度结果'
      if (message.status === 'thinking') return this.currentQwenHint
      if (message.status === 'answering') return '分析完成，正在组织回复'
      return '正在准备上下文'
    },
    getSummaryChips(summary) {
      if (!summary) return []
      if (summary.detections && summary.detections.length > 0) {
        return summary.detections.slice(0, 4).map((d) => ({
          text: `${d.class_name || d.disease_name} ${(d.confidence * 100).toFixed(0)}%`,
          tone: d.confidence > 0.7 ? 'good' : 'info'
        }))
      }
      if (summary.detection_count !== undefined) {
        return [{ text: `检测结果: ${summary.detection_count} 个目标`, tone: summary.detection_count > 0 ? 'good' : 'warn' }]
      }
      const chips = []
      if (summary.harvest === true) chips.push({ text: '可考虑采摘', tone: 'good' })
      if (summary.harvest === false) chips.push({ text: '暂不建议采摘', tone: 'warn' })
      if (summary.fill_light === true) chips.push({ text: '建议补光', tone: 'info' })
      if (summary.manual_review === true) chips.push({ text: '建议人工复核', tone: 'warn' })
      if (summary.confidence_score !== undefined && summary.confidence_score !== null) chips.push({ text: `置信度 ${Number(summary.confidence_score).toFixed(2)}`, tone: 'info' })
      return chips
    },
    consumeSseBuffer(buffer, assistantMessage) {
      const parts = buffer.split('\n\n')
      const remain = parts.pop() || ''
      for (const block of parts) {
        const data = block.split(/\r?\n/).filter((line) => line.startsWith('data: ')).map((line) => line.slice(6)).join('\n')
        if (!data) continue
        const event = JSON.parse(data)
        const maybeError = this.applyStreamEvent(event, assistantMessage)
        if (maybeError) this.qwenError = maybeError
      }
      return remain
    },
    applyStreamEvent(event, assistantMessage) {
      if (event.type === 'status' && event.stage === 'detecting') {
        assistantMessage.status = 'detecting'
      }
      if (event.type === 'ready') {
        assistantMessage.status = 'ready'
        if (event.detections) {
          this.detectionCount = event.detection_count || 0
          this.latestDetections = event.detections || []
          assistantMessage.contextSummary = {
            detection_count: event.detection_count,
            detections: event.detections,
            counts: event.counts
          }
        } else {
          assistantMessage.contextSummary = event.context_summary || null
        }
        this.latestContextSummary = assistantMessage.contextSummary || this.latestContextSummary
      }
      if (event.type === 'thinking' && event.delta) {
        assistantMessage.status = 'thinking'
        assistantMessage.reasoning += event.delta
      }
      if (event.type === 'answer' && event.delta) {
        assistantMessage.status = 'answering'
        assistantMessage.content += event.delta
      }
      if (event.type === 'done') {
        if (!assistantMessage.content && event.reply) assistantMessage.content = event.reply
        assistantMessage.contextSummary = event.context_summary || assistantMessage.contextSummary
        assistantMessage.pending = false
        assistantMessage.status = 'done'
        this.latestContextSummary = assistantMessage.contextSummary || this.latestContextSummary
        if (this.detectionMode) {
          this.removeImage()
        }
      }
      if (event.type === 'error') {
        assistantMessage.pending = false
        assistantMessage.status = 'done'
        return event.error || 'Qwen 流式回答失败'
      }
      return ''
    },
    handleImageSelect(event) {
      const file = event.target.files?.[0]
      if (!file) return
      this.setSelectedImage(file)
    },
    handleImageDrop(event) {
      const file = event.dataTransfer?.files?.[0]
      if (!file) return
      this.setSelectedImage(file)
    },
    setSelectedImage(file) {
      if (!/\.(jpe?g|png|bmp|tiff?|webp)$/i.test(file.name)) {
        window.alert('仅支持 jpg、png、bmp、tif、webp 格式的图片')
        return
      }
      this.selectedImage = file
      this.detectionCount = 0
      this.latestDetections = []
      this.detectionMode = true
      const reader = new FileReader()
      reader.onload = (e) => {
        this.selectedImagePreview = e.target.result
      }
      reader.readAsDataURL(file)
    },
    removeImage() {
      this.selectedImage = null
      this.selectedImagePreview = ''
      this.detectionCount = 0
      this.latestDetections = []
      this.detectionMode = false
      if (this.$refs.imageInput) {
        this.$refs.imageInput.value = ''
      }
    },
    async sendQwenMessage() {
      const content = this.qwenInput.trim()
      if ((!content && !this.selectedImage) || this.qwenLoading) return
      const userContent = content || '请分析这张图片中的草莓成熟度情况'
      const hasImage = !!this.selectedImage
      const userMessage = { id: `u-${Date.now()}`, role: 'user', content: userContent, pending: false, reasoning: '', status: 'done', contextSummary: null, timestamp: new Date() }
      const assistantMessage = { id: `a-${Date.now()}`, role: 'assistant', content: '', pending: true, reasoning: '', status: 'queued', contextSummary: null, timestamp: new Date() }
      const messages = [...this.qwenMessages, userMessage].map((item) => ({ role: item.role, content: item.content }))
      this.qwenMessages.push(userMessage, assistantMessage)
      this.qwenInput = ''
      this.qwenLoading = true
      this.qwenError = ''
      this.startQwenTicker()
      this.scrollChat()

      const apiPath = hasImage ? '/api/detect/chat/stream' : '/api/qwen/chat/stream'
      let body
      let headers = {}

      if (hasImage) {
        const form = new FormData()
        form.append('image', this.selectedImage)
        form.append('message', userContent)
        form.append('messages', JSON.stringify(messages))
        body = form
      } else {
        headers['Content-Type'] = 'application/json'
        body = JSON.stringify({ message: userContent, messages, imageId: this.qwenSession.imageId, plotId: this.qwenSession.plotId, plantBatchId: this.qwenSession.plantBatchId })
      }

      try {
        const response = await fetch(apiPath, { method: 'POST', headers, body })
        if (!response.ok || !response.body) throw new Error(hasImage ? '成熟度分析服务暂时无法响应' : 'Qwen 暂时无法回答')
        const reader = response.body.getReader()
        const decoder = new TextDecoder('utf-8')
        let buffer = ''
        while (true) {
          const { value, done } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          buffer = this.consumeSseBuffer(buffer, assistantMessage)
          this.scrollChat()
        }
        buffer += decoder.decode()
        if (buffer.trim()) this.consumeSseBuffer(buffer, assistantMessage)
        assistantMessage.pending = false
      } catch (error) {
        assistantMessage.pending = false
        assistantMessage.status = 'done'
        this.qwenError = error.message || 'Qwen 接入失败'
      } finally {
        this.qwenLoading = false
        this.stopQwenTicker()
        this.scrollChat()
      }
    }
  }
}
</script>

<style scoped>
.page{min-height:100vh;background:linear-gradient(135deg,#06111d,#0a1d31 55%,#07131f);color:#eef8ff;font-family:'Microsoft YaHei','PingFang SC',sans-serif}
.topbar,.topbar-right,.section-head,.periods,.composer-row,.chips{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.topbar{justify-content:space-between;padding:20px 24px;background:rgba(7,18,32,.82);border-bottom:1px solid rgba(140,194,255,.14)}
.content{padding:20px;display:grid;gap:16px}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}
.grid,.chat-layout{display:grid;grid-template-columns:1.35fr 1fr;gap:16px}
.card{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);border-radius:20px;padding:18px;box-shadow:0 18px 42px rgba(2,10,20,.26)}
.eyebrow,.muted{color:#a7c7e5}.eyebrow{margin:0 0 4px;font-size:.78rem;letter-spacing:.12em;text-transform:uppercase}
h1,h2,h3,p{margin:0}.pill,.chip,.primary,.ghost{border:none;border-radius:999px}.pill{padding:8px 12px;background:rgba(255,255,255,.08)}.pill.off{background:rgba(255,115,87,.14);color:#ffb8aa}.pill.live{background:rgba(65,191,255,.16);color:#a3deff}
.primary,.ghost{padding:10px 14px;font-weight:700;cursor:pointer}.primary{background:linear-gradient(135deg,#65d6ff,#4d86ff);color:#041224}.ghost{background:rgba(255,255,255,.08);color:#eef7ff}.ghost.active{background:rgba(80,177,255,.2);color:#a6deff}.ghost.small{padding:6px 10px;font-size:.8rem}.ghost.block{width:100%;text-align:left}
.metric{cursor:pointer}.metric-head,.bubble-head,.row{display:flex;justify-content:space-between;gap:12px}.metric-value{display:block;margin:12px 0 8px;font-size:2rem}.trend{margin-top:10px}.trend.ok,.chip.good{color:#a7f2bd}.trend.warn,.chip.warn{color:#ffd18c}.chip.info{color:#9fdcff}
.chart{height:220px;display:flex;align-items:flex-end;gap:10px;padding:16px;border-radius:16px;background:rgba(0,0,0,.16)}.bar{flex:1;min-height:18px;border-radius:999px 999px 6px 6px;background:linear-gradient(180deg,#60d8ff,#357dff)}
.gauge{min-height:220px;display:grid;place-items:center}.gauge-ring{width:210px;height:210px;padding:16px;border-radius:50%;display:grid;place-items:center}.gauge-core{width:100%;height:100%;border-radius:50%;display:grid;place-items:center;background:#081423;text-align:center}
.stack{display:grid;gap:12px;margin-top:14px}.row,.thinking,.side,.empty{background:rgba(5,15,27,.52);border:1px solid rgba(255,255,255,.07);border-radius:16px;padding:14px}.alarm{cursor:pointer}
.switch{position:relative;display:inline-block;width:52px;height:28px}.switch input{opacity:0;width:0;height:0}.slider{position:absolute;inset:0;border-radius:999px;background:rgba(255,255,255,.18)}.slider:before{content:'';position:absolute;left:4px;top:4px;width:20px;height:20px;border-radius:50%;background:#fff;transition:transform .2s ease}input:checked + .slider{background:rgba(88,214,141,.72)}input:checked + .slider:before{transform:translateX(24px)}
.chat{max-height:460px;overflow-y:auto;display:flex;flex-direction:column;gap:12px}.bubble{max-width:86%;padding:14px 16px;border-radius:18px;border:1px solid rgba(255,255,255,.08)}.bubble.assistant{align-self:flex-start;background:rgba(56,121,255,.12)}.bubble.user{align-self:flex-end;background:rgba(68,178,110,.13)}.bubble.pending{border-color:rgba(111,198,255,.32)}
.thinking{margin-top:10px;padding:12px}.thinking-title{display:flex;align-items:center;gap:10px;color:#bce7ff}.chips{margin-top:10px}.chip{padding:6px 10px;background:rgba(255,255,255,.07)}.chip.active{background:rgba(75,190,255,.18);color:#b8ebff}.chip.done{background:rgba(87,221,145,.15);color:#a6efc1}
.message{margin-top:12px;white-space:pre-wrap;line-height:1.72}.cursor{display:inline-block;width:8px;height:1em;margin-left:3px;vertical-align:middle;border-radius:2px;background:#9fe0ff;animation:blink .9s infinite}.dots{display:inline-flex;gap:4px}.dots span{width:7px;height:7px;border-radius:50%;background:#7bd5ff;animation:bounce 1.1s infinite ease-in-out}.dots span:nth-child(2){animation-delay:.15s}.dots span:nth-child(3){animation-delay:.3s}
.side{height:fit-content}.divider{height:1px;background:rgba(255,255,255,.08);margin:14px 0}.composer{display:grid;gap:12px;margin-top:14px}.composer textarea{width:100%;min-height:108px;padding:14px 16px;border-radius:16px;border:1px solid rgba(255,255,255,.12);background:rgba(3,12,24,.56);color:#f3fbff;resize:vertical}.composer-row{justify-content:space-between}.error{padding:12px 14px;border-radius:14px;background:rgba(255,115,87,.12);color:#ffc0b2}
@keyframes bounce{0%,80%,100%{transform:translateY(0);opacity:.6}40%{transform:translateY(-4px);opacity:1}}@keyframes blink{0%,45%{opacity:1}55%,100%{opacity:.2}}
.upload-section{margin-top:14px}.upload-zone{display:flex;flex-direction:column;align-items:center;gap:8px;padding:20px;border:2px dashed rgba(255,255,255,.14);border-radius:16px;cursor:pointer;transition:border-color .2s ease}.upload-zone:hover{border-color:rgba(111,198,255,.42)}.upload-icon{font-size:1.8rem;color:#8cc4ff}.image-preview-row{display:flex;align-items:center;gap:14px;padding:12px;border:1px solid rgba(255,255,255,.1);border-radius:16px;background:rgba(5,15,27,.52)}.image-thumb{width:68px;height:68px;border-radius:12px;background-size:cover;background-position:center;border:1px solid rgba(255,255,255,.14);flex-shrink:0}.image-info{flex:1;min-width:0}.upload-label{font-weight:600}.detection-chips{margin-top:6px;display:flex;gap:6px;flex-wrap:wrap}
@media (max-width:1080px){.grid,.chat-layout{grid-template-columns:1fr}}@media (max-width:720px){.topbar{flex-direction:column;align-items:flex-start}.content{padding:16px}.bubble{max-width:100%}.composer-row{flex-direction:column;align-items:stretch}.image-preview-row{flex-direction:column;align-items:stretch}}
</style>
