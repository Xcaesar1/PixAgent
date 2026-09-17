import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { authApi, type Credentials, type User } from '@/api/auth'
import { ApiError } from '@/api/client'

const ME_KEY = ['auth', 'me']

/** 会话状态以服务端 Cookie 为准，前端不持有令牌，只缓存当前用户。 */
export function useCurrentUser() {
  const { data, isPending } = useQuery({
    queryKey: ME_KEY,
    queryFn: () => authApi.me(),
    retry: false,
    staleTime: Infinity,
    // 未登录是正常状态，不作为错误向上抛
    throwOnError: false,
  })
  return { user: data ?? null, isLoading: isPending }
}

export function useAuthActions() {
  const queryClient = useQueryClient()
  const cacheUser = (user: User) => queryClient.setQueryData(ME_KEY, user)

  const login = useMutation({
    mutationFn: (body: Credentials) => authApi.login(body),
    onSuccess: cacheUser,
  })
  const register = useMutation({
    mutationFn: (body: Credentials) => authApi.register(body),
    onSuccess: cacheUser,
  })
  const logout = useMutation({
    mutationFn: () => authApi.logout(),
    onSuccess: () => queryClient.clear(),
  })

  return { login, register, logout }
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return error instanceof Error ? error.message : '请求失败，请稍后重试'
}
