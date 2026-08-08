from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import database as db
from config import config
from services.gemini_service import gemini_service


@dataclass
class TextGenerationRequest:
    prompt: str
    temperature: float = 0.7
    max_tokens: int = 8192
    use_web_search: bool = False
    provider: str = ""
    model: str = ""


@dataclass
class ProviderSelection:
    name: str
    model: str = ""
    provider_type: str = "builtin"
    custom_info: Optional[Dict[str, Any]] = None


class AIProviderService:
    BUILTIN_PROVIDERS = {"gemini", "openai", "anthropic"}
    PROVIDER_ALIASES = {
        "claude": "anthropic",
        "gpt": "openai",
        "zhipu": "glm",
        "zhipuai": "glm",
    }

    @classmethod
    def normalize_provider_name(cls, name: str) -> str:
        normalized = str(name or "").strip().lower()
        return cls.PROVIDER_ALIASES.get(normalized, normalized)

    def _active_custom_providers(self) -> List[Dict[str, Any]]:
        try:
            return db.get_ai_providers(active_only=True)
        except Exception:
            return []

    def resolve_provider(self, provider: str = "", model: str = "") -> ProviderSelection:
        requested = self.normalize_provider_name(provider or getattr(config, "AI_TEXT_PROVIDER", "gemini"))
        if requested in self.BUILTIN_PROVIDERS:
            return ProviderSelection(name=requested, model=str(model or "").strip(), provider_type="builtin")

        custom = self._match_custom_provider(requested)
        if custom:
            return ProviderSelection(
                name=str(custom.get("name") or requested).strip(),
                model=str(model or custom.get("default_model") or "").strip(),
                provider_type=str(custom.get("provider_type") or custom.get("type") or "openai_compatible"),
                custom_info=custom,
            )

        fallback = self.normalize_provider_name(getattr(config, "AI_TEXT_PROVIDER", "gemini"))
        if fallback not in self.BUILTIN_PROVIDERS:
            fallback = "gemini"
        return ProviderSelection(name=fallback, model=str(model or "").strip(), provider_type="builtin")

    def _match_custom_provider(self, requested: str) -> Optional[Dict[str, Any]]:
        normalized_requested = self.normalize_provider_name(requested)
        custom_providers = self._active_custom_providers()

        for provider in custom_providers:
            name = self.normalize_provider_name(provider.get("name"))
            if name == normalized_requested:
                return provider

        for provider in custom_providers:
            haystacks = [
                self.normalize_provider_name(provider.get("name")),
                str(provider.get("api_url") or "").strip().lower(),
                str(provider.get("default_model") or "").strip().lower(),
            ]
            if any(normalized_requested and normalized_requested in haystack for haystack in haystacks):
                return provider

        return None

    async def generate_text(self, request: TextGenerationRequest) -> str:
        selection = self.resolve_provider(request.provider, request.model)
        if selection.custom_info:
            return await gemini_service._call_provider(
                selection.name,
                request.prompt,
                request.temperature,
                request.max_tokens,
                request.use_web_search,
                selection.model,
                custom_info=selection.custom_info,
            )

        return await gemini_service.generate_text(
            request.prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            use_web_search=request.use_web_search,
            provider_override=selection.name,
            model_override=selection.model,
        )


ai_provider_service = AIProviderService()
