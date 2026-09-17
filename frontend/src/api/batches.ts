import type { Asset } from '@/api/assets'
import { api, apiError } from '@/api/client'
import type { Run } from '@/api/runs'
import type { BatchOp } from '@/lib/batch'

export type BatchItem = {
  source: Asset
  status: 'pending' | 'running' | 'succeeded' | 'failed'
  error: string | null
  outputs: Asset[]
}

export type Batch = {
  run: Run
  items: BatchItem[]
  created_at: string
}

export type BatchInput = {
  asset_ids: string[]
  operations: BatchOp[]
  formats: Array<'png' | 'jpg'>
}

export type ExportPack = {
  blob: Blob
  filename: string
}

export const batchesApi = {
  create: (input: BatchInput) => api.post<Run>('/batches', input),
  list: () => api.get<Batch[]>('/batches'),
  get: (id: string) => api.get<Batch>(`/batches/${id}`),
  export: (id: string) => downloadZip(id),
}

async function downloadZip(id: string): Promise<ExportPack> {
  const response = await fetch(`/api/batches/${id}/export`)
  if (!response.ok) throw await apiError(response, '打包失败')
  const encoded = /filename\*=(?:UTF-8'')?([^;]+)/i.exec(
    response.headers.get('Content-Disposition') ?? '',
  )
  const filename = encoded ? decodeURIComponent(encoded[1]) : '批量导出.zip'
  return { blob: await response.blob(), filename }
}
