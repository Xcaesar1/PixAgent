import BrandMark from '@/components/BrandMark'

export default function LandingFooter() {
  return (
    <footer className="border-line border-t">
      <div className="text-faint mx-auto flex max-w-5xl flex-col items-center justify-between gap-3 px-6 py-8 text-xs sm:flex-row">
        <BrandMark size="sm">
          <span className="text-muted font-medium">AI 修图智能体</span>
        </BrandMark>
        <p>为电商运营与内容创作者打造的商品物料工作台</p>
      </div>
    </footer>
  )
}
