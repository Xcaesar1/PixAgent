import { useState } from 'react'
import { Link, NavLink } from 'react-router-dom'

import AgentConversation from '@/components/editor/AgentConversation'
import MessageComposer from '@/components/editor/MessageComposer'
import Button from '@/components/ui/Button'
import { buttonClass } from '@/components/ui/buttonStyles'
import { useSendMessage, useTurns } from '@/hooks/useAgent'
import { errorMessage } from '@/hooks/useAuth'
import { useSessions } from '@/hooks/useSessions'
import { formatDateTime } from '@/lib/format'

export default function SessionSidebar({ activeId }: { activeId: string }) {
  // 历史对话默认收起，尽量把纵向空间留给当前对话
  const [historyOpen, setHistoryOpen] = useState(false)

  return (
    <aside className="border-line bg-paper flex w-72 shrink-0 flex-col border-r">
      <div className="border-line flex items-center gap-2 border-b p-3">
        <Link
          to="/create"
          className={`${buttonClass({ variant: 'outline' })} flex-1 py-2 text-center text-sm`}
        >
          新对话
        </Link>
        <Button
          active={historyOpen}
          className="px-3 py-2"
          onClick={() => setHistoryOpen((open) => !open)}
        >
          历史
        </Button>
      </div>

      {historyOpen && <SessionList activeId={activeId} />}

      {activeId ? (
        <Conversation sessionId={activeId} />
      ) : (
        <p className="text-faint min-h-0 flex-1 px-4 py-4 text-xs leading-relaxed">
          打开一个历史对话，或回到创作页开始新的一张。
        </p>
      )}
    </aside>
  )
}

function Conversation({ sessionId }: { sessionId: string }) {
  const send = useSendMessage(sessionId)
  const { data: turns = [] } = useTurns(sessionId)
  const planActive = turns.some((turn) => turn.status === 'queued' || turn.status === 'running')

  return (
    <>
      <AgentConversation sessionId={sessionId} />
      <MessageComposer
        pending={send.isPending || planActive}
        error={send.isError ? errorMessage(send.error) : null}
        placeholder={
          planActive
            ? '当前计划进行中，确认、取消或等它结束后再发'
            : '说明要怎么改，例如：去背景再水平翻转。回车发送'
        }
        onSend={(text) => send.mutate(text)}
      />
    </>
  )
}

function SessionList({ activeId }: { activeId: string }) {
  const { data: sessions = [], isPending } = useSessions()

  if (isPending) {
    return <p className="text-faint border-line border-b px-4 py-3 text-xs">加载中…</p>
  }

  if (sessions.length === 0) {
    return <p className="text-faint border-line border-b px-4 py-3 text-xs">还没有会话</p>
  }

  return (
    <ul className="border-line scrollbar-slim animate-fade-in max-h-52 shrink-0 space-y-0.5 overflow-y-auto border-b p-2">
      {sessions.map((session) => (
        <li key={session.id}>
          <NavLink
            to={`/editor/${session.id}`}
            className={`rounded-chip block px-2.5 py-2 transition-colors duration-150 ${
              session.id === activeId
                ? 'bg-brand-soft text-brand-strong'
                : 'text-muted hover:bg-soft hover:text-ink'
            }`}
          >
            <span className="block truncate text-xs font-medium">{session.title}</span>
            <span className="text-faint block text-[10px] tabular-nums">
              {formatDateTime(session.updated_at)}
            </span>
          </NavLink>
        </li>
      ))}
    </ul>
  )
}
