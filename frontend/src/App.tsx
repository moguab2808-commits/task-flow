import { useEffect, useState } from 'react'

type Status = 'checking' | 'ok' | 'failed'

function App() {
  const [status, setStatus] = useState<Status>('checking')

  useEffect(() => {
    fetch('/api/health')
      .then((res) => setStatus(res.ok ? 'ok' : 'failed'))
      .catch(() => setStatus('failed'))
  }, [])

  return (
    <main>
      <h1>task-flow</h1>
      <p>
        API 연결:{' '}
        {status === 'checking' && '확인 중'}
        {status === 'ok' && '연결됨'}
        {status === 'failed' && '연결 실패 (API 서버가 켜져 있는지 확인하세요)'}
      </p>
    </main>
  )
}

export default App
