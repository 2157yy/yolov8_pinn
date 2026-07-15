import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'

const testDir = path.dirname(fileURLToPath(import.meta.url))
const projectRoot = path.resolve(testDir, '../..')

test('qwen bridge imports under the active python interpreter', () => {
  const result = spawnSync('python3', ['-c', 'import qwen_web_chat'], {
    cwd: projectRoot,
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    encoding: 'utf8'
  })

  assert.equal(result.status, 0, result.stderr || result.stdout)
})
