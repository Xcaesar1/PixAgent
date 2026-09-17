import { useEffect, useState } from 'react'

/** safe 表示位图可被读取像素，只有它为真时才能在画布上跑实时滤镜。 */
export type CanvasImage = { element: HTMLImageElement; safe: boolean; url: string }

const LIMIT = 16
const cache = new Map<string, CanvasImage>()

function remember(image: CanvasImage) {
  cache.delete(image.url)
  cache.set(image.url, image)
  while (cache.size > LIMIT) {
    const oldest = cache.keys().next().value
    if (!oldest || oldest === image.url) break
    cache.delete(oldest)
  }
}

function read(url: string) {
  return cache.get(url) ?? null
}

function decode(url: string, safe: boolean) {
  return new Promise<CanvasImage>((resolve, reject) => {
    const element = new Image()
    if (safe) element.crossOrigin = 'anonymous'
    element.onload = () => resolve({ element, safe, url })
    element.onerror = () => reject(new Error('image'))
    element.src = url
  })
}

export function preloadCanvasImage(url: string) {
  const hit = read(url)
  if (hit) return Promise.resolve(hit)
  return decode(url, true)
    .catch(() => decode(url, false))
    .then((image) => {
      remember(image)
      return image
    })
    .catch(() => null)
}

/** 把 URL 解码为 Konva 可直接绘制的位图。换源时先留着上一张，避免画布闪白。 */
export function useCanvasImage(url: string | undefined) {
  const [image, setImage] = useState<CanvasImage | null>(() => (url ? read(url) : null))

  useEffect(() => {
    if (!url) return

    const hit = read(url)
    if (hit) {
      setImage(hit)
      return
    }

    let cancelled = false
    void preloadCanvasImage(url).then((next) => {
      if (!cancelled && next) setImage(next)
    })
    return () => {
      cancelled = true
    }
  }, [url])

  return (url && read(url)) || image
}
