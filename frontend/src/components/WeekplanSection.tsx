import { useMemo } from 'react'
import { MSG_FAILED, useWeekplan } from '../hooks/useWeekplan'
import type { Task } from '../types'
import WeekplanCard from './WeekplanCard'
import type { WeekRow } from './WeekplanCard'
import './WeekplanSection.css'

interface Props {
  tasks: Task[]
  onUnauthorized: (err: unknown) => boolean
}

// [오늘 브리핑] 아래의 [이번 주 계획] 버튼과 요일별 표. 보드는 건드리지 않는다.
export default function WeekplanSection({ tasks, onUnauthorized }: Props) {
  const { pending, message, plan, generate, close } = useWeekplan(onUnauthorized)
  // 제목은 보드 목록에서 id 로 찾는다. 보드에 없는 id 는 건너뛰고, 비는 날은 줄을 만들지 않는다.
  const rows = useMemo<WeekRow[]>(() => {
    if (!plan) return []
    const titles = new Map(tasks.map((t) => [t.id, t.title]))
    return plan.days
      .map((d) => ({
        date: d.date,
        titles: d.ids.flatMap((id) => (titles.has(id) ? [titles.get(id) as string] : [])),
      }))
      .filter((r) => r.titles.length > 0)
  }, [plan, tasks])

  return (
    <div className="weekplan">
      <button type="button" disabled={pending} onClick={generate}>
        {pending ? '나누는 중…' : '이번 주 계획'}
      </button>
      {message && <p className="error weekplan-message" role="alert">{message}</p>}
      {plan && rows.length === 0 && (
        <p className="error weekplan-message" role="alert">{MSG_FAILED}</p>
      )}
      {plan && rows.length > 0 && <WeekplanCard plan={plan} rows={rows} onClose={close} />}
    </div>
  )
}
