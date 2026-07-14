# OpenClaw Blog Automation Work Summary

작성일: 2026-07-14

## 작업 목표

- `blog_app`에 OpenClaw 기반 블로그 자동발행 흐름을 연결
- 설정 화면에서 AI 키, 자동 게시, Blogger 계정을 관리
- Google Blogger 계정이 화면에서 사라지지 않도록 복구
- 글쓰기 AI와 OpenClaw 실행 흐름을 분리해서 관리

## 이번에 반영한 내용

### 1. OpenClaw 대시보드 추가

- `openclaw` 라우터와 `/openclaw-dashboard` 페이지를 연결
- OpenClaw 캠페인 생성, 승인 대기, 최근 실행 상태를 한 화면에서 관리하도록 구성

### 2. Blogger 설정 복구

- `/settings` 페이지에 Blogger 계정 목록을 다시 표시하도록 복구
- 서버에서 `blogger_accounts`를 전달해, 새로고침 후에도 계정 카드가 보이게 수정
- Blogger 계정 추가/연동/삭제 흐름을 유지

### 3. API 키 저장/표시 개선

- Gemini, OpenAI, Anthropic 키를 저장하면 마스킹된 형태로 표시되도록 정리
- 저장 상태를 `미저장` / `저장됨 · sk-***...` 형태로 보여줌
- 설정 저장 API가 실제로 `.env`와 DB에 반영되도록 연결

### 4. 글쓰기 AI와 OpenClaw 분리

- 글쓰기 AI는 `AI_TEXT_PROVIDER`와 `AI_TEXT_MODEL`로 선택
- OpenClaw는 자동 발행 실행 흐름으로 분리해서 관리
- 설정 화면에서 현재 사용 중인 AI를 확인할 수 있도록 요약 영역을 추가

### 5. 자동 게시/소셜 연결 관련 정리

- 일일 자동 게시 시간, 주제/카테고리, JSON 배포 대상 설정 유지
- Telegram, Social Publish, WordPress 설정 항목을 유지

## 확인된 상태

- 설정 저장 API는 `200 OK`로 응답함
- 저장된 Anthropic 키는 다시 불러오면 `sk-ant-********************************` 형태로 확인됨
- Blogger 계정은 DB에 남아 있고, 목록 조회 API에서도 확인됨
- `/openclaw-dashboard` 페이지 라우팅이 연결됨

## 남은 주의사항

- 일부 Blogger 계정은 Google 토큰이 만료되어 `invalid_grant`가 발생할 수 있음
- 이 경우 설정 화면에서 계정을 다시 Google 연동해야 함
- `blog_app.db`는 런타임 데이터라서, 필요하면 별도 백업 대상으로 보는 것이 안전함

## 한 줄 요약

- OpenClaw 자동발행과 Blogger 설정 화면을 연결하고, API 키 저장/표시 문제와 Blogger 목록 소실 문제를 정리했다.
