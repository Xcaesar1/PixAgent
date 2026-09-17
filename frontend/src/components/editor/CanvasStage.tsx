import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type Konva from 'konva'
import {
  Circle,
  Group,
  Image as KonvaImage,
  Layer as KonvaLayer,
  Line,
  Rect,
  Stage,
  Text,
  Transformer,
} from 'react-konva'

import type { Layer, LayerDocument } from '@/api/sessions'
import { SelectionOverlay } from '@/components/editor/SelectionOverlay'
import { canvasStamp, useHeldCanvas, type HeldCanvas } from '@/hooks/useHeldCanvas'
import { usePointPreview } from '@/hooks/usePointPreview'
import { useSelectStroke } from '@/hooks/useSelectStroke'
import { useCanvasImage } from '@/hooks/useCanvasImage'
import { useElementSize } from '@/hooks/useElementSize'
import { makeAdjustFilter, toAdjustPreview, type AdjustPreview } from '@/lib/adjustPreview'
import { useCanvasView } from '@/stores/canvasView'
import { useEditorUi, type CanvasSelection, type CropRect, type LayerPreview } from '@/stores/editorUi'

const NO_FILTERS: ((imageData: ImageData) => void)[] = []
// 预览按屏幕分辨率量级缓存，滤镜每帧重算才跟得上滑杆
const PREVIEW_PIXEL_RATIO = 0.6
const SWITCH_FADE_MS = 180

export default function CanvasStage({
  document,
  previous,
  urls,
  selection = null,
  onPoint,
  onStroke,
  onMove,
  onScale,
  onEditText,
}: {
  document: LayerDocument
  previous: LayerDocument | null
  urls: Map<string, string>
  selection?: CanvasSelection | null
  onPoint?: (x: number, y: number) => void
  onStroke?: (points: { x: number; y: number }[]) => void
  onMove?: (layerId: string, x: number, y: number) => void
  onScale?: (layerId: string, scale: number, x: number, y: number) => void
  onEditText?: (layerId: string, text: string) => void
}) {
  const [containerRef, size] = useElementSize<HTMLDivElement>()
  const scale = useCanvasView((state) => state.scale)
  const x = useCanvasView((state) => state.x)
  const y = useCanvasView((state) => state.y)
  const setViewport = useCanvasView((state) => state.setViewport)
  const fit = useCanvasView((state) => state.fit)
  const zoomByWheel = useCanvasView((state) => state.zoomByWheel)
  const panBy = useCanvasView((state) => state.panBy)
  const pan = useCanvasView((state) => state.pan)

  const cropOpen = useEditorUi((state) => state.cropOpen)
  const cropRect = useEditorUi((state) => state.cropRect)
  const cropRatio = useEditorUi((state) => state.cropRatio)
  const setCropRect = useEditorUi((state) => state.setCropRect)
  const compareOpen = useEditorUi((state) => state.compareOpen)
  const compareAt = useEditorUi((state) => state.compareAt)
  const setCompareAt = useEditorUi((state) => state.setCompareAt)
  const adjustPreview = useEditorUi((state) => state.adjustPreview)
  const layerPreview = useEditorUi((state) => state.layerPreview)
  const selectMode = useEditorUi((state) => state.selectMode)
  const selectedLayerId = useEditorUi((state) => state.selectedLayerId)
  const selectLayer = useEditorUi((state) => state.selectLayer)
  const shown = useHeldCanvas(document, urls)
  const canvas = shown.document
  const images = shown.urls
  const shownRef = useRef(shown)
  const [ghost, setGhost] = useState<GhostFrame | null>(null)
  const [ghostOpacity, setGhostOpacity] = useState(0)
  const [holdingStage, setHoldingStage] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const stroke = useSelectStroke()
  const point = usePointPreview(canvas, images)
  const editing = editingId
    ? (canvas.layers.find((layer) => layer.id === editingId && layer.kind === 'text') ?? null)
    : null
  const selecting = Boolean(selectMode)
  const interactive = !selecting && !cropOpen && !compareOpen
  const stageDraggable = !cropOpen && !selecting && !holdingStage

  const settleOverlay = useCallback(() => {
    stroke.settle()
    point.settle()
  }, [stroke.settle, point.settle])

  useEffect(() => {
    if (!selection) settleOverlay()
  }, [selection, settleOverlay])

  useEffect(() => {
    if (selectMode !== 'point') point.settle()
  }, [selectMode, point.settle])

  useEffect(() => {
    if (!interactive) setEditingId(null)
  }, [interactive])

  useEffect(() => {
    if (editingId && !editing) setEditingId(null)
  }, [editingId, editing])

  const fitted = useRef('')

  const canvasPoint = (stage: Konva.Stage | null) => {
    const pointer = stage?.getRelativePointerPosition()
    if (!pointer) return null
    const x = pointer.x / canvas.width
    const y = pointer.y / canvas.height
    if (x < 0 || y < 0 || x > 1 || y > 1) return null
    return { x, y }
  }

  useEffect(() => {
    setViewport(size)
  }, [size, setViewport])

  useLayoutEffect(() => {
    const prev = shownRef.current
    shownRef.current = shown
    if (canvasStamp(prev.document) === canvasStamp(shown.document)) return
    const view = useCanvasView.getState()
    setGhost({
      document: prev.document,
      urls: prev.urls,
      scale: view.scale,
      x: view.x,
      y: view.y,
    })
    setGhostOpacity(1)
  }, [shown])

  useLayoutEffect(() => {
    if (!size.width || !size.height) return
    const shape = `${canvas.width}x${canvas.height}`
    if (fitted.current === shape) return
    // 切图改画幅时一次对齐，不走适应缓动，否则同尺寸硬切、不同尺寸又会缩放到位
    fit(canvas, { animate: false })
    fitted.current = shape
  }, [size.width, size.height, canvas, fit])

  useEffect(() => {
    if (!ghost || ghostOpacity === 0) return
    const frame = requestAnimationFrame(() => setGhostOpacity(0))
    return () => cancelAnimationFrame(frame)
  }, [ghost, ghostOpacity])

  const split = canvas.width * compareAt
  const color = useMemo(() => toAdjustPreview(adjustPreview), [adjustPreview])
  const compareWith = compareOpen ? previous : null

  return (
    <div
      ref={containerRef}
      className={`bg-canvas relative h-full w-full overflow-hidden ${
        selecting || cropOpen ? 'cursor-crosshair' : 'cursor-grab active:cursor-grabbing'
      }`}
    >
      <Stage
        width={size.width}
        height={size.height}
        x={x}
        y={y}
        scaleX={scale}
        scaleY={scale}
        draggable={stageDraggable}
        onMouseDown={(event) => {
          if (selectMode !== 'brush' || !onStroke) return
          const point = canvasPoint(event.target.getStage())
          if (point) stroke.start(point)
        }}
        onMouseMove={(event) => {
          if (selectMode !== 'brush' || !onStroke) return
          const point = canvasPoint(event.target.getStage())
          if (point) stroke.move(point)
        }}
        onMouseUp={() => {
          if (selectMode !== 'brush' || !onStroke) return
          const points = stroke.end()
          if (points.length) onStroke(points)
        }}
        onClick={(event) => {
          if (selectMode !== 'point' || !onPoint) return
          const picked = canvasPoint(event.target.getStage())
          if (!picked) return
          point.pick(picked, selection?.markers ?? [])
          onPoint(picked.x, picked.y)
        }}
        onDragMove={(event) => {
          if (event.target !== event.target.getStage()) return
          pan({ x: event.target.x(), y: event.target.y() })
        }}
        onDblClick={(event) => {
          if (selecting || event.target !== event.target.getStage()) return
          fit(canvas)
        }}
        onWheel={(event) => {
          event.evt.preventDefault()
          // 捏合与 ⌘ 滚动缩放，普通滚动平移，与主流画布一致
          if (event.evt.ctrlKey || event.evt.metaKey) {
            const pointer = event.target.getStage()?.getPointerPosition()
            zoomByWheel(event.evt.deltaY, pointer ?? undefined)
            return
          }
          panBy(-event.evt.deltaX, -event.evt.deltaY)
        }}
      >
        <CanvasBoard width={canvas.width} height={canvas.height} />

        {compareWith ? (
          <>
            <DocumentLayer
              document={compareWith}
              urls={images}
              clip={{ x: 0, y: 0, width: split, height: canvas.height }}
            />
            <DocumentLayer
              document={canvas}
              urls={images}
              color={color}
              layerPreview={layerPreview}
              clip={{
                x: split,
                y: 0,
                width: canvas.width - split,
                height: canvas.height,
              }}
            />
          </>
        ) : (
          <DocumentLayer
            document={canvas}
            urls={images}
            color={color}
            layerPreview={layerPreview}
            interactive={interactive}
            stageDraggable={stageDraggable}
            viewScale={scale}
            selectedId={selectedLayerId}
            editingId={editingId}
            onSelect={selectLayer}
            onMove={onMove}
            onScale={onScale}
            onEdit={interactive ? setEditingId : undefined}
            onHoldStage={setHoldingStage}
          />
        )}

        {compareWith && (
          <CompareDivider canvas={canvas} split={split} scale={scale} onChange={setCompareAt} />
        )}

        {cropOpen && cropRect && (
          <CropLayer
            canvas={canvas}
            rect={cropRect}
            scale={scale}
            keepRatio={cropRatio !== 'free'}
            onChange={setCropRect}
          />
        )}

        {(selection || stroke.draft.length > 0 || point.active) && (
          <SelectionOverlay
            document={canvas}
            selection={selection}
            scale={scale}
            draft={stroke.draft}
            pending={stroke.pending}
            preview={point.preview}
            markers={point.markers.length ? point.markers : selection?.markers}
            onMaskReady={settleOverlay}
          />
        )}
      </Stage>
      {editing && (
        <TextEditor
          layer={editing}
          view={{ scale, x, y }}
          onCommit={(text) => {
            setEditingId(null)
            if (text !== (editing.text || '')) onEditText?.(editing.id, text)
          }}
          onCancel={() => setEditingId(null)}
        />
      )}
      {ghost && (
        <CanvasGhost
          key={canvasStamp(ghost.document)}
          frame={ghost}
          opacity={ghostOpacity}
          size={size}
          onFaded={() => {
            setGhost(null)
            setGhostOpacity(0)
          }}
        />
      )}
    </div>
  )
}

type GhostFrame = HeldCanvas & { scale: number; x: number; y: number }

function CanvasBoard({ width, height }: { width: number; height: number }) {
  return (
    <KonvaLayer listening={false}>
      <Rect
        width={width}
        height={height}
        fill="#ffffff"
        shadowColor="#141a14"
        shadowBlur={32}
        shadowOpacity={0.16}
      />
    </KonvaLayer>
  )
}

function CanvasGhost({
  frame,
  opacity,
  size,
  onFaded,
}: {
  frame: GhostFrame
  opacity: number
  size: { width: number; height: number }
  onFaded: () => void
}) {
  return (
    <div
      className="pointer-events-none absolute inset-0"
      style={{ opacity, transition: `opacity ${SWITCH_FADE_MS}ms ease-out` }}
      onTransitionEnd={(event) => {
        if (event.propertyName === 'opacity' && opacity === 0) onFaded()
      }}
    >
      <Stage
        width={size.width}
        height={size.height}
        x={frame.x}
        y={frame.y}
        scaleX={frame.scale}
        scaleY={frame.scale}
        listening={false}
      >
        <CanvasBoard width={frame.document.width} height={frame.document.height} />
        <DocumentLayer document={frame.document} urls={frame.urls} />
      </Stage>
    </div>
  )
}

function useLayerNodes(selectedId: string | null) {
  const nodes = useRef(new Map<string, Konva.Node>())
  const selectedRef = useRef(selectedId)
  selectedRef.current = selectedId
  const [, bump] = useState(0)

  const register = useCallback((id: string, node: Konva.Node | null) => {
    const prev = nodes.current.get(id) ?? null
    if (prev === node) return
    if (node) nodes.current.set(id, node)
    else nodes.current.delete(id)
    if (id === selectedRef.current) bump((value) => value + 1)
  }, [])

  return {
    selectedNode: selectedId ? (nodes.current.get(selectedId) ?? null) : null,
    register,
  }
}

function useLayerNode(
  id: string,
  onRegister?: (id: string, node: Konva.Node | null) => void,
) {
  const nodeRef = useRef<Konva.Node | null>(null)
  const registerRef = useRef(onRegister)
  registerRef.current = onRegister
  const setRef = useCallback(
    (node: Konva.Node | null) => {
      nodeRef.current = node
      registerRef.current?.(id, node)
    },
    [id],
  )
  return { nodeRef, setRef }
}

function DocumentLayer({
  document,
  urls,
  color,
  layerPreview,
  clip,
  interactive = false,
  stageDraggable = false,
  viewScale = 1,
  selectedId = null,
  editingId = null,
  onSelect,
  onMove,
  onScale,
  onEdit,
  onHoldStage,
}: {
  document: LayerDocument
  urls: Map<string, string>
  color?: AdjustPreview | null
  layerPreview?: LayerPreview | null
  clip?: { x: number; y: number; width: number; height: number }
  interactive?: boolean
  stageDraggable?: boolean
  viewScale?: number
  selectedId?: string | null
  editingId?: string | null
  onSelect?: (id: string) => void
  onMove?: (layerId: string, x: number, y: number) => void
  onScale?: (layerId: string, scale: number, x: number, y: number) => void
  onEdit?: (id: string) => void
  onHoldStage?: (held: boolean) => void
}) {
  const { selectedNode, register } = useLayerNodes(selectedId)
  const [pinned, setPinned] = useState<Pinned | null>(null)
  const waitingStamp = useRef<string | null>(null)
  const layers = document.layers.filter((layer) => layer.visible)
  const selected = layers.find((layer) => layer.id === selectedId) ?? null
  const stamp = selected ? transformStamp(selected) : ''

  useEffect(() => {
    if (!pinned) return
    if (!selected || selected.id !== pinned.id) {
      waitingStamp.current = null
      setPinned(null)
      return
    }
    if (samePinned(selected, pinned)) {
      waitingStamp.current = null
      return
    }
    // 文档还是钉住前的旧值：写入未完成，继续用钉住的画面
    if (stamp === waitingStamp.current) return
    waitingStamp.current = null
    setPinned(null)
  }, [stamp, pinned, selected])

  return (
    <KonvaLayer
      listening={interactive}
      clipX={clip?.x ?? 0}
      clipY={clip?.y ?? 0}
      clipWidth={clip?.width ?? document.width}
      clipHeight={clip?.height ?? document.height}
    >
      {layers.map((layer) =>
        layer.kind === 'text' ? (
          <TextLayer
            key={layer.id}
            layer={layer}
            preview={layerPreview?.id === layer.id ? layerPreview : null}
            pinned={pinned?.id === layer.id ? pinned : null}
            interactive={interactive}
            stageDraggable={stageDraggable}
            selected={selectedId === layer.id}
            editing={editingId === layer.id}
            onSelect={onSelect}
            onMove={onMove}
            onEdit={onEdit}
            onHoldStage={onHoldStage}
            onRegister={register}
          />
        ) : layer.kind === 'image' ? (
          <ImageLayer
            key={layer.id}
            layer={layer}
            url={layer.asset_id ? urls.get(layer.asset_id) : undefined}
            color={color ?? null}
            preview={layerPreview?.id === layer.id ? layerPreview : null}
            pinned={pinned?.id === layer.id ? pinned : null}
            interactive={interactive}
            stageDraggable={stageDraggable}
            selected={selectedId === layer.id}
            onSelect={onSelect}
            onMove={onMove}
            onHoldStage={onHoldStage}
            onRegister={register}
          />
        ) : null,
      )}
      {interactive && selected && selectedNode && editingId !== selected.id && (
        <LayerScaler
          node={selectedNode}
          layer={selected}
          viewScale={viewScale}
          onScale={(layerId, scale, x, y) => {
            waitingStamp.current = stamp
            setPinned({ id: layerId, scale, x, y })
            onScale?.(layerId, scale, x, y)
          }}
          onHoldStage={onHoldStage}
        />
      )}
    </KonvaLayer>
  )
}

function TextLayer({
  layer,
  preview,
  pinned = null,
  interactive = false,
  stageDraggable = false,
  selected = false,
  editing = false,
  onSelect,
  onMove,
  onEdit,
  onHoldStage,
  onRegister,
}: {
  layer: Layer
  preview: LayerPreview | null
  pinned?: Pinned | null
  interactive?: boolean
  stageDraggable?: boolean
  selected?: boolean
  editing?: boolean
  onSelect?: (id: string) => void
  onMove?: (layerId: string, x: number, y: number) => void
  onEdit?: (id: string) => void
  onHoldStage?: (held: boolean) => void
  onRegister?: (id: string, node: Konva.Node | null) => void
}) {
  const drag = useLayerInteract(layer, interactive && !editing, stageDraggable, onSelect, onMove, onHoldStage)
  const { setRef } = useLayerNode(layer.id, onRegister)
  const { transform } = layer
  const point = layerPoint(layer, preview, drag.drop, pinned)
  const sized = layerScale(layer, preview, pinned)

  return (
    <Text
      ref={setRef}
      text={preview?.text ?? layer.text ?? layer.name}
      x={point.x}
      y={point.y}
      offsetX={layer.width / 2}
      offsetY={layer.height / 2}
      width={layer.width}
      height={layer.height}
      fontSize={preview?.font_size ?? layer.font_size ?? Math.max(12, layer.height * 0.72)}
      fill={preview?.fill ?? layer.fill ?? '#141414'}
      align="center"
      verticalAlign="middle"
      scaleX={sized.x}
      scaleY={sized.y}
      rotation={preview?.rotation ?? transform.rotation}
      opacity={editing ? 0 : (preview?.opacity ?? layer.opacity)}
      {...drag.handlers}
      onDblClick={(event) => {
        if (!interactive) return
        event.cancelBubble = true
        onSelect?.(layer.id)
        onEdit?.(layer.id)
      }}
      stroke={selected && interactive && !editing ? '#5f98ad' : undefined}
      strokeWidth={selected && interactive && !editing ? 2 : 0}
      strokeScaleEnabled={false}
    />
  )
}

function TextEditor({
  layer,
  view,
  onCommit,
  onCancel,
}: {
  layer: Layer
  view: { scale: number; x: number; y: number }
  onCommit: (text: string) => void
  onCancel: () => void
}) {
  const [value, setValue] = useState(layer.text || '')
  const ref = useRef<HTMLTextAreaElement>(null)
  const done = useRef(false)
  const scale = Math.abs(layer.transform.scale_x) * view.scale
  const width = Math.max(48, layer.width * scale)
  const height = Math.max(28, layer.height * scale)
  const fontSize = Math.max(12, (layer.font_size ?? 24) * scale)

  useEffect(() => {
    ref.current?.focus()
    ref.current?.select()
  }, [])

  const finish = (next: string | null) => {
    if (done.current) return
    done.current = true
    if (next === null) onCancel()
    else onCommit(next)
  }

  return (
    <textarea
      ref={ref}
      value={value}
      onChange={(event) => setValue(event.target.value)}
      onBlur={() => finish(value)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
          event.preventDefault()
          finish(value)
        }
        if (event.key === 'Escape') {
          event.preventDefault()
          finish(null)
        }
      }}
      className="border-brand bg-paper text-ink absolute z-10 resize-none border px-1 py-0.5 outline-none"
      style={{
        left: view.x + layer.transform.x * view.scale,
        top: view.y + layer.transform.y * view.scale,
        width,
        height,
        fontSize,
        color: layer.fill ?? '#141414',
        lineHeight: `${height}px`,
        textAlign: 'center',
        transform: layer.transform.rotation ? `rotate(${layer.transform.rotation}deg)` : undefined,
        transformOrigin: 'center center',
      }}
    />
  )
}

function ImageLayer({
  layer,
  url,
  color,
  preview,
  pinned = null,
  interactive = false,
  stageDraggable = false,
  selected = false,
  onSelect,
  onMove,
  onHoldStage,
  onRegister,
}: {
  layer: Layer
  url: string | undefined
  color: AdjustPreview | null
  preview: LayerPreview | null
  pinned?: Pinned | null
  interactive?: boolean
  stageDraggable?: boolean
  selected?: boolean
  onSelect?: (id: string) => void
  onMove?: (layerId: string, x: number, y: number) => void
  onHoldStage?: (held: boolean) => void
  onRegister?: (id: string, node: Konva.Node | null) => void
}) {
  const image = useCanvasImage(url)
  const { nodeRef, setRef } = useLayerNode(layer.id, onRegister)
  const drag = useLayerInteract(layer, interactive, stageDraggable, onSelect, onMove, onHoldStage)
  const filtered = color !== null && image?.safe === true
  // 数值不变时保持数组同一引用，平移缩放才不会白白重算滤镜
  const filters = useMemo(
    () => (filtered && color ? [makeAdjustFilter(color)] : NO_FILTERS),
    [filtered, color],
  )

  // 滤镜要求节点先缓存；缓存后的位图同时让缩放平移更省算力
  useEffect(() => {
    const node = nodeRef.current
    if (!node || !image) return
    if (filtered) node.cache({ pixelRatio: PREVIEW_PIXEL_RATIO })
    else node.clearCache()
  }, [image, filtered, layer.width, layer.height])

  if (!image) return null

  const { transform } = layer
  const point = layerPoint(layer, preview, drag.drop, pinned)
  const sized = layerScale(layer, preview, pinned)

  return (
    <KonvaImage
      ref={setRef}
      image={image.element}
      x={point.x}
      y={point.y}
      offsetX={layer.width / 2}
      offsetY={layer.height / 2}
      width={layer.width}
      height={layer.height}
      scaleX={sized.x}
      scaleY={sized.y}
      rotation={preview?.rotation ?? transform.rotation}
      opacity={preview?.opacity ?? layer.opacity}
      filters={filters}
      {...drag.handlers}
      stroke={selected && interactive ? '#5f98ad' : undefined}
      strokeWidth={selected && interactive ? 2 : 0}
      strokeScaleEnabled={false}
    />
  )
}

type Drop = { x: number; y: number }

/** 拖角写入服务端期间钉住的缩放与位置，两者必须成对，否则画面会错位。 */
type Pinned = { id: string; scale: number; x: number; y: number }

function transformStamp(layer: Layer) {
  const { x, y, scale_x, scale_y } = layer.transform
  return `${layer.id}:${x},${y},${scale_x},${scale_y}`
}

function samePinned(layer: Layer, pinned: Pinned) {
  const { x, y, scale_x } = layer.transform
  return (
    Math.abs(Math.abs(scale_x) - pinned.scale) < 0.001 &&
    Math.abs(x - pinned.x) < 0.5 &&
    Math.abs(y - pinned.y) < 0.5
  )
}

function layerPoint(
  layer: Layer,
  preview: LayerPreview | null,
  drop: Drop | null,
  pinned: Pinned | null,
) {
  return {
    x: (drop?.x ?? pinned?.x ?? preview?.x ?? layer.transform.x) + layer.width / 2,
    y: (drop?.y ?? pinned?.y ?? preview?.y ?? layer.transform.y) + layer.height / 2,
  }
}

function layerScale(layer: Layer, preview: LayerPreview | null, pinned: Pinned | null) {
  const magnitude = pinned?.scale ?? preview?.scale ?? Math.abs(layer.transform.scale_x)
  return {
    x: (Math.sign(layer.transform.scale_x) || 1) * magnitude,
    y: (Math.sign(layer.transform.scale_y) || 1) * magnitude,
  }
}

const MIN_LAYER_SCALE = 0.1
const MAX_LAYER_SCALE = 8

function clampLayerScale(value: number) {
  return Math.min(MAX_LAYER_SCALE, Math.max(MIN_LAYER_SCALE, value))
}

function useLayerInteract(
  layer: Layer,
  interactive: boolean,
  stageDraggable: boolean,
  onSelect?: (id: string) => void,
  onMove?: (layerId: string, x: number, y: number) => void,
  onHoldStage?: (held: boolean) => void,
) {
  const [drop, setDrop] = useState<Drop | null>(null)
  const dragged = useRef(false)
  const movable = interactive && !layer.locked

  useEffect(() => {
    if (!drop) return
    if (Math.abs(layer.transform.x - drop.x) < 0.5 && Math.abs(layer.transform.y - drop.y) < 0.5) {
      setDrop(null)
    }
  }, [layer.transform.x, layer.transform.y, drop])

  const restoreStage = (node: Konva.Node) => {
    node.getStage()?.draggable(stageDraggable)
  }

  const pick = () => {
    if (dragged.current) {
      dragged.current = false
      return
    }
    onSelect?.(layer.id)
  }

  return {
    drop,
    handlers: {
      listening: interactive,
      draggable: movable,
      dragDistance: 2,
      onMouseDown: (event: Konva.KonvaEventObject<MouseEvent>) => {
        event.cancelBubble = true
        if (movable) event.target.getStage()?.draggable(false)
      },
      onMouseUp: (event: Konva.KonvaEventObject<MouseEvent>) => {
        if (!dragged.current) restoreStage(event.target)
      },
      onMouseEnter: (event: Konva.KonvaEventObject<MouseEvent>) => {
        const container = event.target.getStage()?.container()
        if (container && movable) container.style.cursor = 'move'
      },
      onMouseLeave: (event: Konva.KonvaEventObject<MouseEvent>) => {
        const container = event.target.getStage()?.container()
        if (container) container.style.cursor = ''
      },
      onClick: pick,
      onTap: pick,
      onDragStart: (event: Konva.KonvaEventObject<DragEvent>) => {
        event.cancelBubble = true
        dragged.current = true
        event.target.getStage()?.draggable(false)
        onHoldStage?.(true)
      },
      onDragMove: (event: Konva.KonvaEventObject<DragEvent>) => {
        event.cancelBubble = true
      },
      onDragEnd: (event: Konva.KonvaEventObject<DragEvent>) => {
        event.cancelBubble = true
        restoreStage(event.target)
        onHoldStage?.(false)
        const next = {
          x: event.target.x() - layer.width / 2,
          y: event.target.y() - layer.height / 2,
        }
        onSelect?.(layer.id)
        if (Math.abs(next.x - layer.transform.x) < 0.5 && Math.abs(next.y - layer.transform.y) < 0.5) {
          return
        }
        setDrop(next)
        onMove?.(layer.id, next.x, next.y)
      },
    },
  }
}

function LayerScaler({
  node,
  layer,
  viewScale,
  onScale,
  onHoldStage,
}: {
  node: Konva.Node
  layer: Layer
  viewScale: number
  onScale?: (layerId: string, scale: number, x: number, y: number) => void
  onHoldStage?: (held: boolean) => void
}) {
  const ref = useRef<Konva.Transformer>(null)
  const invert = 1 / viewScale

  useEffect(() => {
    const transformer = ref.current
    if (!transformer) return
    transformer.nodes([node])
    transformer.getLayer()?.batchDraw()
    return () => {
      transformer.nodes([])
    }
  }, [node])

  return (
    <Transformer
      ref={ref}
      rotateEnabled={false}
      flipEnabled={false}
      keepRatio
      enabledAnchors={['top-left', 'top-right', 'bottom-left', 'bottom-right']}
      ignoreStroke
      anchorSize={10 * invert}
      anchorCornerRadius={3 * invert}
      anchorStrokeWidth={1.5 * invert}
      borderStrokeWidth={invert}
      anchorStroke="#427f95"
      borderStroke="#5f98ad"
      boundBoxFunc={(oldBox, newBox) => {
        const min = MIN_LAYER_SCALE * Math.min(layer.width, layer.height)
        const max = MAX_LAYER_SCALE * Math.max(layer.width, layer.height)
        if (newBox.width < min || newBox.height < min || newBox.width > max || newBox.height > max) {
          return oldBox
        }
        return newBox
      }}
      onTransformStart={() => onHoldStage?.(true)}
      onTransformEnd={() => {
        const next = clampLayerScale((Math.abs(node.scaleX()) + Math.abs(node.scaleY())) / 2)
        const at = { x: node.x() - layer.width / 2, y: node.y() - layer.height / 2 }
        const still =
          Math.abs(next - Math.abs(layer.transform.scale_x)) < 0.001 &&
          Math.abs(at.x - layer.transform.x) < 0.5 &&
          Math.abs(at.y - layer.transform.y) < 0.5
        if (!still) onScale?.(layer.id, next, at.x, at.y)
        onHoldStage?.(false)
      }}
    />
  )
}

/** 对比分割线随画布一起缩放平移，手柄与线宽保持屏幕尺寸不变。 */
function CompareDivider({
  canvas,
  split,
  scale,
  onChange,
}: {
  canvas: LayerDocument
  split: number
  scale: number
  onChange: (value: number) => void
}) {
  const cursor = (node: Konva.Node, shape: string) => {
    const container = node.getStage()?.container()
    if (container) container.style.cursor = shape
  }

  return (
    <KonvaLayer>
      <Line
        points={[split, 0, split, canvas.height]}
        stroke="#ffffff"
        strokeWidth={2}
        strokeScaleEnabled={false}
        shadowColor="#141a14"
        shadowBlur={8}
        shadowOpacity={0.45}
        listening={false}
      />
      <Group
        x={split}
        y={canvas.height / 2}
        scaleX={1 / scale}
        scaleY={1 / scale}
        draggable
        onMouseEnter={(event) => cursor(event.target, 'ew-resize')}
        onMouseLeave={(event) => cursor(event.target, '')}
        onDragMove={(event) => {
          const node = event.target
          // 直接用画布坐标系下的指针位置，手柄自身的反向缩放不参与换算
          const pointer = node.getStage()?.getRelativePointerPosition()
          if (!pointer) return
          const next = Math.min(canvas.width, Math.max(0, pointer.x))
          node.position({ x: next, y: canvas.height / 2 })
          onChange(next / canvas.width)
        }}
      >
        <Circle
          radius={15}
          fill="#ffffff"
          shadowColor="#141a14"
          shadowBlur={10}
          shadowOpacity={0.3}
        />
        <Line points={[-7, -4, -11, 0, -7, 4]} stroke="#6f746f" strokeWidth={1.6} lineCap="round" />
        <Line points={[7, -4, 11, 0, 7, 4]} stroke="#6f746f" strokeWidth={1.6} lineCap="round" />
      </Group>
    </KonvaLayer>
  )
}

function CropLayer({
  canvas,
  rect,
  scale,
  keepRatio,
  onChange,
}: {
  canvas: LayerDocument
  rect: CropRect
  scale: number
  keepRatio: boolean
  onChange: (rect: CropRect) => void
}) {
  const rectRef = useRef<Konva.Rect>(null)
  const transformerRef = useRef<Konva.Transformer>(null)

  useEffect(() => {
    const transformer = transformerRef.current
    const node = rectRef.current
    if (!transformer || !node) return
    transformer.nodes([node])
    transformer.getLayer()?.batchDraw()
  }, [rect])

  // 夹取后的值可能与上一帧相同，此时不会触发重渲染，得手动把节点摆回边界内
  const commit = (next: CropRect) => {
    const clamped = clampRect(next, canvas)
    onChange(clamped)
    return clamped
  }

  // 手柄与描边按倍率反向补偿，缩放后依然是同样的点按面积
  const invert = 1 / scale
  const shade = 'rgba(20,26,20,0.45)'

  return (
    <KonvaLayer>
      <Group listening={false}>
        <Rect width={canvas.width} height={rect.y} fill={shade} />
        <Rect
          y={rect.y + rect.height}
          width={canvas.width}
          height={Math.max(0, canvas.height - rect.y - rect.height)}
          fill={shade}
        />
        <Rect y={rect.y} width={rect.x} height={rect.height} fill={shade} />
        <Rect
          x={rect.x + rect.width}
          y={rect.y}
          width={Math.max(0, canvas.width - rect.x - rect.width)}
          height={rect.height}
          fill={shade}
        />
      </Group>
      <Rect
        ref={rectRef}
        x={rect.x}
        y={rect.y}
        width={rect.width}
        height={rect.height}
        stroke="#5f98ad"
        strokeWidth={2}
        strokeScaleEnabled={false}
        dash={[7 * invert, 5 * invert]}
        draggable
        onDragMove={(event) => {
          const next = commit({
            ...rect,
            x: event.target.x(),
            y: event.target.y(),
          })
          event.target.position({ x: next.x, y: next.y })
        }}
        onTransform={() => {
          const node = rectRef.current
          if (!node) return
          const next = commit({
            x: node.x(),
            y: node.y(),
            width: Math.max(32, node.width() * node.scaleX()),
            height: Math.max(32, node.height() * node.scaleY()),
          })
          node.setAttrs({ ...next, scaleX: 1, scaleY: 1 })
        }}
      />
      <Transformer
        ref={transformerRef}
        rotateEnabled={false}
        flipEnabled={false}
        keepRatio={keepRatio}
        ignoreStroke
        anchorSize={10 * invert}
        anchorCornerRadius={3 * invert}
        anchorStrokeWidth={1.5 * invert}
        borderStrokeWidth={invert}
        anchorStroke="#427f95"
        borderStroke="#5f98ad"
        boundBoxFunc={(oldBox, newBox) =>
          newBox.width < 32 || newBox.height < 32 ? oldBox : newBox
        }
      />
    </KonvaLayer>
  )
}

function clampRect(rect: CropRect, canvas: LayerDocument): CropRect {
  const width = Math.min(rect.width, canvas.width)
  const height = Math.min(rect.height, canvas.height)
  return {
    width,
    height,
    x: Math.min(Math.max(0, rect.x), canvas.width - width),
    y: Math.min(Math.max(0, rect.y), canvas.height - height),
  }
}
