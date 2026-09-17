import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import type { Asset } from '@/api/assets'
import ProgressBar from '@/components/ui/ProgressBar'
import { useRun } from '@/hooks/useRun'
import { useCreateSession } from '@/hooks/useSessions'

export default function CandidatesPage() {
  const { runId = '' } = useParams()
  const navigate = useNavigate()
  const [picked, setPicked] = useState<string | null>(null)
  const { status, progress, stage, error, prompt, candidates, notFound } = useRun(runId || null)
  const createSession = useCreateSession()

  // 采用一张进入编辑，同批其余候选一并带进会话图片墙
  const adopt = () =>
    picked &&
    createSession.mutate(
      {
        current_asset_id: picked,
        asset_ids: candidates.map((asset) => asset.id),
        title: prompt ?? undefined,
      },
      { onSuccess: (session) => navigate(`/editor/${session.id}`) },
    )

  if (notFound) {
    return <Centered title="任务不存在" hint="链接可能已失效，回到创作页重新开始。" />
  }

  if (status === 'failed' || status === 'canceled') {
    return (
      <Centered title="生成失败" hint={error ?? '未知原因'}>
        <Link
          to="/create"
          className="bg-ink hover:bg-dark rounded-control mt-5 px-4 py-2 text-sm font-medium text-white"
        >
          返回重试
        </Link>
      </Centered>
    )
  }

  if (status !== 'succeeded') {
    return <Progress percent={progress} stage={stage} />
  }

  return (
    <div className="mx-auto max-w-5xl px-8 py-10">
      <header className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-ink text-2xl font-semibold tracking-tight">选出一张</h1>
          <p className="text-muted mt-1 text-sm">
            挑一张满意的进入编辑，其余候选图会留在会话图片墙随时切回。
          </p>
        </div>
        <button
          type="button"
          disabled={!picked || createSession.isPending}
          onClick={adopt}
          className="bg-ink hover:bg-dark rounded-control shrink-0 px-4 py-2 text-sm font-medium text-white transition-all duration-150 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-40 disabled:active:scale-100"
        >
          {createSession.isPending ? '打开中…' : picked ? '进入编辑' : '先点选一张'}
        </button>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {candidates.map((asset, index) => (
          <Candidate
            key={asset.id}
            asset={asset}
            index={index}
            selected={picked === asset.id}
            onSelect={() => setPicked(asset.id)}
          />
        ))}
      </div>
    </div>
  )
}

function Candidate({
  asset,
  index,
  selected,
  onSelect,
}: {
  asset: Asset
  index: number
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`rounded-panel group relative block overflow-hidden border-2 bg-white transition-all duration-200 ${
        selected
          ? 'border-brand shadow-lift'
          : 'border-line hover:border-brand hover:-translate-y-0.5 hover:shadow-lift'
      }`}
    >
      <img
        src={asset.url}
        alt={`候选图 ${index + 1}`}
        loading="lazy"
        className="block max-h-[52vh] w-full object-contain transition-transform duration-300 group-hover:scale-[1.01]"
      />
      <span className="text-muted bg-paper/90 absolute top-2 left-2 rounded-full px-2 py-0.5 text-xs font-medium backdrop-blur">
        {index + 1}
      </span>
      {selected && (
        <span className="bg-brand absolute top-2 right-2 rounded-full px-2 py-0.5 text-xs font-medium text-white">
          已选
        </span>
      )}
    </button>
  )
}

function Progress({ percent, stage }: { percent: number; stage: string }) {
  return (
    <Centered title="正在生成" hint={stage || '任务已提交，正在排队'}>
      <ProgressBar value={percent} className="mt-6 h-1 w-64 rounded-full" />
      <p className="text-faint mt-2 text-xs tabular-nums">{percent}%</p>
    </Centered>
  )
}

function Centered({
  title,
  hint,
  children,
}: {
  title: string
  hint: string
  children?: React.ReactNode
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center px-8 text-center">
      <h1 className="text-ink text-xl font-semibold">{title}</h1>
      <p className="text-muted mt-1 max-w-md text-sm">{hint}</p>
      {children}
    </div>
  )
}
