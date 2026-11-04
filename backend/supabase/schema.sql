-- init_db (backend/app/db.py) 의 SQLite 스키마와 같은 테이블 셋. 날짜는 text 그대로.
-- 정책(policy)은 만들지 않는다: RLS 만 켜 둔다.

create table if not exists users (
    id bigint generated always as identity primary key,
    username text not null unique,
    password_hash text,
    created_at text not null
);
alter table users enable row level security;

create table if not exists sessions (
    id text primary key,
    user_id bigint not null references users(id),
    created_at text not null,
    expires_at text not null
);
alter table sessions enable row level security;

create table if not exists tasks (
    id bigint generated always as identity primary key,
    title text not null,
    description text not null default '',
    status text not null default 'TODO',
    created_at text not null,
    updated_at text not null,
    owner_id bigint references users(id),
    priority text not null default 'NORMAL' check (priority in ('LOW', 'NORMAL', 'HIGH')),
    due_date text
);
alter table tasks enable row level security;
