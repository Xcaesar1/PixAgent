import { create } from 'zustand'

export type ToastTone = 'ok' | 'danger'

export type ToastAction = { label: string; run: () => void }

export type Toast = {
  id: number
  text: string
  tone: ToastTone
  action: ToastAction | null
  leaving: boolean
}

type ToastOptions = { action?: ToastAction; duration?: number }

type ToastsState = {
  items: Toast[]
  push: (text: string, tone?: ToastTone, options?: ToastOptions) => void
  dismiss: (id: number) => void
}

const LEAVE_MS = 180
const STAY_MS = 3200
// 带撤销入口的提示要留够反应时间
const STAY_WITH_ACTION_MS = 5200

let nextId = 1

export const useToasts = create<ToastsState>((set, get) => ({
  items: [],

  push: (text, tone = 'ok', options) => {
    const id = nextId++
    const action = options?.action ?? null
    set({
      items: [...get().items.slice(-2), { id, text, tone, action, leaving: false }],
    })
    const stay = options?.duration ?? (action ? STAY_WITH_ACTION_MS : STAY_MS)
    window.setTimeout(() => get().dismiss(id), stay)
  },

  // 先标记退场让动画播完，再从列表移除
  dismiss: (id) => {
    const item = get().items.find((toast) => toast.id === id)
    if (!item || item.leaving) return
    set({
      items: get().items.map((toast) => (toast.id === id ? { ...toast, leaving: true } : toast)),
    })
    window.setTimeout(
      () => set({ items: get().items.filter((toast) => toast.id !== id) }),
      LEAVE_MS,
    )
  },
}))

export function toast(text: string, tone: ToastTone = 'ok', options?: ToastOptions) {
  useToasts.getState().push(text, tone, options)
}
