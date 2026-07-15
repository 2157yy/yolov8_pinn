import fs from 'fs'
import path from 'path'
import mysql from 'mysql2/promise'

const IMAGE_EXTENSIONS = new Set(['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp'])
const DEFAULT_SOURCE_CLASS_NAMES = ['unripe', 'partially_ripe', 'ripe']
const DEFAULT_CANONICAL_CLASSES = ['unripe', 'halfripe', 'ripe']
const DEFAULT_CLASS_ALIASES = {
  unripe: ['unripe', 'notripe', 'not_ripe', 'green', 'immature', 'raw'],
  halfripe: ['halfripe', 'half_ripe', 'partialripe', 'partially_ripe', 'partiallyripe', 'turning', 'breaker', 'midripe'],
  ripe: ['ripe', 'fully_ripe', 'fullyripe', 'mature', 'ready', 'red']
}

const PUBLIC_DATASET_PRESETS = [
  {
    id: 'github-strawberry-ripeness-yolo',
    name: '公开草莓成熟度 YOLO 三分类数据集',
    sourceUrl: 'https://github.com/amitamola/Strawberry-Counting-and-Ripeness-detection',
    sourceType: 'yolo',
    canonicalClasses: DEFAULT_CANONICAL_CLASSES,
    suggestedClassNames: ['unripe', 'partially_ripe', 'fully_ripe'],
    classAliases: {
      unripe: ['unripe'],
      partially_ripe: ['halfripe', 'partially_ripe', 'partialripe'],
      fully_ripe: ['ripe', 'fully_ripe']
    },
    description: '适合导入后统一映射到 unripe / halfripe / ripe。'
  }
]

function clone(value) {
  if (value === undefined) return undefined
  return JSON.parse(JSON.stringify(value))
}

function toArray(value) {
  if (!value) return []
  if (Array.isArray(value)) return value.filter(Boolean).map((item) => String(item).trim()).filter(Boolean)
  return String(value)
    .split(/[,，\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function sanitizeKey(value) {
  return String(value ?? '')
    .trim()
    .toLowerCase()
    .replace(/['"`]/g, '')
    .replace(/[\s_-]+/g, '')
}

function slugify(value) {
  const slug = String(value ?? '')
    .trim()
    .toLowerCase()
    .replace(/[\s_]+/g, '-')
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
  return slug || 'maturity-dataset'
}

function parseMaybeJson(value, fallback) {
  if (value == null || value === '') return fallback
  if (typeof value === 'object') return value
  if (Array.isArray(value)) return value
  try {
    return JSON.parse(String(value))
  } catch (_) {
    return fallback
  }
}

function normalizeClassAliases(classAliases = {}) {
  const aliasMap = {}

  for (const [canonical, aliases] of Object.entries(DEFAULT_CLASS_ALIASES)) {
    const canonicalKey = sanitizeKey(canonical)
    aliasMap[canonicalKey] = canonical
    for (const alias of aliases) {
      aliasMap[sanitizeKey(alias)] = canonical
    }
  }

  for (const [sourceName, targetName] of Object.entries(classAliases || {})) {
    const sourceKey = sanitizeKey(sourceName)
    if (!sourceKey) continue

    if (typeof targetName === 'string') {
      aliasMap[sourceKey] = targetName.trim()
      continue
    }

    if (Array.isArray(targetName) && targetName.length > 0) {
      const canonicalName = String(targetName[0]).trim()
      if (!canonicalName) continue
      aliasMap[sourceKey] = canonicalName
      for (const alias of targetName.slice(1)) {
        aliasMap[sanitizeKey(alias)] = canonicalName
      }
    }
  }

  return aliasMap
}

function canonicalizeClassName(sourceClassName, classAliases = {}) {
  const aliasMap = normalizeClassAliases(classAliases)
  const key = sanitizeKey(sourceClassName)
  return aliasMap[key] || key || 'unknown'
}

function parseDataYamlClasses(text) {
  if (!text) return null
  const lines = String(text).split(/\r?\n/)
  let capturingNames = false
  const classes = []

  for (const rawLine of lines) {
    const line = rawLine.replace(/\t/g, '  ')
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#')) continue

    const namesInline = trimmed.match(/^names\s*:\s*\[(.*)\]\s*$/)
    if (namesInline) {
      return namesInline[1]
        .split(',')
        .map((item) => item.trim().replace(/^['"]|['"]$/g, ''))
        .filter(Boolean)
    }

    if (/^names\s*:\s*$/.test(trimmed)) {
      capturingNames = true
      continue
    }

    if (capturingNames) {
      const numbered = trimmed.match(/^\d+\s*:\s*(.+)$/)
      if (numbered) {
        classes.push(numbered[1].trim().replace(/^['"]|['"]$/g, ''))
        continue
      }

      const bullet = trimmed.match(/^-\s*(.+)$/)
      if (bullet) {
        classes.push(bullet[1].trim().replace(/^['"]|['"]$/g, ''))
        continue
      }

      if (/^[a-zA-Z0-9_]+:\s*/.test(trimmed)) {
        capturingNames = false
      }
    }
  }

  return classes.length ? classes : null
}

function inferClassNamesFromRoot(sourcePath) {
  const root = path.resolve(sourcePath)
  const candidates = ['data.yaml', 'dataset.yaml', 'data.yml']

  for (const candidate of candidates) {
    const fullPath = path.join(root, candidate)
    if (!fs.existsSync(fullPath)) continue
    const parsed = parseDataYamlClasses(fs.readFileSync(fullPath, 'utf8'))
    if (parsed && parsed.length) return parsed
  }

  return null
}

function isImageFile(filePath) {
  return IMAGE_EXTENSIONS.has(path.extname(filePath).toLowerCase())
}

function walkFiles(rootPath) {
  const result = []
  const stack = [rootPath]

  while (stack.length) {
    const current = stack.pop()
    const entries = fs.readdirSync(current, { withFileTypes: true })
    for (const entry of entries) {
      if (entry.name.startsWith('.')) continue
      if (entry.name === '__MACOSX') continue
      const fullPath = path.join(current, entry.name)
      if (entry.isDirectory()) {
        stack.push(fullPath)
        continue
      }
      if (entry.isFile() && isImageFile(fullPath)) {
        result.push(fullPath)
      }
    }
  }

  return result.sort((a, b) => a.localeCompare(b))
}

function inferSplitName(relativePath) {
  const normalized = relativePath.replace(/\\/g, '/').toLowerCase()
  if (/(^|\/)train(\/|$)/.test(normalized)) return 'train'
  if (/(^|\/)val(\/|$)/.test(normalized)) return 'val'
  if (/(^|\/)valid(\/|$)/.test(normalized)) return 'val'
  if (/(^|\/)test(\/|$)/.test(normalized)) return 'test'
  return 'unknown'
}

function resolveLabelPath(rootPath, imagePath) {
  const relative = path.relative(rootPath, imagePath)
  const extless = relative.replace(/\.[^.]+$/, '')
  const candidates = [
    path.join(rootPath, relative.replace(/(^|[\\/])images([\\/])/, '$1labels$2').replace(/\.[^.]+$/, '.txt')),
    path.join(rootPath, extless + '.txt'),
    path.join(rootPath, 'labels', path.basename(extless) + '.txt')
  ]
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate
  }
  return null
}

function parsePolygonPoints(numbers) {
  const points = []
  for (let index = 1; index < numbers.length; index += 2) {
    const x = numbers[index]
    const y = numbers[index + 1]
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue
    points.push({ x, y })
  }
  if (!points.length) return null
  const xs = points.map((point) => point.x)
  const ys = points.map((point) => point.y)
  const minX = Math.min(...xs)
  const minY = Math.min(...ys)
  const maxX = Math.max(...xs)
  const maxY = Math.max(...ys)
  return {
    points,
    bbox: {
      xCenter: Number(((minX + maxX) / 2).toFixed(6)),
      yCenter: Number(((minY + maxY) / 2).toFixed(6)),
      width: Number((maxX - minX).toFixed(6)),
      height: Number((maxY - minY).toFixed(6))
    }
  }
}

function parseLabelLine(line, sourceClassNames, classAliases) {
  const trimmed = line.trim()
  if (!trimmed || trimmed.startsWith('#')) return null
  const parts = trimmed.split(/\s+/)
  const numbers = parts.map((part) => Number(part))
  if (numbers.some((number) => Number.isNaN(number))) return null
  if (numbers.length < 5) return null

  const classId = Math.trunc(numbers[0])
  const sourceClassName = sourceClassNames[classId] ?? `class_${classId}`
  const canonicalClassName = canonicalizeClassName(sourceClassName, classAliases)

  const base = {
    classId,
    sourceClassName,
    canonicalClassName,
    raw: trimmed
  }

  if (numbers.length === 5 || numbers.length === 6) {
    const [xCenter, yCenter, width, height] = numbers.slice(1, 5)
    return {
      ...base,
      bbox: {
        xCenter,
        yCenter,
        width,
        height
      }
    }
  }

  const polygon = parsePolygonPoints(numbers)
  if (!polygon) return null
  return {
    ...base,
    polygonPoints: polygon.points,
    bbox: polygon.bbox
  }
}

function parseLabelFile(labelPath, sourceClassNames, classAliases) {
  if (!labelPath || !fs.existsSync(labelPath)) return []
  const lines = fs.readFileSync(labelPath, 'utf8').split(/\r?\n/)
  const annotations = []
  for (const line of lines) {
    const parsed = parseLabelLine(line, sourceClassNames, classAliases)
    if (parsed) annotations.push(parsed)
  }
  return annotations
}

function choosePrimaryClass(annotations) {
  if (!annotations.length) return 'unknown'
  const counts = new Map()
  for (const annotation of annotations) {
    counts.set(annotation.canonicalClassName, (counts.get(annotation.canonicalClassName) || 0) + 1)
  }
  let winner = annotations[0].canonicalClassName
  let winnerCount = 0
  for (const [className, count] of counts.entries()) {
    if (count > winnerCount) {
      winner = className
      winnerCount = count
    }
  }
  return winner
}

export function scanMaturityDataset(sourcePath, options = {}) {
  const rootPath = path.resolve(sourcePath)
  if (!fs.existsSync(rootPath)) {
    throw new Error(`Dataset path does not exist: ${rootPath}`)
  }

  const sourceClassNames = toArray(options.classNames)
  const inferredClassNames = sourceClassNames.length ? sourceClassNames : inferClassNamesFromRoot(rootPath)
  const resolvedClassNames = (inferredClassNames && inferredClassNames.length ? inferredClassNames : DEFAULT_SOURCE_CLASS_NAMES).map((item) => String(item).trim())
  const classAliases = options.classAliases || {}

  const imagePaths = walkFiles(rootPath)
  const samples = []
  const classCounts = {}
  const splitCounts = {}
  let annotationCount = 0

  for (const imagePath of imagePaths) {
    const relativeImagePath = path.relative(rootPath, imagePath)
    const splitName = inferSplitName(relativeImagePath)
    const labelPath = resolveLabelPath(rootPath, imagePath)
    const annotations = parseLabelFile(labelPath, resolvedClassNames, classAliases)
    const primaryClass = choosePrimaryClass(annotations)

    for (const annotation of annotations) {
      classCounts[annotation.canonicalClassName] = (classCounts[annotation.canonicalClassName] || 0) + 1
    }
    annotationCount += annotations.length
    splitCounts[splitName] = (splitCounts[splitName] || 0) + 1

    samples.push({
      sampleKey: relativeImagePath.replace(/[\\/]/g, '__'),
      splitName,
      imagePath,
      relativeImagePath,
      labelPath,
      sourceClassName: annotations[0]?.sourceClassName || null,
      canonicalClassName: primaryClass,
      annotationCount: annotations.length,
      annotations
    })
  }

  return {
    rootPath,
    sourceClassNames: resolvedClassNames,
    canonicalClasses: DEFAULT_CANONICAL_CLASSES,
    sampleCount: samples.length,
    labeledSampleCount: samples.filter((sample) => sample.annotationCount > 0).length,
    annotationCount,
    classCounts,
    splitCounts,
    samples
  }
}

function buildDatasetSummary(dataset) {
  const classCounts = parseMaybeJson(dataset.class_counts_json, {})
  const splitStats = parseMaybeJson(dataset.split_stats_json, {})
  const canonicalClasses = parseMaybeJson(dataset.canonical_classes_json, DEFAULT_CANONICAL_CLASSES)

  return {
    id: dataset.id,
    datasetKey: dataset.dataset_key,
    name: dataset.name,
    sourceUrl: dataset.source_url,
    sourcePath: dataset.source_path,
    sourceType: dataset.source_type,
    description: dataset.description,
    classNames: parseMaybeJson(dataset.class_names_json, DEFAULT_SOURCE_CLASS_NAMES),
    classAliases: parseMaybeJson(dataset.class_aliases_json, {}),
    canonicalClasses,
    classCounts,
    splitStats,
    sampleCount: Number(dataset.sample_count || 0),
    annotationCount: Number(dataset.annotation_count || 0),
    active: Boolean(dataset.active),
    importStatus: dataset.import_status,
    lastImportedAt: dataset.last_imported_at,
    createdAt: dataset.created_at,
    updatedAt: dataset.updated_at
  }
}

function buildSampleSummary(sample) {
  return {
    id: sample.id,
    datasetId: sample.dataset_id,
    sampleKey: sample.sample_key,
    splitName: sample.split_name,
    imagePath: sample.image_path,
    relativeImagePath: sample.relative_image_path,
    labelPath: sample.label_path,
    sourceClassName: sample.source_class_name,
    canonicalClassName: sample.canonical_class_name,
    annotationCount: Number(sample.annotation_count || 0),
    annotations: parseMaybeJson(sample.annotations_json, []),
    createdAt: sample.created_at,
    updatedAt: sample.updated_at
  }
}

function createMemoryRepository() {
  const datasets = []
  const samples = []
  let nextDatasetId = 1
  let nextSampleId = 1

  const insertDataset = (record) => {
    const dataset = {
      id: nextDatasetId++,
      dataset_key: record.dataset_key,
      name: record.name,
      source_url: record.source_url || null,
      source_path: record.source_path,
      source_type: record.source_type || 'yolo',
      description: record.description || null,
      class_names_json: JSON.stringify(record.class_names),
      class_aliases_json: JSON.stringify(record.class_aliases || {}),
      canonical_classes_json: JSON.stringify(record.canonical_classes || DEFAULT_CANONICAL_CLASSES),
      split_stats_json: JSON.stringify(record.split_stats || {}),
      class_counts_json: JSON.stringify(record.class_counts || {}),
      sample_count: record.sample_count || 0,
      annotation_count: record.annotation_count || 0,
      active: record.active ? 1 : 0,
      import_status: record.import_status || 'ready',
      last_imported_at: new Date().toISOString(),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }
    datasets.push(dataset)
    return dataset
  }

  return {
    storageMode: 'memory',
    mysqlEnabled: false,
    async importDataset(payload) {
      const scan = scanMaturityDataset(payload.sourcePath, payload)
      const dataset = insertDataset({
        dataset_key: payload.datasetKey || `${slugify(payload.name || path.basename(scan.rootPath))}-${Date.now().toString(36)}`,
        name: payload.name || path.basename(scan.rootPath),
        source_url: payload.sourceUrl || null,
        source_path: scan.rootPath,
        source_type: payload.sourceType || 'yolo',
        description: payload.description || null,
        class_names: scan.sourceClassNames,
        class_aliases: payload.classAliases || {},
        canonical_classes: scan.canonicalClasses,
        split_stats: scan.splitCounts,
        class_counts: scan.classCounts,
        sample_count: scan.sampleCount,
        annotation_count: scan.annotationCount,
        active: payload.setActive === false ? false : datasets.length === 0,
        import_status: 'ready'
      })

      for (const sample of scan.samples) {
        samples.push({
          id: nextSampleId++,
          dataset_id: dataset.id,
          sample_key: sample.sampleKey,
          split_name: sample.splitName,
          image_path: sample.imagePath,
          relative_image_path: sample.relativeImagePath,
          label_path: sample.labelPath,
          source_class_name: sample.sourceClassName,
          canonical_class_name: sample.canonicalClassName,
          annotation_count: sample.annotationCount,
          annotations_json: JSON.stringify(sample.annotations),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        })
      }

      if (payload.setActive !== false) {
        for (const otherDataset of datasets) {
          otherDataset.active = otherDataset.id === dataset.id ? 1 : 0
          otherDataset.updated_at = new Date().toISOString()
        }
      }

      return {
        dataset: buildDatasetSummary(dataset),
        sampleCount: scan.sampleCount,
        annotationCount: scan.annotationCount,
        samples: scan.samples.slice(0, 12).map((sample) => ({
          ...sample,
          annotations: clone(sample.annotations)
        }))
      }
    },
    async listDatasets() {
      return datasets.slice().reverse().map((dataset) => buildDatasetSummary(dataset))
    },
    async getDataset(datasetId) {
      const dataset = datasets.find((item) => item.id === Number(datasetId))
      if (!dataset) return null
      return buildDatasetSummary(dataset)
    },
    async listDatasetSamples(datasetId, { limit = 24, offset = 0 } = {}) {
      const datasetSamples = samples
        .filter((sample) => sample.dataset_id === Number(datasetId))
        .slice(offset, offset + limit)
        .map((sample) => buildSampleSummary(sample))
      return {
        items: datasetSamples,
        total: samples.filter((sample) => sample.dataset_id === Number(datasetId)).length
      }
    },
    async setActiveDataset(datasetId) {
      const targetId = Number(datasetId)
      let activeDataset = null
      for (const dataset of datasets) {
        dataset.active = dataset.id === targetId ? 1 : 0
        dataset.updated_at = new Date().toISOString()
        if (dataset.id === targetId) activeDataset = buildDatasetSummary(dataset)
      }
      if (!activeDataset) {
        throw new Error(`Dataset not found: ${datasetId}`)
      }
      return activeDataset
    },
    async getActiveDataset() {
      const active = datasets.find((item) => item.active)
      return active ? buildDatasetSummary(active) : null
    },
    async getDatasetSourcePath(datasetId) {
      const dataset = datasets.find((item) => item.id === Number(datasetId))
      return dataset ? dataset.source_path : null
    },
    async getStorageInfo() {
      return {
        storageMode: 'memory',
        mysqlEnabled: false,
        datasetCount: datasets.length,
        sampleCount: samples.length,
        activeDatasetId: datasets.find((item) => item.active)?.id || null
      }
    },
    getPresets() {
      return clone(PUBLIC_DATASET_PRESETS)
    }
  }
}

async function initializeMysqlSchema(pool) {
  const charset = 'utf8mb4'
  await pool.query(`
    CREATE TABLE IF NOT EXISTS maturity_datasets (
      id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
      dataset_key VARCHAR(191) NOT NULL UNIQUE,
      name VARCHAR(191) NOT NULL,
      source_url TEXT NULL,
      source_path TEXT NOT NULL,
      source_type VARCHAR(32) NOT NULL DEFAULT 'yolo',
      description TEXT NULL,
      class_names_json LONGTEXT NOT NULL,
      class_aliases_json LONGTEXT NOT NULL,
      canonical_classes_json LONGTEXT NOT NULL,
      split_stats_json LONGTEXT NOT NULL,
      class_counts_json LONGTEXT NOT NULL,
      sample_count INT NOT NULL DEFAULT 0,
      annotation_count INT NOT NULL DEFAULT 0,
      active TINYINT(1) NOT NULL DEFAULT 0,
      import_status VARCHAR(32) NOT NULL DEFAULT 'ready',
      last_imported_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      INDEX idx_maturity_datasets_active (active),
      INDEX idx_maturity_datasets_created (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=${charset}
  `)

  await pool.query(`
    CREATE TABLE IF NOT EXISTS maturity_dataset_samples (
      id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
      dataset_id BIGINT UNSIGNED NOT NULL,
      sample_key VARCHAR(255) NOT NULL,
      split_name VARCHAR(32) NOT NULL,
      image_path TEXT NOT NULL,
      relative_image_path TEXT NOT NULL,
      label_path TEXT NULL,
      source_class_name VARCHAR(64) NULL,
      canonical_class_name VARCHAR(32) NOT NULL,
      annotation_count INT NOT NULL DEFAULT 0,
      annotations_json LONGTEXT NOT NULL,
      created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      INDEX idx_maturity_dataset_samples_dataset_id (dataset_id),
      INDEX idx_maturity_dataset_samples_class (canonical_class_name),
      CONSTRAINT fk_maturity_dataset_samples_dataset
        FOREIGN KEY (dataset_id) REFERENCES maturity_datasets(id)
        ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=${charset}
  `)
}

async function createMysqlRepository(pool, config) {
  return {
    storageMode: 'mysql',
    mysqlEnabled: true,
    async importDataset(payload) {
      const scan = scanMaturityDataset(payload.sourcePath, payload)
      const datasetKey = payload.datasetKey || `${slugify(payload.name || path.basename(scan.rootPath))}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
      const datasetName = payload.name || path.basename(scan.rootPath)
      const classAliases = payload.classAliases || {}
      const sourceType = payload.sourceType || 'yolo'
      const description = payload.description || null

      const connection = await pool.getConnection()
      try {
        await connection.beginTransaction()
        const [result] = await connection.execute(
          `
            INSERT INTO maturity_datasets (
              dataset_key, name, source_url, source_path, source_type, description,
              class_names_json, class_aliases_json, canonical_classes_json,
              split_stats_json, class_counts_json, sample_count, annotation_count,
              active, import_status, last_imported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())
          `,
          [
            datasetKey,
            datasetName,
            payload.sourceUrl || null,
            scan.rootPath,
            sourceType,
            description,
            JSON.stringify(scan.sourceClassNames),
            JSON.stringify(classAliases),
            JSON.stringify(scan.canonicalClasses),
            JSON.stringify(scan.splitCounts),
            JSON.stringify(scan.classCounts),
            scan.sampleCount,
            scan.annotationCount,
            payload.setActive === false ? 0 : 1,
            'ready'
          ]
        )

        const datasetId = result.insertId
        const sampleRows = scan.samples.map((sample) => [
          datasetId,
          sample.sampleKey,
          sample.splitName,
          sample.imagePath,
          sample.relativeImagePath,
          sample.labelPath,
          sample.sourceClassName,
          sample.canonicalClassName,
          sample.annotationCount,
          JSON.stringify(sample.annotations)
        ])

        for (let index = 0; index < sampleRows.length; index += 200) {
          const chunk = sampleRows.slice(index, index + 200)
          if (!chunk.length) continue
          await connection.query(
            `
              INSERT INTO maturity_dataset_samples (
                dataset_id, sample_key, split_name, image_path, relative_image_path,
                label_path, source_class_name, canonical_class_name,
                annotation_count, annotations_json
              ) VALUES ?
            `,
            [chunk]
          )
        }

        if (payload.setActive !== false) {
          await connection.query('UPDATE maturity_datasets SET active = 0')
          await connection.query('UPDATE maturity_datasets SET active = 1 WHERE id = ?', [datasetId])
        }

        await connection.commit()

        return {
          dataset: await this.getDataset(datasetId),
          sampleCount: scan.sampleCount,
          annotationCount: scan.annotationCount,
          samples: scan.samples.slice(0, 12).map((sample) => ({
            ...sample,
            annotations: clone(sample.annotations)
          }))
        }
      } catch (error) {
        await connection.rollback()
        throw error
      } finally {
        connection.release()
      }
    },
    async listDatasets() {
      const [rows] = await pool.query('SELECT * FROM maturity_datasets ORDER BY active DESC, created_at DESC, id DESC')
      return rows.map((row) => buildDatasetSummary(row))
    },
    async getDataset(datasetId) {
      const [rows] = await pool.query('SELECT * FROM maturity_datasets WHERE id = ? LIMIT 1', [Number(datasetId)])
      if (!rows.length) return null
      return buildDatasetSummary(rows[0])
    },
    async listDatasetSamples(datasetId, { limit = 24, offset = 0 } = {}) {
      const [rows] = await pool.query(
        'SELECT * FROM maturity_dataset_samples WHERE dataset_id = ? ORDER BY id ASC LIMIT ? OFFSET ?',
        [Number(datasetId), Number(limit), Number(offset)]
      )
      const [countRows] = await pool.query('SELECT COUNT(*) AS total FROM maturity_dataset_samples WHERE dataset_id = ?', [Number(datasetId)])
      return {
        items: rows.map((row) => buildSampleSummary(row)),
        total: Number(countRows[0]?.total || 0)
      }
    },
    async setActiveDataset(datasetId) {
      const id = Number(datasetId)
      const [foundRows] = await pool.query('SELECT id FROM maturity_datasets WHERE id = ? LIMIT 1', [id])
      if (!foundRows.length) throw new Error(`Dataset not found: ${datasetId}`)
      await pool.query('UPDATE maturity_datasets SET active = 0')
      await pool.query('UPDATE maturity_datasets SET active = 1, updated_at = NOW() WHERE id = ?', [id])
      return this.getDataset(id)
    },
    async getActiveDataset() {
      const [rows] = await pool.query('SELECT * FROM maturity_datasets WHERE active = 1 ORDER BY created_at DESC, id DESC LIMIT 1')
      return rows.length ? buildDatasetSummary(rows[0]) : null
    },
    async getDatasetSourcePath(datasetId) {
      const [rows] = await pool.query('SELECT source_path FROM maturity_datasets WHERE id = ? LIMIT 1', [Number(datasetId)])
      return rows[0]?.source_path || null
    },
    async getStorageInfo() {
      const [datasetRows] = await pool.query('SELECT COUNT(*) AS total FROM maturity_datasets')
      const [sampleRows] = await pool.query('SELECT COUNT(*) AS total FROM maturity_dataset_samples')
      const [activeRows] = await pool.query('SELECT id FROM maturity_datasets WHERE active = 1 LIMIT 1')
      return {
        storageMode: 'mysql',
        mysqlEnabled: true,
        mysqlDatabase: config.database || null,
        datasetCount: Number(datasetRows[0]?.total || 0),
        sampleCount: Number(sampleRows[0]?.total || 0),
        activeDatasetId: activeRows[0]?.id || null
      }
    },
    getPresets() {
      return clone(PUBLIC_DATASET_PRESETS)
    }
  }
}

function resolveMysqlConfig(options = {}) {
  const mysqlUrl = options.mysqlUrl || process.env.MYSQL_URL
  if (mysqlUrl) {
    const url = new URL(mysqlUrl)
    return {
      host: url.hostname,
      port: url.port ? Number(url.port) : 3306,
      user: decodeURIComponent(url.username || 'root'),
      password: decodeURIComponent(url.password || ''),
      database: url.pathname.replace(/^\/+/, '') || 'smart_greenhouse_dashboard',
      ssl: url.searchParams.get('ssl') === 'true'
    }
  }

  const host = options.host || process.env.MYSQL_HOST
  if (!host) return null
  return {
    host,
    port: Number(options.port || process.env.MYSQL_PORT || 3306),
    user: options.user || process.env.MYSQL_USER || 'root',
    password: options.password || process.env.MYSQL_PASSWORD || '',
    database: options.database || process.env.MYSQL_DATABASE || 'smart_greenhouse_dashboard'
  }
}

async function ensureDatabaseExists(config) {
  if (!config.database) return
  const baseConfig = {
    host: config.host,
    port: config.port,
    user: config.user,
    password: config.password,
    ssl: config.ssl && config.ssl !== 'false' ? config.ssl : undefined,
    waitForConnections: true,
    connectionLimit: 1
  }
  const adminPool = mysql.createPool(baseConfig)
  const dbName = config.database.replace(/`/g, '``')
  await adminPool.query(`CREATE DATABASE IF NOT EXISTS \`${dbName}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci`)
  await adminPool.end()
}

export async function createMaturityDatasetRepository(options = {}) {
  const mysqlConfig = resolveMysqlConfig(options)
  if (!mysqlConfig) {
    return createMemoryRepository()
  }

  try {
    await ensureDatabaseExists(mysqlConfig)
    const pool = mysql.createPool({
      host: mysqlConfig.host,
      port: mysqlConfig.port,
      user: mysqlConfig.user,
      password: mysqlConfig.password,
      database: mysqlConfig.database,
      ssl: mysqlConfig.ssl && mysqlConfig.ssl !== 'false' ? mysqlConfig.ssl : undefined,
      waitForConnections: true,
      connectionLimit: 10,
      charset: 'utf8mb4',
      dateStrings: true
    })
    await initializeMysqlSchema(pool)
    return createMysqlRepository(pool, mysqlConfig)
  } catch (error) {
    console.warn(`[maturity-dataset-store] MySQL unavailable, falling back to memory store: ${error.message}`)
    return createMemoryRepository()
  }
}

export {
  DEFAULT_CANONICAL_CLASSES,
  DEFAULT_SOURCE_CLASS_NAMES,
  PUBLIC_DATASET_PRESETS,
  canonicalizeClassName,
  inferClassNamesFromRoot,
  parseDataYamlClasses,
  resolveLabelPath,
  resolveMysqlConfig
}
