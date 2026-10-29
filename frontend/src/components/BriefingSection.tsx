import { useMemo } from 'react'
import { MSG_FAILED, useBriefing } from '../hooks/useBriefing'
import type { Task } from '../types'
import BriefingCard from './BriefingCard'
import './BriefingSection.css'

interface Props {
  tasks: Task[]
  onUnauthorized: (err: unknown) => boolean
}

// 등록 폼 아래의 [오늘 브리핑] 버튼과 결과 카드. 보드는 건드리지 않는다.
export default function BriefingSection({ tasks, onUnauthorized }: Props) {
  const { pending, message, briefing, generate, close } = useBriefing(onUnauthorized)
  const titles = useMemo(() => new Map(tasks.map((t) => [t.id, t.title])), [tasks])
  // 받은 id 가 모두 보드에 없으면(받는 사이 삭제 등) 빈 카드 대신 실패로 안내한다.
  const showCard = briefing !== null && briefing.top3.some((p) => titles.has(p.id))

  return (
    <div className="briefing">
      <button type="button" disabled={pending} onClick={generate}>
        {pending ? '만드는 중…' : '오늘 브리핑'}
      </button>
      {message && <p className="error briefing-message" role="alert">{message}</p>}
      {briefing && !showCard && (
        <p className="error briefing-message" role="alert">{MSG_FAILED}</p>
      )}
      {briefing && showCard && <BriefingCard briefing={briefing} titles={titles} onClose={close} />}
    </div>
  )
}
