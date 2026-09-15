// PostToolUse(Write|Edit): format the touched file with the project's own formatter.
// Only formatting and import sorting — never lint auto-fixes, which would delete an
// import added one edit before its first use. Failures never block the edit.
import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { relative, resolve, sep } from 'node:path'

const root = resolve(import.meta.dirname, '..', '..')

let input = ''
for await (const chunk of process.stdin) input += chunk
const file = JSON.parse(input.replace(/^﻿/, '')).tool_input?.file_path
if (!file) process.exit(0)

const rel = relative(root, resolve(file)).split(sep).join('/')
const run = (cwd, cmd, args) =>
  spawnSync(cmd, args, { cwd: resolve(root, cwd), stdio: 'ignore', timeout: 30_000 })

if (rel.startsWith('backend/') && rel.endsWith('.py')) {
  const target = rel.slice('backend/'.length)
  run('backend', 'uv', ['run', 'ruff', 'check', '--select', 'I', '--fix', '--force-exclude', target])
  run('backend', 'uv', ['run', 'ruff', 'format', '--force-exclude', target])
} else if (rel.startsWith('frontend/') && /\.(tsx?|jsx?|json|css)$/.test(rel)) {
  const biome = resolve(root, 'frontend/node_modules/@biomejs/biome/bin/biome')
  if (existsSync(biome)) {
    const target = rel.slice('frontend/'.length)
    run('frontend', process.execPath, [biome, 'check', '--write', '--linter-enabled=false', target])
  }
}
