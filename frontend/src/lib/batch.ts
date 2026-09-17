import type { Ratio } from '@/api/runs'

export type BatchTool =
  | 'remove_background'
  | 'replace_background'
  | 'adjust_image'
  | 'upscale_image'
  | 'expand_canvas'
  | 'prepare_delivery_sizes'

export type BatchOp = {
  tool: BatchTool
  params: Record<string, unknown>
}

export const BATCH_STEPS: { id: BatchTool; label: string; hint: string }[] = [
  { id: 'remove_background', label: '去背景', hint: '去掉背景，保留主体' },
  { id: 'replace_background', label: '换背景', hint: '按描述替换背景' },
  { id: 'adjust_image', label: '调色', hint: '亮度、对比度、饱和度' },
  { id: 'upscale_image', label: '超分', hint: '提高分辨率' },
  { id: 'expand_canvas', label: '扩图', hint: '扩展到指定比例' },
  { id: 'prepare_delivery_sizes', label: '投放尺寸', hint: '完整放入 1:1 / 4:5 / 9:16' },
]

export const EXPAND_RATIOS: Ratio[] = ['1:1', '4:5', '9:16', '16:9']

export type BatchDraft = {
  selected: BatchTool[]
  prompt: string
  brightness: number
  contrast: number
  saturation: number
  scale: 2 | 4
  expandRatio: Ratio
  delivery: Ratio[]
  formats: Array<'png' | 'jpg'>
}

export const EMPTY_DRAFT: BatchDraft = {
  selected: ['remove_background'],
  prompt: '',
  brightness: 0,
  contrast: 0,
  saturation: 0,
  scale: 2,
  expandRatio: '16:9',
  delivery: ['1:1', '4:5', '9:16'],
  formats: ['png'],
}

export function operationsOf(draft: BatchDraft): BatchOp[] {
  return draft.selected.map((tool) => {
    if (tool === 'replace_background') return { tool, params: { prompt: draft.prompt.trim() } }
    if (tool === 'adjust_image') {
      return {
        tool,
        params: {
          brightness: draft.brightness,
          contrast: draft.contrast,
          saturation: draft.saturation,
        },
      }
    }
    if (tool === 'upscale_image') return { tool, params: { scale: draft.scale } }
    if (tool === 'expand_canvas') return { tool, params: { ratio: draft.expandRatio } }
    if (tool === 'prepare_delivery_sizes') return { tool, params: { ratios: draft.delivery } }
    return { tool, params: {} }
  })
}

export function draftReady(draft: BatchDraft, assetCount: number): string | null {
  if (assetCount === 0) return '先选至少一张图'
  if (draft.selected.length === 0) return '先勾选至少一步处理'
  if (draft.selected.includes('replace_background') && !draft.prompt.trim()) {
    return '换背景需要填写描述'
  }
  if (draft.selected.includes('prepare_delivery_sizes') && draft.delivery.length === 0) {
    return '投放尺寸至少选一个比例'
  }
  if (draft.formats.length === 0) return '至少选择一种导出格式'
  return null
}
