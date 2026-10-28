import { useState } from 'react'
import type { FormEvent } from 'react'
import { useAiOptions } from '../hooks/useAiOptions'
import { useAiSuggest } from '../hooks/useAiSuggest'
import type { Priority, Suggestion, TaskOption } from '../types'
import AiOptionsPanel from './AiOptionsPanel'
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
  const options = useAiOptions()
  const aiBusy = ai.pending || options.pending

  // 후보 하나를 고르면 칸만 채운다. 저장은 사용자가 [저장] 을 눌러야 한다.
  function pick(item: TaskOption) {
    setDescription(item.description)
    setPriority(item.priority)
    setDueDate(item.due_date ?? '')
    options.reset()
    ai.reset()
  }

  // [모두 등록]: 지금 있는 등록 기능(onCreate)으로 후보를 차례로 저장한다.
  // 중간에 실패하면 멈추고, 저장된 후보는 목록에서 빼고 나머지를 남긴다.
  async function registerAll() {
    const todo = [...options.items]
    setError(null)
    options.setMessage(null)
    setSaving(true)
    let done = 0
    try {
      for (const item of todo) {
        await onCreate(item.title, item.description, item.priority, item.due_date)
        done++
      }
      options.reset()
      ai.reset()
      setTitle('')
      setDescription('')
      setPriority('NORMAL')
      setDueDate('')
    } catch (err) {
      options.setItems(todo.slice(done))
      const why = err instanceof Error ? err.message : '저장하지 못했습니다.'
      setError(`${done}개를 등록했고 나머지는 등록하지 못했습니다. ${why}`)
    } finally {
      setSaving(false)
    }
  }

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
      options.reset()
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
        <div className="ai-buttons">
          <AiSuggestButton
            pending={ai.pending}
            disabled={options.pending}
            onClick={() => ai.suggest(title, description)}
          />
          <AiSuggestButton
            label="AI 로 할 일 만들기"
            pending={options.pending}
            disabled={ai.pending}
            onClick={() => options.generate(title)}
          />
        </div>
      </div>
      <AiSuggestStatus pending={aiBusy} message={ai.message ?? options.message} />
      <AiOptionsPanel
        items={options.items}
        disabled={saving}
        onPick={pick}
        onRegisterAll={registerAll}
        onCancel={options.reset}
      />
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
