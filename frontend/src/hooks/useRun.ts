import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { isTerminal, runsApi, type GenerateInput, type Run, type RunStatus } from '@/api/runs'
import { useSmoothedProgress } from '@/hooks/useSmoothedProgress'

type Progress = Pick<Run, 'id' | 'tool' | 'status' | 'progress' | 'stage' | 'error' | 'result'>

const runKey = (id: string) => ['run', id]

export function useGenerate() {
  return useMutation({ mutationFn: (input: GenerateInput) => runsApi.generate(input) })
}

/**
 * 合并两个进度来源：SSE 提供实时状态，快照接口提供候选图与刷新后的恢复能力。
 */
export function useRun(runId: string | null) {
  const queryClient = useQueryClient()
  const [live, setLive] = useState<Progress | null>(null)

  const snapshot = useQuery({
    queryKey: runKey(runId ?? ''),
    queryFn: () => runsApi.get(runId as string),
    enabled: Boolean(runId),
  })

  const snapshotStatus = snapshot.data?.status

  useEffect(() => {
    // 已结束的任务不必再挂 SSE，否则重连会反复打快照、刷新签名 URL
    if (!runId || (snapshotStatus && isTerminal(snapshotStatus))) return

    const source = new EventSource(`/events/runs/${runId}`)
    source.onmessage = (event) => {
      const payload = JSON.parse(event.data) as Progress
      setLive(payload)
      if (isTerminal(payload.status)) {
        source.close()
        void queryClient.invalidateQueries({ queryKey: runKey(runId) })
      }
    }

    return () => source.close()
  }, [runId, snapshotStatus, queryClient])

  const run = snapshot.data
  // 切换任务后旧连接的残留帧不应影响新任务
  const current = live?.id === runId ? live : null
  const status: RunStatus | undefined = current?.status ?? run?.status
  const reported = current?.progress ?? run?.progress ?? 0
  const progress = useSmoothedProgress({
    reported,
    status,
    tool: current?.tool ?? run?.tool,
    token: runId,
  })

  return {
    status,
    progress,
    stage: current?.stage ?? run?.stage ?? '',
    error: current?.error ?? run?.error ?? null,
    prompt: run?.prompt ?? null,
    candidates: run?.candidates ?? [],
    result: current?.result ?? run?.result ?? {},
    isLoading: snapshot.isPending,
    notFound: snapshot.isError,
  }
}
