import type { Briefing, Priority, Status, Suggestion, Task, TaskOption, User, Weekplan } from './types'

const API = 'http://localhost:8000/api'
const BASE = `${API}/tasks`

export class ApiError extends Error {
  status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.status = status
  }

  get notFound(): boolean {
    return this.status === 404
  }

  get unauthorized(): boolean {
    return this.status === 401
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    // 5173 에서 8000 으로 세션 쿠키를 함께 보낸다.
    res = await fetch(url, { ...init, credentials: 'include' })
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

export function signup(username: string, password: string): Promise<User> {
  return request<User>(`${API}/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
}

export function login(username: string, password: string): Promise<User> {
  return request<User>(`${API}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
}

export function logout(): Promise<void> {
  return request<void>(`${API}/auth/logout`, { method: 'POST' })
}

export function getMe(): Promise<User> {
  return request<User>(`${API}/auth/me`)
}

export function listTasks(): Promise<Task[]> {
  return request<Task[]>(BASE)
}

export function createTask(
  title: string,
  description: string,
  priority: Priority,
  dueDate: string | null,
): Promise<Task> {
  return request<Task>(BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, description, priority, due_date: dueDate }),
  })
}

export function changeStatus(id: number, status: Status): Promise<Task> {
  return request<Task>(`${BASE}/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  })
}

// dueDate 가 null 이면 마감일을 지운다.
export function updateContent(
  id: number,
  title: string,
  description: string,
  priority: Priority,
  dueDate: string | null,
): Promise<Task> {
  return request<Task>(`${BASE}/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, description, priority, due_date: dueDate }),
  })
}

export function deleteTask(id: number): Promise<void> {
  return request<void>(`${BASE}/${id}`, { method: 'DELETE' })
}

// 제안만 받는다. 서버는 저장하지 않으므로 저장은 사용자가 따로 한다.
export function suggestTask(title: string, description: string): Promise<Suggestion> {
  return request<Suggestion>(`${BASE}/suggest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, description }),
  })
}

// 주제(제목) 한 줄로 할 일 후보 3~5개를 받는다. 서버는 저장하지 않는다.
export async function suggestOptions(title: string): Promise<TaskOption[]> {
  const res = await request<{ items: TaskOption[] }>(`${BASE}/suggest-options`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
  return res.items
}

// 끝나지 않은 할 일은 서버가 DB 에서 모은다. 본문은 없고 저장도 하지 않는다.
export function getBriefing(): Promise<Briefing> {
  return request<Briefing>(`${BASE}/briefing`, { method: 'POST' })
}

// 끝나지 않은 할 일을 오늘부터 7일에 나눈 계획. 본문은 없고 저장도 하지 않는다.
export function getWeekplan(): Promise<Weekplan> {
  return request<Weekplan>(`${BASE}/weekplan`, { method: 'POST' })
}
