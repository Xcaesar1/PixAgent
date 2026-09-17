import { useState } from 'react'

import Button from '@/components/ui/Button'

export default function MessageComposer({
  pending,
  error,
  placeholder = '说明要怎么改，例如：去背景、水平翻转。回车发送',
  onSend,
}: {
  pending: boolean
  error?: string | null
  placeholder?: string
  onSend: (text: string) => void
}) {
  const [text, setText] = useState('')
  const canSend = text.trim().length > 0 && !pending

  const submit = () => {
    if (!canSend) return
    onSend(text.trim())
    setText('')
  }

  return (
    <div className="border-line shrink-0 border-t p-3">
      <textarea
        rows={2}
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault()
            submit()
          }
        }}
        placeholder={placeholder}
        aria-label="修图指令"
        className="border-line text-ink placeholder:text-faint rounded-control focus:border-line-strong w-full resize-none border px-3 py-2 text-xs leading-relaxed outline-none transition-colors"
      />
      <Button variant="solid" block className="mt-2 py-2" disabled={!canSend} onClick={submit}>
        {pending ? '思考中…' : '发送'}
      </Button>
      {error && <p className="text-danger mt-2 text-[11px] leading-relaxed">{error}</p>}
    </div>
  )
}
