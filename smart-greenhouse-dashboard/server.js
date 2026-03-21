import cors from 'cors'
import express from 'express'
import path from 'path'
import { fileURLToPath } from 'url'

const app = express()
const port = Number(process.env.PORT || 3000)
const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const distDir = path.join(__dirname, 'dist')

app.use(cors())
app.use(express.json())

let sensorData = {
  temperature: 25.3,
  humidity: 68,
  light: 850,
  co2: 420,
  soilMoisture: 45,
  ph: 6.8,
  timestamp: new Date().toISOString()
}

let devices = [
  { id: 1, name: '通风系统', status: true, power: 75 },
  { id: 2, name: '灌溉系统', status: false, power: 0 },
  { id: 3, name: '补光系统', status: true, power: 60 },
  { id: 4, name: '加湿系统', status: false, power: 0 }
]

let settings = {
  refreshInterval: 30,
  tempThreshold: { min: 18, max: 32 },
  enableSoundAlarm: true
}

function buildHistory(period = 'day') {
  const history = []
  const now = new Date()
  let count = 24

  if (period === 'week') count = 7 * 24
  if (period === 'month') count = 30 * 24

  for (let i = count; i > 0; i -= 1) {
    const time = new Date(now.getTime() - i * 3600000)
    history.push({
      time: time.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      date: time.toLocaleDateString('zh-CN'),
      temperature: Number((20 + Math.random() * 10).toFixed(1)),
      humidity: Math.round(50 + Math.random() * 30),
      light: Math.round(500 + Math.random() * 800),
      co2: Math.round(300 + Math.random() * 300),
      status: Math.random() > 0.2 ? 'normal' : 'warning'
    })
  }

  return history
}

app.get('/api/health', (_req, res) => {
  res.json({
    success: true,
    message: 'smart-greenhouse-dashboard server is running'
  })
})

app.get('/api/sensors', (_req, res) => {
  sensorData = {
    ...sensorData,
    temperature: Number((20 + Math.random() * 10).toFixed(1)),
    humidity: Math.round(50 + Math.random() * 30),
    light: Math.round(500 + Math.random() * 800),
    co2: Math.round(300 + Math.random() * 300),
    soilMoisture: Math.round(35 + Math.random() * 30),
    ph: Number((6 + Math.random()).toFixed(1)),
    timestamp: new Date().toISOString()
  }

  res.json({
    success: true,
    data: sensorData,
    timestamp: new Date().toISOString()
  })
})

app.get('/api/devices', (_req, res) => {
  res.json({
    success: true,
    data: devices
  })
})

app.post('/api/devices/:id/control', (req, res) => {
  const deviceId = Number(req.params.id)
  const { action } = req.body
  const device = devices.find((item) => item.id === deviceId)

  if (!device) {
    res.status(404).json({
      success: false,
      message: '设备未找到'
    })
    return
  }

  device.status = action === 'on'
  device.power = device.status ? Math.round(50 + Math.random() * 50) : 0

  res.json({
    success: true,
    message: `设备 ${device.name} 已${device.status ? '开启' : '关闭'}`,
    data: device
  })
})

app.get('/api/history', (req, res) => {
  const period = String(req.query.period || 'day')
  const history = buildHistory(period)

  res.json({
    success: true,
    data: history,
    period,
    count: history.length
  })
})

app.get('/api/alerts', (_req, res) => {
  res.json({
    success: true,
    data: [
      {
        id: 1,
        type: 'warning',
        title: '湿度偏低',
        message: '当前湿度低于设定阈值，建议开启加湿系统。',
        timestamp: new Date(Date.now() - 60 * 60 * 1000).toISOString()
      }
    ]
  })
})

app.get('/api/charts', (req, res) => {
  const period = String(req.query.period || 'day')
  res.json({
    success: true,
    data: buildHistory(period),
    period
  })
})

app.get('/api/settings', (_req, res) => {
  res.json({
    success: true,
    data: settings
  })
})

app.post('/api/settings', (req, res) => {
  settings = {
    ...settings,
    ...req.body
  }

  res.json({
    success: true,
    message: '设置已保存',
    data: settings
  })
})

app.get('/api/export', (req, res) => {
  const format = String(req.query.format || 'csv')
  res.json({
    success: true,
    message: `已生成 ${format} 导出任务`,
    data: {
      format,
      downloadUrl: `/downloads/greenhouse-export.${format}`
    }
  })
})

app.use(express.static(distDir))

app.get(/^\/(?!api\/).*/, (_req, res) => {
  res.sendFile(path.join(distDir, 'index.html'))
})

app.listen(port, () => {
  console.log(`Smart Greenhouse Dashboard is running at http://localhost:${port}`)
  console.log(`API base URL: http://localhost:${port}/api`)
})
