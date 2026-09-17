export type StrokePoint = { x: number; y: number }

export type SelectionEntry =
  | { kind: 'stroke'; points: StrokePoint[] }
  | { kind: 'point'; point: StrokePoint }

export function inputsOf(entries: SelectionEntry[]) {
  return {
    strokes: entries.filter((entry) => entry.kind === 'stroke').map((entry) => entry.points),
    points: entries.filter((entry) => entry.kind === 'point').map((entry) => entry.point),
  }
}

/** 选区不进画布历史，本地记每笔以便撤销 / 重做。 */
export function createSelectionHistory() {
  let past: SelectionEntry[][] = []
  let current: SelectionEntry[] = []
  let future: SelectionEntry[][] = []

  return {
    get current() {
      return current
    },
    canUndo() {
      return past.length > 0
    },
    canRedo() {
      return future.length > 0
    },
    commit(entry: SelectionEntry) {
      past = [...past, current]
      current = [...current, entry]
      future = []
    },
    undo() {
      if (!past.length) return null
      future = [...future, current]
      current = past.at(-1) ?? []
      past = past.slice(0, -1)
      return current
    },
    redo() {
      const next = future.at(-1)
      if (!next) return null
      past = [...past, current]
      current = next
      future = future.slice(0, -1)
      return current
    },
    clear() {
      if (!current.length) return false
      past = [...past, current]
      current = []
      future = []
      return true
    },
    reset() {
      past = []
      current = []
      future = []
    },
  }
}
