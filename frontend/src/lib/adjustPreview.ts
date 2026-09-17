/**
 * 画布上的调色预览，算法与后端 pixels.adjust 对齐：
 * 逐像素的项全部覆盖，锐化与清晰度是卷积运算，留给应用时由后端处理。
 */

const PREVIEW_KEYS = [
  'brightness',
  'contrast',
  'saturation',
  'highlights',
  'shadows',
  'temperature',
  'tint',
  'vibrance',
  'vignette',
] as const

export type AdjustPreview = Record<(typeof PREVIEW_KEYS)[number], number>

/** 全部为 0 时返回 null，画布据此跳过缓存与滤镜。 */
export function toAdjustPreview(values: Record<string, number> | null): AdjustPreview | null {
  if (!values) return null
  const preview = Object.fromEntries(
    PREVIEW_KEYS.map((key) => [key, values[key] ?? 0]),
  ) as AdjustPreview
  return PREVIEW_KEYS.some((key) => preview[key]) ? preview : null
}

export function makeAdjustFilter(values: AdjustPreview) {
  return (imageData: ImageData) => {
    const { data, width, height } = imageData

    // 亮度、对比度只与单通道取值有关，查表比逐像素计算省一半时间
    const beforeSaturation = brightnessLut(values, values.contrast ? meanLuma(data) : 128)
    const afterSaturation = {
      red: toneLut(values, values.temperature * 28 + values.tint * 12),
      green: toneLut(values, -values.tint * 20),
      blue: toneLut(values, -values.temperature * 28 + values.tint * 12),
    }

    const saturation = 1 + values.saturation
    const center = { x: width / 2, y: height / 2 }
    const farthest = Math.sqrt(center.x ** 2 + center.y ** 2) || 1

    let index = 0
    for (let y = 0; y < height; y += 1) {
      const dy = (y - center.y) ** 2
      for (let x = 0; x < width; x += 1, index += 4) {
        let red = beforeSaturation[data[index]]
        let green = beforeSaturation[data[index + 1]]
        let blue = beforeSaturation[data[index + 2]]

        if (values.saturation) {
          const gray = luma(red, green, blue)
          red = gray + (red - gray) * saturation
          green = gray + (green - gray) * saturation
          blue = gray + (blue - gray) * saturation
        }

        red = afterSaturation.red[clip(red)]
        green = afterSaturation.green[clip(green)]
        blue = afterSaturation.blue[clip(blue)]

        if (values.vibrance) {
          const average = (red + green + blue) / 3
          const chroma =
            (Math.abs(red - average) + Math.abs(green - average) + Math.abs(blue - average)) / 3
          // 少饱和的像素多加一点，避免已鲜艳的颜色过曝
          const weight = values.vibrance * (1 - chroma / 128)
          red += (red - average) * weight
          green += (green - average) * weight
          blue += (blue - average) * weight
        }

        if (values.vignette) {
          const distance = Math.sqrt((x - center.x) ** 2 + dy) / farthest
          const shade = 1 - values.vignette * Math.min(1, distance ** 1.6)
          red *= shade
          green *= shade
          blue *= shade
        }

        data[index] = red
        data[index + 1] = green
        data[index + 2] = blue
      }
    }
  }
}

function brightnessLut(values: AdjustPreview, pivot: number) {
  const lut = new Uint8ClampedArray(256)
  for (let value = 0; value < 256; value += 1) {
    const lifted = clip(value * (1 + values.brightness))
    lut[value] = pivot + (lifted - pivot) * (1 + values.contrast)
  }
  return lut
}

function toneLut(values: AdjustPreview, offset: number) {
  const lut = new Uint8ClampedArray(256)
  for (let value = 0; value < 256; value += 1) {
    const unit = value / 255
    lut[value] = value + values.shadows * (1 - unit) * 64 + values.highlights * unit * 64 + offset
  }
  return lut
}

/** 后端的对比度以整图平均灰度为轴心，这里同样先统计一遍 */
function meanLuma(data: Uint8ClampedArray) {
  let sum = 0
  for (let index = 0; index < data.length; index += 4) {
    sum += luma(data[index], data[index + 1], data[index + 2])
  }
  return sum / (data.length / 4)
}

function luma(red: number, green: number, blue: number) {
  return 0.299 * red + 0.587 * green + 0.114 * blue
}

function clip(value: number) {
  return value < 0 ? 0 : value > 255 ? 255 : value | 0
}
