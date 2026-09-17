import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import BrandMark from '@/components/BrandMark'
import ToastHost from '@/components/ToastHost'
import { useAuthActions, useCurrentUser } from '@/hooks/useAuth'

const NAV_ITEMS = [
  { to: '/create', label: '创作', icon: 'M12 4v16m8-8H4' },
  { to: '/editor', label: '编辑', icon: 'M4 20h4L20 8l-4-4L4 16v4z' },
  { to: '/marketing', label: '导出', icon: 'M12 3v12m0 0-4-4m4 4 4-4M5 21h14' },
  { to: '/batch', label: '批量', icon: 'M4 6h16M4 12h16M4 18h10' },
]

function NavIcon({ path }: { path: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="size-5 shrink-0" aria-hidden>
      <path d={path} stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

/** 工作台外壳：左侧导航默认收起为图标，悬停展开文字。 */
export default function WorkbenchLayout() {
  const navigate = useNavigate()
  const { user } = useCurrentUser()
  const { logout } = useAuthActions()

  const signOut = () =>
    logout.mutate(undefined, { onSuccess: () => navigate('/', { replace: true }) })

  return (
    <div className="flex h-screen overflow-hidden">
      <nav className="relative z-30 w-16 shrink-0" aria-label="工作台">
        <div className="group border-line bg-paper absolute inset-y-0 left-0 flex w-16 flex-col overflow-hidden border-r py-4 transition-[width,box-shadow] duration-200 hover:w-52 hover:shadow-panel">
          <BrandMark size="sm" className="mb-6 px-5">
            <span className="text-ink truncate text-sm font-semibold opacity-0 transition-opacity group-hover:opacity-100">
              AI 修图智能体
            </span>
          </BrandMark>

          <ul className="flex flex-1 flex-col gap-1 px-2">
            {NAV_ITEMS.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  title={item.label}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-[12px] px-3 py-2.5 text-sm transition-colors ${
                      isActive
                        ? 'bg-brand-soft text-brand-strong font-medium'
                        : 'text-muted hover:bg-soft hover:text-ink'
                    }`
                  }
                >
                  <NavIcon path={item.icon} />
                  <span className="truncate opacity-0 transition-opacity group-hover:opacity-100">
                    {item.label}
                  </span>
                </NavLink>
              </li>
            ))}
          </ul>

          <div className="border-line mt-2 border-t px-2 pt-3">
            <button
              type="button"
              onClick={signOut}
              title={user ? `${user.username} · 退出登录` : '退出登录'}
              className="text-muted hover:bg-soft hover:text-ink flex w-full items-center gap-3 rounded-[12px] px-3 py-2.5 text-sm transition-colors"
            >
              <span className="bg-brand-soft text-brand-strong grid size-5 shrink-0 place-items-center rounded-full text-[11px] font-semibold">
                {user?.username.slice(0, 1).toUpperCase() ?? '?'}
              </span>
              <span className="truncate opacity-0 transition-opacity group-hover:opacity-100">
                退出登录
              </span>
            </button>
          </div>
        </div>
      </nav>

      <main className="min-w-0 flex-1 overflow-auto">
        <Outlet />
      </main>
      <ToastHost />
    </div>
  )
}
