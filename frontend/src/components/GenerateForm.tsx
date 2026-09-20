import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { RATIO_LABELS, runsApi, type GenerateInput, type Ratio } from '@/api/runs'

const RATIOS = Object.keys(RATIO_LABELS) as Ratio[]
const COUNTS = [1, 2, 4, 6]

export default function GenerateForm({
  onSubmit,
  pending,
  defaultPrompt = '',
}: {
  onSubmit: (input: GenerateInput) => void
  pending: boolean
  defaultPrompt?: string
}) {
  const [prompt, setPrompt] = useState(defaultPrompt)
  const [ratio, setRatio] = useState<Ratio>('1:1')
  const [count, setCount] = useState(1)
  const [negative, setNegative] = useState('')
  const [advanced, setAdvanced] = useState(false)
  const [preferredProvider, setPreferredProvider] = useState(() => {
    try {
      return localStorage.getItem('pixagent.generation-provider') ?? ''
    } catch {
      return ''
    }
  })
  const modes = useQuery({ queryKey: ['generation-modes'], queryFn: runsApi.modes })
  const mode =
    modes.data?.modes.find((item) => item.id === preferredProvider && item.enabled) ??
    modes.data?.modes.find((item) => item.id === modes.data?.default && item.enabled)
  const ratios = mode?.ratios ?? RATIOS
  const counts = mode?.counts ?? COUNTS
  const selectedRatio = ratios.includes(ratio) ? ratio : ratios[0]
  const selectedCount = counts.includes(count) ? count : counts[0]

  const canSubmit = prompt.trim().length > 0 && !pending && !!mode && !modes.isError

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        if (!canSubmit) return
        onSubmit({
          prompt: prompt.trim(),
          provider: mode?.id,
          ratio: selectedRatio,
          count: selectedCount,
          negative_prompt: negative.trim() || undefined,
        })
      }}
      className="border-line bg-paper shadow-panel rounded-panel border p-2"
    >
      <div className="flex flex-wrap items-center gap-2 px-4 pt-3">
        <label htmlFor="generation-provider" className="text-muted text-xs">
          生图模式
        </label>
        <select
          id="generation-provider"
          value={mode?.id ?? ''}
          disabled={pending || modes.isPending || modes.isError}
          onChange={(event) => {
            setPreferredProvider(event.target.value)
            try {
              localStorage.setItem('pixagent.generation-provider', event.target.value)
            } catch {
              /* Selection still works when browser storage is disabled. */
            }
          }}
          className="border-line bg-paper text-ink rounded-control max-w-full border px-2 py-1.5 text-sm"
        >
          {!mode && <option value="">{modes.isPending ? '加载模式中…' : '暂无可用模式'}</option>}
          {modes.data?.modes.map((item) => (
            <option key={item.id} value={item.id} disabled={!item.enabled}>
              {item.label}
              {!item.enabled ? `（${item.description}）` : ''}
            </option>
          ))}
        </select>
        <span className="text-faint text-xs">{mode?.description}</span>
        {modes.isError && (
          <button type="button" onClick={() => modes.refetch()} className="text-sm text-red-600">
            模式加载失败，点击重试
          </button>
        )}
      </div>
      <textarea
        maxLength={1500}
        rows={3}
        value={prompt}
        onChange={(event) => setPrompt(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault()
            event.currentTarget.form?.requestSubmit()
          }
        }}
        placeholder="描述你想要的画面，例如：白色陶瓷马克杯放在浅木色桌面，晨光从左侧照入。回车生成，Shift+Enter 换行"
        aria-label="画面描述"
        className="text-ink placeholder:text-faint w-full resize-none bg-transparent px-4 pt-3 pb-1 text-[15px] leading-relaxed outline-none"
      />

      <div className="flex flex-wrap items-center gap-2 px-2 pb-1">
        <Segmented
          label="比例"
          options={ratios.map((value) => ({ value, label: value }))}
          value={selectedRatio}
          onChange={setRatio}
        />
        <Segmented
          label="数量"
          options={counts.map((value) => ({ value, label: String(value) }))}
          value={selectedCount}
          onChange={setCount}
        />

        <button
          type="button"
          onClick={() => setAdvanced((open) => !open)}
          className="text-muted hover:text-ink rounded-control px-2 py-1.5 text-xs font-medium transition-colors"
        >
          {advanced ? '收起排除项' : '排除项'}
        </button>

        <button
          type="submit"
          disabled={!canSubmit}
          className="bg-ink hover:bg-dark rounded-control ml-auto px-4 py-2 text-sm font-medium text-white transition-all duration-150 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-40 disabled:active:scale-100"
        >
          {pending ? '提交中…' : '生成'}
        </button>
      </div>
      <p className="text-faint px-3 pb-2 text-[11px]">
        {pending ? '任务已提交，稍后会跳到候选页' : '回车生成 · Shift+Enter 换行'}
      </p>

      {advanced && (
        <div className="border-line animate-fade-in mt-1 border-t px-4 py-3">
          <input
            maxLength={1500}
            value={negative}
            onChange={(event) => setNegative(event.target.value)}
            placeholder="不希望出现的内容，例如：文字、水印、多余的手"
            aria-label="排除项"
            className="text-ink placeholder:text-faint w-full bg-transparent text-sm outline-none"
          />
        </div>
      )}
    </form>
  )
}

function Segmented<T extends string | number>({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: { value: T; label: string }[]
  value: T
  onChange: (value: T) => void
}) {
  return (
    <div className="border-line rounded-control flex items-center gap-0.5 border p-0.5">
      <span className="text-faint px-1.5 text-xs">{label}</span>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          aria-pressed={option.value === value}
          className={`rounded-[6px] px-2 py-1 text-xs font-medium transition-all duration-150 active:scale-95 ${
            option.value === value ? 'bg-ink text-white' : 'text-muted hover:bg-soft hover:text-ink'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
