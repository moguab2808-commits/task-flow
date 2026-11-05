import { useState } from 'react'
import type { FormEvent } from 'react'
import { PRIORITY_LABEL } from '../types'
import type { Priority, SearchCondition } from '../types'
import './SearchBar.css'

interface Props {
  onSearch: (condition: SearchCondition) => void
  onClear: () => void
}

const PRIORITIES: Priority[] = ['HIGH', 'NORMAL', 'LOW']

// 제목 · 설명 검색과 우선순위 필터. 결과를 어떻게 보여 줄지는 부모가 정한다.
export default function SearchBar({ onSearch, onClear }: Props) {
  const [q, setQ] = useState('')
  const [priority, setPriority] = useState<Priority | ''>('')

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    onSearch({ q, priority })
  }

  function handleClear() {
    setQ('')
    setPriority('')
    onClear()
  }

  return (
    <form className="search-bar" onSubmit={handleSubmit} role="search">
      <input
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="제목 · 설명 검색"
        aria-label="검색어"
      />
      <select
        value={priority}
        onChange={(e) => setPriority(e.target.value as Priority | '')}
        aria-label="우선순위"
      >
        <option value="">전체</option>
        {PRIORITIES.map((p) => (
          <option key={p} value={p}>
            {PRIORITY_LABEL[p]}
          </option>
        ))}
      </select>
      <button type="submit">찾기</button>
      <button type="button" onClick={handleClear}>
        모두 보기
      </button>
    </form>
  )
}
