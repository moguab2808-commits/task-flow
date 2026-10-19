# task-flow

카드형 Task 관리 웹 앱. 화면 React · Vite / API FastAPI / 저장소 SQLite (저장소는 아직 없음).
자기 컴퓨터에서만 실행한다.

## 실행

API (http://localhost:8000):

    cd backend
    uv run uvicorn app.main:app --reload

화면 (http://localhost:5173):

    cd frontend
    npm install
    npm run dev
