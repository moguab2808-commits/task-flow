import { PRIORITY_LABEL } from '../types'
import type { Priority } from '../types'

interface Props {
  priority: Priority
  dueDate: string
  disabled?: boolean
  onPriorityChange: (priority: Priority) => void
  onDueDateChange: (dueDate: string) => void
}

const PRIORITIES = Object.keys(PRIORITY_LABEL) as Priority[]

// 등록 폼과 수정 폼이 함께 쓰는 우선순위 · 마감일 입력. 마감일은 날짜만 받는다.
export default function PriorityDueFields({
  priority,
  dueDate,
  disabled,
  onPriorityChange,
  onDueDateChange,
}: Props) {
  return (
    <div className="task-fields">
      <label>
        우선순위
        <select
          value={priority}
          disabled={disabled}
          onChange={(e) => onPriorityChange(e.target.value as Priority)}
        >
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>{PRIORITY_LABEL[p]}</option>
          ))}
        </select>
      </label>
      <label>
        마감일
        <input
          type="date"
          value={dueDate}
          disabled={disabled}
          onChange={(e) => onDueDateChange(e.target.value)}
        />
      </label>
      {dueDate && (
        <button type="button" disabled={disabled} onClick={() => onDueDateChange('')}>
          마감일 지우기
        </button>
      )}
    </div>
  )
}
