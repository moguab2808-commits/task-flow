import { useEffect, useState } from 'react'
import { changeStatus, createTask, deleteTask, listTasks, updateContent } from './api'
import TaskCard from './components/TaskCard'
import TaskForm from './components/TaskForm'
import type { Status, Task } from './types'

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

  async function handleChangeStatus(id: number, status: Status) {
    const updated = await changeStatus(id, status)
    setTasks((prev) => prev.map((t) => (t.id === id ? updated : t)))
  }

  async function handleEdit(id: number, title: string, description: string) {
    const updated = await updateContent(id, title, description)
    setTasks((prev) => prev.map((t) => (t.id === id ? updated : t)))
  }

  async function handleDelete(id: number) {
    await deleteTask(id)
    setTasks((prev) => prev.filter((t) => t.id !== id))
  }

  return (
    <main>
      <h1>task-flow</h1>
      <TaskForm onCreate={handleCreate} />
      <ul className="task-list">
        {tasks.map((t) => (
          <TaskCard
            key={t.id}
            task={t}
            onChangeStatus={handleChangeStatus}
            onEdit={handleEdit}
            onDelete={handleDelete}
          />
        ))}
      </ul>
    </main>
  )
}

export default App
