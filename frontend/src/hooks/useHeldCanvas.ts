import { useEffect, useState } from 'react'

import type { LayerDocument } from '@/api/sessions'
import { preloadCanvasImage } from '@/hooks/useCanvasImage'

export type HeldCanvas = { document: LayerDocument; urls: Map<string, string> }

/**
 * 只按画幅和图层资源判断是不是换图。签名 URL 每次回写都会变，
 * 不能算进去，否则缩放、位移也会被当成切图，旧倍率先闪一下再淡出。
 */
export function canvasStamp(document: LayerDocument) {
  const layers = document.layers.map((layer) => `${layer.id}:${layer.asset_id ?? ''}`).join('|')
  return `${document.width}x${document.height}:${layers}`
}

function needed(document: LayerDocument, urls: Map<string, string>) {
  return document.layers.flatMap((layer) => {
    if (!layer.visible || layer.kind !== 'image' || !layer.asset_id) return []
    const url = urls.get(layer.asset_id)
    return url ? [url] : []
  })
}

/** 下一张图预加载完成前继续画当前帧，避免切图时空一层再弹出来。 */
export function useHeldCanvas(document: LayerDocument, urls: Map<string, string>): HeldCanvas {
  const incomingKey = canvasStamp(document)
  const [held, setHeld] = useState<HeldCanvas & { key: string }>({
    document,
    urls,
    key: incomingKey,
  })

  useEffect(() => {
    const next = { document, urls, key: incomingKey }
    if (incomingKey === held.key) {
      setHeld((current) =>
        current.document === document && current.urls === urls ? current : next,
      )
      return
    }

    let cancelled = false
    const apply = () => {
      if (!cancelled) setHeld(next)
    }
    const urlsToLoad = needed(document, urls)
    if (urlsToLoad.length === 0) {
      apply()
      return
    }
    const loaded = Promise.all(urlsToLoad.map(preloadCanvasImage))
    const timeout = new Promise((resolve) => setTimeout(resolve, 4000))
    void Promise.race([loaded, timeout]).then(apply)
    return () => {
      cancelled = true
    }
  }, [incomingKey, held.key, document, urls])

  // 同一组图层：变换和刷新后的签名立刻跟上，不必等预加载
  if (incomingKey === held.key) return { document, urls }
  return { document: held.document, urls: held.urls }
}
