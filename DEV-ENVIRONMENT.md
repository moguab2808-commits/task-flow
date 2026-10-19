# DEV-ENVIRONMENT

확인한 날짜: 2026-10-19. 아래 값은 이 컴퓨터에서 실제로 실행한 결과를 그대로 적은 것이다.

## 운영체제 · 셸
| 항목 | 값 |
|---|---|
| 운영체제 | Microsoft Windows 11 Pro 10.0.22631 (build 22631) |
| 셸 | PowerShell 7.6.7 |

## 도구별 버전 (`--version` 결과 그대로)
| 도구 | 실행한 명령 | 결과 |
|---|---|---|
| git | `git --version` | `git version 2.56.0.windows.2` |
| node | `node --version` | 실행 안 됨: `'node' 용어는 cmdlet, 함수, 스크립트 파일 또는 실행 프로그램의 이름으로 인식되지 않습니다.` |
| npm | `npm --version` | 실행 안 됨: `'npm' 용어는 cmdlet, 함수, 스크립트 파일 또는 실행 프로그램의 이름으로 인식되지 않습니다.` |
| uv | `uv --version` | `uv 0.13.1 (62faed335 2026-10-13 x86_64-pc-windows-msvc)` |
| python | `python --version` | 실행 안 됨: `'python' 용어는 cmdlet, 함수, 스크립트 파일 또는 실행 프로그램의 이름으로 인식되지 않습니다.` |
| python (uv 가 설치한 것) | `python3.12 --version` | `Python 3.12.15` |

참고
- `python` 이라는 이름은 PATH 에 없고, `python3.12` 로는 실행된다 (`C:\Users\EZ\.local\bin\python3.12.exe`).
- 같은 Python 3.12.15 의 `sqlite3` 모듈은 SQLite 3.53.1, pip 는 26.2.1 이다.

## 새로 설치한 것
- 없음. 이 문서를 만들 때까지 설치한 도구는 하나도 없다. 위 표는 원래 있던 상태다.

## 아직 없어서 설치가 필요한 것 (설치 전)
- Node.js (npm 포함): React · Vite 화면에 필요. Vite 문서 기준 Node.js 20.19 이상 또는 22.12 이상.
- FastAPI: 프로젝트를 만들 때 uv 로 설치할 예정.
