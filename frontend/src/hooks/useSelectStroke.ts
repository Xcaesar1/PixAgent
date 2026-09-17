import { useCallback, useRef, useState } from 'react'

export function useSelectStroke() {
  const drawing = useRef(false)
  const points = useRef<{ x: number; y: number }[]>([])
  const [draft, setDraft] = useState<{ x: number; y: number }[]>([])
  const [pending, setPending] = useState(false)

  const settle = useCallback(() => {
    drawing.current = false
    points.current = []
    setPending(false)
    setDraft((current) => (current.length ? [] : current))
  }, [])

  return {
    draft,
    pending,
    start: (point: { x: number; y: number }) => {
      drawing.current = true
      points.current = [point]
      setPending(true)
      setDraft([point])
    },
    move: (point: { x: number; y: number }) => {
      if (!drawing.current) return
      points.current = [...points.current, point]
      setDraft(points.current)
    },
    end: () => {
      const stroke = drawing.current ? points.current : []
      drawing.current = false
      // 松手后先留着预览，等服务端遮罩上屏再收，避免中间空一帧
      if (stroke.length < 2) {
        settle()
        return []
      }
      return stroke
    },
    settle,
  }
}
