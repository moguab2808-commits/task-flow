import type { Task } from '../types'
import { STATUS_LABEL } from '../types'

export default function TaskCard({ task }: { task: Task }) {
  return (
    <li className="task-card">
      <div className="task-head">
        <strong>{task.title}</strong>
        <span className={`badge badge-${task.status}`}>{STATUS_LABEL[task.status]}</span>
      </div>
      {task.description && <p className="task-desc">{task.description}</p>}
    </li>
  )
}
