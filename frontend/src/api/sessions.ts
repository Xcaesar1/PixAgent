import type { Asset } from '@/api/assets'
import { api, apiError } from '@/api/client'
import type { Run } from '@/api/runs'

export type LayerKind = 'image' | 'text' | 'shape'

export type Transform = {
  x: number
  y: number
  scale_x: number
  scale_y: number
  rotation: number
}

export type Layer = {
  id: string
  kind: LayerKind
  name: string
  width: number
  height: number
  asset_id: string | null
  transform: Transform
  opacity: number
  visible: boolean
  locked: boolean
  source_hash?: string | null
  text?: string | null
  font_size?: number
  fill?: string
}

export type LayerDocument = {
  width: number
  height: number
  layers: Layer[]
}

export type Session = {
  id: string
  title: string
  revision: number
  history_seq: number
  original_asset_id: string
  current_asset_id: string
  created_at: string
  updated_at: string
}

export type SessionDetail = Session & {
  document: LayerDocument
  previous_document: LayerDocument | null
  assets: Asset[]
  can_undo: boolean
  can_redo: boolean
}

export type HistoryEntry = {
  seq: number
  action: string
  params: Record<string, unknown>
  result: Record<string, unknown>
  created_at: string
}

export type SessionCreateInput = {
  current_asset_id: string
  asset_ids?: string[]
  title?: string
}

export type SessionPatchInput = {
  title?: string
  current_asset_id?: string
}

export type ToolInvoke = {
  run: Run
  session: SessionDetail
}

export const ACTION_LABELS: Record<string, string> = {
  create_session: '新建会话',
  switch_current: '切换当前图',
  generate_image: '生成图片',
  replace_background: '换背景',
  expand_canvas: '扩图',
  upscale_image: '超分',
  remove_background: '去背景',
  adjust_image: '调色',
  erase_region: '局部消除',
  replace_region: '局部替换',
  crop_canvas: '裁剪',
  flip_layer: '翻转',
  set_layer_opacity: '透明度',
  set_layer_visible: '显隐',
  set_layer_text: '改文字',
  reorder_layer: '图层顺序',
  scale_layer: '缩放',
  rotate_layer: '旋转',
  move_layer: '移动',
  split_layers: '拆层',
  promote_object_to_layer: '提升为图层',
  generate_marketing: '营销图',
  prepare_delivery_sizes: '投放尺寸',
}

export type ExportPack = {
  blob: Blob
  filename: string
}

export type Marker = { index: number; x: number; y: number }

export type Selection = {
  revision: number
  mask: Asset
  markers: Marker[]
}

export type SelectInput = {
  revision: number
  points?: { x: number; y: number }[]
  strokes?: { x: number; y: number }[][]
  radius?: number
  append?: boolean
}

export const sessionsApi = {
  create: (input: SessionCreateInput) => api.post<SessionDetail>('/sessions', input),
  list: () => api.get<Session[]>('/sessions'),
  get: (id: string) => api.get<SessionDetail>(`/sessions/${id}`),
  patch: (id: string, input: SessionPatchInput) =>
    api.patch<SessionDetail>(`/sessions/${id}`, input),
  history: (id: string) => api.get<HistoryEntry[]>(`/sessions/${id}/history`),
  invoke: (id: string, tool: string, params: Record<string, unknown> = {}) =>
    api.post<ToolInvoke>(`/sessions/${id}/tools`, { tool, params }),
  undo: (id: string) => api.post<SessionDetail>(`/sessions/${id}/undo`),
  redo: (id: string) => api.post<SessionDetail>(`/sessions/${id}/redo`),
  select: (id: string, input: SelectInput) => api.post<Selection>(`/sessions/${id}/selection`, input),
  prepareSelection: (id: string) => api.post<void>(`/sessions/${id}/selection/prepare`),
  getSelection: (id: string) => api.get<Selection | null>(`/sessions/${id}/selection`),
  clearSelection: (id: string) => api.delete<void>(`/sessions/${id}/selection`),
  export: (id: string, asset_ids: string[] = []) => downloadExport(id, asset_ids),
}

async function downloadExport(id: string, asset_ids: string[]): Promise<ExportPack> {
  const response = await fetch(`/api/sessions/${id}/exports`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ asset_ids }),
  })
  if (!response.ok) throw await apiError(response, '打包失败')
  return { blob: await response.blob(), filename: filenameOf(response.headers.get('Content-Disposition')) }
}

function filenameOf(header: string | null): string {
  if (!header) return '物料.zip'
  const encoded = /filename\*=(?:UTF-8'')?([^;]+)/i.exec(header)
  if (encoded) return decodeURIComponent(encoded[1])
  const plain = /filename="?([^"]+)"?/i.exec(header)
  return plain?.[1] ?? '物料.zip'
}
