import { create } from 'zustand'

import type { Ratio } from '@/api/runs'
import type { LayerDocument } from '@/api/sessions'

export type CropRatio = Ratio | 'free'
export type CropRect = { x: number; y: number; width: number; height: number }
export type SelectMode = 'point' | 'brush'
export type Marker = { index: number; x: number; y: number }
export type CanvasSelection = {
  revision: number
  maskId: string
  maskUrl: string
  markers: Marker[]
}

/** 滑杆拖动期间的即时效果，只作用于画布渲染，松手后由工具写入文档。 */
export type LayerPreview = {
  id: string
  opacity?: number
  scale?: number
  rotation?: number
  x?: number
  y?: number
  font_size?: number
  fill?: string
  text?: string
}

export type Panel = 'layers' | 'adjust' | 'background' | 'expand' | 'replace' | null

type EditorUi = {
  selectedLayerId: string | null
  cropOpen: boolean
  cropRatio: CropRatio
  cropRect: CropRect | null
  compareOpen: boolean
  compareAt: number
  panel: Panel
  selectMode: SelectMode | null
  selection: CanvasSelection | null
  splitIncludeText: boolean
  adjustPreview: Record<string, number> | null
  layerPreview: LayerPreview | null
  selectLayer: (id: string | null) => void
  openCrop: (document: LayerDocument, ratio?: CropRatio) => void
  setCropRatio: (ratio: CropRatio, document: LayerDocument) => void
  setCropRect: (rect: CropRect) => void
  closeCrop: () => void
  setCompareOpen: (open: boolean) => void
  setCompareAt: (value: number) => void
  setPanel: (panel: Panel) => void
  setSelectMode: (mode: SelectMode | null) => void
  setSelection: (selection: CanvasSelection | null) => void
  dropStaleSelection: (revision: number) => void
  setSplitIncludeText: (splitIncludeText: boolean) => void
  setAdjustPreview: (values: Record<string, number> | null) => void
  setLayerPreview: (preview: LayerPreview | null) => void
}

function fitCrop(document: LayerDocument, ratio: CropRatio): CropRect {
  if (ratio === 'free') {
    const inset = 0.08
    return {
      x: document.width * inset,
      y: document.height * inset,
      width: document.width * (1 - inset * 2),
      height: document.height * (1 - inset * 2),
    }
  }
  const [rw, rh] = ratio.split(':').map(Number)
  let width = document.width
  let height = (document.width * rh) / rw
  if (height > document.height) {
    height = document.height
    width = (document.height * rw) / rh
  }
  return {
    x: (document.width - width) / 2,
    y: (document.height - height) / 2,
    width,
    height,
  }
}

// 局部替换依赖当轮选区，一旦离开选择模式表单就没用了，留着只会挡住画布
const withoutReplace = (panel: Panel): Panel => (panel === 'replace' ? null : panel)

export const useEditorUi = create<EditorUi>((set) => ({
  selectedLayerId: null,
  cropOpen: false,
  cropRatio: 'free',
  cropRect: null,
  compareOpen: false,
  compareAt: 0.5,
  panel: null,
  selectMode: null,
  selection: null,
  splitIncludeText: false,
  adjustPreview: null,
  layerPreview: null,

  selectLayer: (selectedLayerId) =>
    set((state) => ({
      selectedLayerId,
      layerPreview: state.layerPreview?.id === selectedLayerId ? state.layerPreview : null,
    })),

  openCrop: (document, ratio = 'free') =>
    set((state) => ({
      cropOpen: true,
      compareOpen: false,
      selectMode: null,
      panel: withoutReplace(state.panel),
      cropRatio: ratio,
      cropRect: fitCrop(document, ratio),
    })),

  setCropRatio: (cropRatio, document) => set({ cropRatio, cropRect: fitCrop(document, cropRatio) }),

  setCropRect: (cropRect) => set({ cropRect }),

  closeCrop: () => set({ cropOpen: false, cropRect: null }),

  setCompareOpen: (compareOpen) =>
    set((state) => ({
      compareOpen,
      cropOpen: compareOpen ? false : state.cropOpen,
      selectMode: compareOpen ? null : state.selectMode,
      panel: compareOpen ? withoutReplace(state.panel) : state.panel,
    })),

  setCompareAt: (compareAt) => set({ compareAt }),

  setPanel: (panel) => set({ panel, adjustPreview: null, layerPreview: null }),

  setSelectMode: (selectMode) =>
    set((state) => ({
      selectMode,
      cropOpen: false,
      compareOpen: false,
      cropRect: selectMode ? null : state.cropRect,
      panel: selectMode ? null : withoutReplace(state.panel),
    })),

  setSelection: (selection) => set({ selection }),

  dropStaleSelection: (revision) =>
    set((state) =>
      state.selection && state.selection.revision !== revision ? { selection: null } : state,
    ),

  setSplitIncludeText: (splitIncludeText) => set({ splitIncludeText }),

  setAdjustPreview: (adjustPreview) => set({ adjustPreview }),

  setLayerPreview: (layerPreview) =>
    set((state) => {
      if (layerPreview == null) return { layerPreview: null }
      const prev = state.layerPreview
      if (prev && prev.id === layerPreview.id) {
        return { layerPreview: { ...prev, ...layerPreview } }
      }
      return { layerPreview }
    }),
}))
