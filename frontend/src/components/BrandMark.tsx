import type { ReactNode } from 'react'

const GLYPH_SIZE = {
  sm: 'size-6 rounded-[7px]',
  md: 'size-8 rounded-[10px]',
} as const

/** 品牌标识：ink 底 + accent 图层符号，落地页、登录页与工作台共用一处。 */
export default function BrandMark({
  size = 'md',
  className = '',
  children,
}: {
  size?: keyof typeof GLYPH_SIZE
  className?: string
  children?: ReactNode
}) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <span
        className={`bg-ink text-accent grid shrink-0 place-items-center ${GLYPH_SIZE[size]}`}
        aria-hidden
      >
        <svg viewBox="0 0 24 24" fill="none" className="size-[62%]">
          <rect x="3.5" y="3.5" width="12" height="12" rx="3.5" stroke="currentColor" strokeWidth="2" />
          <path
            d="M8.5 20.5H17a3.5 3.5 0 0 0 3.5-3.5V8.5"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
          <circle cx="15.5" cy="3.5" r="1.55" fill="currentColor" />
        </svg>
      </span>
      {children}
    </span>
  )
}
