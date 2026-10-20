import type { Status, Task } from './types'

const BASE = 'http://localhost:8000/api/tasks'

export class ApiError extends Error {
  status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.status = status
  }

  get notFound(): boolean {
    return this.status === 404
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, init)
  } catch {
    throw new ApiError('API 서버에 연결하지 못했습니다. 서버가 켜져 있는지 확인해 주세요.')
  }
  if (!res.ok) {
    throw new ApiError(await errorMessage(res), res.status)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json()
    const first = Array.isArray(body.detail) ? body.detail[0]?.msg : body.detail
    if (typeof first === 'string') return first.replace(/^Value error, /, '')
  } catch {
    // 본문이 JSON 이 아니면 아래 기본 문구를 쓴다.
  }
  return `요청이 실패했습니다. (${res.status})`
}

export function listTasks(): Promise<Task[]> {
  return request<Task[]>(BASE)
}

export function createTask(title: string, description: string): Promise<Task> {
  return request<Task>(BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, description }),
  })
}

export function changeStatus(id: number, status: Status): Promise<Task> {
  return request<Task>(`${BASE}/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  })
}

export function updateContent(id: number, title: string, description: string): Promise<Task> {
  return request<Task>(`${BASE}/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, description }),
  })
}

export function deleteTask(id: number): Promise<void> {
  return request<void>(`${BASE}/${id}`, { method: 'DELETE' })
}
