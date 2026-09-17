import { useLayoutEffect, useRef, useState } from 'react'

/** 观察元素实际尺寸，供 Konva Stage 这类需要显式宽高的组件使用。 */
export function useElementSize<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [size, setSize] = useState({ width: 0, height: 0 })

  useLayoutEffect(() => {
    const element = ref.current
    if (!element) return

    // 量到 0 就沿用上一次：ResizeObserver 首帧才回调，面板开合也可能瞬时为 0，
    // 舞台以 0×0 起步会画不出内容，而且视图无法适应画布。
    const measure = (width: number, height: number) =>
      setSize((current) =>
        !width || !height || (current.width === width && current.height === height)
          ? current
          : { width, height },
      )

    measure(element.clientWidth, element.clientHeight)
    const observer = new ResizeObserver(([entry]) =>
      measure(Math.round(entry.contentRect.width), Math.round(entry.contentRect.height)),
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  return [ref, size] as const
}
