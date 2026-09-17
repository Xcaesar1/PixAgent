export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// pydantic 会给自定义校验加这个前缀，对用户没有意义
const VALUE_ERROR = /^Value error,\s*/

function messageOf(item: unknown): string {
  if (typeof item === 'string') return item.trim()
  if (!item || typeof item !== 'object') return ''
  const { msg, message } = item as { msg?: unknown; message?: unknown }
  return messageOf(msg ?? message).replace(VALUE_ERROR, '')
}

/** FastAPI 校验失败时 detail 是 `{loc, msg, type}` 数组，原样当字符串会渲染成 [object Object]。 */
function formatDetail(detail: unknown, fallback: string): string {
  if (Array.isArray(detail)) {
    return detail.map(messageOf).filter(Boolean).join('；') || fallback
  }
  return messageOf(detail) || fallback
}

/** 上传与下载走原生 fetch，错误一律经这里构造，文案格式与 JSON 请求保持一致。 */
export async function apiError(response: Response, fallback: string): Promise<ApiError> {
  const body = await response.json().catch(() => null)
  return new ApiError(response.status, formatDetail(body?.detail, fallback))
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })

  if (!response.ok) throw await apiError(response, response.statusText)
  return response.status === 204 ? (undefined as T) : response.json()
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: body === undefined ? undefined : JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
