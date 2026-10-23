import { useCallback, useEffect, useState } from 'react'
import {
  ApiError,
  changeStatus,
  createTask,
  deleteTask,
  getMe,
  listTasks,
  login,
  logout,
  signup,
  updateContent,
} from './api'
import AuthForm from './components/AuthForm'
import StatusMessage from './components/StatusMessage'
import TaskCard from './components/TaskCard'
import TaskForm from './components/TaskForm'
import { STATUS_LABEL } from './types'
import type { Status, Task, User } from './types'

type LoadState = 'loading' | 'ready' | 'error'
// checking: 로그인 여부를 아직 모른다 / out: 로그인 화면 / in: 보드
type AuthState = 'checking' | 'out' | 'in'

const SECTIONS: Status[] = ['TODO', 'IN_PROGRESS', 'DONE']
const EXPIRED = '로그인이 만료되었습니다. 다시 로그인해 주세요.'

function App() {
  const [authState, setAuthState] = useState<AuthState>('checking')
  const [user, setUser] = useState<User | null>(null)
  const [authNotice, setAuthNotice] = useState<string | null>(null)
  const [authError, setAuthError] = useState('')
  const [tasks, setTasks] = useState<Task[]>([])
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [loadError, setLoadError] = useState('')
  const [notice, setNotice] = useState<string | null>(null)

  // 401 이면 보드를 닫고 로그인 화면으로 보낸다. 처리했으면 true.
  const handleUnauthorized = useCallback((err: unknown): boolean => {
    if (err instanceof ApiError && err.unauthorized) {
      setUser(null)
      setTasks([])
      setAuthNotice(EXPIRED)
      setAuthState('out')
      return true
    }
    return false
  }, [])

  const fetchTasks = useCallback(() => {
    return listTasks().then(
      (list) => {
        setTasks(list)
        setLoadState('ready')
      },
      (err) => {
        if (handleUnauthorized(err)) return
        setLoadError(err instanceof Error ? err.message : '카드를 불러오지 못했습니다.')
        setLoadState('error')
      },
    )
  }, [handleUnauthorized])

  // 다시 불러오기: 불러오는 중 표시로 바꾼 뒤 조회한다. 첫 조회는 초기 상태가 이미 loading 이다.
  const load = useCallback(async () => {
    setLoadState('loading')
    await fetchTasks()
  }, [fetchTasks])

  // 화면이 열릴 때 로그인 여부를 확인한다.
  useEffect(() => {
    getMe().then(
      (me) => {
        setUser(me)
        setAuthState('in')
      },
      (err) => {
        if (!(err instanceof ApiError && err.unauthorized)) {
          setAuthError(err instanceof Error ? err.message : '로그인 상태를 확인하지 못했습니다.')
        }
        setAuthState('out')
      },
    )
  }, [])

  // 로그인된 동안 보드를 불러온다.
  useEffect(() => {
    if (authState === 'in') fetchTasks()
  }, [authState, fetchTasks])

  async function handleLogin(username: string, password: string) {
    const me = await login(username, password)
    setAuthNotice(null)
    setAuthError('')
    setNotice(null)
    setLoadState('loading')
    setUser(me)
    setAuthState('in')
  }

  async function handleSignup(username: string, password: string) {
    await signup(username, password)
  }

  async function handleLogout() {
    try {
      await logout()
    } catch (err) {
      // 로그아웃이 실패하면 로그아웃된 것처럼 보이지 않게 보드에 안내를 남긴다.
      if (!handleUnauthorized(err)) {
        setNotice(err instanceof Error ? err.message : '로그아웃하지 못했습니다.')
      }
      return
    }
    setUser(null)
    setTasks([])
    setAuthNotice(null)
    setAuthState('out')
  }

  // 대상 카드가 이미 없으면 최신 목록을 다시 불러오고 알린다. 그 밖의 실패는 호출한 곳이 안내한다.
  async function guard<T>(action: () => Promise<T>): Promise<T | undefined> {
    setNotice(null)
    try {
      return await action()
    } catch (err) {
      if (handleUnauthorized(err)) return undefined
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
    try {
      const created = await createTask(title, description)
      setTasks((prev) => [...prev, created])
    } catch (err) {
      handleUnauthorized(err)
      throw err
    }
  }

  async function handleChangeStatus(id: number, status: Status) {
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

  if (authState === 'checking') {
    return (
      <main>
        <h1>task-flow</h1>
        <StatusMessage kind="loading" message="불러오는 중입니다…" />
      </main>
    )
  }

  if (authState === 'out') {
    return (
      <main>
        <h1>task-flow</h1>
        {authError && <StatusMessage kind="error" message={authError} />}
        <AuthForm onLogin={handleLogin} onSignup={handleSignup} notice={authNotice} />
      </main>
    )
  }

  return (
    <main>
      <header className="app-header">
        <h1>task-flow</h1>
        <div className="user-bar">
          <span>{user?.username}</span>
          <button type="button" onClick={handleLogout}>로그아웃</button>
        </div>
      </header>
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
