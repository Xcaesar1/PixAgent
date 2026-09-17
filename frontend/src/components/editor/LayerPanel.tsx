import { useEffect, useState } from 'react'

import type { Asset } from '@/api/assets'
import { ACTION_LABELS, type Layer, type SessionDetail } from '@/api/sessions'
import { BackgroundForm, ExpandForm, ReplaceForm } from '@/components/editor/GenerateEdits'
import Button from '@/components/ui/Button'
import { useSessionHistory, type SessionTools } from '@/hooks/useSessions'
import { formatBytes, formatDateTime } from '@/lib/format'
import { wallOnly } from '@/lib/layers'
import { useEditorUi, type Panel } from '@/stores/editorUi'

const ADJUST_FIELDS: { key: string; label: string; min?: number }[] = [
  { key: 'brightness', label: '亮度' },
  { key: 'contrast', label: '对比度' },
  { key: 'highlights', label: '高光' },
  { key: 'shadows', label: '阴影' },
  { key: 'temperature', label: '色温' },
  { key: 'tint', label: '色调' },
  { key: 'saturation', label: '饱和度' },
  { key: 'vibrance', label: '自然饱和度' },
  { key: 'sharpness', label: '锐化' },
  { key: 'clarity', label: '清晰度' },
  { key: 'vignette', label: '晕影', min: 0 },
]

const REORDER_LABELS = {
  top: '置顶',
  up: '上移',
  down: '下移',
  bottom: '置底',
} as const

export default function LayerPanel({
  session,
  tools,
  panel,
}: {
  session: SessionDetail
  tools: SessionTools
  // 由外层传入，关闭动画期间仍能画出原来的表单，不会先塌一半
  panel: Panel
}) {
  const current = session.assets.find((asset) => asset.id === session.current_asset_id)
  const { data: history = [] } = useSessionHistory(session.id)
  const selectedLayerId = useEditorUi((state) => state.selectedLayerId)
  const selectLayer = useEditorUi((state) => state.selectLayer)
  const selection = useEditorUi((state) => state.selection)
  const includeText = useEditorUi((state) => state.splitIncludeText)
  const setIncludeText = useEditorUi((state) => state.setSplitIncludeText)
  const selected =
    session.document.layers.find((layer) => layer.id === selectedLayerId) ??
    session.document.layers.at(-1)
  const onlyToWall = wallOnly(session.document)

  return (
    <aside className="border-line bg-paper scrollbar-slim h-full w-72 shrink-0 overflow-y-auto border-l">
      {panel === 'adjust' && (
        <AdjustForm
          disabled={tools.busy}
          onApply={(params) =>
            tools.invoke('adjust_image', { ...params, layer_id: selectedLayerId })
          }
        />
      )}
      {panel === 'background' && (
        <BackgroundForm
          disabled={tools.busy}
          wallOnly={onlyToWall}
          onApply={(params) => tools.invoke('replace_background', params)}
        />
      )}
      {panel === 'expand' && (
        <ExpandForm
          disabled={tools.busy}
          wallOnly={onlyToWall}
          onApply={(params) => tools.invoke('expand_canvas', params)}
        />
      )}
      {panel === 'replace' && (
        <ReplaceForm
          disabled={tools.busy || !selection}
          onApply={(params) =>
            tools.invoke('replace_region', {
              ...params,
              mask_asset_id: selection?.maskId,
              revision: session.revision,
              layer_id: selectedLayerId,
            })
          }
        />
      )}

      <Section title="图层">
        <label className="text-muted mb-2 flex items-center gap-1.5 text-[11px]">
          <input
            type="checkbox"
            checked={includeText}
            disabled={tools.busy}
            onChange={(event) => setIncludeText(event.target.checked)}
          />
          同时拆出文字
        </label>
        <div className="mb-2.5 flex gap-1">
          <Button
            variant="outline"
            size="sm"
            block
            disabled={tools.busy}
            progress={tools.isRunning('split_layers') ? tools.pendingProgress : null}
            title={includeText ? '拆成背景、主体和文字，可撤销' : '拆成背景和主体，可撤销'}
            onClick={() => tools.invoke('split_layers', { include_text: includeText })}
          >
            拆层
          </Button>
          <Button
            variant="outline"
            size="sm"
            block
            disabled={tools.busy || !selection}
            progress={tools.isRunning('promote_object_to_layer') ? tools.pendingProgress : null}
            title={selection ? '把选区提升为独立图层，可撤销' : '先点选或涂抹'}
            onClick={() =>
              tools.invoke('promote_object_to_layer', {
                mask_asset_id: selection?.maskId,
                revision: session.revision,
              })
            }
          >
            成层
          </Button>
        </div>
        <ul className="space-y-1">
          {[...session.document.layers].reverse().map((layer) => (
            <LayerRow
              key={layer.id}
              layer={layer}
              active={selected?.id === layer.id}
              disabled={tools.busy}
              thumb={layer.asset_id ? session.assets.find((asset) => asset.id === layer.asset_id) : undefined}
              onSelect={() => selectLayer(layer.id)}
              onToggleVisible={() =>
                tools.invoke('set_layer_visible', {
                  layer_id: layer.id,
                  visible: !layer.visible,
                })
              }
            />
          ))}
        </ul>
      </Section>

      {selected?.kind === 'text' && (
        <Section title="文字">
          <p className="text-faint mb-2.5 text-[11px] leading-relaxed">
            改文案、字号或颜色。失焦写入，可用 ⌘Z 撤销。画布上双击文字层也可改。
          </p>
          <TextForm
            layer={selected}
            disabled={tools.busy}
            onCommit={(params) =>
              tools.invoke('set_layer_text', { layer_id: selected.id, ...params })
            }
          />
        </Section>
      )}

      {selected && (
        <Section title="变换">
          <p className="text-faint mb-2.5 text-[11px] leading-relaxed">
            选中图层后拖角缩放、拖动画布移动。滑杆也可改，松手写入，可用 ⌘Z 撤销。
          </p>
          <LayerControls
            layer={selected}
            disabled={tools.busy}
            onOpacity={(opacity) =>
              tools.invoke('set_layer_opacity', {
                layer_id: selected.id,
                opacity,
              })
            }
            onScale={(scale) =>
              tools.invoke('scale_layer', {
                layer_id: selected.id,
                scale_x: scale,
                scale_y: scale,
              })
            }
            onRotate={(rotation) =>
              tools.invoke('rotate_layer', { layer_id: selected.id, rotation })
            }
            onReorder={(place) => tools.invoke('reorder_layer', { layer_id: selected.id, place })}
          />
        </Section>
      )}

      <Section title="属性">
        <Properties document={session.document} current={current} revision={session.revision} />
      </Section>

      <Section title="编辑记录">
        {history.length === 0 ? (
          <p className="text-faint text-xs">暂无记录</p>
        ) : (
          <ol className="space-y-1.5">
            {history.map((entry) => (
              <li key={entry.seq} className="flex items-baseline justify-between gap-2 text-xs">
                <span className="text-ink">{ACTION_LABELS[entry.action] ?? entry.action}</span>
                <span className="text-faint shrink-0 tabular-nums">
                  {formatDateTime(entry.created_at)}
                </span>
              </li>
            ))}
          </ol>
        )}
      </Section>
    </aside>
  )
}

function LayerRow({
  layer,
  active,
  disabled,
  thumb,
  onSelect,
  onToggleVisible,
}: {
  layer: Layer
  active: boolean
  disabled: boolean
  thumb?: Asset
  onSelect: () => void
  onToggleVisible: () => void
}) {
  return (
    <li
      className={`rounded-control flex items-center border transition-all duration-150 ${
        active ? 'border-brand bg-brand-soft' : 'border-line hover:border-line-strong hover:bg-soft'
      } ${layer.visible ? '' : 'opacity-50'}`}
    >
      <button
        type="button"
        onClick={onSelect}
        className="flex min-w-0 flex-1 items-center gap-2 px-2 py-1.5 text-left"
      >
        <span className="bg-canvas border-line rounded-chip size-8 shrink-0 overflow-hidden border">
          {thumb ? (
            <img src={thumb.url} alt="" className="size-full object-cover" />
          ) : (
            <span className="text-faint grid size-full place-items-center text-[10px]">
              {layer.kind === 'text' ? '文' : ''}
            </span>
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="text-ink block truncate text-xs font-medium">{layer.name}</span>
          <span className="text-faint block truncate text-[10px]">
            {layer.kind === 'text'
              ? layer.text || '文字'
              : layer.locked
                ? '已锁定'
                : '图像'}
          </span>
        </span>
        <span className="text-faint shrink-0 text-[10px] tabular-nums">
          {Math.round(layer.opacity * 100)}%
        </span>
      </button>
      <Button
        variant="icon"
        size="sm"
        disabled={disabled}
        title={layer.visible ? '隐藏图层' : '显示图层'}
        onClick={onToggleVisible}
        className="mr-1.5 shrink-0"
      >
        <EyeIcon open={layer.visible} />
      </Button>
    </li>
  )
}

function EyeIcon({ open }: { open: boolean }) {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M1.5 8s2.4-4.5 6.5-4.5S14.5 8 14.5 8 12.1 12.5 8 12.5 1.5 8 1.5 8Z"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinejoin="round"
      />
      {open ? (
        <circle cx="8" cy="8" r="1.7" fill="currentColor" />
      ) : (
        <path d="M3 13 13 3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      )}
    </svg>
  )
}

const TEXT_FIELD =
  'border-line text-ink placeholder:text-faint rounded-control focus:border-line-strong w-full resize-none border px-2.5 py-1.5 text-xs leading-relaxed outline-none'

function toHex6(value: string) {
  const raw = value.replace('#', '')
  if (raw.length === 3) return `#${[...raw].map((ch) => ch + ch).join('')}`
  return `#${raw.padEnd(6, '0')}`.slice(0, 7)
}

function TextForm({
  layer,
  disabled,
  onCommit,
}: {
  layer: Layer
  disabled: boolean
  onCommit: (params: { text: string; font_size: number; fill: string }) => void
}) {
  const [text, setText] = useState(layer.text || '')
  const [fontSize, setFontSize] = useState(layer.font_size ?? 24)
  const [fill, setFill] = useState(toHex6(layer.fill ?? '#141414'))
  const setLayerPreview = useEditorUi((state) => state.setLayerPreview)

  useEffect(() => {
    setText(layer.text || '')
    setFontSize(layer.font_size ?? 24)
    setFill(toHex6(layer.fill ?? '#141414'))
  }, [layer.id, layer.text, layer.font_size, layer.fill])

  const current = {
    text: layer.text || '',
    font_size: layer.font_size ?? 24,
    fill: toHex6(layer.fill ?? '#141414'),
  }

  const commit = (next: { text: string; font_size: number; fill: string }) => {
    if (
      next.text === current.text &&
      next.font_size === current.font_size &&
      next.fill.toLowerCase() === current.fill.toLowerCase()
    ) {
      return
    }
    onCommit(next)
  }

  return (
    <div className="space-y-3">
      <textarea
        rows={3}
        value={text}
        disabled={disabled}
        className={TEXT_FIELD}
        onChange={(event) => {
          const next = event.target.value
          setText(next)
          setLayerPreview({ id: layer.id, text: next })
        }}
        onBlur={() => commit({ text, font_size: fontSize, fill })}
        onKeyDown={(event) => {
          if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
            event.preventDefault()
            commit({ text, font_size: fontSize, fill })
          }
        }}
      />
      <SliderField
        label="字号"
        value={fontSize}
        origin={layer.font_size ?? 24}
        min={8}
        max={120}
        step={1}
        format={(value) => `${Math.round(value)}`}
        disabled={disabled}
        onInput={(value) => {
          setFontSize(value)
          setLayerPreview({ id: layer.id, font_size: value })
        }}
        onCommit={(value) => {
          setFontSize(value)
          commit({ text, font_size: value, fill })
        }}
      />
      <label className="flex items-center justify-between gap-2 text-[11px]">
        <span className="text-muted">颜色</span>
        <input
          type="color"
          value={fill}
          disabled={disabled}
          className="border-line h-7 w-12 cursor-pointer rounded border bg-transparent p-0"
          onChange={(event) => {
            const next = event.target.value
            setFill(next)
            setLayerPreview({ id: layer.id, fill: next })
            commit({ text, font_size: fontSize, fill: next })
          }}
        />
      </label>
    </div>
  )
}

function LayerControls({
  layer,
  disabled,
  onOpacity,
  onScale,
  onRotate,
  onReorder,
}: {
  layer: Layer
  disabled: boolean
  onOpacity: (value: number) => void
  onScale: (value: number) => void
  onRotate: (value: number) => void
  onReorder: (place: 'top' | 'bottom' | 'up' | 'down') => void
}) {
  const preview = useEditorUi((state) => state.layerPreview)
  const setLayerPreview = useEditorUi((state) => state.setLayerPreview)
  const scale = Math.abs(layer.transform.scale_x)

  // 文档追上预览后再撤，避免选中/回写过程把图层拽回原位
  useEffect(() => {
    if (!preview || preview.id !== layer.id) return
    const same =
      (preview.opacity === undefined || preview.opacity === layer.opacity) &&
      (preview.scale === undefined || Math.abs(preview.scale - scale) < 0.001) &&
      (preview.rotation === undefined || preview.rotation === layer.transform.rotation) &&
      (preview.x === undefined || Math.abs(preview.x - layer.transform.x) < 0.5) &&
      (preview.y === undefined || Math.abs(preview.y - layer.transform.y) < 0.5) &&
      (preview.text === undefined || preview.text === (layer.text || '')) &&
      (preview.font_size === undefined || preview.font_size === (layer.font_size ?? 24)) &&
      (preview.fill === undefined ||
        preview.fill.toLowerCase() === (layer.fill ?? '#141414').toLowerCase())
    if (same) setLayerPreview(null)
  }, [
    preview,
    scale,
    setLayerPreview,
    layer.id,
    layer.opacity,
    layer.transform.scale_x,
    layer.transform.rotation,
    layer.transform.x,
    layer.transform.y,
  ])

  useEffect(() => () => setLayerPreview(null), [setLayerPreview])

  return (
    <div className="space-y-3">
      <SliderField
        label="透明度"
        value={layer.opacity}
        origin={1}
        min={0}
        max={1}
        step={0.01}
        format={(value) => `${Math.round(value * 100)}%`}
        disabled={disabled}
        onInput={(opacity) => setLayerPreview({ id: layer.id, opacity })}
        onCommit={onOpacity}
      />
      <SliderField
        label="图层缩放"
        value={scale}
        origin={1}
        min={0.1}
        max={3}
        step={0.05}
        format={(value) => `${Math.round(value * 100)}%`}
        disabled={disabled}
        onInput={(value) => setLayerPreview({ id: layer.id, scale: value })}
        onCommit={onScale}
      />
      <SliderField
        label="旋转"
        value={layer.transform.rotation}
        origin={0}
        min={-180}
        max={180}
        step={1}
        format={(value) => `${Math.round(value)}°`}
        disabled={disabled}
        onInput={(rotation) => setLayerPreview({ id: layer.id, rotation })}
        onCommit={onRotate}
      />
      <div className="grid grid-cols-4 gap-1">
        {(['top', 'up', 'down', 'bottom'] as const).map((place) => (
          <Button
            key={place}
            variant="outline"
            size="sm"
            block
            disabled={disabled}
            onClick={() => onReorder(place)}
          >
            {REORDER_LABELS[place]}
          </Button>
        ))}
      </div>
    </div>
  )
}

function AdjustForm({
  disabled,
  onApply,
}: {
  disabled: boolean
  onApply: (params: Record<string, number>) => void
}) {
  const [values, setValues] = useState<Record<string, number>>({})
  const setAdjustPreview = useEditorUi((state) => state.setAdjustPreview)
  const touched = Object.keys(values).length > 0

  useEffect(() => () => setAdjustPreview(null), [setAdjustPreview])

  const clear = () => {
    setValues({})
    setAdjustPreview(null)
  }

  return (
    <Section title="调色">
      <p className="text-faint mb-2.5 text-[11px] leading-relaxed">
        拖动即在画布预览，锐化与清晰度需应用后可见。点应用写入新版本，可撤销。
      </p>
      <div className="space-y-2.5">
        {ADJUST_FIELDS.map((field) => (
          <SliderField
            key={field.key}
            label={field.label}
            value={values[field.key] ?? 0}
            origin={0}
            min={field.min ?? -1}
            max={1}
            step={0.05}
            format={(value) => value.toFixed(2)}
            disabled={disabled}
            onInput={(value) => setAdjustPreview({ ...values, [field.key]: value })}
            onCommit={(value) => {
              const next = { ...values, [field.key]: value }
              setValues(next)
              setAdjustPreview(next)
            }}
          />
        ))}
        <div className="flex gap-2">
          <Button variant="outline" block disabled={disabled || !touched} onClick={clear}>
            重置
          </Button>
          <Button
            variant="solid"
            block
            disabled={disabled || !touched}
            title={touched ? '写入当前调色，可撤销' : '先拖动滑杆再应用'}
            onClick={() => {
              onApply(values)
              clear()
            }}
          >
            应用
          </Button>
        </div>
      </div>
    </Section>
  )
}

function SliderField({
  label,
  value,
  origin,
  min,
  max,
  step,
  format,
  disabled,
  onInput,
  onCommit,
}: {
  label: string
  value: number
  origin: number
  min: number
  max: number
  step: number
  format: (value: number) => string
  disabled: boolean
  onInput: (value: number) => void
  onCommit: (value: number) => void
}) {
  const [draft, setDraft] = useState<number | null>(null)

  const commit = () => {
    if (draft !== null && draft !== value) onCommit(draft)
    setDraft(null)
  }

  return (
    <label
      className="block select-none"
      title="双击复位"
      onDoubleClick={() => {
        setDraft(null)
        if (value !== origin) onCommit(origin)
      }}
    >
      <span className="mb-1 flex justify-between text-[11px]">
        <span className="text-muted">{label}</span>
        <span className="text-ink tabular-nums">{format(draft ?? value)}</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        value={draft ?? value}
        onChange={(event) => {
          const next = Number(event.target.value)
          setDraft(next)
          onInput(next)
        }}
        onPointerDown={(event) => event.currentTarget.setPointerCapture(event.pointerId)}
        onPointerUp={commit}
        onLostPointerCapture={commit}
      />
    </label>
  )
}

function Properties({
  document,
  current,
  revision,
}: {
  document: { width: number; height: number }
  current: Asset | undefined
  revision: number
}) {
  const rows: [string, string][] = [
    ['画布', `${document.width} × ${document.height}`],
    ['修订号', String(revision)],
  ]
  if (current) {
    rows.push(['格式', current.image_format])
    rows.push(['大小', formatBytes(current.size_bytes)])
    rows.push(['透明通道', current.has_alpha ? '有' : '无'])
  }

  return (
    <dl className="space-y-1.5 text-xs">
      {rows.map(([label, value]) => (
        <div key={label} className="flex justify-between gap-2">
          <dt className="text-muted">{label}</dt>
          <dd className="text-ink tabular-nums">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-line border-b px-4 py-4 last:border-b-0">
      <h2 className="text-muted mb-2.5 text-xs font-medium">{title}</h2>
      {children}
    </section>
  )
}
