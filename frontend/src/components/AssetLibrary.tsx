import { useState } from 'react'

import type { LibraryGroup } from '@/api/assets'
import AssetCard from '@/components/AssetCard'
import { formatDateTime } from '@/lib/format'

export default function AssetLibrary({
  groups,
  onOpenSession,
  onOpenAsset,
}: {
  groups: LibraryGroup[]
  onOpenSession: (sessionId: string) => void
  onOpenAsset: (assetId: string) => void
}) {
  return (
    <ul className="space-y-3">
      {groups.map((group) => (
        <LibraryGroupCard
          key={group.session_id ?? 'orphan'}
          group={group}
          onOpenSession={onOpenSession}
          onOpenAsset={onOpenAsset}
        />
      ))}
    </ul>
  )
}

function LibraryGroupCard({
  group,
  onOpenSession,
  onOpenAsset,
}: {
  group: LibraryGroup
  onOpenSession: (sessionId: string) => void
  onOpenAsset: (assetId: string) => void
}) {
  const [open, setOpen] = useState(false)
  const openGroup = () => {
    if (group.session_id) onOpenSession(group.session_id)
    else onOpenAsset(group.cover.id)
  }

  return (
    <li className="border-line bg-paper overflow-hidden rounded-[18px] border">
      <div className="flex items-stretch">
        <button
          type="button"
          onClick={openGroup}
          className="flex min-w-0 flex-1 items-center gap-3 px-3 py-2.5 text-left"
        >
          <span className="bg-canvas border-line size-14 shrink-0 overflow-hidden rounded-[10px] border">
            <img src={group.cover.url} alt="" className="size-full object-cover" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="text-ink block truncate text-sm font-medium">{group.title}</span>
            <span className="text-faint block text-[11px] tabular-nums">
              {group.assets.length} 张 · {formatDateTime(group.updated_at)}
            </span>
          </span>
        </button>
        {group.assets.length > 1 && (
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            className="text-muted hover:text-ink hover:bg-soft px-3 text-xs font-medium"
          >
            {open ? '收起' : '展开'}
          </button>
        )}
      </div>
      {open && (
        <div className="border-line grid grid-cols-2 gap-3 border-t p-3 sm:grid-cols-3 lg:grid-cols-4">
          {group.assets.map((asset) => (
            <AssetCard
              key={asset.id}
              asset={asset}
              onSelect={() =>
                group.session_id ? onOpenSession(group.session_id) : onOpenAsset(asset.id)
              }
            />
          ))}
        </div>
      )}
    </li>
  )
}
