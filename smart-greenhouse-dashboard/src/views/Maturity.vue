<template>
  <div class="page">
    <header class="topbar">
      <div>
        <p class="eyebrow">Strawberry Maturity</p>
        <h1>草莓成熟度检测</h1>
        <p class="muted">单张图片上传 · 三分类成熟度评估 · 标注结果可视化</p>
      </div>
      <div class="topbar-right">
        <span class="muted">{{ currentTime }}</span>
        <button class="primary nav-btn" @click="goToDashboard">跳转至主监控台</button>
      </div>
    </header>

    <main class="content">
      <section class="card upload-card">
        <div class="section-head">
          <div>
            <p class="eyebrow">Upload</p>
            <h2>上传草莓图片</h2>
          </div>
          <span class="pill" :class="{ live: loading }">{{ loading ? '检测中...' : '等待上传' }}</span>
        </div>

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
            <span class="muted">点击或拖拽上传草莓图片进行成熟度检测</span>
            <span class="muted small-desc">支持 JPG、PNG、BMP、TIFF、WebP 格式</span>
          </div>
          <div v-else class="image-preview-card">
            <div class="image-thumb" :style="{ backgroundImage: `url(${selectedImagePreview})` }"></div>
            <div class="image-actions">
              <button class="primary" :disabled="loading" @click="runDetection">{{ loading ? '检测中...' : '开始检测' }}</button>
              <button class="ghost" :disabled="loading" @click="removeImage">移除图片</button>
            </div>
          </div>
        </div>

        <div v-if="error" class="error">{{ error }}</div>
      </section>

      <section v-if="result" class="card result-card">
        <div class="section-head">
          <div>
            <p class="eyebrow">Result</p>
            <h2>检测结果</h2>
          </div>
          <span class="pill good">检测完成</span>
        </div>

        <div class="result-grid">
          <div class="counts-panel">
            <h3>成熟度统计</h3>
            <div class="count-grid">
              <article v-for="item in maturityStats" :key="item.name" class="count-card" :class="item.name">
                <span class="count-label">{{ item.label }}</span>
                <strong class="count-value">{{ item.count }}</strong>
                <span class="muted">{{ item.percentage }}%</span>
                <div class="count-bar"><div class="bar-fill" :style="{ width: item.percentage + '%', background: item.color }"></div></div>
              </article>
            </div>
            <div class="divider"></div>
            <div class="detail-list" v-if="result.detections && result.detections.length > 0">
              <h3>检测详情</h3>
              <div class="detail-item" v-for="(d, idx) in result.detections" :key="idx">
                <span class="chip" :class="d.class_name">{{ d.class_name }}</span>
                <span class="muted">置信度 {{ (d.confidence * 100).toFixed(1) }}%</span>
                <span class="muted">位置 [{{ d.bbox.x1 }}, {{ d.bbox.y1 }}, {{ d.bbox.x2 }}, {{ d.bbox.y2 }}]</span>
              </div>
            </div>
          </div>

          <div class="image-panel">
            <h3>标注结果</h3>
            <div class="annotated-wrapper" v-if="annotatedImageSrc">
              <img :src="annotatedImageSrc" alt="检测结果标注图" class="annotated-image" />
            </div>
            <div v-else class="empty">暂无标注结果</div>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script>
export default {
  name: 'Maturity',
  data() {
    return {
      currentTime: '',
      loading: false,
      error: '',
      selectedImage: null,
      selectedImagePreview: '',
      result: null,
      annotatedImageSrc: '',
      timeTimer: null
    }
  },
  computed: {
    maturityStats() {
      if (!this.result || !this.result.counts) return []
      const counts = this.result.counts
      const total = (counts.halfripe || 0) + (counts.ripe || 0) + (counts.unripe || 0)
      const items = [
        { name: 'halfripe', label: '半熟 (Halfripe)', color: '#ecc94b' },
        { name: 'ripe', label: '成熟 (Ripe)', color: '#48bb78' },
        { name: 'unripe', label: '未熟 (Unripe)', color: '#ed8936' }
      ]
      return items.map(item => ({
        ...item,
        count: counts[item.name] || 0,
        percentage: total > 0 ? (((counts[item.name] || 0) / total) * 100).toFixed(1) : '0.0'
      }))
    }
  },
  mounted() {
    this.updateTime()
    this.timeTimer = setInterval(this.updateTime, 1000)
  },
  beforeUnmount() {
    if (this.timeTimer) clearInterval(this.timeTimer)
  },
  methods: {
    updateTime() {
      this.currentTime = new Date().toLocaleString('zh-CN', { hour12: false })
    },
    goToDashboard() {
      this.$router.push('/dashboard')
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
      this.result = null
      this.annotatedImageSrc = ''
      this.error = ''
      const reader = new FileReader()
      reader.onload = (e) => {
        this.selectedImagePreview = e.target.result
      }
      reader.readAsDataURL(file)
    },
    removeImage() {
      this.selectedImage = null
      this.selectedImagePreview = ''
      this.result = null
      this.annotatedImageSrc = ''
      this.error = ''
      if (this.$refs.imageInput) {
        this.$refs.imageInput.value = ''
      }
    },
    async runDetection() {
      if (!this.selectedImage || this.loading) return
      this.loading = true
      this.error = ''
      this.result = null
      this.annotatedImageSrc = ''

      const form = new FormData()
      form.append('image', this.selectedImage)

      try {
        const response = await fetch('/api/maturity', { method: 'POST', body: form })
        const data = await response.json()
        if (!data.success) {
          this.error = data.error || '成熟度检测失败'
          return
        }
        this.result = data.data
        if (data.data.annotated_image_base64) {
          this.annotatedImageSrc = 'data:image/jpeg;base64,' + data.data.annotated_image_base64
        }
      } catch (err) {
        this.error = err.message || '成熟度检测服务暂时无法响应'
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.page{min-height:100vh;background:linear-gradient(135deg,#06111d,#0a1d31 55%,#07131f);color:#eef8ff;font-family:'Microsoft YaHei','PingFang SC',sans-serif}
.topbar,.topbar-right,.section-head,.count-grid{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.topbar{justify-content:space-between;padding:20px 24px;background:rgba(7,18,32,.82);border-bottom:1px solid rgba(140,194,255,.14)}
.content{padding:20px;display:grid;gap:16px;max-width:1200px;margin:0 auto}
.card{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);border-radius:20px;padding:18px;box-shadow:0 18px 42px rgba(2,10,20,.26)}
.eyebrow,.muted{color:#a7c7e5}.eyebrow{margin:0 0 4px;font-size:.78rem;letter-spacing:.12em;text-transform:uppercase}
h1,h2,h3,p{margin:0}
.pill{border:none;border-radius:999px;padding:8px 12px;background:rgba(255,255,255,.08)}
.pill.live{background:rgba(65,191,255,.16);color:#a3deff}
.pill.good{background:rgba(87,221,145,.15);color:#a6efc1}
.primary,.ghost{padding:10px 14px;border:none;border-radius:999px;font-weight:700;cursor:pointer}
.primary{background:linear-gradient(135deg,#65d6ff,#4d86ff);color:#041224}
.ghost{background:rgba(255,255,255,.08);color:#eef7ff}
.chip{border:none;border-radius:999px;padding:6px 10px;background:rgba(255,255,255,.07);display:inline-block}
.chip.halfripe{background:rgba(236,201,75,.18);color:#ecc94b}
.chip.ripe{background:rgba(72,187,120,.18);color:#48bb78}
.chip.unripe{background:rgba(237,137,54,.18);color:#ed8936}
.upload-section{margin-top:14px}
.upload-zone{display:flex;flex-direction:column;align-items:center;gap:8px;padding:24px;border:2px dashed rgba(255,255,255,.14);border-radius:16px;cursor:pointer;transition:border-color .2s ease}
.upload-zone:hover{border-color:rgba(111,198,255,.42)}
.upload-icon{font-size:1.8rem;color:#8cc4ff}
.small-desc{font-size:.78rem}
.image-preview-card{display:flex;align-items:center;gap:20px;padding:14px;border:1px solid rgba(255,255,255,.1);border-radius:16px;background:rgba(5,15,27,.52)}
.image-thumb{width:120px;height:120px;border-radius:14px;background-size:cover;background-position:center;border:1px solid rgba(255,255,255,.14);flex-shrink:0}
.image-actions{display:flex;gap:10px;flex-wrap:wrap}
.result-grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:14px}
.counts-panel,.image-panel{min-width:0}
.count-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin:12px 0}
.count-card{padding:14px;border-radius:14px;background:rgba(5,15,27,.52);border:1px solid rgba(255,255,255,.07);text-align:center}
.count-label{display:block;font-size:.82rem;color:#a7c7e5;margin-bottom:4px}
.count-value{display:block;font-size:2rem;font-weight:800}
.count-bar{height:6px;border-radius:3px;background:rgba(255,255,255,.06);margin-top:8px;overflow:hidden}
.bar-fill{height:100%;border-radius:3px;transition:width .6s ease}
.divider{height:1px;background:rgba(255,255,255,.08);margin:16px 0}
.detail-list{margin-top:14px}
.detail-item{display:flex;align-items:center;gap:10px;padding:10px;border-radius:10px;background:rgba(5,15,27,.32);margin-bottom:8px;font-size:.88rem;flex-wrap:wrap}
.annotated-wrapper{margin-top:12px;border-radius:14px;overflow:hidden;border:1px solid rgba(255,255,255,.1)}
.annotated-image{width:100%;display:block;object-fit:contain;max-height:500px}
.empty{padding:40px;text-align:center;color:#a7c7e5;font-size:.88rem;background:rgba(5,15,27,.32);border-radius:14px}
.error{padding:14px;border-radius:14px;background:rgba(255,115,87,.12);color:#ffc0b2;margin-top:14px}
@media (max-width:860px){.result-grid{grid-template-columns:1fr}.count-grid{grid-template-columns:1fr 1fr 1fr}}
@media (max-width:520px){.topbar{flex-direction:column;align-items:flex-start}.content{padding:16px}.count-grid{grid-template-columns:1fr}.image-preview-card{flex-direction:column;align-items:stretch}}
</style>
