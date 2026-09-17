import { useEffect, useRef } from 'react'
import { Circle, Group, Image as KonvaImage, Layer as KonvaLayer, Line, Text } from 'react-konva'

import type { LayerDocument } from '@/api/sessions'
import { useCanvasImage } from '@/hooks/useCanvasImage'
import { brushWidth } from '@/lib/brush'
import type { CanvasSelection } from '@/stores/editorUi'

export function SelectionOverlay({
  document,
  selection,
  scale,
  draft,
  pending = false,
  preview = null,
  markers,
  onMaskReady,
}: {
  document: LayerDocument
  selection: CanvasSelection | null
  scale: number
  draft: { x: number; y: number }[]
  pending?: boolean
  preview?: HTMLCanvasElement | null
  markers?: CanvasSelection['markers']
  onMaskReady?: () => void
}) {
  const mask = useCanvasImage(selection?.maskUrl)
  const maskReady = Boolean(mask && selection && mask.url === selection.maskUrl)
  const wasReady = useRef(false)
  const pins = markers ?? selection?.markers ?? []

  useEffect(() => {
    if (maskReady && !wasReady.current) onMaskReady?.()
    wasReady.current = maskReady
  }, [maskReady, onMaskReady])

  return (
    <KonvaLayer listening={false}>
      {mask && (
        <KonvaImage
          image={mask.element}
          width={document.width}
          height={document.height}
          opacity={0.45}
          listening={false}
        />
      )}
      {preview && (
        <KonvaImage
          image={preview}
          width={document.width}
          height={document.height}
          opacity={0.45}
          listening={false}
        />
      )}
      {draft.length > 1 && pending && (
        <Line
          points={draft.flatMap((point) => [point.x * document.width, point.y * document.height])}
          closed={draft.length > 2}
          fill={draft.length > 2 ? '#5f98ad' : undefined}
          stroke="#5f98ad"
          strokeWidth={brushWidth(document)}
          lineCap="round"
          lineJoin="round"
          opacity={0.45}
          listening={false}
        />
      )}
      {pins.map((marker) => (
        <MarkerBadge
          key={marker.index}
          x={marker.x * document.width}
          y={marker.y * document.height}
          index={marker.index}
          scale={scale}
          pending={!maskReady}
        />
      ))}
    </KonvaLayer>
  )
}

function MarkerBadge({
  x,
  y,
  index,
  scale,
  pending = false,
}: {
  x: number
  y: number
  index: number
  scale: number
  pending?: boolean
}) {
  const invert = 1 / scale
  return (
    <Group x={x} y={y} scaleX={invert} scaleY={invert} listening={false}>
      {pending && <Circle radius={17} stroke="#5f98ad" strokeWidth={2} opacity={0.45} />}
      <Circle radius={11} fill="#5f98ad" shadowColor="#141a14" shadowBlur={8} shadowOpacity={0.35} />
      <Text
        text={String(index)}
        width={22}
        height={22}
        offsetX={11}
        offsetY={11}
        align="center"
        verticalAlign="middle"
        fontSize={11}
        fontStyle="600"
        fill="#ffffff"
      />
    </Group>
  )
}
