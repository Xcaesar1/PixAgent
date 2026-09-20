import { api } from '@/api/client'
import type { Asset } from '@/api/assets'

export type Ratio = '1:1' | '4:5' | '3:4' | '9:16' | '16:9'

export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'canceled'
export type GenerationProvider =
  | 'dashscope'
  | 'l0veyou'
  | 'l0veyou-gpt-image-2-5-flare'
  | 'l0veyou-gpt-image-2-5-full'
  | 'mock'
export type GenerationModes = {
  default: GenerationProvider | null
  modes: {
    id: GenerationProvider
    label: string
    enabled: boolean
    description: string
    ratios: Ratio[]
    counts: number[]
  }[]
}

export type Run = {
  id: string
  tool: string
  status: RunStatus
  progress: number
  stage: string
  error: string | null
  prompt: string | null
  provider?: GenerationProvider | null
  candidates: Asset[]
  result: Record<string, unknown>
}

export type GenerateInput = {
  provider?: GenerationProvider
  prompt: string
  ratio: Ratio
  count: number
  negative_prompt?: string
  reference_asset_ids?: string[]
}

export const RATIO_LABELS: Record<Ratio, string> = {
  '1:1': '方形 1:1',
  '4:5': '竖版 4:5',
  '3:4': '竖版 3:4',
  '9:16': '长图 9:16',
  '16:9': '横版 16:9',
}

export function isTerminal(status: RunStatus) {
  return status === 'succeeded' || status === 'failed' || status === 'canceled'
}

export const runsApi = {
  modes: () => api.get<GenerationModes>('/generation-modes'),
  generate: (input: GenerateInput) => api.post<Run>('/generations', input),
  get: (id: string) => api.get<Run>(`/runs/${id}`),
}
