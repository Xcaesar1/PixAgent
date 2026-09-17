export type ButtonVariant = 'ghost' | 'solid' | 'outline' | 'icon'
export type ButtonSize = 'sm' | 'md'

const BASE =
  'relative overflow-hidden font-medium transition-all duration-150 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-40 disabled:active:scale-100'

const SHAPE: Record<ButtonSize, string> = {
  sm: 'rounded-chip px-2 py-1 text-[11px]',
  md: 'rounded-control px-2.5 py-1.5 text-xs',
}

const ICON_SHAPE: Record<ButtonSize, string> = {
  sm: 'rounded-chip grid size-7 place-items-center text-sm',
  md: 'rounded-chip grid size-8 place-items-center text-sm',
}

const IDLE: Record<ButtonVariant, string> = {
  ghost: 'text-muted hover:bg-soft hover:text-ink',
  solid: 'bg-ink hover:bg-dark text-white',
  outline: 'border-line text-muted hover:bg-soft hover:text-ink border',
  icon: 'text-muted hover:bg-soft hover:text-ink',
}

const ON: Record<ButtonVariant, string> = {
  ghost: 'bg-brand-soft text-brand-strong',
  solid: 'bg-dark text-white',
  outline: 'border-brand bg-brand-soft text-brand-strong border',
  icon: 'bg-brand-soft text-brand-strong',
}

export type ButtonLook = {
  variant?: ButtonVariant
  size?: ButtonSize
  active?: boolean
  block?: boolean
}

/** 供 Link 等非 button 元素复用同一套手感。 */
export function buttonClass({ variant = 'ghost', size = 'md', active, block }: ButtonLook = {}) {
  return [
    BASE,
    variant === 'icon' ? ICON_SHAPE[size] : SHAPE[size],
    active ? ON[variant] : IDLE[variant],
    block ? 'w-full' : '',
  ]
    .filter(Boolean)
    .join(' ')
}
