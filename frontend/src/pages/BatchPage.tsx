import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import type { Asset } from '@/api/assets'
import { isTerminal } from '@/api/runs'
import ImageDropzone from '@/components/ImageDropzone'
import ProgressBar from '@/components/ui/ProgressBar'
import { useCreateBatch, useBatch, useBatches, useExportBatch } from '@/hooks/useBatch'
import { errorMessage } from '@/hooks/useAuth'
import { useAssetLibrary, useUploadAsset } from '@/hooks/useAssets'
import { formatDateTime } from '@/lib/format'
import {
  BATCH_STEPS,
  EMPTY_DRAFT,
  EXPAND_RATIOS,
  type BatchDraft,
  type BatchTool,
  draftReady,
  operationsOf,
} from '@/lib/batch'
import { toast } from '@/stores/toasts'

const MAX_IMAGES = 20

export default function BatchPage() {
  const { runId = '' } = useParams()
  return runId ? <Watch runId={runId} /> : <Compose />
}

function Compose() {
  const navigate = useNavigate()
  const create = useCreateBatch()
  const upload = useUploadAsset()
  const { data: groups = [] } = useAssetLibrary()
  const { data: history = [] } = useBatches()
  const [assets, setAssets] = useState<Asset[]>([])
  const [draft, setDraft] = useState<BatchDraft>(EMPTY_DRAFT)
  const blocked = draftReady(draft, assets.length)

  const add = (asset: Asset) =>
    setAssets((current) =>
      current.some((item) => item.id === asset.id) || current.length >= MAX_IMAGES
        ? current
        : [...current, asset],
    )

  const start = () => {
    if (blocked) return
    create.mutate(
      {
        asset_ids: assets.map((asset) => asset.id),
        operations: operationsOf(draft),
        formats: draft.formats,
      },
      { onSuccess: (run) => navigate(`/batch/${run.id}`) },
    )
  }

  return (
    <div className="mx-auto max-w-5xl px-8 py-10">
      <h1 className="text-ink text-2xl font-semibold tracking-tight">批量</h1>
      <p className="text-muted mt-1 mb-8 text-sm">
        对多张图走同一套像素处理：去背景、换背景、调色、超分、扩图、投放尺寸。
      </p>

      <section className="mb-8">
        <h2 className="text-ink mb-3 text-sm font-medium">选择图片</h2>
        <ImageDropzone
          multiple
          disabled={upload.isPending || assets.length >= MAX_IMAGES}
          hint={`JPG / PNG / WebP，最多 ${MAX_IMAGES} 张`}
          onFile={(file) => upload.mutate(file, { onSuccess: add })}
        />
        {assets.length > 0 && (
          <ul className="mt-3 flex flex-wrap gap-2">
            {assets.map((asset) => (
              <li key={asset.id} className="relative">
                <img
                  src={asset.url}
                  alt=""
                  className="border-line size-16 rounded-[10px] border object-cover"
                />
                <button
                  type="button"
                  onClick={() => setAssets((current) => current.filter((item) => item.id !== asset.id))}
                  className="bg-ink/70 absolute -top-1 -right-1 grid size-5 place-items-center rounded-full text-[10px] text-white"
                  aria-label="移除"
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
        {groups.length > 0 && (
          <div className="mt-4">
            <p className="text-faint mb-2 text-xs">从历史素材添加</p>
            <ul className="flex flex-wrap gap-2">
              {groups.flatMap((group) => group.assets).slice(0, 12).map((asset) => (
                <li key={asset.id}>
                  <button type="button" onClick={() => add(asset)} className="block">
                    <img
                      src={asset.url}
                      alt=""
                      className="border-line size-14 rounded-[10px] border object-cover hover:border-brand"
                    />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <Pipeline draft={draft} onChange={setDraft} />

      <div className="mt-8 flex items-center gap-3">
        <button
          type="button"
          disabled={Boolean(blocked) || create.isPending}
          onClick={start}
          className="bg-ink hover:bg-dark rounded-control px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
        >
          {create.isPending ? '提交中…' : '开始处理'}
        </button>
        {blocked && <p className="text-faint text-xs">{blocked}</p>}
        {create.isError && <p className="text-danger text-xs">{errorMessage(create.error)}</p>}
      </div>

      {history.length > 0 && (
        <section className="mt-12">
          <h2 className="text-ink mb-3 text-sm font-medium">最近任务</h2>
          <ul className="space-y-2">
            {history.map((item) => (
              <li key={item.run.id}>
                <Link
                  to={`/batch/${item.run.id}`}
                  className="border-line bg-paper hover:border-brand flex items-center justify-between rounded-[14px] border px-4 py-3"
                >
                  <span className="text-ink text-sm">
                    {item.items.length} 张 · {item.run.stage || item.run.status}
                  </span>
                  <span className="text-faint text-xs tabular-nums">
                    {formatDateTime(item.created_at)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

function Watch({ runId }: { runId: string }) {
  const { data, live, isError } = useBatch(runId)
  const pack = useExportBatch(runId)
  const done = live.status && isTerminal(live.status)
  const succeeded = data?.items.filter((item) => item.status === 'succeeded').length ?? 0

  const download = () =>
    pack.mutate(undefined, {
      onSuccess: ({ blob, filename }) => {
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = filename
        link.click()
        URL.revokeObjectURL(url)
        toast(`已打包 ${succeeded} 张`)
      },
    })

  if (!data && isError) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-8 text-center">
        <h1 className="text-ink text-lg font-semibold">任务不存在</h1>
        <Link to="/batch" className="text-brand-strong mt-4 text-sm">
          返回批量
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl px-8 py-10">
      <div className="mb-8 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-ink text-2xl font-semibold tracking-tight">批量进度</h1>
          <p className="text-muted mt-1 text-sm">
            {live.stage || '处理中'}
            {done ? '' : ` · ${live.progress}%`}
          </p>
          {!done && (
            <ProgressBar value={live.progress} className="mt-2 h-0.5 w-64 rounded-full" />
          )}
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/batch"
            className="border-line text-muted hover:text-ink rounded-control border px-3 py-1.5 text-xs font-medium"
          >
            新任务
          </Link>
          <button
            type="button"
            disabled={!done || succeeded === 0 || pack.isPending}
            onClick={download}
            className="bg-ink hover:bg-dark rounded-control px-3.5 py-2 text-xs font-medium text-white disabled:opacity-40"
          >
            {pack.isPending ? '打包中…' : '打包下载'}
          </button>
        </div>
      </div>

      {live.error && <p className="text-danger mb-3 text-sm">{live.error}</p>}
      {pack.isError && <p className="text-danger mb-3 text-sm">{errorMessage(pack.error)}</p>}

      <ul className="space-y-3">
        {(data?.items ?? []).map((item) => (
          <li
            key={item.source.id}
            className="border-line bg-paper flex items-center gap-4 rounded-[16px] border p-3"
          >
            <img
              src={item.source.url}
              alt=""
              className="bg-canvas size-16 shrink-0 rounded-[10px] object-contain"
            />
            <div className="min-w-0 flex-1">
              <p className="text-ink text-sm">{statusLabel(item.status)}</p>
              {item.error && <p className="text-danger mt-0.5 text-xs">{item.error}</p>}
              <p className="text-faint mt-0.5 text-xs tabular-nums">
                {item.source.width} × {item.source.height}
                {item.outputs.length ? ` → ${item.outputs.length} 张结果` : ''}
              </p>
            </div>
            <div className="flex gap-1.5">
              {item.outputs.slice(0, 4).map((output) => (
                <img
                  key={output.id}
                  src={output.url}
                  alt=""
                  className="border-line size-12 rounded-[8px] border object-cover"
                />
              ))}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Pipeline({
  draft,
  onChange,
}: {
  draft: BatchDraft
  onChange: (draft: BatchDraft) => void
}) {
  const toggle = (id: BatchTool) => {
    const selected = draft.selected.includes(id)
      ? draft.selected.filter((item) => item !== id)
      : [...draft.selected, id]
    onChange({ ...draft, selected })
  }

  const toggleFormat = (fmt: 'png' | 'jpg') => {
    const formats = draft.formats.includes(fmt)
      ? draft.formats.filter((item) => item !== fmt)
      : [...draft.formats, fmt]
    onChange({ ...draft, formats })
  }

  const toggleDelivery = (ratio: '1:1' | '4:5' | '9:16') => {
    const delivery = draft.delivery.includes(ratio)
      ? draft.delivery.filter((item) => item !== ratio)
      : [...draft.delivery, ratio]
    onChange({ ...draft, delivery })
  }

  return (
    <section>
      <h2 className="text-ink mb-3 text-sm font-medium">处理步骤</h2>
      <ul className="grid gap-3 sm:grid-cols-2">
        {BATCH_STEPS.map((step) => {
          const on = draft.selected.includes(step.id)
          return (
            <li key={step.id} className="border-line bg-paper rounded-[16px] border p-4">
              <label className="flex cursor-pointer items-start gap-3">
                <input
                  type="checkbox"
                  checked={on}
                  onChange={() => toggle(step.id)}
                  className="mt-0.5"
                />
                <span>
                  <span className="text-ink block text-sm font-medium">{step.label}</span>
                  <span className="text-faint block text-xs">{step.hint}</span>
                </span>
              </label>
              {on && step.id === 'replace_background' && (
                <input
                  value={draft.prompt}
                  onChange={(event) => onChange({ ...draft, prompt: event.target.value })}
                  placeholder="例如：浅木色桌面，晨光"
                  className="border-line mt-3 w-full rounded-[10px] border px-3 py-2 text-xs outline-none"
                />
              )}
              {on && step.id === 'adjust_image' && (
                <div className="mt-3 grid grid-cols-3 gap-2">
                  <Slider
                    label="亮度"
                    value={draft.brightness}
                    onChange={(brightness) => onChange({ ...draft, brightness })}
                  />
                  <Slider
                    label="对比"
                    value={draft.contrast}
                    onChange={(contrast) => onChange({ ...draft, contrast })}
                  />
                  <Slider
                    label="饱和"
                    value={draft.saturation}
                    onChange={(saturation) => onChange({ ...draft, saturation })}
                  />
                </div>
              )}
              {on && step.id === 'upscale_image' && (
                <div className="mt-3 flex gap-2">
                  {([2, 4] as const).map((scale) => (
                    <button
                      key={scale}
                      type="button"
                      onClick={() => onChange({ ...draft, scale })}
                      className={`rounded-control px-3 py-1.5 text-xs ${
                        draft.scale === scale ? 'bg-ink text-white' : 'border-line text-muted border'
                      }`}
                    >
                      {scale} 倍
                    </button>
                  ))}
                </div>
              )}
              {on && step.id === 'expand_canvas' && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {EXPAND_RATIOS.map((ratio) => (
                    <button
                      key={ratio}
                      type="button"
                      onClick={() => onChange({ ...draft, expandRatio: ratio })}
                      className={`rounded-control px-3 py-1.5 text-xs ${
                        draft.expandRatio === ratio
                          ? 'bg-ink text-white'
                          : 'border-line text-muted border'
                      }`}
                    >
                      {ratio}
                    </button>
                  ))}
                </div>
              )}
              {on && step.id === 'prepare_delivery_sizes' && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {(['1:1', '4:5', '9:16'] as const).map((ratio) => (
                    <button
                      key={ratio}
                      type="button"
                      onClick={() => toggleDelivery(ratio)}
                      className={`rounded-control px-3 py-1.5 text-xs ${
                        draft.delivery.includes(ratio)
                          ? 'bg-ink text-white'
                          : 'border-line text-muted border'
                      }`}
                    >
                      {ratio}
                    </button>
                  ))}
                </div>
              )}
            </li>
          )
        })}
      </ul>

      <div className="mt-4 flex items-center gap-3">
        <span className="text-muted text-xs">导出格式</span>
        {(['png', 'jpg'] as const).map((fmt) => (
          <label key={fmt} className="text-ink flex items-center gap-1.5 text-xs">
            <input
              type="checkbox"
              checked={draft.formats.includes(fmt)}
              onChange={() => toggleFormat(fmt)}
            />
            {fmt.toUpperCase()}
          </label>
        ))}
      </div>
    </section>
  )
}

function Slider({
  label,
  value,
  onChange,
}: {
  label: string
  value: number
  onChange: (value: number) => void
}) {
  return (
    <label className="text-faint block text-[11px]">
      {label}
      <input
        type="range"
        min={-1}
        max={1}
        step={0.05}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="mt-1 w-full"
      />
    </label>
  )
}

function statusLabel(status: string) {
  if (status === 'succeeded') return '已完成'
  if (status === 'failed') return '失败'
  if (status === 'running') return '处理中'
  return '等待中'
}
