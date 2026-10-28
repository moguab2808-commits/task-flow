interface ButtonProps {
  pending: boolean
  onClick: () => void
}

// 기다리는 동안 이 버튼만 잠근다. 저장 버튼과 입력 칸은 그대로 쓸 수 있다.
export function AiSuggestButton({ pending, onClick }: ButtonProps) {
  return (
    <button type="button" className="ai-button" disabled={pending} onClick={onClick}>
      AI 제안
    </button>
  )
}

interface StatusProps {
  pending: boolean
  message: string | null
}

export function AiSuggestStatus({ pending, message }: StatusProps) {
  if (pending) return <p className="ai-status" role="status">제안을 받는 중..</p>
  if (message) return <p className="error" role="alert">{message}</p>
  return null
}

export function AiSuggestReason({ reason }: { reason: string | null }) {
  if (!reason) return null
  return <p className="ai-reason">{reason}</p>
}
