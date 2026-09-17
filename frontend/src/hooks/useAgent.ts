import { useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { agentApi } from '@/api/agent'
import { isTerminal } from '@/api/runs'

const turnsKey = (sessionId: string) => ['session', sessionId, 'messages']

function useRefreshTurn(sessionId: string) {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: turnsKey(sessionId) })
    void queryClient.invalidateQueries({ queryKey: ['session', sessionId] })
    void queryClient.invalidateQueries({ queryKey: ['session', sessionId, 'history'] })
  }
}

export function useTurns(sessionId: string) {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: turnsKey(sessionId),
    queryFn: () => agentApi.turns(sessionId),
    // 第一步 SSE 结束时下一步可能还没写进计划，整轮 running 时接着拉，避免卡片停在「等待中」
    refetchInterval: (current) =>
      current.state.data?.at(-1)?.status === 'running' ? 800 : false,
  })

  const latest = query.data?.at(-1)?.status
  const previous = useRef(latest)
  useEffect(() => {
    const wasRunning = previous.current === 'running'
    previous.current = latest
    if (!wasRunning || !latest || !isTerminal(latest)) return
    void queryClient.invalidateQueries({ queryKey: ['session', sessionId] })
    void queryClient.invalidateQueries({ queryKey: ['session', sessionId, 'history'] })
  }, [latest, sessionId, queryClient])

  useEffect(() => {
    previous.current = undefined
  }, [sessionId])

  return query
}

export function useSendMessage(sessionId: string) {
  const refresh = useRefreshTurn(sessionId)
  return useMutation({
    mutationFn: (text: string) => agentApi.send(sessionId, text),
    onSuccess: refresh,
  })
}

export function usePlanActions(sessionId: string) {
  const refresh = useRefreshTurn(sessionId)
  const confirm = useMutation({
    mutationFn: (turnId: string) => agentApi.confirm(sessionId, turnId),
    onSuccess: refresh,
  })
  const cancel = useMutation({
    mutationFn: (turnId: string) => agentApi.cancel(sessionId, turnId),
    onSuccess: refresh,
  })
  const retry = useMutation({
    mutationFn: (turnId: string) => agentApi.retry(sessionId, turnId),
    onSuccess: refresh,
  })
  return {
    confirm: (turnId: string) => confirm.mutate(turnId),
    cancel: (turnId: string) => cancel.mutate(turnId),
    retry: (turnId: string) => retry.mutate(turnId),
    busy: confirm.isPending || cancel.isPending || retry.isPending,
  }
}
