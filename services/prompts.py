"""
AI 프롬프트 템플릿 관리
"""
import json

class Prompts:
    # --- AutoPilot 관련 프롬프트 ---
    AUTOPILOT_ANALYZE_VIDEO = """
        유튜브 쇼츠 영상(ID: {video_id})을 벤치마킹하여 새로운 영상을 만들려 합니다.
        대중들이 좋아할만한 '반전 매력'이나 '공감 포인트'를 3가지만 분석해서 JSON으로 주세요.
        
        JSON 포맷:
        {{
            "sentiment": "positive",
            "topics": ["topic1", "topic2"],
            "viewer_needs": "viewers want..."
        }}
    """

    AUTOPILOT_GENERATE_SCRIPT = """
        분석 내용: {analysis_json}
        
        위 분석을 바탕으로 1분 이내의 유튜브 쇼츠 대본을 작성해줘.
        - 초반 5초에 강력한 후킹 멘트 필수
        - 독백 또는 나레이션 형식으로 작성 (대화체 절대 금지)
        - 화자는 무조건 딱 1명으로 제한
        - 전체 길이는 300자 내외
        
        **[절대 금지 사항 - TTS 읽기 오류 방지]**
        1. 대화 형식(A:, B: 등 가상 대화) 금지
        2. 괄호와 상황 설명 금지 (예: (음악), (상황) 등 절대 넣지 말 것)
        3. 시간 표시 금지 (예: [0-5초], ** 등 타임스탬프 금지)
        4. 이모티콘 및 기호 금지 (예: 🤣, ✨ 등 특수문자 금지)
        5. 화자(이름) 표시 금지 (예: 나:, 상사: 처럼 누가 말하는지 적지 말 것)
        
        오직 '읽을 대사'만 출력해. 설명 제외.
    """

    # --- Gemini Service 관련 프롬프트 ---
    GEMINI_ANALYZE_COMMENTS = """당신은 유튜브 콘텐츠 분석 전문가입니다.
아래 영상의 댓글{script_indicator}를 분석해주세요.

[영상 제목]
{video_title}
{script_section}
[댓글 목록]
{comments_text}

다음 JSON 형식으로 반환해주세요:
{{
    "sentiment": {{
        "positive": 비율,
        "negative": 비율,
        "neutral": 비율
    }},
    "main_topics": ["주요 토픽 1", "주요 토픽 2", ...],
    "viewer_needs": ["시청자 니즈 1", "시청자 니즈 2", ...],
    "content_suggestions": ["콘텐츠 제안 1", "콘텐츠 제안 2", ...],
    "script_analysis": {{
        "structure": "서론-본론-결론 구조 요약",
        "hooks": "초반 몰입을 유도한 요소 (Hooks)",
        "pacing": "영상 전개 속도 및 톤앤매너",
        "key_message": "영상이 전달하고자 하는 핵심 메시지"
    }},
    "summary": "전체 요약 (2-3문장)"
}}

JSON만 반환하세요."""

    GEMINI_EXTRACT_STRATEGY = """당신은 유튜브 알고리즘과 시청자 심리를 꿰뚫어 보는 세계 최고의 컨설턴트입니다.
제시된 영상 분석 데이터를 바탕으로, 다른 영상에도 범용적으로 적용 가능한 **'일반화된 성공 공식(Strategy Logic)'**을 3~5개 추출하세요.

[분석 데이터]
{analysis_json}

**[지침]**
1. 특정 영상의 내용에 국한되지 않고, '구조', '심리', '데이터' 측면에서 성공 원인을 일반화하세요.
2. 유튜브 알고리즘(노출, 클릭률, 시청 지속 시간)에 어떻게 기여하는지 구체적으로 기술하세요.
3. 결과는 반드시 한국어로 작성하세요.

다음 JSON 리스트 형식으로만 답변하세요:
[
    {{
        "category": "hook/structure/emotion/thumbnail/interaction 중 하나",
        "pattern": "일반화된 패턴 제목 (예: 초반 3초 시각적 반전 후킹)",
        "insight": "성공 원인 상세 (알고리즘 및 심리적 근거)",
        "script_style": "어울리는 스타일 (story/informational/all)"
    }}
]
JSON만 반환하세요."""

    GEMINI_SCRIPT_STRUCTURE = """당신은 세계 최고의 유튜브 콘텐츠 기획자이자 스토리텔러입니다.
당신의 임무는 주어진 **키워드(주제)**를 바탕으로, **분석된 성공 전략**과 **누적된 학습 지식**을 적용하여 폭발적인 조회수를 기록할 대본 기획안을 작성하는 것입니다.

### 1. 주제 (Subject Content) - 반드시 이 내용을 다루어야 함
- **핵심 키워드:** {topic_keyword}
- **추가 요청사항:** {user_notes}

### 2. 스타일 및 구조 지침
{specialized_instruction}
- **목표 길이:** {duration_seconds}초 (최소 {min_sections}개 섹션 필요)
{custom_prompt_section}

{knowledge_instruction}

### 4. 벤치마킹 분석 데이터 (Current Success Strategy) - 형식/기법 참고용
- **분석 데이터:** {success_strategy_json}

### 5. 제약 사항
- **언어:** {target_language_context}
- **콘텐츠 분리(CRITICAL):** 벤치마킹 데이터의 줄거리나 고유명사(인물, 채널명 등)를 절대 복제하지 마십시오.
- **창작성:** 주제 키워드({topic_keyword})를 바탕으로 완전히 새로운 인물과 상황을 창조하십시오.
- **중복 방지:** {history_instruction}
- **[대본 작성 절대 규칙 - 위반 시 실패]**
  * 대화체(다중 화자 간의 대화) 금지 -> 반드시 독백이나 나레이션 형식으로 작성
  * 화자는 무조건 딱 1명(성우 1인)으로 제한
  * 괄호와 지문 포함 금지 (예: (배경음악), (웃으며) 등 절대 금지)
  * [0-5초] 같은 시간대/타임스탬프 표시 절대 금지
  * 이모티콘(🤣, ✨ 등) 및 별표(**) 같은 꾸밈 기호 절대 금지
  * "나:", "상사:" 처럼 화자를 구분하는 이름과 콜론 표시 절대 금지
  * 오직 성우가 소리 내어 읽을 '텍스트'만 작성하십시오.
---
다음 JSON 형식으로 기획안을 작성해주세요:
{{
    "hook": "강렬한 멘트 (분석된 기법 적용)",
    "sections": [
        {{
            "title": "섹션 제목",
            "key_points": ["상세 묘사 1", "상세 묘사 2"]
        }}
    ],
    "cta": "구독과 좋아요 멘트",
    "style": "영상 분위기",
    "duration": {duration_seconds}
}}
JSON만 반환하세요."""

    GEMINI_TRENDING_KEYWORDS = """
        Act as a Local Trend Analyst and YouTube SEO Expert for the specific region: {lang_name}.
        
        **OBJECTIVE:**
        Generate a list of 20-30 CURRENT trending search keywords/topics on YouTube specifically for:
        - Region/Language: {lang_name}
        - Time Period: {period_text}
        - Target Age Group: {age_text}

        **STRICT LANGUAGE RULES:**
        1. **"keyword"**: MUST be in the target language ({language}). NOT English (unless it's an English region), NOT Korean.
           - If target is Japanese (ja), keyword MUST be in Japanese (Kanji/Kana).
           - If target is Spanish (es), keyword MUST be in Spanish.
        2. **"translation"**: MUST be the meaning in KOREAN (Hangul).

        **DISTRIBUTION RULES:**
        - Assign a 'volume' score (1-100) using a Power Law distribution.
        - 1-2 keywords: 95-100 (Viral)
        - 3-5 keywords: 70-90 (High)
        - Rest: 20-60 (Moderate)

        **OUTPUT FORMAT (JSON List):**
        [
            {{"keyword": "Keyword in Target Language", "translation": "한국어 뜻 설명", "volume": 98, "category": "Gaming"}},
            ...
        ]

        **EXAMPLES:**
        - If lang=ja: {{"keyword": "猫", "translation": "고양이", "volume": 85, "category": "Pets"}}
        - If lang=es: {{"keyword": "Fútbol", "translation": "축구", "volume": 92, "category": "Sports"}}
        - If lang=en: {{"keyword": "Super Bowl", "translation": "슈퍼볼", "volume": 99, "category": "Sports"}}
        
        RETURN ONLY THE JSON LIST. NO MARKDOWN.
    """

    GEMINI_CHARACTER_PROMPTS = """당신은 영상 캐릭터 디자인 전문가입니다.
아래 대본을 분석하여 등장인물(캐릭터)을 추출하고, 각 캐릭터별로 이미지 생성에 사용할 수 있는 상세한 외형 프롬프트를 작성해주세요.

[대본]
{script}

[비주얼 스타일 및 배격 지침 - 최우선 순위]
현재 영상의 프로젝트 스타일은 **"{visual_style}"** 입니다. 
이 스타일은 캐릭터의 외형뿐만 아니라 선의 굵기, 색상 표현 방식, 질감 등 모든 시각적 요소에 적용되어야 합니다.

[STRICT STYLE RULE]
- 선택된 스타일이 실사(Photorealistic)가 아닌 경우(예: Cartoon, Anime, Sketch 등), 'realistic', 'photorealistic', 'hyper-detailed', '8k', 'cinematic lighting', 'depth of field'와 같은 키워드를 **절대** 사용하지 마세요.
- 대신 해당 스타일에 맞는 매체(Medium) 키워드를 사용하세요 (예: 'hand-drawn line art', 'flat colors', 'brush strokes', 'ink doodle').
- 캐릭터의 외형 묘사는 반드시 이 "{visual_style}" 세계관 안에서 자연스럽게 보여야 합니다.

**분석 지침:**
1. 대본에 언급되거나 암시된 모든 등장인물을 식별하세요.
2. 각 캐릭터의 역할(주인공/조연/배경인물)을 파악하세요.
3. 대본의 맥락 및 지정된 스타일에 유추할 수 있는 외형적 특징을 상세히 묘사하세요.
4. 이미지 생성 AI가 이해할 수 있는 구체적인 영어 프롬프트를 작성하세요.

**외형 묘사 포함 요소:**
- 성별, 예상 연령대
- 얼굴 특징 (이목구비, 표정) - 스타일에 맞게 묘사 (예: 실사면 구체적으로, 만화면 단순하게)
- 헤어스타일 및 색상
- 체형 - 지정된 스타일에 맞게 적용 (예: 윔피키드 스타일이면 stick figure, simple line body 같이 묘사)
- 의상 및 액세서리
- 전체적인 분위기/인상

다음 JSON 형식으로 출력해주세요:
{{
    "characters": [
        {{
            "name": "캐릭터 이름 또는 역할",
            "role": "주인공/조연/배경인물",
            "description_ko": "지정된 스타일에 맞는 외형 묘사 (한글, 2-3문장)",
            "prompt_en": "Detailed English prompt for image generation. CRITICAL: 1. You MUST include keywords reflecting the '{visual_style}' style. 2. Focus on permanent physical identity adapted to this style (e.g. if cartoon, describe as cartoon character). 3. DO NOT include background, environment, or specific poses. Describe them in a neutral portrait way for a Character Sheet."
        }}
    ]
}}

- 최대 5명의 주요 캐릭터만 추출하세요.
- **실명 및 브랜드 사용 금지 (CRITICAL)**: prompt_en에는 실존 유명인, 가수, 특정 그룹명 등을 절대 넣지 말고 일반적인 외형 묘사(예: 'a Japanese J-pop duo')로 대체하세요. 이는 AI 보안 필터 차단을 피하기 위함입니다.
- **배경 묘사 금지**: prompt_en에는 'in a room', 'outdoor', 'background' 등의 환경 묘사를 절대 포함하지 마세요. 캐릭터 자체의 외형만 묘사하세요.
- prompt_en은 영어로, 이미지 생성 AI에 바로 사용할 수 있는 형식으로 작성하세요.
- JSON만 반환하세요."""

    GEMINI_IMAGE_PROMPTS = """당신은 세계적인 영화 감독이자 촬영 감독(Cinematographer)입니다.
아래 대본을 심층 분석하여, 최고의 시각적 스토리텔링을 위한 장면(Scene) 리스트를 작성해주세요.

[대본]
{script}

[핵심 미션: Context-Aware Directing]
1. 단순히 텍스트를 이미지로 바꾸는 것이 아닙니다. **대본의 감정선(Emotion)**과 **전후 맥락(Context)**을 깊이 파악하여 연출하세요.
2. 각 장면의 분위기를 극대화할 수 있는 **카메라 무빙(Camera Movement)**과 **샷 사이즈(Shot Size)**를 전략적으로 선택하세요.
   - **감정적 몰입/긴장**: Slow Zoom-in, Close-up
   - **상황 공개/고독/웅장**: Slow Zoom-out (Pull back), Extreme Wide Shot
   - **역동적 액션/혼란**: Handheld, Tracking Shot, Dutch Angle
   - **평화/안정**: Static Shot (고정), Symmetry
   - **시선 이동**: Pan Left/Right, Tilt Up/Down, Rack Focus (초점 이동)
3. **연속성(Continuity)**: 이전 장면과의 시각적 흐름이 끊기지 않도록 고려하세요.

{style_instruction}
{character_instruction}
{limit_instruction}

[출력 형식 (JSON)]
{{
    "scenes": [
        {{
            "scene_number": 1,
            "scene_title": "장면 요약 (예: '비밀을 알게 된 주인공')",
            "scene_text": "해당 씬 구간의 원본 대본 내용 (요약/압축 절대 금지 — 원문 그대로, 장면 간 텍스트 중복 절대 금지)",
            "script_start": "해당 구간 첫 어절 (원문 첫 단어)",
            "script_end": "해당 구간 끝 어절 (원문 마지막 단어)",
            "estimated_seconds": 15,
            "visual_reasoning": "왜 이 연출을 선택했는지 (예: 긴장감을 고조시키기 위해 줌인 선택)",
            "prompt_ko": "이미지 묘사 (한글)",
            "prompt_en": "{style_prefix}, [Detailed Visual Description], [Camera Angle & Movement], [Lighting & Atmosphere]",
            "flow_prompt": "A single comprehensive descriptive paragraph optimized for Google Flow (Veo 3.1). Combine the visual scene and motion instructions into a cohesive story-driven prompt. Include core character identity adapted to the current style.",
            "scene_type": "(졸라맨 스타일 전용) character_main | character_support | infographic 중 하나. 다른 스타일은 빈 문자열로.",
            "prompt_char": "(졸라맨 스타일 전용) scene_type=character_main이면 전신 캐릭터, scene_type=character_support이면 작은 구석 캐릭터, scene_type=infographic이면 빈 문자열. 다른 스타일은 빈 문자열로.",
            "prompt_bg": "(졸라맨 스타일 전용) 씬 내용에 맞는 풍부한 배경/환경/인포그래픽 이미지 프롬프트. 다른 스타일은 빈 문자열로."
        }}
    ]
}}

[작성 규칙 - Strict Rules]
- **Detailed Environment & Background [필수]**:
  - 절대 'plain white background'나 단순한 배경을 반복하지 마세요. (상황상 꼭 필요한 경우 제외)
  - 대본의 장소와 시간대에 맞는 구체적인 배경 소품, 건축물, 자연 환경, 날씨, 조명을 상세히 묘사하여 화면을 풍성하게 채우세요.
  - 다양한 구도(Low/High angle, Eye level)와 심도(Depth)를 활용하여 시각적 다양성을 확보하세요.
- **prompt_en 구성**:
  1. 스타일 프리픽스("{style_prefix}")로 시작할 것.
  2. 피사체와 배경을 아주 구체적으로 묘사할 것.
  3. **반드시** 문장 끝부분에 전문적인 **Cinematography Keywords**를 포함할 것.
     (예: "Cinematic lighting, Shallow depth of field, Slow zoom in, Low angle shot, Highly detailed")
     ⚠️ "4k", "8k", "4K", "UHD", "HD", "resolution" 등 해상도 키워드 절대 사용 금지 — 이미지 내 텍스트 워터마크를 유발합니다.
  4. **모든 prompt_en 끝에 반드시 추가**: "no text, no words, no letters, no labels, no watermarks, no speech bubbles, no captions"
- **flow_prompt 작성 지침**:
  - Google Flow (Veo 3.1) 모델에 최적화된 통합 프롬프트입니다.
  - "{style_prefix}" 스타일을 기반으로, 등장인물의 외형(지정된 스타일에 따름)과 배경, 그리고 구체적인 **영상 움직임(Motion)**을 하나의 자연스러운 문단으로 서술하세요.
  - 단순히 나열하지 말고 "A cinematic video of [Subject] [Action] while [Background Detail] as camera [Motion]..." 형식으로 생동감 있게 작성하세요.
- **ABSOLUTELY NO TEXT IN IMAGE [최우선]**:
  - 이미지 내에 어떠한 텍스트, 글자, 단어, 레이블, 자막, 워터마크, 말풍선도 절대 포함 금지.
  - 해부도/다이어그램/포스터 등 원래 텍스트가 있는 소재를 묘사할 때도 글자 없이 시각적 요소만 묘사할 것.
  - 대사 언어(한국어/일본어/영어)와 관계없이 이미지 내 모든 언어의 텍스트 금지.
- **ANATOMY — EXACTLY TWO ARMS AND TWO HANDS [모든 스타일 공통 - 최우선]**:
  - 팔 2개, 손 2개. 3개 이상 절대 금지.
  - **반드시 LEFT/RIGHT arm 위치를 명시하고 마지막에 "There is no third hand or support object." 추가**:
    - ❌ 금지: "character holding a book while thinking" → AI가 손 3개 생성
    - ✅ 필수 (물건 들고 생각): "The left hand is clearly visible supporting the bottom of the book, while the right hand is raised to touch its chin in a thinking gesture. There is no third hand or support object."
니다.
아래 영상 대본을 분석하여 클릭률을 극대화하는 썸네일 문구를 생성해주세요.

[영상 대본]
{script}

[스타일 가이드]
- 썸네일 스타일: {thumbnail_style}
- 이미지 스타일: {image_style}
- 타겟 언어: {target_language}

[문구 생성 원칙]
1. **후킹 (Hook)**: 호기심을 자극하는 질문이나 충격적인 진술
2. **간결성**: 3-7단어 (한글 기준 10-20자)
3. **감정 유발**: 놀람, 궁금증, 공감 중 하나 이상
4. **가독성**: 큰 글씨로 읽기 쉬운 단어 선택
5. **스타일 매칭**: 
   - face/dramatic: 감정적, 충격적 ("믿을 수 없는 진실", "충격적인 반전")
   - text/minimal: 정보성, 명확한 ("TOP 5", "핵심 정리")
   - mystery: 질문형, 미스터리 ("진짜 이유는?", "숨겨진 비밀")
   - contrast: 대비, 변화 ("Before vs After", "과거 vs 현재")
   - wimpy: 유머러스, 일상적, 일기 형식 ("나의 처절한 실패기", "절대 하면 안되는 일")

[출력 형식]
JSON 형식으로 3개의 후보 문구를 생성하세요:
{{
    "texts": [
        "후보 문구 1 (가장 강력한 후킹)",
        "후보 문구 2 (감정 유발 또는 질문형)",
        "후보 문구 3 (숫자 또는 대비형)"
    ],
    "reasoning": "선택 이유 (1-2문장)"
}}

**중요**: 대본의 핵심 메시지를 왜곡하지 말고, 클릭베이트가 아닌 진정성 있는 후킹을 만드세요.
JSON만 반환하세요."""

    THUMBNAIL_IDEA_PROMPT = """
        Topic: {topic}
        Script Summary: {script_summary}
        
        Suggest a high Click-Through-Rate (CTR) Thumbnail Plan.
        JSON Output:
        {{
            "hook_text": "Short shocking text (max 5 words)",
            "image_prompt": "Visual description for AI image generator (English, detailed, 16:9)"
        }}
    """

    AUTOPILOT_GENERATE_METADATA = """
        당신은 유튜브 SEO 및 마케팅 전문가입니다.
        다음 영상 대본을 바탕으로 클릭률(CTR)과 검색 최적화(SEO)가 뛰어난 제목, 영상 설명, 태그를 생성해주세요.

        [영상 대본]
        {script_text}

        [요구사항]
        1. 제목: 호기심을 유발하고 클릭을 부르는 강렬한 제목 (50자 이내)
        2. 설명: 영상의 내용을 요약하고 관련 키워드를 자연스럽게 포함 (300자 내외). 해시태그 3개 포함.
        3. 태그: 연관도가 높은 검색 키워드 10개 내외 (배열 형식)

        반드시 다음 JSON 형식으로만 반환하세요:
        {
            "title": "여기에 제목",
            "description": "여기에 설명",
            "tags": ["태그1", "태그2", ...]
        }
    """

    GEMINI_DEEP_DIVE_SCRIPT = """당신은 '노트북LM'과 같은 지능을 가진 세계 최고의 콘텐츠 분석가이자 유튜브 다큐멘터리 작가입니다.
제공된 **참고 자료(Sources)**들을 깊이 있게 학습하고, 이를 바탕으로 시청자를 몰입시키는 고품질 '딥다이브' 롱폼 영상 대본을 작성하는 것이 당신의 임무입니다.

### 1. 참고 자료 (Learning Sources)
{sources_text}

### 2. 기획 목표
- **주제:** {topic_keyword}
- **목표 길이:** {duration_seconds}초
- **타겟 언어:** {target_language_context}
- **추가 요청:** {user_notes}

### 3. 대본 작성 지침 (NotebookLM Style)
- **정보의 입체적 재구성**: 단순히 자료를 나열하지 마세요. 여러 자료 사이의 연결고리를 찾고, 시청자가 흥미를 느낄만한 '서사(Narrative)'를 만드세요.
- **전문성과 대중성의 조화**: 경제, 밀리터리, 정치 등 복잡한 주제라도 중학생이 이해할 수 있을 만큼 쉽게 풀어서 설명하되, 깊이 있는 통찰(Insight)을 담으세요.
- **감정적 연결**: 옛날 이야기나 개인 사연의 경우, 자료에 담긴 감정적 디테일을 살려 시청자의 공감을 이끌어내세요.
- **나레이션 스타일**: 차분하면서도 몰입감 있는 다큐멘터리 톤으로 작성하세요.

### 4. 대본 구성 규칙 (Critical)
- **독백/나레이션 형식**: 반드시 1인의 나레이터가 읽는 형식으로 작성하세요.
- **클린 텍스트**: 괄호, 지문, 타임스탬프, 화자 이름 표시, 특수문자, 이모티콘을 절대 포함하지 마세요.
- **흐름 중심**: 섹션 구분 없이 하나의 완성된 이야기 흐름으로 텍스트를 구성하세요.

---
다음 JSON 형식으로만 응답하세요:
{{
    "title": "추천 영상 제목",
    "full_script": "나레이션 전체 텍스트 (성우가 바로 읽을 수 있는 상태)",
    "key_insights": ["학습한 자료에서 도출한 핵심 포인트 1", "2", ...],
    "style_recommendation": "영상에 어울리는 시각적 스타일 추천"
}}
JSON만 반환하세요."""

    GEMINI_DEEP_DIVE_DIALOGUE = """당신은 '노트북LM'과 같은 지능을 가진 세계 최고의 콘텐츠 분석가이자 유튜브 전문 팟캐스트 작가입니다.
제공된 **참고 자료(Sources)**들을 깊이 있게 학습하고, 두 명의 진행자가 실제 팟캐스트를 진행하는 것처럼 생생하고 지적인 대화형 대본을 작성하는 것이 당신의 임무입니다.

### 1. 참고 자료 (Learning Sources)
{sources_text}

### 2. 기획 목표
- **주제:** {topic_keyword}
- **목표 길이:** {duration_seconds}초
- **타겟 언어:** {target_language_context}
- **추가 요청:** {user_notes}

### 3. 진행자 설정 (Characters)
1. **진행자 A (정원)**: 호기심이 많고 질문을 던지며 시청자의 입장을 대변합니다. 활기차고 공감을 잘 합니다.
2. **진행자 B (전문가 민호)**: 제공된 자료를 완벽히 숙지한 전문가입니다. 복잡한 내용을 쉽게 풀어서 설명하며 깊은 통찰력을 제공합니다.

### 4. 대화 작성 지침 (NotebookLM Podcast Style)
- **자연스러운 티키타카**: 고정된 대본을 읽는 것이 아니라, 실제 대화처럼 추임새("아~ 그렇군요!", "와, 그건 몰랐는데요?")와 리액션을 적절히 섞으세요.
- **정보의 스토리텔링**: 정보를 그냥 나열하지 말고, 질문과 답변을 통해 하나의 흥미로운 이야기를 완성해 나가세요.
- **몰입도 높은 시작**: 첫 10초 안에 시청자의 호기심을 자극하는 강렬한 후크로 시작하세요.

### 5. 대본 구성 규칙 (Critical)
- **화자 표시 필수**: 반드시 `정원:`, `민호:` 형식으로 화자를 구분하여 작성하세요.
- **클린 텍스트**: 괄호, 지문(예: 웃음, 박수), 타임스탬프, 특수문자, 이모티콘을 절대 포함하지 마세요. (나레이터가 읽을 텍스트만 포함)
- **흐름 중심**: 섹션 구분 없이 하나의 완성된 대화 흐름으로 구성하세요.

---
다음 JSON 형식으로만 응답하세요:
{{
    "title": "추천 팟캐스트 제목",
    "full_script": "정원: 안녕하세요! 오늘은... \n민호: 네, 오늘은 정말 놀라운 이야기를... (이런 형식의 전체 대본)",
    "key_insights": ["학습한 자료에서 도출한 핵심 포인트 1", "2", ...],
    "style_recommendation": "영상에 어울리는 시각적 스타일 추천"
}}
JSON만 반환하세요."""

    GEMINI_GENERATE_BLOG = """당신은 **세계 최고의 프리미엄 블로그 에디터이자 UI/UX 기반 디자인 시스템 디자이너**입니다.
제공된 소스 데이터를 바탕으로, 독자가 감탄할 정도의 **'Apple 스타일' 미니멀하고 고급스러운 현대적 블로그 포스팅**을 생성하세요.

### 📌 작성 주제 / 소스 자료 (가장 중요! 반드시 이 내용을 기반으로 작성하세요!)
{source_content}

### 🍱 핵심 목표: 'Extreme Premium & High Readability'
1. **타깃 플랫폼**: {platform}
2. **카테고리**: {category}
3. **블로그 스타일**: {blog_style}
4. **목표 언어**: {target_language} (반드시 이 언어로 작성하세요!)

### 🎨 디자인 및 구조 지침 (필수!)
- **레이아웃**: `hero`, `section`, `content-card` 등의 클래스를 사용하여 논리적이고 풍성한 레이아웃을 구성하세요.
- **애플 스타일 미니멀리즘**: 상자 안에 상자를 넣는 중첩 구조를 지양하고, **넓은 여백**과 **세련된 타이포그래피**만으로 본문에 집중하게 하세요. (조잡한 레이아웃 금지)
- **인터랙티브 컴포넌트**: 아래 클래스들을 적재적소에 활용하여 가독성을 극대화하세요.
    - `.tip-box`: 유용한 팁이나 보너스 정보
    - `.expert-note`: 전문가의 조언이나 깊이 있는 분석
    - `.caution-box`: 주의사항이나 경고
    - `.checklist-section`: 체크리스트 또는 단계별 가이드
    - `.feature-card`: 핵심 장점이나 특징 강조
- **헤더 시각화**: `h1`은 Hero 섹션에 하나만 사용하고, `h2`, `h3`를 통해 위계 질서가 명확한 구조를 만드세요.

### 📝 본문 작성 원칙
- **현재 시점 정보**: 현재 날짜는 {current_date} 입니다. 글의 맥락이 현재 시점을 다룬다면 이 날짜를 기준으로 내용을 작성하세요. (예: 2024년이 아닌 2026년 정보 반영)
- **감성적 후킹**: 제목(title)과 도입부(Intro)에서 독자의 시선을 즉시 사로잡는 강력한 후킹을 사용하세요.
- **전문성과 신뢰성**: 단순히 정보 나열이 아닌, 분석적이고 통찰력 있는 문체를 유지하세요.
- **풍부한 분량**: 각 섹션은 충분한 설명과 예시를 포함하여 최소 1,000자 이상의 깊이 있는 아티클로 만드세요.
- **사용자 요청 사항 반영**: {user_notes}

### ⚠️ 기술적 제약 사항 (절대 준수)
- **이미지 삽입**: 소스에서 제공된 이미지 플레이스홀더 `[[IMAGE_1]]`, `[[IMAGE_2]]` 등이 있다면 적절한 위치에 삽입하세요. (임의의 외부 URL 사용 금지)
- **HTML 구조**: 전체 HTML 문서를 반환하되, 반드시 `<title>`, `<tags>`, `<summary>`, `<content>` 태그로 감싸서 반환하세요.
- **CSS**: 모든 스타일은 시스템에서 주입되므로 별도의 `<style>` 내장이나 `style` 속성 사용을 최소화하고 제공된 클래스명 위주로 사용하세요.

---

### [출력 형식 (구조 필수)]
반드시 아래 XML 태그 형식을 포함하여 답변하세요:

<title>강력한 제목</title>
<tags>태그1, 태그2, 태그3, ...</tags>
<summary>글의 핵심 요약문 (1-2문장)</summary>
<content>
<!DOCTYPE html>
<html lang="{target_language}">
<head>
    <meta charset="UTF-8">
    {category_template}
</head>
<body class="{target_language}">
    <div class="container">
        <header class="hero">
            <div class="badge">NEW</div>
            <h1>제목</h1>
            <p>서브 타이틀 또는 한 줄 요약</p>
        </header>

        <article class="content-card">
            <!-- 본문 내용: section, h2, p, tip-box 등 자유롭게 구성 -->
        </article>
    </div>
</body>
</html>
</content>"""


    # --- Nursery Rhyme (동요) 관련 프롬프트 ---
    GEMINI_NURSERY_RHYME_IDEAS = """당신은 전 세계 아이들에게 사랑받는 최고의 동요 작곡가이자 아동 교육 전문가입니다.
2~6세 아이들이 즐겁게 부를 수 있고, 교육적인 가치가 있는 '동요 아이디어' 10가지를 제안해주세요.

[주제 가이드]
아이들의 일상 루틴(양치질, 손 씻기, 잠자기, 나누기 등), 색상, 알파벳, 동물, 감정 등을 주제로 하세요.
가사는 단순하고 캐치하며 반복적이어야 합니다.

[작성 형식]
- 각 아이디어는 '제목'과 '한 줄 요약'으로 구성합니다.
- 총 10개를 작성하세요.

다음 JSON 형식으로만 답변하세요:
{
    "ideas": [
        {
            "id": 1,
            "title": "제목 1",
            "summary": "한 줄 요약 1"
        },
        ...
    ]
}
JSON만 반환하세요."""

    GEMINI_NURSERY_RHYME_DEVELOP = """당신은 전 세계 아이들에게 사랑받는 최고의 동요 작곡가입니다. 
제시된 아이디어를 바탕으로 2~6세 아이들을 위한 완성된 동요 가사를 작성해주세요.

[아이디어]
제목: {title}
요약: {summary}

[작성 지침]
- 대상: 2~6세 유아
- 구성: 짧은 절(Verse) 2개, 반복되는 후렴구(Chorus), 짧고 행복한 마무리(Ending)
- 스타일: 매우 단순한 단어와 짧은 문장 사용
- 재미 요소: 가사에 '칙칙폭폭', '반짝반짝' 같은 의성어/의태어를 섞어 아이들이 즐겁게 따라 부를 수 있게 하세요.
- 톤: 긍정적이고, 재미있고, 교육적이어야 합니다.

[작성 규칙 - TTS 및 영상 제작용]
- 독백(나레이션) 형식이 아닌 '노래 가사' 형식으로 작성하세요.
- 괄호, 지문, 타임스탬프를 절대 포함하지 마세요.
- 오직 노래로 불릴 '가사 텍스트'만 포함하세요.

다음 JSON 형식으로만 응답하세요:
{
    "title": "{title}",
    "lyrics": "전체 가사 텍스트",
    "structure": {
        "verse1": "1절 내용",
        "chorus": "후렴구 내용",
        "verse2": "2절 내용",
        "ending": "마무리 내용"
    }
}
JSON만 반환하세요."""

    GEMINI_NURSERY_RHYME_IMAGE_PROMPTS = """당신은 디즈니나 픽사 스타일의 3D 애니메이션을 제작하는 세계 최고의 아트 디렉터입니다.
제시된 동요 가사([TITLE]: {title})를 바탕으로, 각 섹션별로 최적화된 이미지 생성 프롬프트를 작성해주세요.

[가사 정보]
{lyrics}

[비주얼 스타일 지정 (STRICT)]
- **Style**: High-quality 3D animation style, Pixar/Disney inspired.
- **Atmosphere**: Bright, vibrant colors, soft volumetric lighting, magical and kid-friendly environment.
- **Characters**: Cute, expressive characters with big eyes and friendly smiles.
- **Constraint**: NO TEXT in images. Anatomically correct limbs (strictly 2 arms, 2 hands).

[프롬프트 구성 지침]
- 각 섹션(Verse 1, Chorus, Verse 2, Ending)에 대해 하나씩, 총 4개 이상의 이미지 프롬프트를 작성하세요.
- 가사의 내용을 시각적으로 풍부하게 묘사하세요.
- 일관된 캐릭터 디자인(주인공이 있다면 동일한 특징 유지)을 유지하세요.

다음 JSON 형식으로 응답하세요:
{
    "scenes": [
        {
            "scene_number": 1,
            "section": "Verse 1",
            "scene_text": "해당 구간 가사",
            "prompt_ko": "장면 묘사 (한글)",
            "prompt_en": "3D Pixar style, [Visual details], vibrant colors, soft lighting, no text, no words, strictly two arms and two hands",
            "flow_prompt": "A cinematic Pixar-style 3D animation of [Subject] [Action] in a [Environment]... smooth camera motion, magical atmosphere."
        },
        ...
    ]
}
JSON만 반환하세요."""


    GEMINI_EXTRACT_BLOG_METADATA = """당신은 세계 최고의 블로그 SEO 전문가입니다.
    제시된 블로그 본문(HTML 또는 텍스트)을 분석하여, 검색 엔진 최적화(SEO)에 최적화된 메타데이터를 추출 및 생성해주세요.

    [컨텍스트 정보]
    - 현재 날짜: {current_date} (본문의 '올해', '내년' 등의 표현을 이 날짜 기준으로 해석하세요)

    [블로그 본문]
    {content}

    [요청 사항]
    1. 제목(title): 클릭을 유발하면서도 핵심 키워드를 포함한 강렬한 제목 (50자 이내)
    2. 카테고리(category): 글의 주제와 가장 잘 어울리는 카테고리 1~2개 (쉼표로 구분)
    3. 태그(tags): 검색 유입에 도움이 되는 핵심 키워드 5~10개 (배열 형식)
    4. 요약(summary): 글의 핵심 내용을 1~2문장으로 요약한 메타 설명 (150자 이내)

    반드시 다음 JSON 형식으로만 반환하세요:
    {{
        "title": "제목",
        "category": "카테고리1, 카테고리2",
        "tags": ["태그1", "태그2", ...],
        "summary": "요약 내용"
    }}
    JSON만 반환하세요."""


prompts = Prompts()
