import { useMemo, useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import AssetLibrary from '@/components/AssetLibrary'
import ProgressBar from '@/components/ui/ProgressBar'
import type { Asset } from '@/api/assets'
import type { SessionDetail } from '@/api/sessions'
import { errorMessage } from '@/hooks/useAuth'
import { useAssetLibrary } from '@/hooks/useAssets'
import { useCreateSession, useExportPack, useSession, useSessionTools, useSessions } from '@/hooks/useSessions'
import { shortTitle } from '@/lib/format'
import {
  DELIVERY_RATIOS,
  KIND_LABELS,
  MARKETING_KINDS,
  defaultSelected,
  packable,
  ratioLabel,
} from '@/lib/marketing'
import { toast } from '@/stores/toasts'

export default function MarketingPage() {
  const { sessionId = '' } = useParams()
  return sessionId ? <Workspace sessionId={sessionId} /> : <Picker />
}

function Picker() {
  const navigate = useNavigate()
  const { data: groups = [], isPending } = useAssetLibrary()
  const createSession = useCreateSession()

  const open = (id: string) => navigate(`/marketing/${id}`)

  return (
    <div className="mx-auto max-w-4xl px-8 py-10">
      <PageTitle />
      <h2 className="text-muted mb-3 text-sm font-medium">选择会话</h2>
      {isPending ? (
        <p className="text-faint text-sm">加载中…</p>
      ) : groups.length === 0 ? (
        <p className="text-faint text-sm">
          还没有可导出的会话，先到
          <Link to="/create" className="text-brand-strong mx-1">
            创作
          </Link>
          打开一张图。
        </p>
      ) : (
        <AssetLibrary
          groups={groups}
          onOpenSession={open}
          onOpenAsset={(assetId) =>
            createSession.mutate(
              { current_asset_id: assetId },
              { onSuccess: (session) => open(session.id) },
            )
          }
        />
      )}
    </div>
  )
}

function Workspace({ sessionId }: { sessionId: string }) {
  const { data: session, isError } = useSession(sessionId)
  const tools = useSessionTools(sessionId)
  const pack = useExportPack(sessionId)
  const [copy, setCopy] = useState('')
  const [picked, setPicked] = useState<string[] | null>(null)

  const selected = useMemo(() => {
    if (!session) return []
    return picked ?? defaultSelected(session.assets, session.current_asset_id)
  }, [session, picked])

  if (!session) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-8 text-center">
        <h1 className="text-ink text-lg font-semibold">{isError ? '会话不存在' : '加载中'}</h1>
        <p className="text-muted mt-1 text-sm">
          {isError ? '回到列表另选一个会话。' : '正在读取画布与素材'}
        </p>
        {isError && (
          <Link to="/marketing" className="text-brand-strong mt-4 text-sm">
            返回导出物料
          </Link>
        )}
      </div>
    )
  }

  const current = session.assets.find((asset) => asset.id === session.current_asset_id)
  const items = session.assets.filter((asset) => packable(asset, session.current_asset_id))

  const toggle = (id: string) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setPicked([...next])
  }

  const toggleAll = () => {
    const ids = items.map((asset) => asset.id)
    setPicked(ids.every((id) => selected.includes(id)) ? [] : ids)
  }

  // 不传 ratios 是「一次三个尺寸」，传了则只跑该比例
  const deliveryRunning = (ratio?: string) =>
    tools.isRunning('prepare_delivery_sizes', (params) => {
      const ratios = params.ratios as string[] | undefined
      return ratio ? ratios?.[0] === ratio : !ratios
    })

  const download = () =>
    pack.mutate(selected, {
      onSuccess: ({ blob, filename }) => {
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = filename
        link.click()
        URL.revokeObjectURL(url)
        toast(`已打包 ${selected.length} 张`)
      },
    })

  return (
    <div className="mx-auto max-w-5xl px-8 py-10">
      <PageTitle
        action={
          <Link
            to={`/editor/${sessionId}`}
            className="border-line text-muted hover:bg-soft hover:text-ink shrink-0 rounded-control border px-3 py-1.5 text-xs font-medium"
          >
            回编辑器
          </Link>
        }
      />

      <section className="border-line bg-paper mb-8 flex items-center gap-4 rounded-[18px] border p-4">
        <div className="bg-canvas border-line size-20 shrink-0 overflow-hidden rounded-[12px] border">
          {current && <img src={current.url} alt="" className="size-full object-contain" />}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-ink truncate text-sm font-medium" title={session.title}>
            {shortTitle(session.title, 28)}
          </p>
          <p className="text-faint mt-1 text-xs tabular-nums">
            画布 {session.document.width} × {session.document.height}
          </p>
        </div>
        <SessionSwitch currentId={sessionId} />
      </section>

      <section className="mb-8">
        <SectionHead
          title="四类营销图"
          hint="以当前画布为参考生成，结果进图片墙，不改画布。"
        />
        <input
          value={copy}
          onChange={(event) => setCopy(event.target.value)}
          disabled={tools.busy}
          placeholder="可选：海报文案或补充要求，例如「新品首发 限时 8 折」"
          className="border-line text-ink placeholder:text-faint rounded-control mb-3 w-full border px-3 py-2 text-sm outline-none"
        />
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {MARKETING_KINDS.map((item) => (
            <KindCard
              key={item.id}
              label={item.label}
              hint={item.hint}
              disabled={tools.busy}
              running={tools.isRunning('generate_marketing', (params) => params.kind === item.id)}
              onGenerate={() =>
                tools.invoke('generate_marketing', {
                  kind: item.id,
                  caption: copy.trim() || undefined,
                })
              }
            />
          ))}
        </div>
      </section>

      <section className="mb-8">
        <SectionHead
          title="投放尺寸"
          hint="扩到目标比例，主体不被裁切。默认可一次出三个投放尺寸。"
        />
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={tools.busy}
            onClick={() => tools.invoke('prepare_delivery_sizes')}
            className="bg-ink hover:bg-dark rounded-control px-3.5 py-2 text-xs font-medium text-white disabled:opacity-40"
          >
            {deliveryRunning() ? '生成中…' : '生成 1:1 / 4:5 / 9:16'}
          </button>
          {DELIVERY_RATIOS.map((ratio) => (
            <button
              key={ratio.value}
              type="button"
              disabled={tools.busy}
              onClick={() => tools.invoke('prepare_delivery_sizes', { ratios: [ratio.value] })}
              className="border-line text-muted hover:text-ink rounded-control border px-3 py-2 text-xs disabled:opacity-40"
            >
              {ratio.label}
              <span className="text-faint ml-1">
                {deliveryRunning(ratio.value) ? '生成中…' : ratio.size}
              </span>
            </button>
          ))}
        </div>
        {tools.busy && (
          <div className="mt-2">
            <p className="text-muted text-xs">
              {tools.pendingStage || '处理中'}
              {tools.pending ? ` · ${tools.pendingProgress}%` : ''}
            </p>
            {tools.pending && (
              <ProgressBar
                value={tools.pendingProgress}
                tone="brand"
                className="mt-1.5 h-0.5 w-48 rounded-full"
              />
            )}
          </div>
        )}
      </section>

      <PackList
        session={session}
        items={items}
        selected={selected}
        disabled={pack.isPending || tools.busy}
        packing={pack.isPending}
        onToggle={toggle}
        onToggleAll={toggleAll}
        onDownload={download}
        error={pack.isError ? errorMessage(pack.error) : null}
      />
    </div>
  )
}

function PageTitle({ action }: { action?: ReactNode }) {
  return (
    <header className="mb-8">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-ink text-2xl font-semibold tracking-tight">导出物料</h1>
        {action}
      </div>
      <p className="text-muted mt-1 max-w-xl text-sm">
        从当前会话出四类营销图和投放尺寸，再打包下载。
      </p>
    </header>
  )
}

function SectionHead({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="mb-3">
      <h2 className="text-ink text-sm font-medium">{title}</h2>
      <p className="text-faint mt-0.5 text-xs">{hint}</p>
    </div>
  )
}

function SessionSwitch({ currentId }: { currentId: string }) {
  const navigate = useNavigate()
  const { data: sessions = [] } = useSessions()
  if (sessions.length < 2) return null
  return (
    <select
      value={currentId}
      onChange={(event) => navigate(`/marketing/${event.target.value}`)}
      className="border-line text-ink max-w-44 shrink-0 truncate rounded-control border bg-transparent px-2 py-1.5 text-xs"
      aria-label="切换会话"
    >
      {sessions.map((item) => (
        <option key={item.id} value={item.id}>
          {shortTitle(item.title)}
        </option>
      ))}
    </select>
  )
}

function KindCard({
  label,
  hint,
  disabled,
  running,
  onGenerate,
}: {
  label: string
  hint: string
  disabled: boolean
  running: boolean
  onGenerate: () => void
}) {
  return (
    <div className="border-line bg-paper flex flex-col rounded-[16px] border p-4">
      <p className="text-ink text-sm font-medium">{label}</p>
      <p className="text-faint mt-1 min-h-8 flex-1 text-xs leading-relaxed">{hint}</p>
      <button
        type="button"
        disabled={disabled}
        onClick={onGenerate}
        className="border-line text-ink hover:bg-soft rounded-control mt-3 px-3 py-1.5 text-xs font-medium disabled:opacity-40"
      >
        {running ? '生成中…' : '生成'}
      </button>
    </div>
  )
}

function PackList({
  session,
  items,
  selected,
  disabled,
  packing,
  onToggle,
  onToggleAll,
  onDownload,
  error,
}: {
  session: SessionDetail
  items: Asset[]
  selected: string[]
  disabled: boolean
  packing: boolean
  onToggle: (id: string) => void
  onToggleAll: () => void
  onDownload: () => void
  error: string | null
}) {
  const allSelected = items.length > 0 && items.every((asset) => selected.includes(asset.id))

  return (
    <section>
      <div className="mb-3 flex items-start justify-between gap-3">
        <SectionHead title="打包下载" hint="勾选要进 ZIP 的图片，包内含 manifest.json。" />
        <div className="flex shrink-0 items-center gap-2">
          {items.length > 0 && (
            <button
              type="button"
              disabled={disabled}
              onClick={onToggleAll}
              className="border-line text-muted hover:text-ink rounded-control border px-3 py-2 text-xs font-medium disabled:opacity-40"
            >
              {allSelected ? '取消全选' : '全选'}
            </button>
          )}
          <button
            type="button"
            disabled={disabled || selected.length === 0}
            onClick={onDownload}
            className="bg-ink hover:bg-dark rounded-control px-3.5 py-2 text-xs font-medium text-white disabled:opacity-40"
          >
            {packing ? '处理中…' : `打包 ${selected.length} 张`}
          </button>
        </div>
      </div>
      {error && <p className="text-danger mb-2 text-xs">{error}</p>}
      {items.length === 0 ? (
        <p className="text-faint text-sm">还没有素材。</p>
      ) : (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {items.map((asset) => {
            const active = selected.includes(asset.id)
            return (
              <li key={asset.id}>
                <button
                  type="button"
                  onClick={() => onToggle(asset.id)}
                  aria-pressed={active}
                  className={`w-full overflow-hidden rounded-[16px] border-2 text-left transition-colors ${
                    active
                      ? 'border-brand bg-brand-soft shadow-control'
                      : 'border-line bg-paper hover:border-brand'
                  }`}
                >
                  <div className="bg-canvas relative aspect-square">
                    <img src={asset.url} alt="" className="size-full object-contain" />
                    <span
                      className={`absolute top-2 left-2 grid size-6 place-items-center rounded-full border-2 ${
                        active
                          ? 'border-brand bg-brand text-white'
                          : 'border-white/90 bg-ink/35 text-white/0'
                      }`}
                      aria-hidden
                    >
                      <CheckIcon />
                    </span>
                    <span className="bg-ink/70 absolute right-0 bottom-0 left-0 py-0.5 text-center text-[10px] text-white">
                      {KIND_LABELS[asset.kind]} · {ratioLabel(asset.width, asset.height)}
                    </span>
                  </div>
                  <p
                    className={`px-2.5 py-2 text-[11px] tabular-nums ${
                      active ? 'text-brand-strong' : 'text-muted'
                    }`}
                  >
                    {asset.width} × {asset.height}
                    {asset.id === session.current_asset_id ? ' · 当前' : ''}
                  </p>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" className="size-3.5" aria-hidden>
      <path
        d="M3.5 8.2 6.4 11l6.1-6.5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
