import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, changeStatus, createTask, sendCommand, updateContent } from '../api'
import { PRIORITY_LABEL } from '../types'
import type { CommandAction, Task } from '../types'
import './CommandSection.css'

export const MSG_UNAVAILABLE = '지금은 시킬 수 없습니다'
export const MSG_FAILED = '알아듣지 못했습니다'
const MSG_GONE = '이미 없는 카드입니다.'
const MAX_LENGTH = 200

interface Props {
  tasks: Task[]
  onUnauthorized: (err: unknown) => boolean
  // 적용이 끝난 뒤 서버가 정한 순서의 목록을 다시 받는다.
  onApplied: () => Promise<void>
}

interface Line {
  action: CommandAction
  // due · done 의 대상 카드. add 는 없다.
  task?: Task
  label: string
}

function describe(action: CommandAction, task?: Task): string {
  if (action.kind === 'done') return `${task?.title} — 완료로`
  if (action.kind === 'due') {
    return `${task?.title}(지금 마감 ${task?.due_date ?? '없음'}) — 마감을 ${action.due_date}(으)로`
  }
  const priority = PRIORITY_LABEL[action.priority ?? 'NORMAL']
  const due = action.due_date ? ` · 마감 ${action.due_date}` : ''
  return `${action.title} — 새 카드로 (우선순위 ${priority}${due})`
}

// 동작 하나를 기존 API 한 번으로 적용한다.
async function run({ action, task }: Line): Promise<void> {
  if (action.kind === 'add') {
    await createTask(action.title ?? '', '', action.priority ?? 'NORMAL', action.due_date)
  } else if (action.kind === 'done') {
    await changeStatus(action.id ?? 0, 'DONE')
  } else if (task) {
    // 마감일만 바꾸고 나머지는 보드의 지금 값을 그대로 보낸다.
    await updateContent(task.id, task.title, task.description, task.priority, action.due_date)
  }
}

// 브리핑 아래 · 보드 위의 [시키기] 입력란과 확인 카드. 서버는 제안만 하고, 적용은 여기서 한다.
export default function CommandSection({ tasks, onUnauthorized, onApplied }: Props) {
  const [text, setText] = useState('')
  const [pending, setPending] = useState(false)
  const [applying, setApplying] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [ask, setAsk] = useState<string | null>(null)
  const [actions, setActions] = useState<CommandAction[] | null>(null)
  // 적용에 실패한 동작의 이유. actions 와 같은 순서다.
  const [reasons, setReasons] = useState<string[]>([])
  const [applied, setApplied] = useState<string | null>(null)
  const generation = useRef(0)

  // 보드가 닫히면(로그아웃 등) 진행 중이던 요청의 결과는 버린다.
  useEffect(() => {
    const counter = generation
    return () => {
      counter.current++
    }
  }, [])

  // 받은 뒤 보드에서 사라진 카드를 가리키는 동작은 카드에서 뺀다.
  const lines = useMemo<Line[]>(() => {
    const byId = new Map(tasks.map((t) => [t.id, t]))
    const out: Line[] = []
    for (const action of actions ?? []) {
      const task = action.id === null ? undefined : byId.get(action.id)
      if (action.kind !== 'add' && !task) continue
      out.push({ action, task, label: describe(action, task) })
    }
    return out
  }, [actions, tasks])

  const failed = reasons.length > 0
  const busy = pending || applying

  function reset() {
    setMessage(null)
    setAsk(null)
    setActions(null)
    setReasons([])
    setApplied(null)
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    const sentence = text.trim()
    if (!sentence || busy) return
    const mine = ++generation.current
    reset()
    setPending(true)
    try {
      const result = await sendCommand(sentence)
      if (mine !== generation.current) return
      if (result.actions.length > 0) setActions(result.actions)
      else if (result.ask) setAsk(result.ask)
      else setMessage(MSG_FAILED)
    } catch (err) {
      if (mine !== generation.current) return
      if (onUnauthorized(err)) return
      if (err instanceof ApiError) {
        if (err.status === 503) setMessage(MSG_UNAVAILABLE)
        else if (err.status === 502) setMessage(MSG_FAILED)
        else setMessage(err.message)
      } else {
        setMessage(MSG_FAILED)
      }
    } finally {
      if (mine === generation.current) setPending(false)
    }
  }

  async function apply() {
    if (busy || lines.length === 0) return
    const mine = generation.current
    setApplying(true)
    const failedLines: Line[] = []
    const failedReasons: string[] = []
    for (const line of lines) {
      try {
        await run(line)
      } catch (err) {
        if (onUnauthorized(err)) return
        failedLines.push(line)
        failedReasons.push(
          err instanceof ApiError && err.notFound
            ? MSG_GONE
            : err instanceof Error
              ? err.message
              : '바꾸지 못했습니다.',
        )
      }
    }
    // 일부만 바뀌었어도 서버의 최신 목록을 받는다.
    await onApplied()
    if (mine !== generation.current) return
    setApplying(false)
    if (failedLines.length === 0) {
      setActions(null)
      setReasons([])
      setText('')
      setApplied(`${lines.length}개를 바꿨습니다.`)
    } else {
      setActions(failedLines.map((l) => l.action))
      setReasons(failedReasons)
    }
  }

  function cancel() {
    if (applying) return
    generation.current++
    setPending(false)
    reset()
  }

  const showCard = lines.length > 0

  return (
    <div className="command">
      <form className="command-form" onSubmit={submit}>
        <input
          type="text"
          value={text}
          maxLength={MAX_LENGTH}
          disabled={applying}
          aria-label="한 문장으로 시키기"
          placeholder="예: 보고서는 완료로 하고 내일까지 우유 사기 추가해줘"
          onChange={(e) => setText(e.target.value)}
        />
        <button type="submit" disabled={busy || !text.trim()}>
          {pending ? '알아듣는 중…' : '시키기'}
        </button>
      </form>
      {message && <p className="error command-message" role="alert">{message}</p>}
      {ask && <p className="command-ask" role="status">{ask}</p>}
      {applied && <p className="command-ask" role="status">{applied}</p>}
      {actions && !showCard && <p className="error command-message" role="alert">{MSG_FAILED}</p>}
      {showCard && (
        <div className="command-card">
          <h3>
            {failed ? `${lines.length}개를 바꾸지 못했습니다` : `이렇게 바꿀까요? ${lines.length}개`}
          </h3>
          <ul className="command-lines">
            {lines.map((line, i) => (
              <li key={i}>
                <span>{line.label}</span>
                {reasons[i] && <span className="error command-reason"> — {reasons[i]}</span>}
              </li>
            ))}
          </ul>
          <div className="command-buttons">
            <button type="button" disabled={applying} onClick={apply}>
              {applying ? '적용하는 중…' : failed ? '다시 적용' : '적용'}
            </button>
            <button type="button" disabled={applying} onClick={cancel}>취소</button>
          </div>
        </div>
      )}
    </div>
  )
}
