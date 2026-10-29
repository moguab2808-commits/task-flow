import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, getWeekplan } from '../api'
import type { Weekplan } from '../types'

export const MSG_UNAVAILABLE = '지금은 이번 주 계획을 쓸 수 없습니다'
export const MSG_FAILED = '이번 주 계획을 받지 못했습니다'
export const MSG_EMPTY = '오늘은 비어 있어요'

// [이번 주 계획] 호출 상태. 받아서 보여 줄 뿐 저장하지 않는다.
// close() 와 새 요청은 그 전에 보낸 요청의 늦은 응답을 버린다.
export function useWeekplan(onUnauthorized: (err: unknown) => boolean) {
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [plan, setPlan] = useState<Weekplan | null>(null)
  const generation = useRef(0)

  // 보드가 닫히면(로그아웃 등) 진행 중이던 요청의 응답은 버린다.
  useEffect(() => {
    const counter = generation
    return () => {
      counter.current++
    }
  }, [])

  const generate = useCallback(async () => {
    const mine = ++generation.current
    setMessage(null)
    setPlan(null)
    setPending(true)
    try {
      const result = await getWeekplan()
      if (mine !== generation.current) return
      if (result.days.length === 0) setMessage(MSG_EMPTY)
      else setPlan(result)
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
  }, [onUnauthorized])

  const close = useCallback(() => {
    generation.current++
    setPending(false)
    setMessage(null)
    setPlan(null)
  }, [])

  return { pending, message, plan, generate, close }
}
