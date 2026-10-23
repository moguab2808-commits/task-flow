import { useState } from 'react'
import type { FormEvent } from 'react'

interface Props {
  onLogin: (username: string, password: string) => Promise<void>
  onSignup: (username: string, password: string) => Promise<void>
  notice?: string | null
}

type Mode = 'login' | 'signup'

export default function AuthForm({ onLogin, onSignup, notice }: Props) {
  const [mode, setMode] = useState<Mode>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(notice ?? null)
  const [saving, setSaving] = useState(false)

  function switchMode(next: Mode) {
    setMode(next)
    setPassword('')
    setError(null)
    setInfo(null)
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!username.trim()) {
      setError('사용자 이름을 입력해 주세요.')
      return
    }
    if (!password) {
      setError('비밀번호를 입력해 주세요.')
      return
    }
    if (mode === 'signup' && password.length < 8) {
      setError('비밀번호는 8자 이상이어야 합니다.')
      return
    }
    setError(null)
    setInfo(null)
    setSaving(true)
    try {
      if (mode === 'login') {
        await onLogin(username, password)
      } else {
        await onSignup(username, password)
        // 가입 뒤에는 자동 로그인하지 않고, 사용자 이름을 남긴 채 비밀번호를 다시 입력받는다.
        setMode('login')
        setPassword('')
        setInfo('가입되었습니다. 로그인해 주세요.')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '요청에 실패했습니다.')
    } finally {
      setSaving(false)
    }
  }

  const isLogin = mode === 'login'

  return (
    <form className="task-form auth-form" onSubmit={submit}>
      <h2>{isLogin ? '로그인' : '회원가입'}</h2>
      <input
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        placeholder="사용자 이름"
        aria-label="사용자 이름"
        autoComplete="username"
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder={isLogin ? '비밀번호' : '비밀번호 (8자 이상)'}
        aria-label="비밀번호"
        autoComplete={isLogin ? 'current-password' : 'new-password'}
      />
      {info && <p className="auth-info" role="status">{info}</p>}
      {error && <p className="error" role="alert">{error}</p>}
      <button type="submit" disabled={saving}>{isLogin ? '로그인' : '가입'}</button>
      <button
        type="button"
        className="link-button"
        onClick={() => switchMode(isLogin ? 'signup' : 'login')}
        disabled={saving}
      >
        {isLogin ? '계정이 없나요? 회원가입' : '이미 계정이 있나요? 로그인'}
      </button>
    </form>
  )
}
