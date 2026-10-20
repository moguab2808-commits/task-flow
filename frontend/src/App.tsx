import { useEffect, useState } from 'react'
import { createTask, listTasks } from './api'
import TaskCard from './components/TaskCard'
import TaskForm from './components/TaskForm'
import type { Task } from './types'

function App() {
  const [tasks, setTasks] = useState<Task[]>([])

  useEffect(() => {
    listTasks().then(setTasks).catch(() => {
      // 불러오기 실패 화면은 이슈 #4 에서 다룬다.
    })
  }, [])

  async function handleCreate(title: string, description: string) {
    const created = await createTask(title, description)
    setTasks((prev) => [...prev, created])
  }

  return (
    <main>
      <h1>task-flow</h1>
      <TaskForm onCreate={handleCreate} />
      <ul className="task-list">
        {tasks.map((t) => (
          <TaskCard key={t.id} task={t} />
        ))}
      </ul>
    </main>
  )
}

export default App
