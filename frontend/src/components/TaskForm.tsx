import { useState } from 'react'
import type { FormEvent } from 'react'
import { useAiSuggest } from '../hooks/useAiSuggest'
import type { Priority, Suggestion } from '../types'
import { AiSuggestButton, AiSuggestReason, AiSuggestStatus } from './AiSuggestControls'
import PriorityDueFields from './PriorityDueFields'

interface Props {
  onCreate: (
    title: string,
    description: string,
    priority: Priority,
    dueDate: string | null,
  ) => Promise<void>
}

export default function TaskForm({ onCreate }: Props) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState<Priority>('NORMAL')
  const [dueDate, setDueDate] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const ai = useAiSuggest((s: Suggestion) => {
    setPriority(s.priority)
    setDueDate(s.due_date ?? '')
  })

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!title.trim()) {
      setError('제목을 입력해 주세요.')
      return
    }
    setError(null)
    setSaving(true)
    try {
      await onCreate(title, description, priority, dueDate || null)
      setTitle('')
      setDescription('')
      setPriority('NORMAL')
      setDueDate('')
      ai.reset()
    } catch (err) {
      setError(err instanceof Error ? err.message : '저장하지 못했습니다.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="task-form" onSubmit={submit}>
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="제목 (필수)"
        aria-label="제목"
      />
      <div className="ai-row">
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="설명 (선택)"
          aria-label="설명"
          rows={2}
        />
        <AiSuggestButton pending={ai.pending} onClick={() => ai.suggest(title, description)} />
      </div>
      <AiSuggestStatus pending={ai.pending} message={ai.message} />
      <PriorityDueFields
        priority={priority}
        dueDate={dueDate}
        disabled={saving}
        onPriorityChange={setPriority}
        onDueDateChange={setDueDate}
      />
      <AiSuggestReason reason={ai.reason} />
      {error && <p className="error" role="alert">{error}</p>}
      <button type="submit" disabled={saving}>저장</button>
    </form>
  )
}
