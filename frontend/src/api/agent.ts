import { api } from '@/api/client'
import type { RunStatus } from '@/api/runs'

export type StepStatus =
  | 'pending'
  | 'waiting'
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'canceled'

export type PlanStep = {
  id: string
  tool: string
  label: string
  depends_on: string[]
  run_id: string | null
  status: StepStatus
}

export type Turn = {
  id: string
  revision: number
  goal: string
  reply: string
  status: RunStatus
  error: string | null
  created_at: string
  steps: PlanStep[]
}

export const agentApi = {
  turns: (sessionId: string) => api.get<Turn[]>(`/sessions/${sessionId}/messages`),
  send: (sessionId: string, text: string) =>
    api.post<Turn>(`/sessions/${sessionId}/messages`, { text }),
  confirm: (sessionId: string, turnId: string) =>
    api.post<Turn>(`/sessions/${sessionId}/messages/${turnId}/confirm`),
  cancel: (sessionId: string, turnId: string) =>
    api.post<Turn>(`/sessions/${sessionId}/messages/${turnId}/cancel`),
  retry: (sessionId: string, turnId: string) =>
    api.post<Turn>(`/sessions/${sessionId}/messages/${turnId}/retry`),
}
