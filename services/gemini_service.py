"""
Gemini API 서비스 (블로그 앱 전용)
- 텍스트 생성 (블로그 본문, 메타데이터 분석 등)
- 이미지 생성 (Imagen)
- 트렌드/아마존 리뷰 보조 생성

블로그 본문 생성 로직은 services.gemini_blog_content_service 로 분리되어 있으며,
이 클래스의 generate_blog_content 가 위임한다.
"""
import httpx
from typing import Any, Dict, List
import base64
import os
import json
import re
import database as db

from config import config
from services.prompts import prompts
from services.gemini_blog_content_service import GeminiBlogContentService


class GeminiService:
    HUMAN_SUBJECT_KEYWORDS = (
        "person", "people", "human", "man", "woman", "boy", "girl", "adult", "child",
        "character", "portrait", "face", "model", "student", "worker", "doctor",
        "teacher", "family", "couple", "bride", "groom", "athlete", "singer", "actor"
    )
    ANATOMY_GUARDRAIL = (
        " exactly one person, no extra people, exactly two arms, exactly two hands, "
        "five fingers on each hand, anatomically correct hands, anatomically correct arms, "
        "natural human proportions, no extra limbs, no duplicate arms, no duplicate hands, "
        "no fused fingers, no distorted fingers, no cropped hands, hands fully visible"
    )

    def __init__(self):
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.blog_content_service = GeminiBlogContentService(
            generate_text_fn=self.generate_text,
            cultural_context_fn=self.get_cultural_context,
            hooking_strategy_fn=self.get_hooking_strategy,
        )

    @property
    def api_key(self):
        return config.GEMINI_API_KEY

    @property
    def selected_provider(self) -> str:
        return str(getattr(config, "AI_TEXT_PROVIDER", "gemini") or "gemini").strip().lower()

    @property
    def selected_model(self) -> str:
        return str(getattr(config, "AI_TEXT_MODEL", "") or "").strip()

    def _provider_model_options(self, provider: str) -> List[str]:
        options = getattr(config, "AI_TEXT_MODEL_OPTIONS", {}).get(provider, [])
        return [item["id"] for item in options if item.get("id")]

    @classmethod
    def _mentions_human_subject(cls, prompt: str) -> bool:
        normalized = str(prompt or "").lower()
        return any(keyword in normalized for keyword in cls.HUMAN_SUBJECT_KEYWORDS)

    @classmethod
    def _apply_anatomy_guardrail(cls, prompt: str, no_human: bool) -> str:
        prompt = str(prompt or "").strip()
        if not prompt:
            return prompt
        if no_human or not cls._mentions_human_subject(prompt):
            return prompt
        if "exactly two arms" in prompt.lower():
            return prompt
        return f"{prompt.rstrip(' ,.')},{cls.ANATOMY_GUARDRAIL}"

    @staticmethod
    def _normalize_model_name(model: str) -> str:
        model = str(model or "").strip()
        if model.startswith("models/"):
            model = model[len("models/"):]
        return model

    def _resolve_text_models(self, provider: str, model_override: str = "") -> List[str]:
        configured = self._normalize_model_name(model_override or self.selected_model)
        provider_options = self._provider_model_options(provider)
        candidates = [configured] + provider_options

        if provider == "gemini" and not model_override:
            fallback_raw = getattr(config, "GEMINI_TEXT_FALLBACK_MODELS", "")
            candidates.extend([m.strip() for m in str(fallback_raw).split(",")])

        models = []
        for model in candidates:
            model = self._normalize_model_name(model)
            if model and model not in models:
                models.append(model)

        return models or provider_options or ["gemini-3.5-flash"]

    @property
    def text_models(self) -> List[str]:
        return self._resolve_text_models(self.selected_provider, self.selected_model)

    def _text_api_key(self, provider: str) -> str:
        if provider == "openai":
            return getattr(config, "OPENAI_API_KEY", "")
        if provider == "anthropic":
            return getattr(config, "ANTHROPIC_API_KEY", "")
        if provider not in ("gemini", "openai", "anthropic"):
            return self._get_custom_api_key(provider)
        return getattr(config, "GEMINI_API_KEY", "")

    @staticmethod
    def _provider_label(provider: str) -> str:
        return {"openai": "OpenAI", "anthropic": "Claude", "gemini": "Gemini"}.get(provider, provider)

    @staticmethod
    def _looks_like_auth_error(error: Exception) -> bool:
        message = str(error).lower()
        return any(token in message for token in [
            "api key",
            "x-api-key",
            "authentication",
            "unauthenticated",
            "permission_denied",
            "invalid",
            "인증",
            "키",
            "401",
            "403",
        ])

    async def generate_text(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        use_web_search: bool = False,
        provider_override: str = "",
        model_override: str = "",
    ) -> str:
        """텍스트 생성 - 모든 설정된 provider의 키가 없으면 자동 최대 프로바이더 포랫백을 시도합니다."""
        # provider_override가 지정된 경우 해당 provider만 사용, 실패시 모든 가능한 provider를 순서 시도
        if provider_override:
            provider = provider_override.strip().lower()
        else:
            provider = str(self.selected_provider or "gemini").strip().lower()

        custom_info = None
        if provider not in ("gemini", "openai", "anthropic"):
            custom_info = self._get_custom_provider(provider)
            if not custom_info and not provider_override:
                provider = "gemini"

        # 지정된 provider가 가능하며 provider_override가 없으면 바로 사용
        if self._text_api_key(provider):
            try:
                result = await self._call_provider(
                    provider,
                    prompt,
                    temperature,
                    max_tokens,
                    use_web_search,
                    model_override,
                    custom_info=custom_info,
                )
                return result
            except Exception as e:
                if provider_override:
                    raise  # caller가 확정지정했으며 실패하면 그대로 전파4
                print(f"[GeminiService] {self._provider_label(provider)} failed: {e}. Trying fallback providers...")
        else:
            if provider_override:
                label = self._provider_label(provider)
                raise Exception(f"{label} API 키가 설정되지 않았습니다.")
            print(f"[GeminiService] {self._provider_label(provider)} key not set. Trying fallback providers...")

        # 프로바이더 포랫백 체인: 지정된 provider 보다 다른 가능한 provider를 순서 시도
        fallback_order = [p for p in self._get_provider_priority_list() if p.get("name", "").lower() != provider]
        for fb in fallback_order:
            fb_provider = str(fb.get("name") or "").strip().lower()
            fb_custom_info = None if fb.get("is_builtin") else fb
            if self._text_api_key(fb_provider):
                try:
                    print(f"[GeminiService] Falling back to {self._provider_label(fb_provider)}...")
                    result = await self._call_provider(
                        fb_provider,
                        prompt,
                        temperature,
                        max_tokens,
                        use_web_search,
                        model_override or str(fb.get("default_model") or ""),
                        custom_info=fb_custom_info,
                    )
                    return result
                except Exception as e:
                    print(f"[GeminiService] {self._provider_label(fb_provider)} also failed: {e}")
                    continue

        # 모든 provider 실패
        raise Exception(f"모든 AI provider(Gemini/OpenAI/Anthropic)의 API 키가 없으나 없습니다. 설정 > 글쓰기 AI에서 최소 1개의 API 키를 설정하세요.")


    def _get_custom_provider(self, name: str):
        """DB에서 커스텀 provider 정보를 조회"""
        try:
            providers = db.get_ai_providers(active_only=True)
            for p in providers:
                if p["name"].lower() == name.lower():
                    return p
        except Exception:
            pass
        return None

    def _get_provider_priority_list(self) -> list:
        """우선순위 순서대로 모든 사용 가능한 provider 목록 반환
        내장 provider + 커스텀 provider를 합쳐서 우선순위 정렬"""
        result = []
        # 내장 provider: 설정된 우선순위 순서
        try:
            builtin_order = db.get_builtin_provider_order()
        except Exception:
            builtin_order = ["gemini", "openai", "anthropic"]

        for name in builtin_order:
            has_key = bool(self._text_api_key(name))
            result.append({"name": name, "type": name, "has_key": has_key, "priority": 0, "is_builtin": True})

        # 커스텀 provider
        try:
            customs = db.get_ai_providers(active_only=True)
            for cp in customs:
                result.append({
                    "name": cp["name"],
                    "type": "openai_compatible",
                    "has_key": bool(cp.get("api_key")),
                    "priority": cp.get("priority", 100),
                    "is_builtin": False,
                    "api_url": cp.get("api_url", ""),
                    "api_key": cp.get("api_key", ""),
                    "default_model": cp.get("default_model", ""),
                    "id": cp["id"],
                })
        except Exception:
            pass

        # 정렬: 내장이 먼저, 같은 priority면 순서 유지
        result.sort(key=lambda x: (0 if x["is_builtin"] else 1, x["priority"]))
        return result

    def _get_custom_api_key(self, name: str) -> str:
        """커스텀 provider의 API 키 반환"""
        provider = self._get_custom_provider(name)
        return provider["api_key"] if provider else ""



    async def _generate_text_openai_compatible(self, prompt: str, temperature: float, max_tokens: int, api_url: str, api_key: str, model_override: str = "") -> str:
        """OpenAI 호환 API (Ollama, vLLM, Together, Groq 등) 호출"""
        import httpx
        url = f"{api_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": model_override or "default",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                error_body = resp.text[:500]
                raise Exception(f"OpenAI-compatible API error {resp.status_code}: {error_body}")
            data = resp.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")


    async def _call_provider(self, provider: str, prompt: str, temperature: float, max_tokens: int, use_web_search: bool, model_override: str, custom_info: dict = None) -> str:
        """provider를 선택하여 텍스트를 생성합니다."""
        if custom_info and custom_info.get("type") == "openai_compatible":
            return await self._generate_text_openai_compatible(
                prompt, temperature, max_tokens,
                api_url=custom_info["api_url"],
                api_key=custom_info["api_key"],
                model_override=model_override or custom_info.get("default_model", ""),
            )
        if provider == "openai":
            return await self._generate_text_openai(prompt, temperature, max_tokens, use_web_search, model_override)
        if provider == "anthropic":
            return await self._generate_text_anthropic(prompt, temperature, max_tokens, model_override)
        return await self._generate_text_gemini(prompt, temperature, max_tokens, use_web_search, model_override)
    async def _generate_text_gemini(self, prompt: str, temperature: float, max_tokens: int, use_web_search: bool, model_override: str = "") -> str:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
        }
        
        if use_web_search:
            payload["tools"] = [{"googleSearch": {}}]

        last_error = None
        retryable_statuses = {404, 429, 503}
        retryable_api_statuses = {"NOT_FOUND", "RESOURCE_EXHAUSTED", "UNAVAILABLE"}

        async with httpx.AsyncClient(timeout=120.0) as client:
            for model_name in self._resolve_text_models("gemini", model_override):
                url = f"{self.base_url}/models/{model_name}:generateContent?key={self.api_key}"
                response = await client.post(url, json=payload)
                try:
                    result = response.json()
                except ValueError:
                    result = {"error": {"message": response.text}}

                candidates = result.get("candidates") if isinstance(result, dict) else None
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and parts[0].get("text"):
                        return parts[0]["text"]

                last_error = result
                api_status = None
                if isinstance(result, dict):
                    api_status = result.get("error", {}).get("status")

                if response.status_code in retryable_statuses or api_status in retryable_api_statuses:
                    print(f"[GeminiService] Text model {model_name} failed ({response.status_code}/{api_status}); trying fallback.")
                    continue

                # Some preview models can return a 200 with no text when token budget is consumed.
                print(f"[GeminiService] Text model {model_name} returned no text; trying fallback.")
                continue

        raise Exception(f"Gemini API 오류: {last_error}")

    async def _generate_text_openai(self, prompt: str, temperature: float, max_tokens: int, use_web_search: bool, model_override: str = "") -> str:
        headers = {
            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        last_error = None

        async with httpx.AsyncClient(timeout=120.0) as client:
            for model_name in self._resolve_text_models("openai", model_override):
                payload: Dict[str, Any] = {
                    "model": model_name,
                    "input": prompt,
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                }
                if use_web_search:
                    payload["tools"] = [{"type": "web_search_preview"}]

                response = await client.post("https://api.openai.com/v1/responses", headers=headers, json=payload)
                result = self._safe_json(response)

                if response.status_code == 400 and use_web_search:
                    payload.pop("tools", None)
                    response = await client.post("https://api.openai.com/v1/responses", headers=headers, json=payload)
                    result = self._safe_json(response)

                text = self._extract_openai_text(result)
                if text:
                    return text

                last_error = result
                friendly_error = self._normalize_text_provider_error("openai", response, result)
                if friendly_error:
                    raise Exception(friendly_error)
                api_error = result.get("error", {}) if isinstance(result, dict) else {}
                if response.status_code in {404, 429, 503} or api_error.get("type") in {"model_not_found", "rate_limit_exceeded", "server_error"}:
                    print(f"[GeminiService] OpenAI model {model_name} failed ({response.status_code}); trying fallback.")
                    continue
                break

        raise Exception(f"OpenAI API 오류: {last_error}")

    async def _generate_text_anthropic(self, prompt: str, temperature: float, max_tokens: int, model_override: str = "") -> str:
        headers = {
            "x-api-key": config.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        last_error = None

        async with httpx.AsyncClient(timeout=120.0) as client:
            for model_name in self._resolve_text_models("anthropic", model_override):
                payload = {
                    "model": model_name,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": [{"role": "user", "content": prompt}],
                }
                response = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
                result = self._safe_json(response)
                text = self._extract_anthropic_text(result)
                if text:
                    return text

                last_error = result
                friendly_error = self._normalize_text_provider_error("anthropic", response, result)
                if friendly_error:
                    raise Exception(friendly_error)
                api_error = result.get("error", {}) if isinstance(result, dict) else {}
                if response.status_code in {404, 429, 503} or api_error.get("type") in {"not_found_error", "rate_limit_error", "overloaded_error"}:
                    print(f"[GeminiService] Anthropic model {model_name} failed ({response.status_code}); trying fallback.")
                    continue
                break

        raise Exception(f"Anthropic API 오류: {last_error}")

    @staticmethod
    def _safe_json(response: httpx.Response) -> Dict[str, Any]:
        try:
            return response.json()
        except ValueError:
            return {"error": {"message": response.text}}

    @staticmethod
    def _normalize_text_provider_error(provider: str, response: httpx.Response, result: Dict[str, Any]) -> str:
        error = result.get("error", {}) if isinstance(result, dict) else {}
        error_type = str(error.get("type", "") or "").strip().lower()
        message = str(error.get("message", "") or "").strip()

        if provider == "anthropic":
            if response.status_code in {401, 403} or error_type == "authentication_error":
                return "Anthropic API 키 인증에 실패했습니다. 설정 페이지에서 Claude API 키를 다시 확인하세요."
            if response.status_code == 429 or error_type == "rate_limit_error":
                return "Anthropic API 한도에 도달했습니다. 잠시 후 다시 시도하세요."
        elif provider == "openai":
            if response.status_code in {401, 403} or error_type == "invalid_request_error" and "api key" in message.lower():
                return "OpenAI API 키 인증에 실패했습니다. 설정 페이지에서 GPT API 키를 다시 확인하세요."
            if response.status_code == 429 or error_type == "rate_limit_exceeded":
                return "OpenAI API 한도에 도달했습니다. 잠시 후 다시 시도하세요."
        elif provider == "gemini":
            api_status = str(error.get("status", "") or "").strip().upper()
            if response.status_code in {401, 403} or api_status in {"UNAUTHENTICATED", "PERMISSION_DENIED"}:
                return "Gemini API 키 인증에 실패했습니다. 설정 페이지에서 Gemini API 키를 다시 확인하세요."
            if response.status_code == 429 or api_status == "RESOURCE_EXHAUSTED":
                return "Gemini API 한도에 도달했습니다. 잠시 후 다시 시도하세요."

        return ""

    @staticmethod
    def _extract_openai_text(result: Dict[str, Any]) -> str:
        output_text = result.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        texts = []
        for item in (result.get("output", []) if isinstance(result, dict) else []):
            for content in item.get("content", []):
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text.strip())
        return "\n".join(texts).strip()

    @staticmethod
    def _extract_anthropic_text(result: Dict[str, Any]) -> str:
        texts = []
        for block in (result.get("content", []) if isinstance(result, dict) else []):
            if block.get("type") == "text" and block.get("text"):
                texts.append(block["text"])
        return "\n".join(texts).strip()





    async def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        num_images: int = 1,
        no_human: bool = True
    ) -> List[bytes]:
        """이미지 생성 (Imagen 3 우선, 실패 시 Imagen 2로 폴백)"""
        
        # [나노바나나 2.0] 최신 이미지 모델 최우선 적용 및 사람 제외 규칙 강화
        prompt = self._apply_anatomy_guardrail(prompt, no_human=no_human)
        models = [
            "gemini-3.1-flash-live-preview", # 사용자가 요청한 최신 모델
            "imagen-4.0-generate-001",
            "imagen-3.0-generate-001",
            "imagen-3.0-fast-generate-001",
        ]
        
        # [CRITICAL] 사람 제거 옵션에 따라 프롬프트 Prefix 동적 구성
        if no_human:
            # 인물 배제 모드: 추상화 방지를 위해 사물/풍경 정밀 묘사 강화
            no_human_prefix = "[STRICT PRODUCTION RULE: NO HUMANS, NO PEOPLE, NO FACE, NO BODY PARTS, NO PORTRAITS]. Focus ONLY on professional product photography of objects, technical symbols, or detailed scenery. Prompt: "
            prompt = no_human_prefix + prompt
        else:
            # 인물 허용 모드: 본문 맥락에 맞는 자유로운 생성 (고품질 실사 스타일 강조)
            pro_prefix = "[STYLE: PROFESSIONAL PHOTOTECHNICAL PHOTOGRAPHY, HIGH RESOLUTION]. Focus on cinematic composition and natural subjects. Prompt: "
            prompt = pro_prefix + prompt
        
        last_error = None
        
        for model_name in models:
            try:
                url = f"{self.base_url}/models/{model_name}:predict?key={self.api_key}"
                print(f"🎨 [Imagen] Trying model: {model_name}")
                
                # [NEW] Style Reinforcement for Non-Realistic Styles
                # If the prompt contains stylistic markers but avoids realism, reinforce negative prompts
                stylistic_keywords = ["k_manhwa", "k_webtoon", "anime", "cartoon", "ghibli", "sketch", "line art", "doodle", "wimpy", "webtoon", "infographic"]
                is_stylistic = any(kw in prompt.lower() for kw in stylistic_keywords)
                contains_photo = any(kw in prompt.lower() for kw in ["photo", "realistic", "8k", "cinematic"])
                is_infographic = "infographic" in prompt.lower()
                
                is_wimpy = any(kw in prompt.lower() for kw in ["wimpy", "stick figure", "stickman", "졸라맨", "jollaman"])
                # K만화/웹툰은 배경이 있어야 하므로 wimpy(흰배경) 처리 제외
                if is_wimpy and any(kw in prompt.lower() for kw in ["webtoon", "manhwa", "k-manhwa", "k만화", "k_manhwa"]):
                    is_wimpy = False

                final_prompt = prompt
                # 비실사 스타일: 실사 키워드 차단
                if is_stylistic and not contains_photo:
                    if is_infographic:
                        final_prompt += ", professional graphic design, vector illustration, clean lines"
                    else:
                        final_prompt += ", flat 2D style, no photorealism, no text, no words"
                # 졸라맨 여부 재판단 (배경 유무와 상관없이 캐릭터 형태 기준)
                is_jollaman = any(kw in prompt.lower() for kw in ["wimpy", "stick figure", "stickman", "졸라맨", "jollaman"])
                
                # 졸라맨: arm 강제 문구를 앞에 추가 + 뒤 suffix 강화
                if is_wimpy:
                    # 순수 졸라맨 (흰배경)
                    final_prompt = (
                        "EXACTLY TWO ARMS ONLY. NO EXTRA ARMS. NO EXTRA HANDS. "
                        "ARM COLOR MUST BE TEAL-BLUE. DO NOT DRAW BLACK ARMS. "
                        "THE CHARACTER MUST HAVE A PAIR OF BLACK DOT EYES AND A SMALL ARC SMILE ON THE FACE. "
                        + final_prompt
                        + ", the character has exactly one left arm and one right arm total,"
                        " no third arm no fourth arm no duplicate limbs,"
                        " flat 2D vector no gradients no 3D, perfectly bald smooth round white circular head, no hair, no hairstyle,"
                        " a pair of distinct black dot eyes and a simple black arc smile (MUST HAVE EYES AND MOUTH),"
                        " Face must NEVER be blank or empty. "
                        " vibrant teal-blue hoodie with front pocket and THICK CYLINDRICAL FULL-LENGTH TEAL-BLUE SLEEVES covering the entire arm completely down to the white gloves,"
                        " THE TEAL-BLUE FABRIC MUST REACH THE WHITE GLOVES. NO BLACK LINES VISIBLE FOR ARMS. "
                        " NO ROLLED-UP SLEEVES, NO BLACK SKIN VISIBLE ON ARMS, NO BLACK ARMS, NO SHORT SLEEVES, sleeves must be teal-blue (same color as the hoodie),"
                        " solid black trousers, white sneakers with black trim,"
                        " small rounded white-gloved fist-shaped hands with black outlines (NOT white balls NOT white circles),"
                        " pure white background, single scene"
                    )
                elif is_jollaman:
                    # 배경이 있는 졸라맨 (웹툰 등)
                    final_prompt = (
                        "EXACTLY TWO ARMS ONLY. NO EXTRA ARMS. NO EXTRA HANDS. "
                        "ARM COLOR MUST BE TEAL-BLUE. DO NOT DRAW BLACK ARMS. "
                        + final_prompt
                        + ", the character has a perfectly bald smooth round white circular head, no hair, no hairstyle,"
                        " a pair of distinct black dot eyes and a simple black arc smile (MUST HAVE EYES AND MOUTH),"
                        " Face must NEVER be blank or empty. "
                        " THICK CYLINDRICAL FULL-LENGTH TEAL-BLUE SLEEVES covering the entire arm completely down to the white gloves,"
                        " THE TEAL-BLUE FABRIC MUST REACH THE WHITE GLOVES. NO BLACK LINES VISIBLE FOR ARMS. "
                        " NO ROLLED-UP SLEEVES, no black skin visible on arms, NO BLACK ARMS, NO SHORT SLEEVES,"
                        " strictly two arms total, no extra limbs"
                    )
                # 모든 스타일 공통: 초강력 해부학 제약 (여러 팔/손 생성 방지)
                if not no_human:
                    # 인물이 허용된 경우: 사용자가 지시한 포즈와 해부학적 제약 문구 강제 추가
                    final_prompt += (
                        ", upper-body or medium shot preferred, uncrossed arms, hands separated from the torso, "
                        "professional corporate photography style, looking at the camera, a natural pose, "
                        "correct anatomy, natural human body proportions, normal number of limbs"
                    )

                payload = {
                    "instances": [{"prompt": final_prompt}],
                    "parameters": {
                        "sampleCount": num_images,
                        "aspectRatio": aspect_ratio,
                        "safetySetting": "block_low_and_above",
                        "negativePrompt": "extra arms, extra limbs, multiple arms, deformed hands, mutated fingers, bad anatomy, extra legs, bad body proportions"
                    }
                }
                
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(url, json=payload)
                    
                    # 404 에러면 다음 모델 시도
                    if response.status_code == 404:
                        print(f"⚠️ [Imagen] Model {model_name} not found (404), trying next...")
                        last_error = f"Model {model_name} not found"
                        continue
                    
                    # 다른 에러는 즉시 실패 (단, 429 Quota 에러면 다음 모델 시도)
                    if response.status_code != 200:
                        error_info = response.text
                        print(f"❌ [Imagen] Error ({response.status_code}): {error_info}")
                        if response.status_code == 429:
                            print(f"⚠️ [Imagen] Quota exceeded for {model_name}, trying next model...")
                            last_error = f"Quota exceeded for {model_name}"
                            continue
                        raise Exception(f"API Error ({response.status_code}): {error_info}")
                    
                    result = response.json()
                    print(f"🔍 [Imagen] Response from {model_name}:")
                    print(f"   Keys: {list(result.keys())}")
                    
                    images = []
                    if "predictions" in result:
                        print(f"   Predictions count: {len(result['predictions'])}")
                        for idx, pred in enumerate(result["predictions"]):
                            print(f"   Prediction {idx} keys: {list(pred.keys())}")
                            if "bytesBase64Encoded" in pred:
                                img_bytes = base64.b64decode(pred["bytesBase64Encoded"])
                                images.append(img_bytes)
                                print(f"   ✅ Decoded image {idx}, size: {len(img_bytes)} bytes")
                            # Add check for other formats if needed
                            elif "mimeType" in pred and "bytesBase64Encoded" in pred: # Some versions
                                 img_bytes = base64.b64decode(pred["bytesBase64Encoded"])
                                 images.append(img_bytes)
                                 print(f"   ✅ Decoded image {idx} (alt format), size: {len(img_bytes)} bytes")
                            else:
                                print(f"⚠️ [Imagen] Unknown prediction format: {pred.keys()}")
                                print(f"   Full prediction content: {pred}")
                                # Check if there's a safety/filter reason
                                if "error" in pred:
                                    print(f"   ❌ Error in prediction: {pred['error']}")
                                if "safetyRatings" in pred:
                                    print(f"   🚫 Safety ratings: {pred['safetyRatings']}")
                    else:
                        print(f"⚠️ [Imagen] No 'predictions' key in response. Keys: {result.keys()}")
                        print(f"   Full response: {str(result)[:500]}")

                    # Check if we got images (MOVED OUTSIDE else block!)
                    if images:
                        print(f"✅ [Imagen] Successfully generated {len(images)} image(s) with {model_name}")
                        return images
                    
                    # No images generated - try next model or fail
                    error_msg = result.get('error', {}).get('message', 'No image data in response')
                    print(f"⚠️ [Imagen] No images from {model_name}: {error_msg}")
                    last_error = f"No images: {error_msg}"
                    continue
                    
            except httpx.TimeoutException:
                print(f"⏱️ [Imagen] Timeout with {model_name}, trying next...")
                last_error = f"Timeout with {model_name}"
                continue
            except Exception as e:
                # 404가 아닌 다른 에러는 즉시 실패
                if "404" not in str(e):
                    raise
                print(f"⚠️ [Imagen] Error with {model_name}: {e}, trying next...")
                last_error = str(e)
                continue
        
        # 모든 모델 시도 실패
        if "No images" in str(last_error) or "Safety" in str(last_error):
             raise Exception(f"이미지 생성기(Imagen) 보안 필터에 의해 차단되었습니다. 유명인 이름, 브랜드명, 또는 부적절한 키워드가 포함되어 있는지 확인하세요. (Last error: {last_error})")
        raise Exception(f"모든 이미지 생성 모델 시도 실패. 잠시 후 다시 시도해주세요. (Last error: {last_error})")









    async def generate_title_recommendations(self, keyword: str, topic: str = "", language: str = "ko") -> List[str]:
        """추천 제목 5개 생성"""
        hooking_strategy = self.get_hooking_strategy(language)
        prompt = f"""
        당신은 유튜브 콘텐츠 기획 전문가입니다.
        다음 정보를 바탕으로 클릭률(CTR)이 높은 롱폼/쇼츠 유튜브 제목 5개를 제안해주세요.

        [정보]
        - 키워드: {keyword}
        - 주제/설명: {topic}
        - 언어: {language}

        [제목 후킹 전략]
        {hooking_strategy}

        [요구사항]
        1. 5개의 제목을 생성하세요.
        2. 위 '제목 후킹 전략'을 적극적으로 반영하여 호기심을 유발하거나, 혜택을 명확히 하거나, 감정을 자극하는 제목을 만드세요.
        3. 50자 이내로 짧고 강렬하게.
        4. 번호 붙이지 말고 오직 JSON 배열로 반환하세요. 예: ["제목1", "제목2", ...]
        """

        try:
            response_text = await self.generate_text(prompt, temperature=0.8)
            cleaned_text = re.sub(r'```json\s*|\s*```', '', response_text).strip()
            match = re.search(r'\[.*\]', cleaned_text, re.DOTALL)
            
            if match:
                titles = json.loads(match.group(0))
                return titles[:5]
            else:
                # Fallback
                return [line.strip().lstrip('-').lstrip('1.').strip() for line in cleaned_text.split('\n') if line.strip()][:5]
        except Exception as e:
            print(f"Title Gen Error: {e}")
            return []


    def get_cultural_context(self, language: str) -> str:
        """언어별 맞춤형 문화/실정 가이드라인 반환"""
        contexts = {
            "ko": "대한민국: 최신 트렌드에 민감하며, 실용적이고 빠른 정보를 선호합니다. 정중하면서도 전문적인 어조를 사용하세요.",
            "ja": "일본: 예의와 정중함을 극도로 중시합니다. 직접적인 광고보다는 정보 제공형 콘텐츠를 선호하며, 계절감이나 세밀한 디테일에 민감합니다. 독자의 감성을 자극하는 부드러운 화법을 사용하세요.",
            "en": "미국/글로벌: 결론부터 말하는 두괄식 구조와 효율성을 중시합니다. 데이터와 근거를 바탕으로 한 설득력 있는 어조를 사용하며, '나에게 어떤 이득이 있는가'를 명확히 제시하세요.",
            "vi": "베트남: 커뮤니티의 반응과 실질적인 혜택을 중시합니다. 친근하면서도 예의를 갖춘 어조를 사용하고, 젊은 층의 활기찬 에너지를 반영하세요.",
            "ar": "아랍권: 전통과 명예를 중시하며, 화려하고 서술적인 표현을 즐깁니다. 종교적/문화적 금기사항에 유의하고 신뢰 관계 형성을 강조하세요.",
            "it": "이탈리아: 예술, 디자인, 역사적 자부심이 강합니다. 감각적이고 열정적인 표현을 사용하며 스타일과 퀄리티를 강조하세요."
        }
        return contexts.get(language, "해당 언어권의 일반적인 문화적 정서와 사회적 관습을 반영하여 독자가 깊이 공감할 수 있도록 작성하세요.")

    def get_hooking_strategy(self, language: str) -> str:
        """언어별 클릭률(CTR)을 극대화하는 제목 후킹 전략 반환"""
        strategies = {
            "ko": "질문형(~하는 이유?), 부정적 강조(절대 하지 마세요), 권위/비밀(나만 아는 비밀, 전문가만 아는), 시간/효율(딱 3분만 투자하세요, 10분 만에 끝내는) 등 강렬한 단어를 사용하세요.",
            "ja": "대괄호를 활용한 강조(【衝撃】, 【保存版】, 【2026最新】), 손실 회피(知らないと損する), 의외성(実は...だった, 意外な真実), 감성적인 어구(心에 남는, 納得의 퀄리티)를 사용하세요.",
            "en": "Direct Benefit (How to..., Stop wasting time on...), Mystery (The hidden truth about..., What they don't tell you), Power words (Ultimate, Revealed, Insane, Life-changing), Urgency (Before it's too late)를 활용하세요.",
            "vi": "Sử dụng các từ khóa gây tò mò (Bật mí bí mật, Sự thật bất ngờ), tập trung vào lợi ích (Cách để... hiệu quả nhất), hoặc cảnh báo (Đừng làm... nếu không muốn).",
            "ar": "استخدم عبارات قوية ومؤثرة (أسرار لا تعرفها، كيف تحقق...)، ركز على الفائدة المباشرة والمصداقية، واستخدم أسلوباً قصصياً جذاباً.",
            "it": "Usa aggettivi appassionati (Incredibile, Unico, Segreto), punta sulla qualità e sullo stile (Il segreto del vero stile, La guida definitiva), e crea un senso di esclusività."
        }
        return strategies.get(language, "독자의 호기심을 자극하고 클릭을 유도하는 강렬한 후킹 문구를 사용하세요. 숫자를 활용하거나(Top 5, 3가지 방법) 질문을 던지는 것이 효과적입니다.")

    async def generate_blog_content(
        self,
        source_content: str,
        platform: str,
        blog_style: str,
        language: str = "ko",
        user_notes: str = "",
        category: str = None,
        provider_override: str = "",
        model_override: str = "",
    ) -> dict:
        """블로그 콘텐츠 생성은 분리된 전용 서비스에 위임."""
        return await self.blog_content_service.generate_blog_content(
            source_content=source_content,
            platform=platform,
            blog_style=blog_style,
            language=language,
            user_notes=user_notes,
            category=category,
            provider_override=provider_override,
            model_override=model_override,
        )



    async def generate_trending_keywords(self, language: str = "ko", period: str = "now", age: str = "all") -> list:
        """
        언어/기간/연령별 인기 유튜브 트렌드 키워드 생성 (Search Volume 시뮬레이션)
        """
        lang_name = ""
        if language == "ko": lang_name = "South Korea (Korean)"
        elif language == "ja": lang_name = "Japan (Japanese)"
        elif language == "en": lang_name = "USA/International (English)"
        elif language == "es": lang_name = "Spain/Latin America (Spanish)"
        elif language == "vi": lang_name = "Vietnam (Vietnamese)"
        else: lang_name = "South Korea (Korean)"

        # 기간 텍스트
        period_text = "REAL-TIME / NOW"
        if period == "week": period_text = "THIS WEEK (Last 7 days)"
        elif period == "month": period_text = "THIS MONTH (Last 30 days)"

        # 연령 텍스트
        age_text = "ALL Ages"
        if age == "10s": age_text = "Teenagers (10-19)"
        elif age == "20s": age_text = "Young Adults (20-29)"
        elif age == "30s": age_text = "Adults (30-39)"
        elif age == "40s": age_text = "Middle-aged (40-49)"
        elif age == "50s": age_text = "Seniors (50+)"

        prompt = prompts.GEMINI_TRENDING_KEYWORDS.format(
            lang_name=lang_name,
            period_text=period_text,
            age_text=age_text,
            language=language
        )
        
        try:
            text = await self.generate_text(prompt, temperature=0.9, provider_override=provider_override, model_override=model_override)
            
            import json
            import re
            
            match = re.search(r'\[[\s\S]*\]', text)
            if match:
                json_str = match.group(0)
                return json.loads(json_str)
            else:
                # Fallback data if parse fails
                return []
                
        except Exception as e:
            print(f"Trend keywords generation failed: {e}")
            return []

    async def generate_amazon_review(self, product_data: dict, language: str = "ko") -> str:
        """아마존 상품 정보를 바탕으로 설득형 리뷰 생성"""
        cultural_context = "local sentiment"
        lang_map = {
            "ko": "한국의 가성비와 편리함 중시",
            "ja": "일본의 정중함과 세밀함, 품질 신뢰 중시",
            "en": "미국/글로벌의 직설적인 성능과 실용성 위주",
            "es": "스페인/중남미의 열정적이고 감성적인 추천",
            "fr": "프랑스의 세련미와 디자인, 브랜드 가치 중시",
            "de": "독일의 내구성과 정밀성, 기술적 완성도 중시",
        }
        lang_name_map = {
            "ko": "Korean",
            "en": "English",
            "ja": "Japanese",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "vi": "Vietnamese",
            "it": "Italian",
            "ar": "Arabic"
        }
        target_lang_name = lang_name_map.get(language, language)
        cultural_context = lang_map.get(language, "General global marketing sentiment")
        
        hooking_strategy = self.get_hooking_strategy(language)
        
        # [FIX] 데이터 누락 방지 및 클리닝
        title = (product_data.get("title") or "Selected Quality Product").strip()
        price = product_data.get("price") or "Competitive Price"
        features_list = product_data.get("features") or []
        features = ", ".join([str(f) for f in features_list]) if features_list else "Premium features and design"
        description = (product_data.get("description") or "Check product details for more information").strip()
        
        prompt = prompts.GEMINI_AMAZON_REVIEW.format(
            title=title[:500],
            price=price,
            features=features[:2000],
            description=description[:3000],
            rating=product_data.get("rating") or "Top Rated",
            review_count=product_data.get("review_count") or "High Satisfaction",
            language=target_lang_name,
            cultural_context=cultural_context,
            hooking_strategy=hooking_strategy
        )
        
        try:
            return await self.generate_text(prompt, temperature=0.8)
        except Exception as e:
            print(f"[GeminiService] Amazon Review Error: {e}")
            raise e


    async def generate_amazon_trends(self) -> List[dict]:
        """미국 아마존 트렌드 키워드 생성"""
        from config import config
        current_date = config.get_kst_time().strftime("%Y-%m-%d")
        
        prompt = f"""
        Current Date: {current_date}
        Target Market: USA (Amazon.com)
        Role: Amazon Affiliate Marketing Expert
        
        Identify 5 high-potential, trending product keywords for Amazon Affiliate marketing right now.
        Consider seasonality (holidays, weather), viral trends (TikTok/Instagram), and new tech releases.
        
        Return ONLY a JSON array of objects:
        [
            {{
                "keyword": "search term",
                "reason": "Why it sells now (short)"
            }},
            ...
        ]
        """
        
        try:
            text = await self.generate_text(prompt, temperature=0.9)
            import json, re
            cleaned = re.sub(r'```json\s*|\s*```', '', text).strip()
            match = re.search(r'\[[\s\S]*\]', cleaned)
            if match:
                return json.loads(match.group(0))
            return []
        except Exception as e:
            print(f"Trend Gen Error: {e}")
            return []

    async def generate_general_blog_trends(self, category: str = "General", provider_override: str = "", model_override: str = "") -> list:
        """일반 블로그(독립적 자동화) 카테고리별 트렌드 키워드 생성"""
        from config import config
        current_date = config.get_kst_time().strftime("%Y-%m-%d")
        
        prompt = f"""
        Current Date: {current_date}
        Target Audience: Korean Blog Readers (Naver, Tistory, WordPress, Blogger)
        Category: {category}
        Role: Professional SEO Expert & Trend Analyst
        
        Identify 5 high-potential, explosive-view blog topics/keywords for the given category right now.
        Consider seasonal trends, viral issues, breaking news, or highly searched informational queries in South Korea.
        The recommended keyword/topic should be highly clickable and engaging.
        
        Return ONLY a JSON array of objects:
        [
            {{
                "keyword": "A highly clickable blog topic or keyword (Korean)",
                "reason": "Why this topic will get explosive views right now (short Korean)"
            }},
            ...
        ]
        """
        
        try:
            text = await self.generate_text(prompt, temperature=0.9)
            import json, re
            cleaned = re.sub(r'```json\s*|\s*```', '', text).strip()
            match = re.search(r'\[[\s\S]*\]', cleaned)
            if match:
                return json.loads(match.group(0))
            return self.fallback_general_blog_trends(category)
        except Exception as e:
            print(f"General Trend Gen Error: {e}")
            return self.fallback_general_blog_trends(category)

    @staticmethod
    def fallback_general_blog_trends(category: str = "General") -> List[dict]:
        normalized = (category or "General").lower()
        fx_topics = [
            ("달러/원 환율 전망: 외환 트레이더가 주목해야 할 3가지 시나리오", "환율 변동성이 클 때 검색 수요가 급증하는 핵심 FX 주제입니다."),
            ("초보자도 따라하는 FX 마진거래 입문 완벽 가이드", "외환 거래 입문자의 검색 수요가 가장 높은 evergreen 주제입니다."),
            ("메이저 통화쌍 분석: USD/EUR, GBP/USD, USD/JPY 핵심 포인트", "실전 트레이더들이 매일 검색하는 기술 분석 주제입니다."),
            ("금리 차이가 환율에 미치는 영향과 캐리 트레이드 전략", "파운드 캐리 트레이드 등 금리 관련 외환 전략에 대한 관심이 높습니다."),
            ("스왑 포인트로 수익 내는 FX 장기 투자법", "스왑 이자 수익을 노리는 개인 투자자들이 지속적으로 검색합니다."),
        ]
        finance_topics = [
            ("AI 시대 최대 수혜 산업과 투자 관점 정리", "AI 확산과 금융/산업 수혜주 관심을 함께 다룰 수 있습니다."),
            ("금리 인하 기대감이 주식시장에 미치는 영향", "투자자들이 꾸준히 검색하는 거시경제 주제입니다."),
            ("월급쟁이를 위한 2026 자산 배분 전략", "실용성과 검색 수요가 모두 높은 재테크 주제입니다."),
            ("달러 환율 변동이 내 지갑에 미치는 영향", "일상과 경제를 연결해 클릭 유도가 쉽습니다."),
            ("AI가 바꾸는 직업과 돈 버는 방식", "AI와 소득 변화에 대한 대중 관심이 큽니다."),
        ]
        it_topics = [
            ("AI 시대 최대의 수혜자는 누구인가", "사용자가 입력한 주제와 맞고 확장성이 좋습니다."),
            ("생성형 AI로 사라지는 일과 새로 생기는 일", "직업 변화와 AI를 함께 다루는 고관심 주제입니다."),
            ("2026년에 주목해야 할 AI 서비스 TOP 7", "리스트형 글로 클릭률을 높이기 쉽습니다."),
            ("AI 검색 시대 블로그 운영 방식이 바뀌는 이유", "블로그 사용자에게 직접적인 가치가 있습니다."),
            ("스마트폰보다 더 큰 변화, 온디바이스 AI", "기술 트렌드와 일상 변화를 연결할 수 있습니다."),
        ]
        general_topics = [
            ("AI 시대 최대의 수혜자는 누구인가", "넓은 독자층이 이해하기 쉬운 시사형 주제입니다."),
            ("요즘 사람들이 불안해하는 진짜 이유", "감정 공감형 주제로 체류 시간을 만들기 좋습니다."),
            ("2026년에 바뀌는 생활 트렌드 5가지", "연도형 키워드는 검색 유입에 유리합니다."),
            ("하루 10분으로 생산성을 높이는 현실적인 방법", "실용형 글로 저장/공유 가능성이 있습니다."),
            ("지금 시작하기 좋은 온라인 부업 아이디어", "대중 검색 수요가 높은 evergreen 주제입니다."),
        ]
        if "fx" in normalized or "forex" in normalized or "trading" in normalized or "외환" in normalized or "환율" in normalized:
            selected = fx_topics
        elif "finance" in normalized or "경제" in normalized or "금융" in normalized:
            selected = finance_topics
        elif "it" in normalized or "tech" in normalized or "테크" in normalized or "웹서비스" in normalized:
            selected = it_topics
        else:
            selected = general_topics
        return [{"keyword": keyword, "reason": reason} for keyword, reason in selected]




    





    # ============================================================
    # [NEW] Level 2: Gemini Vision 기반 자산 유형 자동 분류
    # ============================================================

    # 유형 → 효과 매핑 테이블











    async def analyze_blog_metadata(self, content: str, language: str = "ko") -> dict:
        """블로그 메타데이터 분석은 분리된 전용 서비스에 위임."""
        return await self.blog_content_service.analyze_blog_metadata(content, language=language)


# 싱글톤 인스턴스
gemini_service = GeminiService()
