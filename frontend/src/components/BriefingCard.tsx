import type { Briefing } from '../types'

interface Props {
  briefing: Briefing
  // 보드 목록의 id → 제목. 목록에 없는 id 는 건너뛴다.
  titles: Map<number, string>
  onClose: () => void
}

const NUMBERS = ['①', '②', '③']

export default function BriefingCard({ briefing, titles, onClose }: Props) {
  const top = briefing.top3.filter((p) => titles.has(p.id))
  const later = briefing.later.filter((id) => titles.has(id))
  return (
    <div className="briefing-card" role="region" aria-label="오늘 브리핑">
      <h3>먼저 할 일</h3>
      <ol className="briefing-top">
        {top.map((p, i) => (
          <li key={p.id}>
            <span className="briefing-num">{NUMBERS[i]}</span>
            <span>
              <strong>{titles.get(p.id)}</strong> — {p.reason}
            </span>
          </li>
        ))}
      </ol>
      {later.length > 0 && (
        <>
          <h3>미뤄도 되는 일</h3>
          <ul className="briefing-later">
            {later.map((id) => (
              <li key={id}>{titles.get(id)}</li>
            ))}
          </ul>
        </>
      )}
      <p className="briefing-cheer">{briefing.cheer}</p>
      <button type="button" onClick={onClose}>닫기</button>
    </div>
  )
}
