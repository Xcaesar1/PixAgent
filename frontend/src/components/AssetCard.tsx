import type { Asset } from '@/api/assets'
import { formatBytes, formatDateTime } from '@/lib/format'

export default function AssetCard({ asset, onSelect }: { asset: Asset; onSelect?: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      title="点击打开编辑"
      className="border-line bg-paper hover:border-brand group overflow-hidden rounded-[18px] border text-left transition-colors"
    >
      <div className="bg-canvas relative aspect-square">
        <img
          src={asset.url}
          alt=""
          loading="lazy"
          className="size-full object-contain transition-transform group-hover:scale-[1.02]"
        />
        {asset.has_alpha && (
          <span className="bg-ink/80 absolute top-2 left-2 rounded px-1.5 py-0.5 text-[10px] text-white">
            透明底
          </span>
        )}
      </div>

      <dl className="text-muted space-y-0.5 px-3 py-2.5 text-xs">
        <div className="text-ink font-medium">
          {asset.width} × {asset.height}
        </div>
        <div>
          {asset.image_format} · {formatBytes(asset.size_bytes)}
        </div>
        <div className="text-faint">{formatDateTime(asset.created_at)}</div>
      </dl>
    </button>
  )
}
