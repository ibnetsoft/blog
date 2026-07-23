# 🤖 OpenClaw & Discord Blog Automation System

Human-in-the-Loop 구조를 적용한 에이전트 기반 블로그 자동화 파이프라인입니다. 
OpenClaw 에이전트가 생성한 초안을 디스코드 인터페이스를 통해 사용자가 검토 및 승인/반려할 수 있습니다.

## 📁 폴더 구조
- `/core`: 기존 블로그 API 및 콘텐츠 생성 엔진 (보존 구역)
- `/openclaw_tools`: 에이전트 호출용 래퍼 레이어 (`blog_tools.py`)
- `discord_bot.py`: FastAPI 내장형 디스코드 양방향 봇 메인 엔진

## 🚀 시작 가이드
1. 의존성 설치: `pip install -r requirements.txt`
2. 환경 변수 세팅: `.env` 파일에 토큰 및 채널 ID 입력
3. 시스템 구동: `python discord_bot.py`
