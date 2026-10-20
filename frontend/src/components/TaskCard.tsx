import { useState } from 'react'
import type { Status, Task } from '../types'
import { STATUS_LABEL } from '../types'

interface Props {
  task: Task
  onChangeStatus: (id: number, status: Status) => Promise<void>
}

const STATUSES = Object.keys(STATUS_LABEL) as Status[]

export default function TaskCard({ task, onChangeStatus }: Props) {
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleStatus(status: Status) {
    setError(null)
    setBusy(true)
    try {
      await onChangeStatus(task.id, status)
    } catch (err) {
      setError(err instanceof Error ? err.message : '상태를 바꾸지 못했습니다.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <li className="task-card">
      <div className="task-head">
        <strong>{task.title}</strong>
        <select
          className={`badge badge-${task.status}`}
          value={task.status}
          disabled={busy}
          aria-label="상태"
          onChange={(e) => handleStatus(e.target.value as Status)}
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>{STATUS_LABEL[s]}</option>
          ))}
        </select>
      </div>
      {task.description && <p className="task-desc">{task.description}</p>}
      {error && <p className="error" role="alert">{error}</p>}
    </li>
  )
}
