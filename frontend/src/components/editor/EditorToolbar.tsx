import { useState } from 'react'
import { Link } from 'react-router-dom'

import type { SessionDetail } from '@/api/sessions'
import Button from '@/components/ui/Button'
import { buttonClass } from '@/components/ui/buttonStyles'
import type { SessionSelection } from '@/hooks/useSelection'
import type { SessionTools } from '@/hooks/useSessions'
import { wallOnly } from '@/lib/layers'
import { ZOOM_STEP, useCanvasView } from '@/stores/canvasView'
import { useEditorUi, type CropRatio } from '@/stores/editorUi'

const CROP_RATIOS: { value: CropRatio; label: string }[] = [
  { value: 'free', label: '自由' },
  { value: '1:1', label: '1:1' },
  { value: '4:5', label: '4:5' },
  { value: '9:16', label: '9:16' },
  { value: '16:9', label: '16:9' },
]

export default function EditorToolbar({
  session,
  tools,
  picking,
  onRename,
}: {
  session: SessionDetail
  tools: SessionTools
  picking: SessionSelection
  onRename: (title: string) => void
}) {
  const scale = useCanvasView((state) => state.scale)
  const fit = useCanvasView((state) => state.fit)
  const stepZoom = useCanvasView((state) => state.stepZoom)
  const zoomTo = useCanvasView((state) => state.zoomTo)
  const ui = useEditorUi()

  // 只有发起的那个按钮显示百分比，其余按钮照常禁用
  const running = (tool: string, match?: (params: Record<string, unknown>) => boolean) =>
    tools.isRunning(tool, match) ? tools.pendingProgress : null

  const confirmCrop = () => {
    if (!ui.cropRect) return
    tools.invoke('crop_canvas', {
      rect: {
        x: ui.cropRect.x / session.document.width,
        y: ui.cropRect.y / session.document.height,
        width: ui.cropRect.width / session.document.width,
        height: ui.cropRect.height / session.document.height,
      },
    })
    ui.closeCrop()
  }

  return (
    <header className="border-line bg-paper scrollbar-slim flex h-14 shrink-0 items-center gap-2 overflow-x-auto border-b px-3">
      <TitleField value={session.title} onCommit={onRename} />

      <span className="text-faint hidden shrink-0 text-xs tabular-nums sm:block">
        {session.document.width} × {session.document.height}
      </span>

      <div className="ml-1 flex shrink-0 items-center gap-1">
        {ui.selectMode ? (
          <>
            <Button
              active={ui.selectMode === 'point'}
              title="点击物体生成选区"
              onClick={() => ui.setSelectMode(ui.selectMode === 'point' ? null : 'point')}
            >
              点选
            </Button>
            <Button
              active={ui.selectMode === 'brush'}
              title="涂抹出选区"
              onClick={() => ui.setSelectMode(ui.selectMode === 'brush' ? null : 'brush')}
            >
              笔刷
            </Button>
            <Button
              disabled={tools.busy || picking.busy || !picking.selection}
              progress={running('erase_region')}
              title={picking.selection ? '消除选中区域' : '先点选或涂抹'}
              onClick={() =>
                tools.invoke('erase_region', {
                  mask_asset_id: picking.selection?.maskId,
                  revision: session.revision,
                  layer_id: ui.selectedLayerId,
                })
              }
            >
              消除
            </Button>
            <Button
              disabled={!picking.selection}
              active={ui.panel === 'replace'}
              title={picking.selection ? '按描述替换选区' : '先点选或涂抹'}
              onClick={() => ui.setPanel(ui.panel === 'replace' ? null : 'replace')}
            >
              替换
            </Button>
            <Button
              disabled={tools.busy || picking.busy || !picking.selection}
              progress={running('promote_object_to_layer')}
              title={picking.selection ? '把选区提升为独立图层，可撤销' : '先点选或涂抹'}
              onClick={() =>
                tools.invoke('promote_object_to_layer', {
                  mask_asset_id: picking.selection?.maskId,
                  revision: session.revision,
                })
              }
            >
              成层
            </Button>
            <Button
              disabled={!picking.selection || picking.busy}
              title="清除当前选区"
              onClick={picking.clear}
            >
              清除
            </Button>
            <Button title="退出选择 Esc" onClick={() => ui.setSelectMode(null)}>
              完成
            </Button>
          </>
        ) : ui.cropOpen ? (
          <>
            {CROP_RATIOS.map((item) => (
              <Button
                key={item.value}
                active={ui.cropRatio === item.value}
                title={item.value === 'free' ? '自由裁剪' : `按 ${item.label} 裁剪`}
                onClick={() => ui.setCropRatio(item.value, session.document)}
              >
                {item.label}
              </Button>
            ))}
            <Button title="按当前框裁剪画布，可撤销" onClick={confirmCrop}>
              确定
            </Button>
            <Button title="退出裁剪 Esc" onClick={ui.closeCrop}>
              取消
            </Button>
          </>
        ) : (
          <>
            <Button
              disabled={tools.busy}
              active={ui.cropOpen}
              title="按比例裁剪画布"
              onClick={() => ui.openCrop(session.document)}
            >
              裁剪
            </Button>
            <Button
              disabled={tools.busy}
              progress={running('flip_layer', (params) => params.direction === 'horizontal')}
              title="左右翻转当前图层"
              onClick={() =>
                tools.invoke('flip_layer', {
                  direction: 'horizontal',
                  layer_id: ui.selectedLayerId,
                })
              }
            >
              水平翻转
            </Button>
            <Button
              disabled={tools.busy}
              progress={running('flip_layer', (params) => params.direction === 'vertical')}
              title="上下翻转当前图层"
              onClick={() =>
                tools.invoke('flip_layer', {
                  direction: 'vertical',
                  layer_id: ui.selectedLayerId,
                })
              }
            >
              垂直翻转
            </Button>
            <Button
              disabled={tools.busy}
              progress={running('remove_background')}
              title="抠出主体，背景变透明"
              onClick={() => tools.invoke('remove_background', { layer_id: ui.selectedLayerId })}
            >
              去背景
            </Button>
            <Button
              disabled={tools.busy}
              active={ui.panel === 'background'}
              title="按描述替换背景"
              onClick={() => ui.setPanel(ui.panel === 'background' ? null : 'background')}
            >
              换背景
            </Button>
            <Button
              disabled={tools.busy}
              active={ui.panel === 'expand'}
              title="扩展画布到新比例"
              onClick={() => ui.setPanel(ui.panel === 'expand' ? null : 'expand')}
            >
              扩图
            </Button>
            <Button
              disabled={tools.busy}
              progress={running('upscale_image')}
              title={
                wallOnly(session.document)
                  ? '放大到两倍，已拆层所以结果只进图片墙'
                  : '把当前画布放大到两倍'
              }
              onClick={() => tools.invoke('upscale_image', { scale: 2 })}
            >
              超分
            </Button>
            <Button
              active={ui.panel === 'adjust'}
              title="调整亮度、对比度和色彩"
              onClick={() => ui.setPanel(ui.panel === 'adjust' ? null : 'adjust')}
            >
              调色
            </Button>
            <Button
              disabled={tools.busy}
              progress={running('split_layers')}
              title="拆成背景和主体，文字需在图层面板勾选，可撤销"
              onClick={() => tools.invoke('split_layers', { include_text: ui.splitIncludeText })}
            >
              拆层
            </Button>
            <Button
              disabled={tools.busy}
              title="点选物体建立选区"
              onClick={() => ui.setSelectMode('point')}
            >
              点选
            </Button>
            <Button
              disabled={tools.busy}
              title="涂抹建立选区"
              onClick={() => ui.setSelectMode('brush')}
            >
              笔刷
            </Button>
          </>
        )}
      </div>

      <div className="ml-auto flex shrink-0 items-center gap-1">
        <Button
          disabled={tools.busy || picking.busy || !(picking.canUndo || session.can_undo)}
          title={
            picking.canUndo
              ? '撤销选区 ⌘Z'
              : session.can_undo
                ? '撤销上一步 ⌘Z'
                : '没有可撤销的操作'
          }
          onClick={() => (picking.canUndo ? picking.undo() : tools.undo())}
        >
          撤销
        </Button>
        <Button
          disabled={tools.busy || picking.busy || !(picking.canRedo || session.can_redo)}
          title={
            picking.canRedo
              ? '重做选区 ⌘⇧Z'
              : session.can_redo
                ? '重做 ⌘⇧Z'
                : '没有可重做的操作'
          }
          onClick={() => (picking.canRedo ? picking.redo() : tools.redo())}
        >
          重做
        </Button>
        <Button
          active={ui.compareOpen}
          disabled={!session.previous_document}
          title={session.previous_document ? '与上一版对比' : '还没有上一版'}
          onClick={() => ui.setCompareOpen(!ui.compareOpen)}
        >
          对比
        </Button>

        <div className="border-line rounded-control ml-1 flex items-center gap-0.5 border p-0.5">
          <Button
            variant="icon"
            size="sm"
            title="缩小 -"
            onClick={() => stepZoom(1 / ZOOM_STEP)}
          >
            －
          </Button>
          <Button
            size="sm"
            title="实际像素 · 按 1"
            className="w-12 tabular-nums"
            onClick={() => zoomTo(1)}
          >
            {Math.round(scale * 100)}%
          </Button>
          <Button variant="icon" size="sm" title="放大 +" onClick={() => stepZoom(ZOOM_STEP)}>
            ＋
          </Button>
          <Button
            size="sm"
            title="适应窗口 · 按 0，画布内双击同样生效"
            onClick={() => fit(session.document)}
          >
            适应
          </Button>
        </div>

        <Link to={`/marketing/${session.id}`} title="导出营销图和投放尺寸" className={buttonClass()}>
          导出
        </Link>
        <Button
          active={ui.panel === 'layers'}
          title="图层、变换和编辑记录"
          onClick={() => ui.setPanel(ui.panel === 'layers' ? null : 'layers')}
        >
          图层
        </Button>
      </div>
    </header>
  )
}

function TitleField({ value, onCommit }: { value: string; onCommit: (title: string) => void }) {
  const [draft, setDraft] = useState<string | null>(null)

  const commit = () => {
    const next = draft?.trim()
    setDraft(null)
    if (next && next !== value) onCommit(next)
  }

  return (
    <input
      value={draft ?? value}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === 'Enter') event.currentTarget.blur()
        if (event.key === 'Escape') setDraft(null)
      }}
      aria-label="会话标题"
      className="text-ink hover:bg-soft focus:bg-soft rounded-chip w-28 shrink-0 px-2 py-1 text-sm font-medium transition-colors duration-150 outline-none sm:w-40"
    />
  )
}
