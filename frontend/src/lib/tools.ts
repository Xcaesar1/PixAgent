import { ACTION_LABELS } from '@/api/sessions'

/**
 * 结果不容易手工还原的操作。这类操作不做二次确认，改为完成后在提示里给撤销入口，
 * 手感更轻但仍然可退。图层变换、显隐这些随手可改的就不打扰。
 */
const UNDOABLE = new Set([
  'split_layers',
  'promote_object_to_layer',
  'remove_background',
  'replace_background',
  'expand_canvas',
  'upscale_image',
  'erase_region',
  'replace_region',
  'adjust_image',
  'crop_canvas',
  'flip_layer',
])

export function toolLabel(tool: string | undefined) {
  if (!tool) return ''
  return ACTION_LABELS[tool] ?? ''
}

export function offersUndo(tool: string | undefined) {
  return Boolean(tool && UNDOABLE.has(tool))
}
