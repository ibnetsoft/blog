# 기능 및 사용 설명서

이 문서는 블로그 자동화 앱의 주요 기능과 실제 사용 흐름을 정리한 운영 가이드입니다.

## 1. 앱 개요

이 앱은 AI로 블로그 글을 생성하고, 생성된 콘텐츠를 여러 채널에 게시하는 로컬 웹 도구입니다.

지원 흐름은 크게 다음과 같습니다.

1. 소스 또는 주제를 입력해 콘텐츠 생성
2. 플랫폼별 글/이미지/메타데이터 검토
3. WordPress, Blogger, Telegram, Facebook, Instagram, TikTok 등에 게시
4. 게시 결과와 실패 원인을 로그에서 확인
5. 필요 시 자동 게시 스케줄러로 반복 실행

기본 실행 주소는 다음과 같습니다.

```text
http://127.0.0.1:8000
```

## 2. 주요 화면

### 2.1 독립 블로그 생성

경로:

```text
/blog-independent
```

용도:

- 주제 1개를 기반으로 플랫폼별 콘텐츠 생성
- WordPress용 한국어 장문 글 생성
- 여러 Blogger 계정 언어에 맞춘 독립 글 생성
- Telegram, Facebook, Instagram, TikTok용 짧은 소셜 포스트 생성
- 생성된 글을 탭으로 전환하며 직접 수정
- 이미지 자동 생성 후 본문에 삽입
- 선택한 플랫폼에 한 번에 게시

기본 사용 순서:

1. 왼쪽에서 카테고리와 주제를 입력합니다.
2. 게시할 플랫폼을 선택합니다.
   - WordPress
   - Blogger 계정들
   - Telegram
   - Facebook
   - Instagram
   - TikTok
3. `AI 다국어 동시 작성 시작` 버튼을 누릅니다.
4. 생성된 탭별 제목, 본문, 태그, 요약을 확인합니다.
5. 필요하면 내용을 직접 수정합니다.
6. 이미지가 필요하면 이미지 생성 기능을 실행합니다.
7. 게시 버튼으로 선택한 플랫폼에 발행합니다.

참고:

- 카테고리를 바꿔도 추천 주제는 자동으로 다시 불러오지 않습니다.
- 필요할 때 `추천 새로고침`을 눌러 추천 후보를 불러옵니다.
- 생성 실패 결과는 저장 상태에서 제외되도록 처리됩니다.

### 2.2 Publish Hub

경로:

```text
/publish-hub
```

용도:

- 하나의 원본 콘텐츠를 게시 세션으로 관리
- 본문에 들어갈 이미지/비디오 슬롯 관리
- 로컬 이미지/비디오 업로드
- 공개 URL로 미디어 승격
- WordPress, Blogger, Facebook, Instagram, TikTok에 게시
- 플랫폼별 성공/실패/부분 성공 결과 확인

기본 사용 순서:

1. 새 게시 세션을 만듭니다.
2. 제목과 원본 콘텐츠를 입력합니다.
3. 이미지 분석 또는 이미지 추가로 미디어 슬롯을 준비합니다.
4. 필요한 이미지 또는 비디오 파일을 업로드합니다.
5. WordPress Media Library 또는 공개 URL 승격 기능으로 외부 접근 가능한 URL을 준비합니다.
6. 게시 대상 플랫폼을 선택합니다.
7. 게시를 실행합니다.
8. 결과 카드에서 각 플랫폼의 URL, 실패 원인, 재시도 가능 여부를 확인합니다.

주의:

- TikTok 게시에는 공개 접근 가능한 `video_url`이 필요합니다.
- 로컬 `/output/...` URL은 배포 환경에 따라 외부 플랫폼에서 접근하지 못할 수 있습니다.
- 실제 소셜 게시에는 각 플랫폼의 권한, 토큰, 앱 심사 상태가 필요합니다.

### 2.3 설정

경로:

```text
/settings
```

설정 가능한 항목:

- 글쓰기 AI provider
  - Gemini
  - OpenAI
  - Anthropic
- 글쓰기 모델
- Gemini API Key
- OpenAI API Key
- Anthropic API Key
- WordPress URL / 사용자명 / 앱 비밀번호
- Telegram Bot Token / Chat ID / 채널 목록
- Facebook Page ID / Access Token
- Instagram Account ID / Access Token
- TikTok Access Token
- 자동 게시 사용 여부와 시간
- 자동 게시 대상 플랫폼 JSON
- 게시 후 작성된 글 자동 열기 여부
- 게시 전 AI 품질 검사 사용 여부
- AI 품질 최소 점수
- Blogger 계정 OAuth 연결

비밀값 처리:

- 저장된 API 키, 비밀번호, 토큰은 입력칸에 다시 표시되지 않습니다.
- 빈 값으로 저장해도 기존 비밀값을 덮어쓰지 않습니다.
- 새 값으로 바꾸고 싶을 때만 해당 입력칸에 값을 입력합니다.

### 2.4 로그

경로:

```text
/logs
```

확인 가능한 내용:

- 게시 플랫폼
- 계정명
- 제목
- 성공 / 부분 성공 / 실패 상태
- 게시 URL
- 실패 메시지
- 재시도 가능 여부
- 자동 게시 결과 요약

부분 성공 예시:

- WordPress 성공
- Blogger 일부 실패
- Instagram 토큰 오류
- TikTok 비디오 URL 없음

이 경우 로그에는 성공 플랫폼과 실패 플랫폼이 분리되어 표시됩니다.

### 2.5 Amazon 리뷰 보조

경로:

```text
/amazon-review
```

용도:

- Amazon 상품 리뷰형 콘텐츠 생성
- WordPress/Blogger 게시 전 AI 품질 검토 적용
- 게시 결과와 품질 검토 결과를 함께 반환

## 3. AI 글쓰기 및 품질 검사

### 3.1 글쓰기 Provider

설정 화면에서 글쓰기 AI provider를 선택할 수 있습니다.

```text
gemini
openai
anthropic
```

동작 방식:

- 선택한 provider의 API 키가 있으면 해당 provider로 글을 생성합니다.
- OpenAI/Anthropic 키가 없거나 인증 오류가 나고 Gemini 키가 있으면 Gemini fallback을 시도합니다.
- Gemini는 설정된 fallback model 목록을 순서대로 재시도합니다.

### 3.2 AI 품질 검사

게시 직전 다음 항목을 검토합니다.

- 제목 클릭 매력도
- 검색 의도 적합성
- 본문 가독성
- 태그 품질
- 요약 품질
- 플랫폼별 적합성
- Blogger 라벨에 부적합한 문자 포함 여부

품질 검사 결과는 게시 응답의 `quality_reviews`에 포함됩니다.

저장되는 정보:

- 플랫폼
- 언어
- 원본 제목
- 개선 제목
- 점수
- 발견 이슈
- 개선 내용

품질 검사 최소 점수는 설정 화면의 `AI 품질 최소 점수`에서 조정할 수 있습니다.

## 4. 플랫폼별 게시 기능

### 4.1 WordPress

필요 설정:

```text
WP_URL
WP_USERNAME
WP_PASSWORD
```

권장:

- `WP_PASSWORD`는 일반 비밀번호가 아니라 WordPress Application Password를 사용합니다.
- 이미지가 포함된 글은 WordPress Media Library 업로드를 먼저 수행하면 안정적입니다.

### 4.2 Blogger

필요 설정:

- Google OAuth Client ID
- Google OAuth Client Secret
- Blogger 계정 연결

사용 순서:

1. 설정 화면에서 Blogger 계정을 추가합니다.
2. OAuth 연결을 시작합니다.
3. Google 인증 후 연결 상태를 확인합니다.
4. 독립 블로그 생성 화면에서 Blogger 계정을 선택해 게시합니다.

### 4.3 Telegram

필요 설정:

```text
TELEGRAM_TOKEN
TELEGRAM_CHAT_ID 또는 TELEGRAM_CHANNELS
```

용도:

- 블로그형 장문보다 짧은 모바일용 요약 포스트에 적합합니다.

### 4.4 Facebook

필요 설정:

```text
FACEBOOK_PAGE_ID
FACEBOOK_ACCESS_TOKEN
```

주의:

- Page 게시 권한이 있는 Access Token이 필요합니다.
- 연결 점검은 설정 화면의 `연결 점검` 버튼에서 확인합니다.

### 4.5 Instagram

필요 설정:

```text
INSTAGRAM_ACCOUNT_ID
INSTAGRAM_ACCESS_TOKEN
```

주의:

- Instagram Graph API를 사용할 수 있는 Business/Creator 계정이 필요합니다.
- 이미지 URL은 외부에서 접근 가능해야 합니다.

### 4.6 TikTok

필요 설정:

```text
TIKTOK_ACCESS_TOKEN
```

주의:

- TikTok 게시에는 공개 접근 가능한 비디오 URL이 필요합니다.
- 앱 권한과 심사 상태에 따라 실제 게시 가능 범위가 제한될 수 있습니다.

## 5. 자동 게시

자동 게시 설정 위치:

```text
/settings
```

주요 항목:

- 자동 게시 사용 여부
- 게시 시간
- 기본 카테고리
- 이미지 생성 시 사람 제외 여부
- 자동 게시 대상 플랫폼 JSON

자동 게시 대상 JSON 예시:

```json
[
  {"language": "ko", "platform": "wordpress", "target_id": "wordpress"},
  {"language": "ja", "platform": "blogger", "target_id": "blogger:1"},
  {"language": "ko", "platform": "facebook", "target_id": "facebook"},
  {"language": "ko", "platform": "instagram", "target_id": "instagram"}
]
```

자동 게시 결과는 로그에 다음 형태로 저장됩니다.

- 전체 상태: 성공 / 부분 성공 / 실패
- 성공 플랫폼 수
- 실패 플랫폼 수
- 성공 플랫폼 목록
- 실패 플랫폼 목록
- 재시도 가능 플랫폼 목록
- 플랫폼별 원본 결과

## 6. 환경변수 요약

`.env`에 직접 설정하거나, 대부분의 값은 설정 화면에서 저장할 수 있습니다.

```env
GEMINI_API_KEY=your_gemini_api_key_here
AI_TEXT_PROVIDER=gemini
AI_TEXT_MODEL=gemini-3.5-flash
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GEMINI_TEXT_FALLBACK_MODELS=gemini-3.1-pro-preview,gemini-3-flash-preview,gemini-3.1-flash-lite,gemini-2.5-flash

WP_URL=https://your-blog.com
WP_USERNAME=your_wp_username
WP_PASSWORD=your_wp_app_password

BLOG_CLIENT_ID=your_google_client_id
BLOG_CLIENT_SECRET=your_google_client_secret
BLOG_ID=your_blogger_blog_id

TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
TELEGRAM_CHANNELS=[]

FACEBOOK_PAGE_ID=your_facebook_page_id
FACEBOOK_ACCESS_TOKEN=your_facebook_access_token
INSTAGRAM_ACCOUNT_ID=your_instagram_account_id
INSTAGRAM_ACCESS_TOKEN=your_instagram_access_token
TIKTOK_ACCESS_TOKEN=your_tiktok_access_token

HOST=127.0.0.1
PORT=8000
DEBUG=false
APP_LANG=ko
```

## 7. 실행 및 확인

설치:

```bash
pip install -r requirements.txt
```

실행:

```bash
python main.py
```

브라우저에서 접속:

```text
http://127.0.0.1:8000
```

헬스 체크:

```text
/api/health
/api/settings/social-health
```

## 8. 문제 해결

### 8.1 게시 성공 URL이 자동으로 열립니다

설정 화면에서 `게시 완료 후 작성된 글 자동 열기`를 끄면 됩니다.

### 8.2 소셜 연결 점검이 실패합니다

확인 항목:

- 토큰이 저장되어 있는지
- 토큰 권한이 충분한지
- Page ID / Account ID가 올바른지
- 플랫폼 앱이 필요한 심사 또는 권한을 통과했는지

### 8.3 TikTok 게시가 실패합니다

대부분 다음 원인입니다.

- `video_url`이 없음
- 비디오 URL이 외부에서 접근 불가
- TikTok API 권한 또는 앱 심사 제한

### 8.4 생성 결과가 너무 짧다는 오류가 납니다

AI가 `...`처럼 축약된 본문을 반환했거나 본문 길이가 너무 짧은 경우입니다.

해결 방법:

- 같은 주제로 다시 생성
- provider/model 변경
- 프롬프트가 될 주제를 더 구체적으로 입력
- API 키와 quota 확인

### 8.5 일부 플랫폼만 실패합니다

정상 동작일 수 있습니다. 앱은 부분 성공을 지원합니다.

- 성공한 플랫폼은 URL이 반환됩니다.
- 실패한 플랫폼은 `error_type`, `retryable`, `error`를 확인합니다.
- 로그 화면에서 실패 원인을 확인하고 재시도합니다.

## 9. 운영 주의사항

- 실제 API 키와 토큰은 Git에 커밋하지 마세요.
- SQLite DB 파일과 `.env`는 `.gitignore` 대상입니다.
- 외부 SNS 플랫폼은 API 정책과 권한 상태에 따라 동작이 달라질 수 있습니다.
- 로컬 URL은 외부 플랫폼에서 접근할 수 없으므로, 이미지/비디오는 공개 URL로 승격한 뒤 게시하는 것이 안전합니다.
- 자동 게시를 켜기 전에는 수동 게시로 각 플랫폼 연동을 먼저 확인하세요.
