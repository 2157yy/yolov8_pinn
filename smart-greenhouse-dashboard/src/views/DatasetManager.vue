<template>
  <div class="page">
    <header class="topbar">
      <div>
        <p class="eyebrow">Dataset Management</p>
        <h1>草莓成熟度数据集统一管理</h1>
        <p class="muted">导入公开 YOLO 数据集 · 统一映射 halfripe / ripe / unripe · MySQL 持久化</p>
      </div>
      <div class="topbar-right">
        <span class="pill" :class="{ live: storageInfo.mysqlEnabled }">{{ storageInfo.mysqlEnabled ? 'MySQL 已启用' : '内存模式' }}</span>
        <button class="ghost" @click="goToDashboard">回到主监控台</button>
        <button class="primary" @click="goToMaturity">回到成熟度检测</button>
      </div>
    </header>

    <main class="content">
      <section class="stats-grid">
        <article class="card stat-card">
          <p class="eyebrow">Storage</p>
          <strong>{{ storageInfo.storageMode || 'unknown' }}</strong>
          <span class="muted">数据库模式</span>
        </article>
        <article class="card stat-card">
          <p class="eyebrow">Datasets</p>
          <strong>{{ storageInfo.datasetCount || 0 }}</strong>
          <span class="muted">已导入数据集</span>
        </article>
        <article class="card stat-card">
          <p class="eyebrow">Samples</p>
          <strong>{{ storageInfo.sampleCount || 0 }}</strong>
          <span class="muted">统一样本数</span>
        </article>
        <article class="card stat-card">
          <p class="eyebrow">Active</p>
          <strong>#{{ storageInfo.activeDatasetId || '—' }}</strong>
          <span class="muted">当前启用数据集</span>
        </article>
      </section>

      <section class="grid">
        <article class="card">
          <div class="section-head">
            <div>
              <p class="eyebrow">Import</p>
              <h2>导入公开草莓成熟度数据集</h2>
            </div>
            <span class="pill" :class="{ live: importing }">{{ importing ? '导入中...' : '等待导入' }}</span>
          </div>

          <div class="import-form">
            <label>
              <span>数据集名称</span>
              <input v-model="form.name" type="text" placeholder="公开草莓成熟度 YOLO 数据集" />
            </label>
            <label>
              <span>本地文件夹</span>
              <input ref="folderInput" type="file" webkitdirectory directory multiple @change="handleFolderSelect" />
              <small class="muted">选择包含 data.yaml / images / labels 的本地数据集文件夹</small>
            </label>
            <label>
              <span>来源链接</span>
              <input v-model="form.sourceUrl" type="text" placeholder="https://github.com/..." />
            </label>
            <label>
              <span>类名列表</span>
              <textarea v-model="form.classNamesText" rows="3" placeholder="unripe,partially_ripe,fully_ripe"></textarea>
            </label>
            <label>
              <span>统一映射</span>
              <textarea v-model="form.classAliasesText" rows="5" placeholder='{"partially_ripe":"halfripe","fully_ripe":"ripe"}'></textarea>
            </label>
            <label>
              <span>说明</span>
              <textarea v-model="form.description" rows="3" placeholder="可填写来源、数据规模、许可说明等"></textarea>
            </label>

            <div class="import-actions">
              <button class="ghost" :disabled="importing" @click="fillPreset">套用预设</button>
              <button class="primary" :disabled="importing" @click="importDataset">{{ importing ? '导入中...' : '开始导入' }}</button>
            </div>
          </div>

          <div v-if="error" class="error">{{ error }}</div>
          <div v-if="message" class="message">{{ message }}</div>
        </article>

        <article class="card">
          <div class="section-head">
            <div>
              <p class="eyebrow">Presets</p>
              <h2>公开数据集预设</h2>
            </div>
            <button class="ghost small" @click="refreshAll">刷新</button>
          </div>

          <div class="preset-list">
            <button
              v-for="preset in presets"
              :key="preset.id"
              class="preset-item"
              :class="{ active: selectedPresetId === preset.id }"
              @click="selectPreset(preset)"
            >
              <div class="preset-head">
                <strong>{{ preset.name }}</strong>
                <span class="pill">{{ preset.sourceType }}</span>
              </div>
              <div class="muted">{{ preset.description }}</div>
              <div class="chip-row">
                <span v-for="cls in preset.canonicalClasses" :key="cls" class="chip">{{ cls }}</span>
              </div>
              <div class="muted small">{{ preset.sourceUrl }}</div>
            </button>
          </div>
        </article>
      </section>

      <section class="card">
        <div class="section-head">
          <div>
            <p class="eyebrow">Registry</p>
            <h2>已导入数据集</h2>
          </div>
          <span class="muted">点击条目查看样本</span>
        </div>

        <div v-if="datasets.length === 0" class="empty">暂无已导入数据集</div>
        <div v-else class="dataset-list">
          <article
            v-for="dataset in datasets"
            :key="dataset.id"
            class="dataset-item"
            :class="{ active: selectedDatasetId === dataset.id }"
            @click="selectDataset(dataset.id)"
          >
            <div class="dataset-head">
              <div>
                <h3>{{ dataset.name }}</h3>
                <div class="muted small">{{ dataset.sourcePath }}</div>
              </div>
              <div class="dataset-badges">
                <span v-if="dataset.active" class="pill live">当前启用</span>
                <span class="pill">{{ dataset.sourceType }}</span>
              </div>
            </div>

            <div class="chip-row">
              <span class="chip good">样本 {{ dataset.sampleCount }}</span>
              <span class="chip info">标注 {{ dataset.annotationCount }}</span>
              <span v-for="(value, key) in dataset.classCounts" :key="key" class="chip">{{ key }} {{ value }}</span>
            </div>

            <div class="muted small">导入时间：{{ formatTime(dataset.lastImportedAt || dataset.createdAt) }}</div>

            <div class="dataset-actions">
              <button class="ghost small" @click.stop="selectDataset(dataset.id)">查看样本</button>
              <button class="primary small" :disabled="dataset.active" @click.stop="activateDataset(dataset.id)">设为启用</button>
            </div>
          </article>
        </div>
      </section>

      <section class="card">
        <div class="section-head">
          <div>
            <p class="eyebrow">Samples</p>
            <h2>统一样本预览</h2>
          </div>
          <span class="muted" v-if="selectedDataset">{{ selectedDataset.name }}</span>
        </div>

        <div v-if="selectedDatasetSamples.length === 0" class="empty">请选择一个数据集查看样本</div>
        <div v-else class="sample-grid">
          <article v-for="sample in selectedDatasetSamples" :key="sample.id" class="sample-card">
            <div class="sample-thumb">
              <img
                v-if="sample.previewUrl"
                class="sample-image"
                :src="sample.previewUrl"
                :alt="sample.relativeImagePath"
                loading="lazy"
              />
              <div v-else class="sample-placeholder">无预览</div>
            </div>
            <div class="sample-body">
              <div class="sample-head">
                <strong>{{ sample.canonicalClassName }}</strong>
                <span class="chip">{{ sample.splitName }}</span>
              </div>
              <div class="muted small">源类名：{{ sample.sourceClassName || '—' }}</div>
              <div class="muted small">标注数：{{ sample.annotationCount }}</div>
              <div class="muted small">文件：{{ sample.relativeImagePath }}</div>
            </div>
          </article>
        </div>
      </section>
    </main>
  </div>
</template>

<script>
export default {
  name: 'DatasetManager',
  data() {
    return {
      storageInfo: {},
      presets: [],
      datasets: [],
      selectedDatasetId: null,
      selectedDataset: null,
      selectedDatasetSamples: [],
      importing: false,
      error: '',
      message: '',
      selectedPresetId: '',
      selectedFolderName: '',
      form: {
        name: '公开草莓成熟度 YOLO 数据集',
        sourcePath: '',
        sourceUrl: 'https://github.com/amitamola/Strawberry-Counting-and-Ripeness-detection',
        classNamesText: 'unripe,partially_ripe,fully_ripe',
        classAliasesText: '{"partially_ripe":"halfripe","fully_ripe":"ripe"}',
        description: '公开草莓成熟度数据集导入到 MySQL，统一映射 halfripe / ripe / unripe。'
      }
    }
  },
  mounted() {
    this.refreshAll()
  },
  methods: {
    async refreshAll() {
      this.error = ''
      this.message = ''
      try {
        const [storageRes, presetRes, datasetRes] = await Promise.all([
          fetch('/api/maturity-datasets/storage'),
          fetch('/api/maturity-datasets/presets'),
          fetch('/api/maturity-datasets')
        ])
        const [storageData, presetData, datasetData] = await Promise.all([
          storageRes.json(),
          presetRes.json(),
          datasetRes.json()
        ])

        if (storageData.success) this.storageInfo = storageData.data || {}
        if (presetData.success) this.presets = presetData.data || []
        if (datasetData.success) this.datasets = datasetData.data || []

        const activeId = this.storageInfo.activeDatasetId || this.datasets.find((item) => item.active)?.id || this.datasets[0]?.id || null
        if (activeId) {
          await this.selectDataset(activeId, { silent: true })
        }
      } catch (error) {
        this.error = error.message || '刷新数据失败'
      }
    },
    goToDashboard() {
      this.$router.push('/dashboard')
    },
    goToMaturity() {
      this.$router.push('/maturity')
    },
    formatTime(value) {
      if (!value) return '—'
      const date = new Date(value)
      if (Number.isNaN(date.getTime())) return String(value)
      return date.toLocaleString('zh-CN', { hour12: false })
    },
    selectPreset(preset) {
      this.selectedPresetId = preset.id
      this.form.name = preset.name
      this.form.sourceUrl = preset.sourceUrl || ''
      this.form.classNamesText = (preset.suggestedClassNames || []).join(',')
      this.form.classAliasesText = JSON.stringify(preset.classAliases || {}, null, 2)
      this.form.description = preset.description || ''
    },
    fillPreset() {
      const preset = this.presets.find((item) => item.id === this.selectedPresetId) || this.presets[0]
      if (preset) this.selectPreset(preset)
    },
    parseClassNames() {
      return this.form.classNamesText
        .split(/[,，\n]/)
        .map((item) => item.trim())
        .filter(Boolean)
    },
    parseClassAliases() {
      if (!this.form.classAliasesText.trim()) return {}
      const parsed = JSON.parse(this.form.classAliasesText)
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('统一映射必须是 JSON 对象')
      }
      return parsed
    },
    handleFolderSelect(event) {
      const files = Array.from(event.target?.files || [])
      if (!files.length) {
        this.form.sourcePath = ''
        this.selectedFolderName = ''
        return
      }

      const firstFile = files[0]
      const relativePath = firstFile.webkitRelativePath || firstFile.name
      const rootName = relativePath.split('/')[0] || firstFile.name
      this.selectedFolderName = rootName
      this.form.sourcePath = rootName
      this.message = `已选择文件夹：${rootName}，共 ${files.length} 个文件`
    },
    async importDataset() {
      this.importing = true
      this.error = ''
      this.message = ''

      try {
        const folderInput = this.$refs.folderInput
        const files = Array.from(folderInput?.files || [])
        const payload = {
          name: this.form.name.trim(),
          sourceUrl: this.form.sourceUrl.trim(),
          classNames: this.parseClassNames(),
          classAliases: this.parseClassAliases(),
          description: this.form.description.trim(),
          sourceType: 'yolo',
          folderName: this.selectedFolderName || this.form.name.trim()
        }

        if (!files.length) {
          throw new Error('请先选择本地数据集文件夹')
        }

        const formData = new FormData()
        formData.append('name', payload.name)
        formData.append('sourceUrl', payload.sourceUrl)
        formData.append('description', payload.description)
        formData.append('sourceType', payload.sourceType)
        formData.append('folderName', payload.folderName)
        formData.append('classNames', JSON.stringify(payload.classNames))
        formData.append('classAliases', JSON.stringify(payload.classAliases))

        for (const file of files) {
          const relativePath = file.webkitRelativePath || file.name
          formData.append('files', file, relativePath)
        }

        const response = await fetch('/api/maturity-datasets/import-folder', {
          method: 'POST',
          body: formData
        })
        const data = await response.json()
        if (!data.success) {
          throw new Error(data.error || '导入失败')
        }

        this.message = `导入完成：${data.data.dataset.name}（样本 ${data.data.sampleCount}，标注 ${data.data.annotationCount}）`
        await this.refreshAll()
        this.selectedDatasetId = data.data.dataset.id
        await this.selectDataset(data.data.dataset.id)
        if (folderInput) folderInput.value = ''
        this.selectedFolderName = ''
      } catch (error) {
        this.error = error.message || '导入失败'
      } finally {
        this.importing = false
      }
    },
    async selectDataset(datasetId, { silent = false } = {}) {
      if (!datasetId) return
      this.selectedDatasetId = Number(datasetId)
      try {
        const response = await fetch(`/api/maturity-datasets/${datasetId}/samples?limit=12`)
        const data = await response.json()
        if (!data.success) {
          throw new Error(data.error || '加载样本失败')
        }
        this.selectedDataset = data.dataset || null
        this.selectedDatasetSamples = data.data || []
        if (!silent) this.message = `已查看数据集 #${datasetId}`
      } catch (error) {
        this.error = error.message || '加载样本失败'
      }
    },
    async activateDataset(datasetId) {
      try {
        const response = await fetch(`/api/maturity-datasets/${datasetId}/activate`, { method: 'POST' })
        const data = await response.json()
        if (!data.success) {
          throw new Error(data.error || '启用失败')
        }
        this.message = `已启用数据集 #${datasetId}`
        await this.refreshAll()
      } catch (error) {
        this.error = error.message || '启用失败'
      }
    }
  }
}
</script>

<style scoped>
.page{min-height:100vh;background:linear-gradient(135deg,#06111d,#0a1d31 55%,#07131f);color:#eef8ff;font-family:'Microsoft YaHei','PingFang SC',sans-serif}
.topbar,.topbar-right,.section-head,.stats-grid,.chip-row,.dataset-head,.dataset-actions,.sample-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.topbar{justify-content:space-between;padding:20px 24px;background:rgba(7,18,32,.82);border-bottom:1px solid rgba(140,194,255,.14)}
.content{padding:20px;display:grid;gap:16px;max-width:1280px;margin:0 auto}
.card{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);border-radius:20px;padding:18px;box-shadow:0 18px 42px rgba(2,10,20,.26)}
.eyebrow,.muted{color:#a7c7e5}
.eyebrow{margin:0 0 4px;font-size:.78rem;letter-spacing:.12em;text-transform:uppercase}
h1,h2,h3,p{margin:0}
.pill{border:none;border-radius:999px;padding:8px 12px;background:rgba(255,255,255,.08)}
.pill.live{background:rgba(65,191,255,.16);color:#a3deff}
.primary,.ghost{padding:10px 14px;border:none;border-radius:999px;font-weight:700;cursor:pointer}
.primary{background:linear-gradient(135deg,#65d6ff,#4d86ff);color:#041224}
.ghost{background:rgba(255,255,255,.08);color:#eef7ff}
.ghost.small,.primary.small{padding:6px 10px;font-size:.82rem}
.stat-card{min-width:170px;display:grid;gap:6px}
.stat-card strong{font-size:1.6rem}
.grid{display:grid;grid-template-columns:1.2fr .8fr;gap:16px}
.import-form{display:grid;gap:12px;margin-top:14px}
.import-form label{display:grid;gap:6px}
.import-form input,.import-form textarea{width:100%;padding:12px 14px;border-radius:14px;border:1px solid rgba(255,255,255,.12);background:rgba(3,12,24,.56);color:#f3fbff;resize:vertical}
.import-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:8px}
.preset-list{display:grid;gap:12px;margin-top:14px}
.preset-item{width:100%;text-align:left;padding:14px;border-radius:16px;border:1px solid rgba(255,255,255,.08);background:rgba(5,15,27,.38);color:#eef8ff;cursor:pointer;transition:border-color .2s ease}
.preset-item:hover,.preset-item.active{border-color:#6fc6ff6b}
.preset-head{display:flex;justify-content:space-between;align-items:center;gap:10px}
.small{font-size:.82rem}
.chip{border:none;border-radius:999px;padding:6px 10px;background:rgba(255,255,255,.07);display:inline-block}
.chip.good{background:rgba(87,221,145,.15);color:#a6efc1}
.chip.info{background:rgba(111,198,255,.16);color:#9fdcff}
.dataset-list{display:grid;gap:12px;margin-top:14px}
.dataset-item{padding:16px;border-radius:18px;background:rgba(5,15,27,.4);border:1px solid rgba(255,255,255,.08);cursor:pointer;transition:border-color .2s ease}
.dataset-item:hover,.dataset-item.active{border-color:#6fc6ff6b}
.dataset-head{justify-content:space-between}
.dataset-badges{display:flex;gap:8px;flex-wrap:wrap}
.dataset-actions{justify-content:flex-end;margin-top:10px}
.sample-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px;margin-top:14px}
.sample-card{display:grid;gap:10px;padding:12px;border-radius:16px;background:rgba(5,15,27,.38);border:1px solid rgba(255,255,255,.08)}
.sample-thumb{width:100%;aspect-ratio:4/3;border-radius:12px;background-color:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);overflow:hidden}
.sample-image{width:100%;height:100%;object-fit:cover;display:block}
.sample-placeholder{width:100%;height:100%;display:grid;place-items:center;color:#a7c7e5}
.sample-body{display:grid;gap:6px}
.empty{padding:32px;text-align:center;color:#a7c7e5;background:rgba(5,15,27,.32);border-radius:14px}
.error{padding:12px 14px;border-radius:14px;background:rgba(255,115,87,.12);color:#ffc0b2;margin-top:12px}
.message{padding:12px 14px;border-radius:14px;background:rgba(87,221,145,.12);color:#bff2d0;margin-top:12px}
@media (max-width:980px){.grid{grid-template-columns:1fr}.topbar{flex-direction:column;align-items:flex-start}.topbar-right{width:100%}}
@media (max-width:640px){.content{padding:16px}.dataset-actions{justify-content:flex-start}.preset-head{flex-direction:column;align-items:flex-start}}
</style>
