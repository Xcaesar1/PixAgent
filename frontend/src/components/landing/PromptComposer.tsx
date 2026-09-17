import type { RefObject } from 'react'

function AttachIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="size-4" aria-hidden>
      <rect x="3" y="4.5" width="18" height="15" rx="3" stroke="currentColor" strokeWidth="1.6" />
      <path d="M3.5 16l4.6-4a2 2 0 0 1 2.6 0l5.3 4.6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="15.5" cy="9.5" r="1.6" fill="currentColor" />
    </svg>
  )
}

function SubmitIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="size-4" aria-hidden>
      <path d="M5 12h13M13 6.5l5.5 5.5L13 17.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

/**
 * 需求输入面板：受控组件，只负责采集与提交，不关心提交后去哪。
 * Enter 提交、Shift + Enter 换行，与主流对话式产品保持一致。
 */
export default function PromptComposer({
  value,
  onChange,
  onSubmit,
  onAttach,
  submitLabel,
  placeholder,
  inputRef,
}: {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  onAttach: () => void
  submitLabel: string
  placeholder: string
  inputRef?: RefObject<HTMLTextAreaElement | null>
}) {
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit()
      }}
      className="border-line bg-paper shadow-panel rounded-panel focus-within:border-brand relative border p-2 text-left transition-colors"
    >
      <textarea
        ref={inputRef}
        rows={3}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault()
            onSubmit()
          }
        }}
        placeholder={placeholder}
        aria-label="描述你想要的商品物料"
        className="text-ink placeholder:text-faint w-full resize-none bg-transparent px-4 pt-3 pb-1 text-[15px] leading-relaxed outline-none"
      />

      <div className="flex items-center justify-between gap-3 px-2 pb-1">
        <button
          type="button"
          onClick={onAttach}
          className="text-muted hover:border-line-strong hover:text-ink border-line rounded-control flex items-center gap-1.5 border px-2.5 py-1.5 text-xs font-medium transition-colors"
        >
          <AttachIcon />
          上传商品图
        </button>

        <div className="flex items-center gap-3">
          <span className="text-faint hidden text-xs sm:block">Enter 发送 · Shift + Enter 换行</span>
          <button
            type="submit"
            className="bg-ink hover:bg-dark rounded-control flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white transition-colors"
          >
            {submitLabel}
            <SubmitIcon />
          </button>
        </div>
      </div>
    </form>
  )
}
