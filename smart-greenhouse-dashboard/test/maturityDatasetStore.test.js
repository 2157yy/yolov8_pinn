import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import {
  canonicalizeClassName,
  createMaturityDatasetRepository,
  parseDataYamlClasses,
  scanMaturityDataset
} from '../lib/maturityDatasetStore.js'

function makeTempDataset() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'maturity-dataset-'))
  fs.mkdirSync(path.join(root, 'images', 'train'), { recursive: true })
  fs.mkdirSync(path.join(root, 'labels', 'train'), { recursive: true })
  fs.mkdirSync(path.join(root, 'images', 'val'), { recursive: true })
  fs.mkdirSync(path.join(root, 'labels', 'val'), { recursive: true })
  fs.mkdirSync(path.join(root, 'images', 'test'), { recursive: true })

  fs.writeFileSync(
    path.join(root, 'data.yaml'),
    ['names:', '  - unripe', '  - partially_ripe', '  - fully_ripe'].join('\n'),
    'utf8'
  )
  fs.writeFileSync(path.join(root, 'images', 'train', 'sample-1.jpg'), '', 'utf8')
  fs.writeFileSync(path.join(root, 'labels', 'train', 'sample-1.txt'), '1 0.5 0.5 0.2 0.3\n', 'utf8')
  fs.writeFileSync(path.join(root, 'images', 'val', 'sample-2.jpg'), '', 'utf8')
  fs.writeFileSync(path.join(root, 'labels', 'val', 'sample-2.txt'), '2 0.4 0.4 0.1 0.2\n', 'utf8')
  fs.writeFileSync(path.join(root, 'images', 'test', 'sample-3.jpg'), '', 'utf8')

  return root
}

test('canonicalizeClassName maps public ripeness aliases to canonical labels', () => {
  assert.equal(canonicalizeClassName('partially_ripe'), 'halfripe')
  assert.equal(canonicalizeClassName('fully_ripe'), 'ripe')
  assert.equal(canonicalizeClassName('unripe'), 'unripe')
})

test('parseDataYamlClasses reads common YOLO names layouts', () => {
  const inline = parseDataYamlClasses('names: [unripe, partially_ripe, ripe]')
  assert.deepEqual(inline, ['unripe', 'partially_ripe', 'ripe'])

  const block = parseDataYamlClasses(['names:', '  - unripe', '  - partially_ripe', '  - ripe'].join('\n'))
  assert.deepEqual(block, ['unripe', 'partially_ripe', 'ripe'])
})

test('scanMaturityDataset normalizes a YOLO maturity dataset', () => {
  const root = makeTempDataset()
  const report = scanMaturityDataset(root, {
    classAliases: {
      partially_ripe: ['halfripe', 'partially_ripe'],
      fully_ripe: ['ripe', 'fully_ripe']
    }
  })

  assert.equal(report.sampleCount, 3)
  assert.equal(report.annotationCount, 2)
  assert.equal(report.classCounts.halfripe, 1)
  assert.equal(report.classCounts.ripe, 1)
  assert.equal(report.samples.find((sample) => sample.relativeImagePath.endsWith('sample-1.jpg'))?.canonicalClassName, 'halfripe')
  assert.equal(report.samples.find((sample) => sample.relativeImagePath.endsWith('sample-2.jpg'))?.canonicalClassName, 'ripe')
  assert.equal(report.samples.find((sample) => sample.relativeImagePath.endsWith('sample-3.jpg'))?.canonicalClassName, 'unknown')
})

test('memory repository stores imported datasets and marks the latest as active', async () => {
  const root = makeTempDataset()
  const repo = await createMaturityDatasetRepository()
  const imported = await repo.importDataset({
    name: '公开草莓成熟度数据集',
    sourcePath: root,
    sourceUrl: 'https://github.com/amitamola/Strawberry-Counting-and-Ripeness-detection',
    classNames: ['unripe', 'partially_ripe', 'fully_ripe'],
    classAliases: {
      partially_ripe: ['halfripe', 'partially_ripe'],
      fully_ripe: ['ripe', 'fully_ripe']
    }
  })

  assert.equal(imported.dataset.active, true)
  assert.equal(imported.sampleCount, 3)

  const datasets = await repo.listDatasets()
  assert.equal(datasets.length, 1)
  assert.equal(datasets[0].active, true)
  assert.equal(datasets[0].sampleCount, 3)

  const samples = await repo.listDatasetSamples(datasets[0].id, { limit: 10, offset: 0 })
  assert.equal(samples.total, 3)
  assert.equal(samples.items.length, 3)
})
