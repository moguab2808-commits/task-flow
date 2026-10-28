import { useCallback, useRef, useState } from 'react'
import { ApiError, suggestTask } from '../api'
import type { Suggestion } from '../types'

export const MSG_TITLE_REQUIRED = '제목을 입력해 주세요.'
export const MSG_UNAVAILABLE = '지금은 AI 제안을 쓸 수 없습니다. 직접 입력해 주세요.'
export const MSG_FAILED = '제안을 못 받았습니다. 다시 제안 버튼을 눌러 보세요.'

function failureMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 503) return MSG_UNAVAILABLE
    if (err.status === 502) return MSG_FAILED
    return err.message
  }
  return MSG_FAILED
}

// [AI 제안] 호출 상태. 저장은 하지 않고, 받은 값을 onApply 로 폼 칸에 채우기만 한다.
// reset() 은 저장 · 취소 때 부르며, 그 전에 보낸 요청의 늦은 응답은 버린다.
export function useAiSuggest(onApply: (suggestion: Suggestion) => void) {
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [reason, setReason] = useState<string | null>(null)
  const generation = useRef(0)

  const suggest = useCallback(
    async (title: string, description: string) => {
      if (!title.trim()) {
        setMessage(MSG_TITLE_REQUIRED)
        return
      }
      const mine = ++generation.current
      setMessage(null)
      setPending(true)
      try {
        const result = await suggestTask(title, description)
        if (mine !== generation.current) return
        onApply(result)
        setReason(result.reason)
      } catch (err) {
        if (mine !== generation.current) return
        setMessage(failureMessage(err))
      } finally {
        if (mine === generation.current) setPending(false)
      }
    },
    [onApply],
  )

  const reset = useCallback(() => {
    generation.current++
    setPending(false)
    setMessage(null)
    setReason(null)
  }, [])

  return { pending, message, reason, suggest, reset }
}
