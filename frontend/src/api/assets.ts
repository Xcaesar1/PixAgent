import { ApiError, apiError } from '@/api/client'

export type AssetKind =
  | 'original'
  | 'generated'
  | 'subject'
  | 'background'
  | 'mask'
  | 'marketing'
  | 'export'

export type Asset = {
  id: string
  kind: AssetKind
  source: 'upload' | 'generate' | 'tool'
  image_format: string
  width: number
  height: number
  size_bytes: number
  has_alpha: boolean
  created_at: string
  url: string
}

export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024
export const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp']

export type LibraryGroup = {
  session_id: string | null
  title: string
  updated_at: string
  cover: Asset
  assets: Asset[]
}

export const assetsApi = {
  async upload(file: File): Promise<Asset> {
    const body = new FormData()
    body.append('file', file)

    const response = await fetch('/api/assets', { method: 'POST', body })
    if (!response.ok) throw await apiError(response, '上传失败')
    return response.json()
  },

  async list(limit = 50): Promise<Asset[]> {
    const response = await fetch(`/api/assets?limit=${limit}`)
    if (!response.ok) throw new ApiError(response.status, '读取素材失败')
    return response.json()
  },

  async library(limit = 50): Promise<LibraryGroup[]> {
    const response = await fetch(`/api/assets/library?limit=${limit}`)
    if (!response.ok) throw new ApiError(response.status, '读取素材失败')
    return response.json()
  },
}
