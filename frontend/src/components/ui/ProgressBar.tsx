/**
 * 进度值本身已经是逐帧动画，所以条体不再加 CSS 过渡，否则两层插值叠起来会拖影。
 */
export default function ProgressBar({
  value,
  tone = 'ink',
  className = 'h-0.5',
}: {
  value: number
  tone?: 'ink' | 'brand'
  className?: string
}) {
  const clamped = Math.max(0, Math.min(100, value))

  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(clamped)}
      aria-valuemin={0}
      aria-valuemax={100}
      className={`bg-line overflow-hidden ${className}`}
    >
      <div
        className={`h-full ${tone === 'brand' ? 'bg-brand-strong' : 'bg-ink'}`}
        style={{ width: `${Math.max(clamped, 2)}%` }}
      />
    </div>
  )
}
