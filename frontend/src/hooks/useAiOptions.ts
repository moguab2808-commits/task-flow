import { useCallback, useRef, useState } from 'react'
import { suggestOptions } from '../api'
import type { TaskOption } from '../types'
import { MSG_TITLE_REQUIRED, failureMessage } from './useAiSuggest'

// [AI 로 할 일 만들기] 호출 상태. 후보를 받아 보여 줄 뿐 저장하지 않는다.
// reset() 은 저장 · 취소 때 부르며, 그 전에 보낸 요청의 늦은 응답은 버린다.
export function useAiOptions() {
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [items, setItems] = useState<TaskOption[]>([])
  const generation = useRef(0)

  const generate = useCallback(async (title: string) => {
    if (!title.trim()) {
      setMessage(MSG_TITLE_REQUIRED)
      return
    }
    const mine = ++generation.current
    setMessage(null)
    setItems([])
    setPending(true)
    try {
      const result = await suggestOptions(title)
      if (mine !== generation.current) return
      setItems(result)
    } catch (err) {
      if (mine !== generation.current) return
      setMessage(failureMessage(err))
    } finally {
      if (mine === generation.current) setPending(false)
    }
  }, [])

  const reset = useCallback(() => {
    generation.current++
    setPending(false)
    setMessage(null)
    setItems([])
  }, [])

  return { pending, message, items, setItems, setMessage, generate, reset }
}
