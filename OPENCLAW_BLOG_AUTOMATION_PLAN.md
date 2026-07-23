# OpenClaw Blog Automation Plan

## 1. Goal

`blog_app`을 OpenClaw 기반 블로그 포스팅 자동화 플랫폼으로 확장한다.

이번 확장의 핵심은 단순한 "글 생성"이 아니라 아래 운영 문제를 함께 해결하는 것이다.

- 어떤 주제를 언제 발행할지 자동 결정
- 플랫폼별 언어/톤/포맷 차이를 관리
- 자동 발행과 승인 대기를 함께 지원
- 실패한 발행을 재시도하고 원인 추적
- 사람이 나중에 봐도 흐름을 이해할 수 있도록 로그를 남김

즉, 기존 `blog_service`, `publish_service`, `scheduler_service` 위에 OpenClaw 오케스트레이션 계층을 추가한다.


## 2. Current State

현재 코드베이스에는 이미 아래 기능이 존재한다.

- 블로그 초안 생성: `services/blog_service.py`
- 이미지 삽입 및 HTML 구성: `services/publish_service.py`
- 플랫폼 발행: `services/publish_service.py`, `services/social_publish_service.py`
- 예약 실행: `services/scheduler_service.py`
- 블로그 API: `app/routers/blog.py`
- OpenClaw 보조 도구: `openclaw_tools/blog_tools.py`
- 설정 저장 및 작업 로그: `database.py`

현재 구조는 "개별 발행 기능"은 갖고 있지만, "캠페인 단위 자동 운영" 개념은 약하다.  
따라서 OpenClaw 확장의 1차 목표는 기능 추가보다 운영 계층 정리다.


## 3. Product Vision

사용자는 한 번만 캠페인을 설정하면 된다.

- 카테고리
- 타겟 플랫폼
- 언어
- 발행 스케줄
- 승인 정책
- 이미지 정책
- 품질 기준

그 후 OpenClaw가 다음을 반복 수행한다.

1. 주제 수집
2. 초안 생성
3. 품질 검토
4. 이미지 생성
5. 승인 여부 판단
6. 발행
7. 실패 재시도
8. 실행 로그 저장


## 4. Proposed Architecture

### 4.1 New Services

#### `services/openclaw_service.py`

역할:

- 캠페인 실행 진입점
- 단계별 상태 전이 관리
- 기존 서비스 호출 조합
- 실행 결과 저장

핵심 메서드 예시:

- `run_campaign(campaign_id: int)`
- `run_campaign_once(campaign: dict)`
- `generate_topic(campaign: dict)`
- `generate_variants(run_id: int, topic: str, campaign: dict)`
- `review_variants(run_id: int)`
- `publish_run(run_id: int)`
- `retry_failed_tasks(run_id: int)`

#### `services/openclaw_policy_service.py`

역할:

- 자동 발행 기준 판단
- 카테고리별 금지어/민감어 차단
- AI 품질 점수 컷오프
- 수동 승인 필요 여부 판단

핵심 메서드 예시:

- `should_require_approval(campaign, content_review) -> bool`
- `check_policy_violations(content, category) -> list[str]`
- `is_duplicate_topic(topic, recent_days=30) -> bool`

#### `services/openclaw_queue_service.py`

역할:

- 재시도 큐 관리
- 승인 대기 큐 관리
- 지연 실행 예약

핵심 메서드 예시:

- `enqueue_retry(task_id, reason, retry_at)`
- `claim_pending_retry_tasks(limit=10)`
- `enqueue_approval(run_id, target_id, payload)`
- `approve_item(approval_id, reviewer)`


## 5. Data Model

기존 `database.py`에 아래 테이블을 추가하는 것을 권장한다.

### 5.1 `openclaw_campaigns`

캠페인 설정 저장

권장 컬럼:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `name TEXT NOT NULL`
- `status TEXT DEFAULT 'active'`
- `category TEXT`
- `default_language TEXT DEFAULT 'ko'`
- `platforms_json TEXT NOT NULL`
- `schedule_type TEXT DEFAULT 'daily'`
- `schedule_time TEXT DEFAULT '09:00'`
- `timezone TEXT DEFAULT 'Asia/Seoul'`
- `topic_mode TEXT DEFAULT 'trend'`
- `approval_mode TEXT DEFAULT 'auto'`
- `quality_min_score INTEGER DEFAULT 82`
- `image_policy_json TEXT DEFAULT '{}'`
- `prompt_profile_json TEXT DEFAULT '{}'`
- `is_active INTEGER DEFAULT 1`
- `created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`
- `updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`

예시 `platforms_json`:

```json
[
  { "platform": "wordpress", "language": "ko", "target_id": "wordpress" },
  { "platform": "blogger", "language": "ja", "target_id": "blogger_1" }
]
```

### 5.2 `openclaw_runs`

한 번의 캠페인 실행 단위 저장

권장 컬럼:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `campaign_id INTEGER NOT NULL`
- `topic TEXT`
- `status TEXT DEFAULT 'queued'`
- `current_stage TEXT DEFAULT 'queued'`
- `approval_required INTEGER DEFAULT 0`
- `started_at TIMESTAMP`
- `completed_at TIMESTAMP`
- `error_message TEXT`
- `summary_json TEXT`
- `created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`

상태 예시:

- `queued`
- `running`
- `waiting_approval`
- `partial`
- `completed`
- `failed`

### 5.3 `openclaw_tasks`

세부 작업 추적

권장 컬럼:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `run_id INTEGER NOT NULL`
- `task_type TEXT NOT NULL`
- `target_id TEXT`
- `status TEXT DEFAULT 'queued'`
- `attempt_count INTEGER DEFAULT 0`
- `max_attempts INTEGER DEFAULT 3`
- `input_json TEXT`
- `output_json TEXT`
- `error_message TEXT`
- `next_retry_at TIMESTAMP`
- `created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`
- `updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`

`task_type` 예시:

- `topic`
- `draft`
- `quality_review`
- `image_generation`
- `approval`
- `publish`
- `retry_publish`

### 5.4 `approval_queue`

수동 승인 대기 큐

권장 컬럼:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `run_id INTEGER NOT NULL`
- `task_id INTEGER`
- `target_id TEXT`
- `title TEXT`
- `summary TEXT`
- `content_html TEXT`
- `status TEXT DEFAULT 'pending'`
- `reviewer TEXT`
- `review_note TEXT`
- `approved_at TIMESTAMP`
- `created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`

### 5.5 `content_variants`

플랫폼/언어별 결과 저장

권장 컬럼:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `run_id INTEGER NOT NULL`
- `target_id TEXT NOT NULL`
- `platform TEXT NOT NULL`
- `language TEXT NOT NULL`
- `title TEXT`
- `summary TEXT`
- `tags_json TEXT`
- `content_html TEXT`
- `images_json TEXT`
- `quality_score INTEGER`
- `quality_report_json TEXT`
- `publish_status TEXT DEFAULT 'draft'`
- `publish_url TEXT`
- `publish_post_id TEXT`
- `created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`
- `updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`


## 6. API Design

새 라우터 파일:

- `app/routers/openclaw.py`

### 6.1 Campaign APIs

- `GET /api/openclaw/campaigns`
  - 캠페인 목록 조회
- `POST /api/openclaw/campaigns`
  - 캠페인 생성
- `GET /api/openclaw/campaigns/{campaign_id}`
  - 캠페인 상세 조회
- `PUT /api/openclaw/campaigns/{campaign_id}`
  - 캠페인 수정
- `POST /api/openclaw/campaigns/{campaign_id}/toggle`
  - 활성/비활성 전환

### 6.2 Run APIs

- `POST /api/openclaw/campaigns/{campaign_id}/run`
  - 수동 1회 실행
- `GET /api/openclaw/runs`
  - 실행 이력 목록
- `GET /api/openclaw/runs/{run_id}`
  - 실행 상세
- `POST /api/openclaw/runs/{run_id}/retry`
  - 실패 작업 재실행

### 6.3 Approval APIs

- `GET /api/openclaw/approvals`
  - 승인 대기 목록
- `POST /api/openclaw/approvals/{approval_id}/approve`
  - 승인 후 발행 진행
- `POST /api/openclaw/approvals/{approval_id}/reject`
  - 반려 후 재생성 또는 종료

### 6.4 Monitoring APIs

- `GET /api/openclaw/dashboard/summary`
  - 성공/실패/대기 현황
- `GET /api/openclaw/logs`
  - OpenClaw 실행 로그


## 7. Scheduler Integration

현재 `scheduler_service.py`는 전역 설정 기반으로 하루 한 번 실행한다.  
OpenClaw 도입 후에는 "전역 1개 작업"이 아니라 "활성 캠페인 여러 개"를 순회하는 형태로 바꾸는 것이 좋다.

개선 방향:

1. 활성 캠페인 조회
2. 각 캠페인의 스케줄 검사
3. 실행 중인 동일 캠페인 중복 방지
4. `openclaw_service.run_campaign(campaign_id)` 호출

추가 규칙:

- 같은 날짜/시간대에 동일 캠페인 중복 실행 금지
- 이전 실행이 `running`이면 신규 실행 보류
- `waiting_approval` 상태는 재실행하지 않음


## 8. UI/UX Plan

새 페이지 제안:

- `templates/pages/openclaw_dashboard.html`

### 8.1 Dashboard Sections

- 활성 캠페인 카드
- 오늘 실행 결과
- 승인 대기 목록
- 실패 작업 목록
- 플랫폼별 성공률

### 8.2 Campaign Form

필드:

- 캠페인 이름
- 카테고리
- 타겟 플랫폼 목록
- 언어 설정
- 스케줄 시간
- 승인 모드
- 최소 품질 점수
- 이미지 생성 규칙
- 커스텀 프롬프트 프로필

### 8.3 Approval Screen

각 승인 항목에서 바로 확인할 수 있어야 할 정보:

- 제목
- 요약
- 본문 미리보기
- 품질 점수
- 정책 위반 여부
- 발행 대상 플랫폼
- 승인 / 반려 / 수정 요청 버튼


## 9. Workflow Definition

### 9.1 Auto Mode

1. 스케줄러가 캠페인 실행
2. 주제 생성
3. 플랫폼별 초안 생성
4. 품질 검토
5. 이미지 생성
6. 정책 검사
7. 기준 통과 시 자동 발행
8. 결과 저장

### 9.2 Human-in-the-Loop Mode

1. 스케줄러가 캠페인 실행
2. 초안 생성 및 품질 검토
3. 승인 큐 저장
4. 사용자 승인
5. 승인된 변형만 발행
6. 결과 저장

### 9.3 Retry Workflow

1. 발행 실패 감지
2. 재시도 가능 여부 판정
3. 백오프 시간 계산
4. `openclaw_tasks.next_retry_at` 기록
5. 주기적으로 재시도 큐 소비


## 10. Quality and Safety Rules

OpenClaw 자동화에서 가장 중요한 기준은 아래와 같다.

### 10.1 Quality

- 최소 품질 점수 미달 시 자동 발행 금지
- 제목 과장도 검사
- 문단 길이와 가독성 검사
- 태그 누락 검사
- 플랫폼별 HTML 유효성 검사

### 10.2 Safety

- 카테고리별 금지어
- 의료/금융 민감 주제 플래그
- 과도한 확정 표현 차단
- 중복 주제 방지
- 동일 URL 또는 동일 제목 반복 게시 방지

### 10.3 Operational Safety

- 플랫폼별 API 실패 시 재시도 횟수 제한
- 이미지 생성 실패 시 텍스트만 발행 가능 여부 옵션화
- 승인 대기 중인 콘텐츠는 자동 덮어쓰기 금지


## 11. Implementation Roadmap

### Phase 1: MVP

목표:

- 캠페인 생성/조회
- 수동 1회 실행
- 실행 이력 저장
- 플랫폼별 초안 저장
- 승인 대기 큐

작업:

- DB 스키마 추가
- `openclaw_service.py` 기본 골격
- `openclaw.py` 라우터 추가
- 대시보드 초안 추가

### Phase 2: Automation

목표:

- 스케줄러 연동
- 자동 발행
- 실패 재시도
- 품질/정책 게이트

작업:

- `scheduler_service.py` 캠페인 기반 전환
- `openclaw_policy_service.py` 추가
- `openclaw_queue_service.py` 추가
- 상태 로그 세분화

### Phase 3: Optimization

목표:

- 성과 기반 개선
- 중복 주제 회피
- 프롬프트 프로필 고도화
- 플랫폼별 페르소나 운영

작업:

- 성과 데이터 연계
- 주제 히스토리 기반 추천
- 카테고리별 템플릿 정교화


## 12. Recommended File Plan

추가 파일:

- `services/openclaw_service.py`
- `services/openclaw_policy_service.py`
- `services/openclaw_queue_service.py`
- `app/routers/openclaw.py`
- `templates/pages/openclaw_dashboard.html`
- `static/js/openclaw.js`

수정 파일:

- `database.py`
- `main.py`
- `services/scheduler_service.py`
- `templates/base.html`


## 13. First Implementation Slice

가장 먼저 구현할 최소 단위는 아래 순서가 좋다.

1. `database.py`에 OpenClaw 테이블 추가
2. `services/openclaw_service.py` 생성
3. `app/routers/openclaw.py` 생성
4. `main.py`에 라우터 등록
5. 수동 실행 API 1개 구현
6. 실행 결과를 `content_variants`와 `openclaw_runs`에 저장
7. 승인 대기 API 구현

이렇게 하면 스케줄러를 건드리기 전에도 실제 워크플로우를 검증할 수 있다.


## 14. Success Criteria

아래 조건을 만족하면 1차 성공으로 본다.

- 사용자가 캠페인을 생성할 수 있다
- 캠페인 1회를 수동 실행할 수 있다
- 플랫폼별 초안이 저장된다
- 승인 모드가 `human-in-loop`일 때 승인 큐에 쌓인다
- 승인 후 실제 발행이 이어진다
- 실패한 플랫폼은 재시도 대상이 된다
- 실행 이력이 대시보드에서 조회된다


## 15. Next Step Recommendation

바로 구현을 시작한다면 다음 범위를 추천한다.

- `Phase 1 MVP` 전체
- 특히 `DB + service + router`까지 우선 구현

이 범위가 끝나면 기존 앱을 크게 흔들지 않고도 OpenClaw 기반 자동 포스팅의 핵심 흐름을 실제로 돌려볼 수 있다.
