const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export { API_BASE_URL }

export async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem('medical-rag-token')
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(options?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options?.headers ?? {}),
    },
  })

  if (!response.ok) {
    let message = `请求失败：${response.status}`
    try {
      const payload = await response.json() as { detail?: string }
      if (payload.detail) message = payload.detail
    } catch {
      // ignore non-JSON error body
    }
    throw new Error(message)
  }

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}
