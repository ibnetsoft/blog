# OpenClaw 블로그 자동화 프로젝트 현황 요약

작성일: 2026-07-17

## 1. 프로젝트 개요
기존의 `blog_app` 블로그 API를 확장하여, **OpenClaw 기반 에이전트와 Discord 인터페이스를 결합한 Human-in-the-Loop 블로그 포스팅 자동화 플랫폼**을 구축하고 있습니다. 
단순한 텍스트/초안 생성에 그치지 않고, 캠페인 단위의 주제 선정, 품질 검수, 사용자 승인(Human-in-the-Loop), 발행 후 재시도까지 전체 운영 파이프라인을 자동화하는 것이 목표입니다.

## 2. 주요 구조
* **`discord_bot.py`**: FastAPI 내장형 디스코드 봇으로, OpenClaw가 생성한 초안을 사용자가 디스코드에서 검토 및 승인/반려할 수 있는 핵심 인터페이스입니다.
* **`/core` & `/services`**: 기존 블로그 발행 로직, 자동화 스케줄링 및 OpenClaw 연동 서비스 레이어
* **`/openclaw_tools` (`blog_tools.py`)**: 에이전트 호출 및 외부 API(LLM 등) 통신을 담당하는 래퍼 레이어
* **`/app/routers` & `/templates`**: 웹 대시보드 인터페이스 (`/openclaw-dashboard`, `/settings` 등)
* **`database.py`**: 캠페인 데이터, 실행(Run) 기록, 큐(Queue) 상태 등을 관리하기 위한 데이터베이스 로직

## 3. 현재까지 완료된 핵심 작업
1. **OpenClaw 관리 대시보드 신설**
   * `/openclaw-dashboard` 라우팅 및 페이지 연동 완료.
   * 캠페인 생성, 실행 상태, 승인 대기 항목을 웹 화면에서 관리할 수 있도록 기반을 마련했습니다.
2. **설정 화면 및 계정 연동 문제 해결**
   * `/settings` 화면에서 사라졌던 Google Blogger 계정 목록을 복구하고, 새로고침 시에도 유지되도록 수정했습니다.
   * Gemini, OpenAI, Anthropic 등 AI API 키 저장 시 보안을 위한 마스킹(`sk-***...`) 처리 및 DB 반영 로직을 구현했습니다.
3. **역할 분리 (글쓰기 AI vs OpenClaw)**
   * 순수 텍스트 생성용 AI와 전체 발행 흐름을 제어하는 OpenClaw(오케스트레이터)의 역할을 시스템 설정 레벨에서 분리했습니다.
4. **발행/소셜 연동 설정 유지**
   * Telegram, WordPress, 카테고리 설정 등 기존 자동 게시 옵션들이 정상적으로 동작하도록 정리했습니다.

## 4. 진행 중 및 향후 계획 (Next Steps)
* **스케줄러 고도화**: 단일 스케줄이 아닌 개별 '캠페인'별 스케줄과 타임존을 기반으로 작동하도록 스케줄러 업그레이드
* **실행 및 재시도 큐 관리 (`openclaw_queue_service`)**: 일시적 오류 등으로 실패한 발행 작업을 관리하고 자동으로 재시도(Back-off)하는 시스템 적용
* **품질 및 안전장치 (`openclaw_policy_service`)**: 최소 품질 컷오프(Scoring), 금지어 및 민감어 필터링, 중복 주제 발행 방지 로직 적용
* **데이터베이스 확장**: 진행 상황과 이력을 완벽히 추적할 수 있도록 `openclaw_campaigns`, `openclaw_runs`, `openclaw_tasks` 등 신규 테이블 도입

---
*참고: 이 문서는 `OPENCLAW_WORK_SUMMARY.md` 및 `OPENCLAW_BLOG_AUTOMATION_PLAN.md`를 바탕으로 전체 현황을 간결히 파악할 수 있도록 정리되었습니다.*
