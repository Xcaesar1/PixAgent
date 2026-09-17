/**
 * 各工具的典型耗时（秒）。服务端只上报几个离散台阶，远程生成期间可能整段静默，
 * 这里用预估时长把台阶之间铺成连续进度，纯展示用途，不参与任何业务判断。
 */
const SECONDS: Record<string, number> = {
  crop_canvas: 0.8,
  flip_layer: 0.8,
  rotate_layer: 0.8,
  move_layer: 0.8,
  scale_layer: 0.8,
  set_layer_opacity: 0.8,
  set_layer_visible: 0.8,
  set_layer_text: 0.8,
  reorder_layer: 0.8,
  adjust_image: 2,
  prepare_delivery_sizes: 8,
  remove_background: 10,
  generate_image: 40,
  erase_region: 40,
  replace_region: 40,
  promote_object_to_layer: 40,
  replace_background: 45,
  expand_canvas: 45,
  upscale_image: 45,
  generate_marketing: 45,
  batch_process: 60,
  split_layers: 70,
}

const FALLBACK = 25
// 走到预估时长时约到 88%，之后继续趋近上限，任何阶段都不会彻底停住
const SHAPE = 2.2

/** 运行中的展示上限，留出最后一格给真正的完成。 */
export const PROGRESS_CEILING = 99

export function pacingSeconds(tool: string | undefined) {
  if (!tool) return FALLBACK
  return SECONDS[tool] ?? FALLBACK
}

export function pacedProgress(elapsedMs: number, seconds: number) {
  const tau = (seconds / SHAPE) * 1000
  return PROGRESS_CEILING * (1 - Math.exp(-elapsedMs / tau))
}
