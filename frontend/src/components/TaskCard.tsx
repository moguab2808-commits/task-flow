import { useState } from 'react'
import type { FormEvent } from 'react'
import type { Status, Task } from '../types'
import { STATUS_LABEL } from '../types'

interface Props {
  task: Task
  onChangeStatus: (id: number, status: Status) => Promise<void>
  onEdit: (id: number, title: string, description: string) => Promise<void>
  onDelete: (id: number) => Promise<void>
}

const STATUSES = Object.keys(STATUS_LABEL) as Status[]

export default function TaskCard({ task, onChangeStatus, onEdit, onDelete }: Props) {
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(task.title)
  const [description, setDescription] = useState(task.description)

  async function run(action: () => Promise<void>, fallback: string): Promise<boolean> {
    setError(null)
    setBusy(true)
    try {
      await action()
      return true
    } catch (err) {
      setError(err instanceof Error ? err.message : fallback)
      return false
    } finally {
      setBusy(false)
    }
  }

  function startEdit() {
    setTitle(task.title)
    setDescription(task.description)
    setError(null)
    setEditing(true)
  }

  async function save(e: FormEvent) {
    e.preventDefault()
    if (!title.trim()) {
      setError('제목을 입력해 주세요.')
      return
    }
    if (await run(() => onEdit(task.id, title, description), '저장하지 못했습니다.')) {
      setEditing(false)
    }
  }

  async function remove() {
    if (!window.confirm('이 카드를 삭제할까요? 삭제하면 되돌릴 수 없습니다.')) return
    await run(() => onDelete(task.id), '삭제하지 못했습니다.')
  }

  if (editing) {
    return (
      <li className="task-card">
        <form className="task-form" onSubmit={save}>
          <input value={title} onChange={(e) => setTitle(e.target.value)} aria-label="제목" />
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            aria-label="설명"
            rows={2}
          />
          {error && <p className="error" role="alert">{error}</p>}
          <div className="task-actions">
            <button type="submit" disabled={busy}>저장</button>
            <button type="button" disabled={busy} onClick={() => setEditing(false)}>취소</button>
          </div>
        </form>
      </li>
    )
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
          onChange={(e) =>
            run(() => onChangeStatus(task.id, e.target.value as Status), '상태를 바꾸지 못했습니다.')
          }
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>{STATUS_LABEL[s]}</option>
          ))}
        </select>
      </div>
      {task.description && <p className="task-desc">{task.description}</p>}
      {error && <p className="error" role="alert">{error}</p>}
      <div className="task-actions">
        <button type="button" disabled={busy} onClick={startEdit}>수정</button>
        <button type="button" disabled={busy} onClick={remove}>삭제</button>
      </div>
    </li>
  )
}
