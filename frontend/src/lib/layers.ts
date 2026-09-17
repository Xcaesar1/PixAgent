import type { LayerDocument } from '@/api/sessions'

const BASE = 'base'
const SUBJECT = 'subject'
const BACKGROUND = 'background'

/**
 * 与后端 `_layered` 对齐：已拆层或有多张图像层时，整图类生成（换背景、扩图、超分）
 * 只把结果挂到图片墙，不写回画布。界面据此说清结果去哪了。
 */
export function wallOnly(document: LayerDocument): boolean {
  if (document.layers.filter((layer) => layer.kind === 'image').length > 1) return true
  const ids = new Set(document.layers.map((layer) => layer.id))
  if (ids.has(BACKGROUND) && ids.has(SUBJECT)) return true
  return ids.has(BACKGROUND) && !ids.has(BASE)
}
