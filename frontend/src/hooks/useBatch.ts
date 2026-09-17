import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { batchesApi, type BatchInput } from '@/api/batches'
import { isTerminal } from '@/api/runs'
import { errorMessage } from '@/hooks/useAuth'
import { useRun } from '@/hooks/useRun'
import { toast } from '@/stores/toasts'

const LIST_KEY = ['batches']
const batchKey = (id: string) => ['batch', id]

export function useBatches() {
  return useQuery({ queryKey: LIST_KEY, queryFn: batchesApi.list })
}

export function useBatch(id: string | null) {
  const live = useRun(id)
  const queryClient = useQueryClient()
  const detail = useQuery({
    queryKey: batchKey(id ?? ''),
    queryFn: () => batchesApi.get(id as string),
    enabled: Boolean(id),
    refetchInterval: id && live.status && !isTerminal(live.status) ? 1200 : false,
  })

  useEffect(() => {
    if (!id || !live.status || !isTerminal(live.status)) return
    void queryClient.invalidateQueries({ queryKey: batchKey(id) })
    void queryClient.invalidateQueries({ queryKey: LIST_KEY })
  }, [id, live.status, queryClient])

  return { ...detail, live }
}

export function useCreateBatch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: BatchInput) => batchesApi.create(input),
    onSuccess: (run) => {
      void queryClient.invalidateQueries({ queryKey: LIST_KEY })
      queryClient.setQueryData(batchKey(run.id), undefined)
    },
    onError: (error) => toast(errorMessage(error), 'danger'),
  })
}

export function useExportBatch(id: string) {
  return useMutation({
    mutationFn: () => batchesApi.export(id),
    onError: (error) => toast(errorMessage(error), 'danger'),
  })
}
