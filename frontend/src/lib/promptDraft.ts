const KEY = 'retouch:prompt-draft'

/**
 * 落地页写入并回填的需求草稿，只活在当前标签页。
 */
export function savePromptDraft(text: string): void {
  const value = text.trim()
  try {
    if (value) sessionStorage.setItem(KEY, value)
    else sessionStorage.removeItem(KEY)
  } catch {
    // 隐私模式下 sessionStorage 不可写，草稿丢失不影响主流程
  }
}

export function readPromptDraft(): string {
  try {
    return sessionStorage.getItem(KEY) ?? ''
  } catch {
    return ''
  }
}
