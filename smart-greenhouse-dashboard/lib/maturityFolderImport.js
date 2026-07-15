import path from 'path'

export function normalizeUploadedRelativePath(originalName) {
  const raw = String(originalName ?? '').replace(/\\/g, '/').trim()
  if (!raw) {
    throw new Error('Empty upload path')
  }

  const normalized = path.posix.normalize(raw)
  if (
    normalized === '.' ||
    normalized === '/' ||
    normalized.startsWith('../') ||
    normalized.includes('/../') ||
    path.posix.isAbsolute(normalized)
  ) {
    throw new Error(`Illegal upload path: ${originalName}`)
  }

  return normalized.replace(/^\.\/+/, '')
}

export function buildDatasetImportRoot(baseDir, importId) {
  return path.join(baseDir, `dataset-${importId}`)
}

export function makeImportId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}
