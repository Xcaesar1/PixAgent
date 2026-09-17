import { api } from '@/api/client'

export type User = { id: string; username: string }
export type Credentials = { username: string; password: string }

export const authApi = {
  register: (body: Credentials) => api.post<User>('/auth/register', body),
  login: (body: Credentials) => api.post<User>('/auth/login', body),
  logout: () => api.post<void>('/auth/logout'),
  me: () => api.get<User>('/auth/me'),
}
