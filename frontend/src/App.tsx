import { useCallback, useEffect, useState } from 'react'
import { ApiError, changeStatus, createTask, deleteTask, listTasks, updateContent } from './api'
import StatusMessage from './components/StatusMessage'
import TaskCard from './components/TaskCard'
import TaskForm from './components/TaskForm'
import { STATUS_LABEL } from './types'
import type { Status, Task } from './types'

type LoadState = 'loading' | 'ready' | 'error'

const SECTIONS: Status[] = ['TODO', 'IN_PROGRESS', 'DONE']

function App() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [loadError, setLoadError] = useState('')
  const [notice, setNotice] = useState<string | null>(null)

  const fetchTasks = useCallback(() => {
    return listTasks().then(
      (list) => {
        setTasks(list)
        setLoadState('ready')
      },
      (err) => {
        setLoadError(err instanceof Error ? err.message : '카드를 불러오지 못했습니다.')
        setLoadState('error')
      },
    )
  }, [])

  // 다시 불러오기: 불러오는 중 표시로 바꾼 뒤 조회한다. 첫 조회는 초기 상태가 이미 loading 이다.
  const load = useCallback(async () => {
    setLoadState('loading')
    await fetchTasks()
  }, [fetchTasks])

  useEffect(() => {
    fetchTasks()
  }, [fetchTasks])

  // 대상 카드가 이미 없으면 최신 목록을 다시 불러오고 알린다. 그 밖의 실패는 호출한 곳이 안내한다.
  async function guard<T>(action: () => Promise<T>): Promise<T | undefined> {
    setNotice(null)
    try {
      return await action()
    } catch (err) {
      if (err instanceof ApiError && err.notFound) {
        await load()
        setNotice('이미 없는 카드입니다. 최신 목록을 다시 불러왔습니다.')
        return undefined
      }
      throw err
    }
  }

  async function handleCreate(title: string, description: string) {
    setNotice(null)
    const created = await createTask(title, description)
    setTasks((prev) => [...prev, created])
  }

  async function handleChangeStatus(id: number, status: Status) {
    setTasks((prev) => prev.map((t) => (t.id === id ? { ...t, status } : t)))
    const updated = await guard(() => changeStatus(id, status))
    if (updated) setTasks((prev) => prev.map((t) => (t.id === id ? updated : t)))
  }

  async function handleEdit(id: number, title: string, description: string) {
    const updated = await guard(() => updateContent(id, title, description))
    if (updated) setTasks((prev) => prev.map((t) => (t.id === id ? updated : t)))
  }

  async function handleDelete(id: number) {
    const done = await guard(async () => {
      await deleteTask(id)
      return true
    })
    if (done) setTasks((prev) => prev.filter((t) => t.id !== id))
  }

  return (
    <main>
      <h1>task-flow</h1>
      <TaskForm onCreate={handleCreate} />
      {notice && <StatusMessage kind="notice" message={notice} />}
      {loadState === 'loading' && <StatusMessage kind="loading" message="불러오는 중입니다…" />}
      {loadState === 'error' && (
        <StatusMessage kind="error" message={loadError} onRetry={load} />
      )}
      {loadState === 'ready' && tasks.length === 0 && (
        <StatusMessage kind="empty" message="아직 카드가 없습니다. 위에서 첫 카드를 만들어 보세요." />
      )}
      {loadState === 'ready' && tasks.length > 0 && (
        <div className="sections">
          {SECTIONS.map((status) => {
            const items = tasks.filter((t) => t.status === status)
            return (
              <section key={status} className="section" aria-label={STATUS_LABEL[status]}>
                <h2>
                  {STATUS_LABEL[status]} <span className="count">{items.length}</span>
                </h2>
                {items.length === 0 ? (
                  <p className="section-empty">카드가 없습니다.</p>
                ) : (
                  <ul className="task-list">
                    {items.map((t) => (
                      <TaskCard
                        key={t.id}
                        task={t}
                        onChangeStatus={handleChangeStatus}
                        onEdit={handleEdit}
                        onDelete={handleDelete}
                      />
                    ))}
                  </ul>
                )}
              </section>
            )
          })}
        </div>
      )}
    </main>
  )
}

export default App
