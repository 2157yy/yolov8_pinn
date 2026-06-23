import cors from 'cors'
import express from 'express'
import fs from 'fs'
import multer from 'multer'
import path from 'path'
import { spawn } from 'child_process'
import { fileURLToPath } from 'url'

const app = express()
const port = Number(process.env.PORT || 3000)
const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const projectRoot = path.resolve(__dirname, '..')
const distDir = path.join(__dirname, 'dist')
const qwenBridgeScript = path.join(projectRoot, 'qwen_web_chat.py')
const detectBridgeScript = path.join(projectRoot, 'detect_bridge.py')
const detectChatBridgeScript = path.join(projectRoot, 'detect_chat_bridge.py')
const maturityBridgeScript = path.join(projectRoot, 'strawberry_maturity_bridge.py')
const pythonCandidates = process.env.PYTHON_COMMAND
  ? [process.env.PYTHON_COMMAND]
  : process.platform === 'win32'
    ? ['py', 'python']
    : ['python3', 'python']

const uploadDir = path.join(projectRoot, 'uploads')
if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir, { recursive: true })
}

const storage = multer.diskStorage({
  destination: uploadDir,
  filename(_req, file, cb) {
    const ext = path.extname(file.originalname) || '.jpg'
    const name = `${Date.now()}-${Math.round(Math.random() * 1e9)}${ext}`
    cb(null, name)
  }
})

const upload = multer({
  storage,
  limits: { fileSize: 16 * 1024 * 1024 },
  fileFilter(_req, file, cb) {
    const allowed = /\.(jpe?g|png|bmp|tiff?|webp)$/i
    if (!allowed.test(path.extname(file.originalname))) {
      cb(new Error('Unsupported image format'))
      return
    }
    cb(null, true)
  }
})

app.use(cors())
app.use(express.json({ limit: '1mb' }))

function safeJsonParse(value, fallback) {
  if (typeof value === 'string') {
    try { return JSON.parse(value) } catch (_) { return fallback }
  }
  if (Array.isArray(value) || (value && typeof value === 'object')) return value
  return fallback
}

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

function sendSseEvent(res, event) {
  res.write(`data: ${JSON.stringify(event)}\n\n`)
}

// ---------------------------------------------------------------------------
// Qwen bridge helpers
// ---------------------------------------------------------------------------

function spawnPython(command, payload) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, [qwenBridgeScript], {
      cwd: projectRoot,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
    })

    let stdout = ''
    let stderr = ''
    const timer = setTimeout(() => {
      child.kill()
      reject(new Error(`Qwen bridge timed out while using ${command}`))
    }, 180000)

    child.stdout.on('data', (chunk) => { stdout += chunk.toString() })
    child.stderr.on('data', (chunk) => { stderr += chunk.toString() })

    child.on('error', (error) => {
      clearTimeout(timer)
      reject(error)
    })

    child.on('close', (code) => {
      clearTimeout(timer)
      if (code !== 0 && !stdout.trim()) {
        reject(new Error(stderr.trim() || `${command} exited with code ${code}`))
        return
      }
      try {
        const parsed = JSON.parse(stdout || '{}')
        if (!parsed.success) {
          reject(new Error(parsed.error || 'Qwen bridge returned an unknown error'))
          return
        }
        resolve(parsed)
      } catch (error) {
        reject(new Error(`Unable to parse Qwen bridge output from ${command}: ${stdout || stderr || error.message}`))
      }
    })

    child.stdin.write(JSON.stringify(payload))
    child.stdin.end()
  })
}

async function runQwenBridge(payload) {
  const errors = []
  for (const command of pythonCandidates) {
    try { return await spawnPython(command, payload) }
    catch (error) { errors.push(`${command}: ${error.message}`) }
  }
  throw new Error(errors.join(' | '))
}

function streamWithPython(command, payload, req, res) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, [qwenBridgeScript], {
      cwd: projectRoot,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
    })

    let stderr = ''
    let stdoutBuffer = ''
    let settled = false
    const timer = setTimeout(() => {
      child.kill()
      reject(new Error(`Qwen bridge timed out while using ${command}`))
    }, 180000)

    const cleanup = () => {
      clearTimeout(timer)
      req.off('close', handleClose)
    }
    const handleClose = () => { child.kill() }
    req.on('close', handleClose)

    child.stdout.on('data', (chunk) => {
      stdoutBuffer += chunk.toString()
      const lines = stdoutBuffer.split(/\r?\n/)
      stdoutBuffer = lines.pop() || ''
      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed) continue
        try { sendSseEvent(res, JSON.parse(trimmed)) }
        catch (_error) { sendSseEvent(res, { type: 'error', error: `Unable to parse streaming chunk from ${command}: ${trimmed}` }) }
      }
    })

    child.stderr.on('data', (chunk) => { stderr += chunk.toString() })

    child.on('error', (error) => {
      if (settled) return
      settled = true; cleanup(); reject(error)
    })

    child.on('close', (code) => {
      if (settled) return
      settled = true; cleanup()
      const finalChunk = stdoutBuffer.trim()
      if (finalChunk) {
        try { sendSseEvent(res, JSON.parse(finalChunk)) }
        catch (_error) { sendSseEvent(res, { type: 'error', error: `Unable to parse final streaming chunk from ${command}: ${finalChunk}` }) }
      }
      if (code !== 0) {
        reject(new Error(stderr.trim() || `${command} exited with code ${code}`))
        return
      }
      resolve()
    })

    child.stdin.write(JSON.stringify({ ...payload, stream: true }))
    child.stdin.end()
  })
}

async function runQwenBridgeStream(payload, req, res) {
  const errors = []
  for (const command of pythonCandidates) {
    try { await streamWithPython(command, payload, req, res); return }
    catch (error) { errors.push(`${command}: ${error.message}`) }
  }
  sendSseEvent(res, { type: 'error', error: errors.join(' | ') })
}

// ---------------------------------------------------------------------------
// Detect bridge helpers
// ---------------------------------------------------------------------------

async function spawnDetectBridge(payload, command) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, [detectBridgeScript], {
      cwd: projectRoot,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
    })

    let stdout = ''
    let stderr = ''
    const timer = setTimeout(() => {
      child.kill()
      reject(new Error(`Detect bridge timed out using ${command}`))
    }, 120000)

    child.stdout.on('data', (chunk) => { stdout += chunk.toString() })
    child.stderr.on('data', (chunk) => { stderr += chunk.toString() })

    child.on('error', (error) => { clearTimeout(timer); reject(error) })

    child.on('close', (code) => {
      clearTimeout(timer)
      if (code !== 0 && !stdout.trim()) {
        reject(new Error(stderr.trim() || `${command} exited with code ${code}`))
        return
      }
      try {
        const parsed = JSON.parse(stdout || '{}')
        if (!parsed.success) {
          reject(new Error(parsed.error || 'Detect bridge returned an unknown error'))
          return
        }
        resolve(parsed)
      } catch (error) {
        reject(new Error(`Unable to parse detect bridge output from ${command}: ${stdout || stderr || error.message}`))
      }
    })

    child.stdin.write(JSON.stringify(payload))
    child.stdin.end()
  })
}

async function runDetectBridge(payload) {
  const errors = []
  for (const command of pythonCandidates) {
    try { return await spawnDetectBridge(payload, command) }
    catch (error) { errors.push(`${command}: ${error.message}`) }
  }
  throw new Error(errors.join(' | '))
}

// ---------------------------------------------------------------------------
// Detect + Chat bridge helpers
// ---------------------------------------------------------------------------

async function spawnDetectChatBridge(payload, command) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, [detectChatBridgeScript], {
      cwd: projectRoot,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
    })

    let stdout = ''
    let stderr = ''
    const timer = setTimeout(() => {
      child.kill()
      reject(new Error(`Detect chat bridge timed out using ${command}`))
    }, 180000)

    child.stdout.on('data', (chunk) => { stdout += chunk.toString() })
    child.stderr.on('data', (chunk) => { stderr += chunk.toString() })

    child.on('error', (error) => { clearTimeout(timer); reject(error) })

    child.on('close', (code) => {
      clearTimeout(timer)
      if (code !== 0 && !stdout.trim()) {
        reject(new Error(stderr.trim() || `${command} exited with code ${code}`))
        return
      }
      try {
        const parsed = JSON.parse(stdout || '{}')
        if (!parsed.success) {
          reject(new Error(parsed.error || 'Detect chat bridge returned an unknown error'))
          return
        }
        resolve(parsed)
      } catch (error) {
        reject(new Error(`Unable to parse detect chat bridge output from ${command}: ${stdout || stderr || error.message}`))
      }
    })

    child.stdin.write(JSON.stringify(payload))
    child.stdin.end()
  })
}

async function runDetectChatBridge(payload) {
  const errors = []
  for (const command of pythonCandidates) {
    try { return await spawnDetectChatBridge(payload, command) }
    catch (error) { errors.push(`${command}: ${error.message}`) }
  }
  throw new Error(errors.join(' | '))
}

function streamDetectChatBridge(payload, command, req, res) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, [detectChatBridgeScript], {
      cwd: projectRoot,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
    })

    let stderr = ''
    let stdoutBuffer = ''
    let settled = false
    const timer = setTimeout(() => {
      child.kill()
      reject(new Error(`Detect chat bridge timed out using ${command}`))
    }, 180000)

    const cleanup = () => {
      clearTimeout(timer)
      req.off('close', handleClose)
    }
    const handleClose = () => { child.kill() }
    req.on('close', handleClose)

    child.stdout.on('data', (chunk) => {
      stdoutBuffer += chunk.toString()
      const lines = stdoutBuffer.split(/\r?\n/)
      stdoutBuffer = lines.pop() || ''
      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed) continue
        try { sendSseEvent(res, JSON.parse(trimmed)) }
        catch (_error) { sendSseEvent(res, { type: 'error', error: `Unable to parse streaming chunk from ${command}: ${trimmed}` }) }
      }
    })

    child.stderr.on('data', (chunk) => { stderr += chunk.toString() })

    child.on('error', (error) => {
      if (settled) return
      settled = true; cleanup(); reject(error)
    })

    child.on('close', (code) => {
      if (settled) return
      settled = true; cleanup()
      const finalChunk = stdoutBuffer.trim()
      if (finalChunk) {
        try { sendSseEvent(res, JSON.parse(finalChunk)) }
        catch (_error) { sendSseEvent(res, { type: 'error', error: `Unable to parse final streaming chunk from ${command}: ${finalChunk}` }) }
      }
      if (code !== 0) {
        reject(new Error(stderr.trim() || `${command} exited with code ${code}`))
        return
      }
      resolve()
    })

    child.stdin.write(JSON.stringify({ ...payload, stream: true }))
    child.stdin.end()
  })
}

async function runDetectChatBridgeStream(payload, req, res) {
  const errors = []
  for (const command of pythonCandidates) {
    try { await streamDetectChatBridge(payload, command, req, res); return }
    catch (error) { errors.push(`${command}: ${error.message}`) }
  }
  sendSseEvent(res, { type: 'error', error: errors.join(' | ') })
}

// ===========================================================================
// API Routes
// ===========================================================================

app.get('/api/health', (_req, res) => {
  res.json({ success: true, message: 'smart-greenhouse-dashboard server is running' })
})

// -- Qwen status -----------------------------------------------------------

app.get('/api/qwen/status', (_req, res) => {
  res.json({
    success: true,
    data: { pythonCandidates, qwenBridgeScript }
  })
})

// -- Qwen chat -------------------------------------------------------------

app.post('/api/qwen/chat', async (req, res) => {
  const message = String(req.body?.message || '').trim()
  const messages = Array.isArray(req.body?.messages) ? req.body.messages : []
  if (!message && messages.length === 0) {
    res.status(400).json({ success: false, error: 'message is required' })
    return
  }
  try {
    const response = await runQwenBridge({
      message, messages,
      image_id: req.body?.imageId,
      plot_id: req.body?.plotId,
      plant_batch_id: req.body?.plantBatchId,
      storage_path: req.body?.storagePath
    })
    res.json(response)
  } catch (error) {
    res.status(500).json({ success: false, error: error.message })
  }
})

app.post('/api/qwen/chat/stream', async (req, res) => {
  const message = String(req.body?.message || '').trim()
  const messages = Array.isArray(req.body?.messages) ? req.body.messages : []
  if (!message && messages.length === 0) {
    res.status(400).json({ success: false, error: 'message is required' })
    return
  }
  res.setHeader('Content-Type', 'text/event-stream; charset=utf-8')
  res.setHeader('Cache-Control', 'no-cache, no-transform')
  res.setHeader('Connection', 'keep-alive')
  res.setHeader('X-Accel-Buffering', 'no')
  res.flushHeaders?.()
  await runQwenBridgeStream(
    { message, messages,
      image_id: req.body?.imageId,
      plot_id: req.body?.plotId,
      plant_batch_id: req.body?.plantBatchId,
      storage_path: req.body?.storagePath },
    req, res
  )
  res.end()
})

// -- YOLO detection --------------------------------------------------------

app.post('/api/detect', upload.single('image'), async (req, res) => {
  if (!req.file) {
    res.status(400).json({ success: false, error: 'No image file uploaded' })
    return
  }
  const imagePath = req.file.path
  const runPipeline = req.body.run_pipeline === 'true' || req.body.run_pipeline === true
  try {
    const response = await runDetectBridge({
      image_path: imagePath,
      model_path: req.body.model_path || 'models/yolov8s-seg.pt',
      conf_threshold: Number(req.body.conf_threshold) || 0.25,
      run_pipeline: runPipeline,
      metadata: {
        image_id: req.body.image_id || req.file.originalname,
        plot_id: req.body.plot_id,
        plant_batch_id: req.body.plant_batch_id
      }
    })
    fs.unlink(imagePath, () => {})
    res.json(response)
  } catch (error) {
    fs.unlink(imagePath, () => {})
    res.status(500).json({ success: false, error: error.message })
  }
})

app.post('/api/detect/analyze', upload.single('image'), async (req, res) => {
  if (!req.file) {
    res.status(400).json({ success: false, error: 'No image file uploaded' })
    return
  }
  const imagePath = req.file.path
  try {
    const response = await runDetectBridge({
      image_path: imagePath,
      model_path: req.body.model_path || 'models/yolov8s-seg.pt',
      conf_threshold: Number(req.body.conf_threshold) || 0.25,
      run_pipeline: true,
      metadata: {
        image_id: req.body.image_id || req.file.originalname,
        plot_id: req.body.plot_id,
        plant_batch_id: req.body.plant_batch_id
      }
    })
    fs.unlink(imagePath, () => {})
    res.json(response)
  } catch (error) {
    fs.unlink(imagePath, () => {})
    res.status(500).json({ success: false, error: error.message })
  }
})

// -- Unified detect + Qwen chat --------------------------------------------

app.post('/api/detect/chat', upload.single('image'), async (req, res) => {
  if (!req.file) {
    res.status(400).json({ success: false, error: 'No image file uploaded' })
    return
  }
  const message = String(req.body?.message || '').trim()
  const messages = safeJsonParse(req.body?.messages, [])
  if (!message && messages.length === 0) {
    fs.unlink(req.file.path, () => {})
    res.status(400).json({ success: false, error: 'message is required' })
    return
  }
  const imagePath = req.file.path
  try {
    const response = await runDetectChatBridge({
      image_path: imagePath, message, messages,
      model_path: req.body.model_path || 'models/yolov8s-seg.pt',
      conf_threshold: Number(req.body.conf_threshold) || 0.25
    })
    fs.unlink(imagePath, () => {})
    res.json(response)
  } catch (error) {
    fs.unlink(imagePath, () => {})
    res.status(500).json({ success: false, error: error.message })
  }
})

app.post('/api/detect/chat/stream', upload.single('image'), async (req, res) => {
  if (!req.file) {
    res.status(400).json({ success: false, error: 'No image file uploaded' })
    return
  }
  const message = String(req.body?.message || '').trim()
  const messages = safeJsonParse(req.body?.messages, [])
  if (!message && messages.length === 0) {
    fs.unlink(req.file.path, () => {})
    res.status(400).json({ success: false, error: 'message is required' })
    return
  }
  const imagePath = req.file.path
  res.setHeader('Content-Type', 'text/event-stream; charset=utf-8')
  res.setHeader('Cache-Control', 'no-cache, no-transform')
  res.setHeader('Connection', 'keep-alive')
  res.setHeader('X-Accel-Buffering', 'no')
  res.flushHeaders?.()
  try {
    await runDetectChatBridgeStream(
      { image_path: imagePath, message, messages,
        model_path: req.body.model_path || 'models/yolov8s-seg.pt',
        conf_threshold: Number(req.body.conf_threshold) || 0.25 },
      req, res
    )
  } catch (error) {
    sendSseEvent(res, { type: 'error', error: error.message })
  } finally {
    fs.unlink(imagePath, () => {})
    res.end()
  }
})

// -- Strawberry maturity detection -----------------------------------------

async function spawnMaturityBridge(payload, command) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, [maturityBridgeScript], {
      cwd: projectRoot,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
    })

    let stdout = ''
    let stderr = ''
    const timer = setTimeout(() => {
      child.kill()
      reject(new Error(`Maturity bridge timed out using ${command}`))
    }, 120000)

    child.stdout.on('data', (chunk) => { stdout += chunk.toString() })
    child.stderr.on('data', (chunk) => { stderr += chunk.toString() })

    child.on('error', (error) => { clearTimeout(timer); reject(error) })

    child.on('close', (code) => {
      clearTimeout(timer)
      if (code !== 0 && !stdout.trim()) {
        reject(new Error(stderr.trim() || `${command} exited with code ${code}`))
        return
      }
      try {
        const parsed = JSON.parse(stdout || '{}')
        if (!parsed.success) {
          reject(new Error(parsed.error || 'Maturity bridge returned an unknown error'))
          return
        }
        resolve(parsed)
      } catch (error) {
        reject(new Error(`Unable to parse maturity bridge output from ${command}: ${stdout || stderr || error.message}`))
      }
    })

    child.stdin.write(JSON.stringify(payload))
    child.stdin.end()
  })
}

async function runMaturityBridge(payload) {
  const errors = []
  for (const command of pythonCandidates) {
    try { return await spawnMaturityBridge(payload, command) }
    catch (error) { errors.push(`${command}: ${error.message}`) }
  }
  throw new Error(errors.join(' | '))
}

// -- Strawberry maturity endpoint ------------------------------------------

app.post('/api/maturity', upload.single('image'), async (req, res) => {
  if (!req.file) {
    res.status(400).json({ success: false, error: 'No image file uploaded' })
    return
  }
  const imagePath = req.file.path
  try {
    const response = await runMaturityBridge({
      image_path: imagePath,
      model_path: req.body.model_path || 'models/strawberry_maturity.pt',
      conf_threshold: Number(req.body.conf_threshold) || 0.25
    })
    fs.unlink(imagePath, () => {})
    res.json(response)
  } catch (error) {
    fs.unlink(imagePath, () => {})
    res.status(500).json({ success: false, error: error.message })
  }
})

// -- Sensors / Devices / History / Alerts / Settings -----------------------

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
  res.json({ success: true, data: sensorData, timestamp: new Date().toISOString() })
})

app.get('/api/devices', (_req, res) => {
  res.json({ success: true, data: devices })
})

app.post('/api/devices/:id/control', (req, res) => {
  const deviceId = Number(req.params.id)
  const { action } = req.body
  const device = devices.find((item) => item.id === deviceId)
  if (!device) {
    res.status(404).json({ success: false, message: '设备未找到' })
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
  res.json({ success: true, data: history, period, count: history.length })
})

app.get('/api/alerts', (_req, res) => {
  res.json({
    success: true,
    data: [{
      id: 1, type: 'warning', title: '湿度偏低',
      message: '当前湿度低于设定阈值，建议开启加湿系统。',
      timestamp: new Date(Date.now() - 60 * 60 * 1000).toISOString()
    }]
  })
})

app.get('/api/charts', (req, res) => {
  const period = String(req.query.period || 'day')
  res.json({ success: true, data: buildHistory(period), period })
})

app.get('/api/settings', (_req, res) => {
  res.json({ success: true, data: settings })
})

app.post('/api/settings', (req, res) => {
  settings = { ...settings, ...req.body }
  res.json({ success: true, message: '设置已保存', data: settings })
})

app.get('/api/export', (req, res) => {
  const format = String(req.query.format || 'csv')
  res.json({
    success: true,
    message: `已生成 ${format} 导出任务`,
    data: { format, downloadUrl: `/downloads/greenhouse-export.${format}` }
  })
})

// -- Static & SPA fallback -------------------------------------------------

app.use(express.static(distDir))

app.get(/^\/(?!api\/).*/, (_req, res) => {
  res.sendFile(path.join(distDir, 'index.html'))
})

app.listen(port, () => {
  console.log(`Smart Greenhouse Dashboard is running at http://localhost:${port}`)
  console.log(`API base URL: http://localhost:${port}/api`)
})
