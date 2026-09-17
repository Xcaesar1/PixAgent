/** 笔刷粗细按画布短边取比例。前端显式带上同一个值，预览与服务端遮罩才同宽。 */
export const BRUSH_RADIUS = 0.03

export function brushWidth(canvas: { width: number; height: number }) {
  return Math.max(2, Math.min(canvas.width, canvas.height) * BRUSH_RADIUS)
}
