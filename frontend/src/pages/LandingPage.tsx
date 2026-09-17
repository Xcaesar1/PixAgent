import { useNavigate } from 'react-router-dom'

import CapabilityShowcase from '@/components/landing/CapabilityShowcase'
import DeliverySteps from '@/components/landing/DeliverySteps'
import LandingFooter from '@/components/landing/LandingFooter'
import LandingHeader from '@/components/landing/LandingHeader'
import LandingHero from '@/components/landing/LandingHero'
import StartBanner from '@/components/landing/StartBanner'
import { useCurrentUser } from '@/hooks/useAuth'
import { readPromptDraft, savePromptDraft } from '@/lib/promptDraft'

export default function LandingPage() {
  const navigate = useNavigate()
  const { user } = useCurrentUser()

  // 未登录一律先去登录页，登录态直接进工作台
  const entry = user ? { label: '进入工作台', to: '/create' } : { label: '免费开始', to: '/auth' }

  const start = (prompt: string) => {
    savePromptDraft(prompt)
    navigate(entry.to)
  }

  return (
    <div className="flex min-h-screen flex-col">
      <LandingHeader account={user?.username ?? null} />

      <main className="flex-1">
        <LandingHero
          initialPrompt={readPromptDraft()}
          submitLabel={entry.label}
          onStart={start}
        />
        <CapabilityShowcase />
        <DeliverySteps />
        <StartBanner label={entry.label} to={entry.to} />
      </main>

      <LandingFooter />
    </div>
  )
}
