import { Navigate, Outlet } from 'react-router-dom'

import { useCurrentUser } from '@/hooks/useAuth'

export default function RequireAuth() {
  const { user, isLoading } = useCurrentUser()

  if (isLoading) {
    return <div className="text-muted flex h-screen items-center justify-center text-sm">加载中…</div>
  }
  return user ? <Outlet /> : <Navigate to="/auth" replace />
}
