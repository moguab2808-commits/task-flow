interface Props {
  kind: 'loading' | 'empty' | 'error' | 'notice'
  message: string
  onRetry?: () => void
}

export default function StatusMessage({ kind, message, onRetry }: Props) {
  return (
    <div className={`status-message status-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      <p>{message}</p>
      {onRetry && (
        <button type="button" onClick={onRetry}>
          다시 불러오기
        </button>
      )}
    </div>
  )
}
