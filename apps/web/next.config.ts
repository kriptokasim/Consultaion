import type { NextConfig } from 'next'
import fs from 'fs'
import path from 'path'

const ensureLocalNodeTypes = () => {
  try {
    const projectRoot = __dirname
    const targetDir = path.join(projectRoot, 'node_modules', '@types', 'node')
    const stubDir = path.join(projectRoot, 'types', 'node-stubs')
    if (fs.existsSync(path.join(targetDir, 'index.d.ts')) || !fs.existsSync(stubDir)) {
      return
    }
    fs.mkdirSync(targetDir, { recursive: true })
    fs.copyFileSync(path.join(stubDir, 'index.d.ts'), path.join(targetDir, 'index.d.ts'))
    fs.copyFileSync(path.join(stubDir, 'package.json'), path.join(targetDir, 'package.json'))
  } catch (error) {
    console.warn('Unable to prepare local Node types, continuing without stub', error)
  }
}

ensureLocalNodeTypes()

const nextConfig: NextConfig = {}

export default nextConfig
