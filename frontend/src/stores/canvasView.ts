import { create } from 'zustand'

const MIN_SCALE = 0.05
const MAX_SCALE = 8
// 适应画布时留出四周余量，避免图片贴边
const FIT_RATIO = 0.92
const GLIDE_MS = 260
// 触控板捏合每帧只有几个像素，鼠标滚轮一格上百；先夹住再取指数，两种设备都跟手
const WHEEL_CAP = 50
const WHEEL_GAIN = 0.0035

export const ZOOM_STEP = 1.25

type Size = { width: number; height: number }
type Point = { x: number; y: number }
type Viewport = { scale: number; x: number; y: number }

type CanvasViewState = Viewport & {
  viewport: Size
  // 视口还没量出来时排队的适应请求，量到之后立刻补上
  awaitingFit: Size | null
  autoFit: boolean
  lastFit: Size | null
  setViewport: (viewport: Size) => void
  fit: (document: Size, options?: { animate?: boolean }) => void
  zoomBy: (factor: number, anchor?: Point) => void
  zoomByWheel: (delta: number, anchor?: Point) => void
  stepZoom: (factor: number) => void
  zoomTo: (scale: number) => void
  panBy: (dx: number, dy: number) => void
  pan: (point: Point) => void
}

const clamp = (scale: number) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale))

const easeOut = (progress: number) => 1 - (1 - progress) ** 3

let frame = 0

function stopGlide() {
  if (frame) cancelAnimationFrame(frame)
  frame = 0
}

/** 按钮触发的缩放与适应走缓动，手势与拖拽直接跟手。 */
function glide(apply: (view: Viewport) => void, from: Viewport, to: Viewport) {
  stopGlide()
  const start = performance.now()
  const tick = (now: number) => {
    const ratio = easeOut(Math.min(1, (now - start) / GLIDE_MS))
    apply({
      scale: from.scale + (to.scale - from.scale) * ratio,
      x: from.x + (to.x - from.x) * ratio,
      y: from.y + (to.y - from.y) * ratio,
    })
    frame = ratio < 1 ? requestAnimationFrame(tick) : 0
  }
  frame = requestAnimationFrame(tick)
}

/**
 * 观察倍率与位移，只影响编辑器视图，不参与导出。图层缩放另存于 LayerDocument。
 */
export const useCanvasView = create<CanvasViewState>((set, get) => ({
  scale: 1,
  x: 0,
  y: 0,
  viewport: { width: 0, height: 0 },
  awaitingFit: null,
  autoFit: true,
  lastFit: null,

  // 还在适应模式时，侧栏开合按新视口重新居中；手动缩放/平移则只锚住画面中心
  setViewport: (next) => {
    const { viewport, x, y, awaitingFit, autoFit, lastFit } = get()
    const ready = Boolean(next.width && next.height)
    const grown = {
      width: next.width - viewport.width,
      height: next.height - viewport.height,
    }
    if (!viewport.width || !viewport.height || (!grown.width && !grown.height)) {
      set({ viewport: next })
    } else if (autoFit && lastFit) {
      set({ viewport: next })
      get().fit(lastFit, { animate: true })
      return
    } else {
      set({ viewport: next, x: x + grown.width / 2, y: y + grown.height / 2 })
    }
    if (ready && awaitingFit) get().fit(awaitingFit, { animate: false })
  },

  fit: (document, options) => {
    const { viewport, scale, x, y } = get()
    // 视口还没量出来就先记下来，等 setViewport 拿到真实尺寸再适应
    if (!viewport.width || !viewport.height) {
      set({ awaitingFit: document, autoFit: true, lastFit: document })
      return
    }

    const next = clamp(
      Math.min(viewport.width / document.width, viewport.height / document.height) * FIT_RATIO,
    )
    const target = {
      scale: next,
      x: (viewport.width - document.width * next) / 2,
      y: (viewport.height - document.height * next) / 2,
    }

    stopGlide()
    if (options?.animate === false) {
      set({ ...target, awaitingFit: null, autoFit: true, lastFit: document })
      return
    }
    set({ awaitingFit: null, autoFit: true, lastFit: document })
    glide(set, { scale, x, y }, target)
  },

  zoomBy: (factor, anchor) => {
    stopGlide()
    const { scale, x, y, viewport } = get()
    const next = clamp(scale * factor)
    const pivot = anchor ?? { x: viewport.width / 2, y: viewport.height / 2 }
    // 以锚点为不动点，指针位置下的画面内容不漂移
    const ratio = next / scale
    set({
      autoFit: false,
      scale: next,
      x: pivot.x - (pivot.x - x) * ratio,
      y: pivot.y - (pivot.y - y) * ratio,
    })
  },

  zoomByWheel: (delta, anchor) => {
    const capped = Math.max(-WHEEL_CAP, Math.min(WHEEL_CAP, delta))
    get().zoomBy(Math.exp(-capped * WHEEL_GAIN), anchor)
  },

  stepZoom: (factor) => {
    const { scale, x, y, viewport } = get()
    const next = clamp(scale * factor)
    const pivot = { x: viewport.width / 2, y: viewport.height / 2 }
    const ratio = next / scale
    set({ autoFit: false })
    glide(
      set,
      { scale, x, y },
      {
        scale: next,
        x: pivot.x - (pivot.x - x) * ratio,
        y: pivot.y - (pivot.y - y) * ratio,
      },
    )
  },

  zoomTo: (scale) => get().stepZoom(scale / get().scale),

  panBy: (dx, dy) => {
    stopGlide()
    const { x, y } = get()
    set({ autoFit: false, x: x + dx, y: y + dy })
  },

  pan: (point) => {
    stopGlide()
    set({ autoFit: false, ...point })
  },
}))
