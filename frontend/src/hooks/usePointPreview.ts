import { useCallback, useRef, useState } from 'react'

import type { LayerDocument } from '@/api/sessions'
import { floodPreview } from '@/lib/floodPreview'
import type { Marker } from '@/stores/editorUi'

export function usePointPreview(document: LayerDocument, urls: Map<string, string>) {
  const token = useRef(0)
  const [preview, setPreview] = useState<HTMLCanvasElement | null>(null)
  const [markers, setMarkers] = useState<Marker[]>([])

  const settle = useCallback(() => {
    token.current += 1
    setPreview(null)
    setMarkers((current) => (current.length ? [] : current))
  }, [])

  const pick = useCallback(
    (point: { x: number; y: number }, existing: Marker[]) => {
      const next = [...existing, { index: existing.length + 1, x: point.x, y: point.y }]
      const stamp = ++token.current
      setMarkers(next)
      void floodPreview(document, urls, point).then((canvas) => {
        if (stamp !== token.current || !canvas) return
        setPreview(canvas)
      })
    },
    [document, urls],
  )

  return {
    preview,
    markers,
    active: markers.length > 0 || Boolean(preview),
    pick,
    settle,
  }
}
