import { useEffect, useRef, useState } from 'react'

import { isTerminal, type RunStatus } from '@/api/runs'
import { PROGRESS_CEILING, pacedProgress, pacingSeconds } from '@/lib/runPacing'

// 服务端跳一大格时缓动追上，避免画面硬跳
const CATCH_UP_S = 0.35
// 完成后收束到 100 的时间尺度
const SETTLE_S = 0.25
// 每秒至少往前挪这么多，任何阶段都不会看起来完全停住
const CREEP_PER_S = 0.12
// 小于这个变化量不触发重渲染
const EPSILON = 0.4

/**
 * 服务端进度是几个离散台阶，长等待期间不上报。这里按工具预估耗时铺成连续值。
 *
 * 展示进度只增不减：只有换任务（token 变化）才归零，失败或取消时停在原处。
 */
export function useSmoothedProgress({
  reported,
  status,
  tool,
  token,
}: {
  reported: number
  status: RunStatus | undefined
  tool: string | undefined
  token: string | null
}) {
  const [shown, setShown] = useState(0)
  const current = useRef(0)
  const emitted = useRef(0)
  const startedAt = useRef(0)

  useEffect(() => {
    current.current = 0
    emitted.current = 0
    startedAt.current = performance.now()
    setShown(0)
  }, [token])

  const done = Boolean(status && isTerminal(status))
  const succeeded = status === 'succeeded' || reported >= 100
  const seconds = pacingSeconds(tool)

  useEffect(() => {
    // 失败或取消：停在当前值，既不归零也不冲到 100
    if (!token || (done && !succeeded)) return

    let frame = 0
    let last = performance.now()

    const tick = (now: number) => {
      const dt = Math.min(0.25, (now - last) / 1000)
      last = now
      const from = current.current
      let next: number

      if (succeeded) {
        next = from + (100 - from) * Math.min(1, dt / SETTLE_S)
        if (next > 99.5) next = 100
      } else {
        const paced = pacedProgress(now - startedAt.current, seconds)
        const target = Math.min(PROGRESS_CEILING, Math.max(reported, paced))
        const eased = from + (target - from) * (1 - Math.exp(-dt / CATCH_UP_S))
        const creep = Math.min(PROGRESS_CEILING, from + CREEP_PER_S * dt)
        next = Math.max(from, eased, creep)
      }

      current.current = next
      if (Math.abs(next - emitted.current) >= EPSILON || (next === 100 && emitted.current !== 100)) {
        emitted.current = next
        setShown(next)
      }

      if (next < 100) frame = requestAnimationFrame(tick)
    }

    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [token, reported, done, succeeded, seconds])

  return Math.round(shown)
}
