/** Base API client with typed fetch wrapper. */

const BASE_URL = ''

export interface ApiError {
  ok: false
  error: string
  errors?: Record<string, string>
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown
): Promise<T> {
  const url = `${BASE_URL}${path}`
  const headers: Record<string, string> = {}
  let options: RequestInit = { method }

  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    options = { ...options, body: JSON.stringify(body) }
  }

  if (Object.keys(headers).length > 0) {
    options = { ...options, headers }
  }

  const res = await fetch(url, options)

  if (!res.ok) {
    const data = (await res.json().catch(() => ({}))) as Record<string, unknown>
    const error = (data.error as string) || `Request failed with status ${res.status}`
    const apiError: ApiError = { ok: false, error }
    if (data.errors) {
      apiError.errors = data.errors as Record<string, string>
    }
    throw apiError
  }

  return res.json() as Promise<T>
}

export function get<T>(path: string): Promise<T> {
  return request<T>('GET', path)
}

export function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>('POST', path, body)
}

export function del<T>(path: string): Promise<T> {
  return request<T>('DELETE', path)
}
