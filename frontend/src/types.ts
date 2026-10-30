export type Status = 'TODO' | 'IN_PROGRESS' | 'DONE'
export type Priority = 'LOW' | 'NORMAL' | 'HIGH'

export interface Task {
  id: number
  title: string
  description: string
  status: Status
  created_at: string
  updated_at: string
  priority: Priority
  // YYYY-MM-DD. 마감일이 없으면 null
  due_date: string | null
  // 서버가 목록을 줄 때 계산한다. 화면이 따로 계산하지 않는다.
  is_overdue: boolean
}

export interface User {
  username: string
}

export const STATUS_LABEL: Record<Status, string> = {
  TODO: '할 일',
  IN_PROGRESS: '진행 중',
  DONE: '완료',
}

export const PRIORITY_LABEL: Record<Priority, string> = {
  LOW: '낮음',
  NORMAL: '보통',
  HIGH: '높음',
}

export interface Suggestion {
  priority: Priority
  // YYYY-MM-DD. 제안할 마감일이 없으면 null
  due_date: string | null
  reason: string
}

// AI 가 만든 할 일 후보. 저장 전의 값이다.
export interface TaskOption {
  title: string
  description: string
  priority: Priority
  // YYYY-MM-DD. 없으면 null
  due_date: string | null
}

// 오늘 브리핑. 서버가 보낸 적 있는 id 만 담아 준다. 제목은 보드 목록에서 id 로 찾는다.
export interface Briefing {
  top3: { id: number; reason: string }[]
  later: number[]
  cheer: string
}

// 이번 주 계획. 서버가 보낸 적 있는 id 만 담아 준다. 요일 · 제목은 화면이 만든다.
export interface Weekplan {
  days: { date: string; ids: number[] }[]
  note: string
}

// 한 문장으로 시키기의 동작 하나. 해당 없는 값은 null. add 는 id 가 null 이고 priority 가 항상 있다.
export interface CommandAction {
  kind: 'add' | 'due' | 'done'
  id: number | null
  title: string | null
  priority: Priority | null
  // YYYY-MM-DD. 없으면 null
  due_date: string | null
}

// 동작 제안. 동작이 하나도 없으면 ask 에 되묻는 한 문장이 있다. 서버는 저장하지 않는다.
export interface CommandResult {
  actions: CommandAction[]
  ask: string | null
}
