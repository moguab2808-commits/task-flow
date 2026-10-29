import type { Weekplan } from '../types'

export interface WeekRow {
  date: string
  titles: string[]
}

interface Props {
  plan: Weekplan
  // 줄로 그릴 날짜와 제목. 보드에 없는 id 는 이미 빠져 있다.
  rows: WeekRow[]
  onClose: () => void
}

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']

// 'YYYY-MM-DD' → 'MM-DD (요일)'. 시간대 때문에 하루 어긋나지 않게 로컬 날짜로 계산한다.
function dayLabel(date: string): string {
  const [y, m, d] = date.split('-').map(Number)
  return `${date.slice(5)} (${WEEKDAYS[new Date(y, m - 1, d).getDay()]})`
}

export default function WeekplanCard({ plan, rows, onClose }: Props) {
  return (
    <div className="weekplan-card" role="region" aria-label="이번 주 계획">
      <table className="weekplan-table">
        <tbody>
          {rows.map((r) => (
            <tr key={r.date}>
              <th scope="row">{dayLabel(r.date)}</th>
              <td>
                {r.titles.map((t, i) => (
                  <div key={i}>{t}</div>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="weekplan-note">{plan.note}</p>
      <button type="button" onClick={onClose}>닫기</button>
    </div>
  )
}
