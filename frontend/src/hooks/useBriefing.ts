import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, getBriefing } from '../api'
import type { Briefing } from '../types'

export const MSG_UNAVAILABLE = '지금은 브리핑을 쓸 수 없습니다'
export const MSG_FAILED = '브리핑을 받지 못했습니다'
export const MSG_EMPTY = '오늘은 비어 있어요'

// [오늘 브리핑] 호출 상태. 받아서 보여 줄 뿐 저장하지 않는다.
// close() 와 새 요청은 그 전에 보낸 요청의 늦은 응답을 버린다.
export function useBriefing(onUnauthorized: (err: unknown) => boolean) {
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [briefing, setBriefing] = useState<Briefing | null>(null)
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
    setBriefing(null)
    setPending(true)
    try {
      const result = await getBriefing()
      if (mine !== generation.current) return
      if (result.top3.length === 0) setMessage(MSG_EMPTY)
      else setBriefing(result)
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
    setBriefing(null)
  }, [])

  return { pending, message, briefing, generate, close }
}
