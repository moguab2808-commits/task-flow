import { PRIORITY_LABEL } from '../types'
import type { TaskOption } from '../types'

interface Props {
  items: TaskOption[]
  disabled?: boolean
  onPick: (item: TaskOption) => void
  // 없으면 [모두 등록] 을 보이지 않는다 (수정 폼).
  onRegisterAll?: () => void
  onCancel: () => void
}

// AI 가 만든 할 일 후보. 하나를 누르면 폼 칸에 채워지고, 저장은 사용자가 따로 한다.
export default function AiOptionsPanel({ items, disabled, onPick, onRegisterAll, onCancel }: Props) {
  if (items.length === 0) return null
  return (
    <div className="ai-options">
      <h3>AI 가 만든 할 일 {items.length}개</h3>
      <p className="ai-options-hint">
        하나를 누르면 설명 · 우선순위 · 마감일 칸에 채워집니다. 저장은 직접 눌러야 합니다.
      </p>
      <ul>
        {items.map((item, i) => (
          <li key={i}>
            <button type="button" className="ai-option" disabled={disabled} onClick={() => onPick(item)}>
              <span className="ai-option-top">
                <strong>{item.title}</strong>
                <span className="ai-option-meta">
                  <span className={`badge badge-priority-${item.priority}`}>
                    우선순위 {PRIORITY_LABEL[item.priority]}
                  </span>
                  <span>{item.due_date ?? '마감일 없음'}</span>
                </span>
              </span>
              {item.description && <span className="ai-option-desc">{item.description}</span>}
            </button>
          </li>
        ))}
      </ul>
      <div className="ai-options-actions">
        {onRegisterAll && (
          <button type="button" disabled={disabled} onClick={onRegisterAll}>모두 등록</button>
        )}
        <button type="button" disabled={disabled} onClick={onCancel}>취소</button>
      </div>
    </div>
  )
}
