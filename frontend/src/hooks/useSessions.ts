import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { isTerminal } from '@/api/runs'
import {
  sessionsApi,
  type SessionCreateInput,
  type SessionDetail,
  type SessionPatchInput,
} from '@/api/sessions'
import { errorMessage } from '@/hooks/useAuth'
import { useRun } from '@/hooks/useRun'
import { offersUndo, toolLabel } from '@/lib/tools'
import { toast } from '@/stores/toasts'

const LIST_KEY = ['sessions']
const detailKey = (id: string) => ['session', id]
const historyKey = (id: string) => ['session', id, 'history']

export function useSessions() {
  return useQuery({ queryKey: LIST_KEY, queryFn: sessionsApi.list })
}

export function useSession(id: string | null) {
  return useQuery({
    queryKey: detailKey(id ?? ''),
    queryFn: () => sessionsApi.get(id as string),
    enabled: Boolean(id),
  })
}

export function useSessionHistory(id: string | null) {
  return useQuery({
    queryKey: historyKey(id ?? ''),
    queryFn: () => sessionsApi.history(id as string),
    enabled: Boolean(id),
  })
}

function useCacheSession(id: string) {
  const queryClient = useQueryClient()
  return (detail: SessionDetail) => {
    queryClient.setQueryData(detailKey(id), detail)
    void queryClient.invalidateQueries({ queryKey: LIST_KEY })
    void queryClient.invalidateQueries({ queryKey: historyKey(id) })
  }
}

export function useCreateSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: SessionCreateInput) => sessionsApi.create(input),
    onSuccess: (detail) => {
      queryClient.setQueryData(detailKey(detail.id), detail)
      void queryClient.invalidateQueries({ queryKey: LIST_KEY })
    },
  })
}

export function usePatchSession(id: string) {
  const cache = useCacheSession(id)
  return useMutation({
    mutationFn: (input: SessionPatchInput) => sessionsApi.patch(id, input),
    onSuccess: cache,
  })
}

export function useExportPack(id: string) {
  return useMutation({
    mutationFn: (assetIds: string[]) => sessionsApi.export(id, assetIds),
    onError: (error) => toast(errorMessage(error), 'danger'),
  })
}

export function useSessionTools(id: string) {
  const queryClient = useQueryClient()
  const cache = useCacheSession(id)
  const [pendingRunId, setPendingRunId] = useState<string | null>(null)
  const live = useRun(pendingRunId)

  const invoke = useMutation({
    mutationFn: ({ tool, params }: { tool: string; params?: Record<string, unknown> }) =>
      sessionsApi.invoke(id, tool, params),
    onSuccess: (body) => {
      cache(body.session)
      if (!isTerminal(body.run.status)) setPendingRunId(body.run.id)
    },
    onError: (error) => toast(errorMessage(error), 'danger'),
  })

  const historyLock = useRef(false)
  const unlockHistory = () => {
    historyLock.current = false
  }

  const undo = useMutation({
    mutationFn: () => sessionsApi.undo(id),
    onSuccess: cache,
    onError: (error) => toast(errorMessage(error), 'danger'),
    onSettled: unlockHistory,
  })
  const redo = useMutation({
    mutationFn: () => sessionsApi.redo(id),
    onSuccess: cache,
    onError: (error) => toast(errorMessage(error), 'danger'),
    onSettled: unlockHistory,
  })

  const waiting = Boolean(pendingRunId && (!live.status || !isTerminal(live.status)))
  const busy = invoke.isPending || undo.isPending || redo.isPending || waiting

  // 提示里的撤销要在完成那一刻才可用，用 ref 拿最新的 mutation，避免把它塞进 effect 依赖
  const undoRef = useRef(() => undo.mutate())
  undoRef.current = () => undo.mutate()
  const pendingTool = invoke.variables?.tool
  // 一个任务只播报一次，后续依赖变化不会再弹提示
  const announced = useRef<string | null>(null)

  useEffect(() => {
    if (!pendingRunId || !live.status || !isTerminal(live.status)) return
    if (announced.current === pendingRunId) return
    announced.current = pendingRunId
    void queryClient.invalidateQueries({ queryKey: detailKey(id) })
    void queryClient.invalidateQueries({ queryKey: historyKey(id) })
    if (live.status === 'failed') {
      toast(live.error || '处理失败', 'danger')
      return
    }
    const label = toolLabel(pendingTool)
    toast(
      label ? `${label}完成` : live.stage || '已完成',
      'ok',
      offersUndo(pendingTool)
        ? { action: { label: '撤销', run: () => undoRef.current() } }
        : undefined,
    )
  }, [pendingRunId, live.status, live.error, live.stage, pendingTool, id, queryClient])

  /**
   * 当前在跑的是不是这一次调用。工具层同时只跑一个任务，界面据此只给发起的那个按钮
   * 换进度文案，其余按钮虽然一样禁用，但不会看起来像是也在生成。
   */
  const isRunning = (tool: string, match?: (params: Record<string, unknown>) => boolean) => {
    const pending = invoke.isPending || waiting ? invoke.variables : undefined
    if (pending?.tool !== tool) return false
    return match ? match(pending.params ?? {}) : true
  }

  const runHistory = (action: () => void) => {
    if (historyLock.current || busy) return
    historyLock.current = true
    action()
  }

  return {
    invoke: (tool: string, params?: Record<string, unknown>) => invoke.mutate({ tool, params }),
    undo: () => runHistory(() => undo.mutate()),
    redo: () => runHistory(() => redo.mutate()),
    busy,
    isRunning,
    pending: waiting,
    pendingStage: waiting ? live.stage : '',
    pendingProgress: waiting ? live.progress : 0,
  }
}

export type SessionTools = ReturnType<typeof useSessionTools>
