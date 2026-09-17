import { Link } from 'react-router-dom'

import BrandMark from '@/components/BrandMark'

export default function LandingHeader({ account }: { account: string | null }) {
  return (
    <header className="border-line/70 bg-canvas/80 sticky top-0 z-10 border-b backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3.5">
        <Link to="/" aria-label="AI 修图智能体首页">
          <BrandMark size="sm">
            <span className="text-ink text-sm font-semibold">AI 修图智能体</span>
          </BrandMark>
        </Link>

        {account ? (
          <Link
            to="/create"
            className="border-line-strong text-ink hover:bg-soft rounded-control border px-3.5 py-1.5 text-sm font-medium transition-colors"
          >
            {account} · 进入工作台
          </Link>
        ) : (
          <Link to="/auth" className="text-muted hover:text-ink text-sm transition-colors">
            登录
          </Link>
        )}
      </div>
    </header>
  )
}
