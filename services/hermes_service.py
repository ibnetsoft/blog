import json
import re
from typing import Any, Dict, List

from services.ai_provider_service import TextGenerationRequest, ai_provider_service
from services.blog_service import blog_service
from services.gemini_service import gemini_service
from services.publish_workflow_service import BlogPostRequest, publish_workflow_service


class HermesService:
    @staticmethod
    def _extract_json_array(text: str) -> List[Dict[str, Any]]:
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", text or "").strip()
        match = re.search(r"\[[\s\S]*\]", cleaned)
        if not match:
            return []
        try:
            parsed = json.loads(match.group(0))
        except Exception:
            return []
        return parsed if isinstance(parsed, list) else []

    @staticmethod
    def _pick_topic(candidates: List[Dict[str, Any]], category: str) -> str:
        for item in candidates:
            if not isinstance(item, dict):
                continue
            for key in ("title", "topic", "keyword", "name"):
                value = str(item.get(key) or "").strip()
                if value:
                    return value

        fallback = gemini_service.fallback_general_blog_trends(category)
        if fallback:
            first = fallback[0]
            return str(first.get("keyword") or first.get("title") or f"{category} 최신 트렌드").strip()
        return f"{category} 최신 트렌드"

    async def publish_blog_post(self, req: BlogPostRequest) -> Dict[str, Any]:
        return await publish_workflow_service.publish_blog_post(req)

    async def generate_topic_bundle(
        self,
        category: str,
        language: str = "ko",
        provider: str = "",
        model: str = "",
        topic_mode: str = "trend",
    ) -> Dict[str, Any]:
        prompt = f"""
You are a senior SEO strategist for blog automation.
Category: {category}
Target language: {language}
Topic mode: {topic_mode}

Generate 5 highly clickable blog topic ideas for this campaign.
Return ONLY valid JSON array. Each object must contain:
- title: short, specific, and clickable
- reason: one short sentence explaining why it is timely
"""

        raw = await ai_provider_service.generate_text(
            TextGenerationRequest(
                prompt=prompt,
                temperature=0.85,
                max_tokens=900,
                provider=provider,
                model=model,
            )
        )
        candidates = self._extract_json_array(raw)
        return {
            "topic": self._pick_topic(candidates, category),
            "candidates": candidates,
            "raw": raw,
        }

    async def build_publish_request(
        self,
        topic: str,
        category: str,
        platforms: List[Dict[str, str]],
        source_content: str = "",
        provider: str = "",
        model: str = "",
        image_count: int = 2,
        no_human: bool = True,
    ) -> Dict[str, Any]:
        generated = await blog_service.generate_independent_multi_language_blogs(
            topic=topic,
            platforms=platforms,
            source_content=source_content,
            provider_override=provider,
            model_override=model,
        )
        if generated.get("status") != "ok":
            return generated

        results = generated.get("results", [])
        req_contents = {}
        req_metadata = {}
        platform_langs = {}
        post_platforms = []
        social_assets = {}

        for item in results:
            if item.get("status") != "ok":
                continue

            target_id = item.get("target_id")
            lang_content = item.get("content", "")
            if not target_id or not lang_content:
                continue

            try:
                image_result = await blog_service.add_images_to_content(
                    content=lang_content,
                    project_id=None,
                    image_count=image_count,
                    no_human=no_human,
                )
                if image_result.get("status") == "ok" and image_result.get("content"):
                    lang_content = image_result["content"]
            except Exception as image_error:
                print(f"[Hermes] Image generation error for {target_id}: {image_error}")

            req_contents[target_id] = lang_content
            req_metadata[target_id] = {
                "title": item.get("title", ""),
                "tags": item.get("tags", []),
                "category": category,
                "summary": item.get("summary", ""),
            }
            platform_langs[target_id] = item.get("language", "ko")
            post_platforms.append(target_id)

            if item.get("platform") in ("facebook", "instagram", "tiktok", "telegram"):
                social_assets[target_id] = {
                    "caption": "\n\n".join(filter(None, [item.get("title", ""), item.get("summary", "")])),
                    "image_urls": [],
                    "video_urls": [],
                }

        if not req_contents:
            return {"status": "error", "error": "No generated content succeeded."}

        primary_target = "wordpress" if "wordpress" in req_contents else list(req_contents.keys())[0]
        primary_meta = req_metadata[primary_target]
        request = BlogPostRequest(
            title=primary_meta["title"],
            content=req_contents[primary_target],
            tags=primary_meta["tags"],
            categories=[category],
            summary=primary_meta["summary"],
            platforms=post_platforms,
            platform_langs=platform_langs,
            contents=req_contents,
            metadata=req_metadata,
            social_assets=social_assets,
        )
        return {"status": "ok", "request": request, "results": results}

    async def run_legacy_autopost(
        self,
        category: str,
        platforms: List[Dict[str, str]],
        provider: str = "",
        model: str = "",
        no_human: bool = True,
    ) -> Dict[str, Any]:
        topic_bundle = await self.generate_topic_bundle(
            category=category,
            language="ko",
            provider=provider,
            model=model,
            topic_mode="trend",
        )
        build_result = await self.build_publish_request(
            topic=topic_bundle["topic"],
            category=category,
            platforms=platforms,
            provider=provider,
            model=model,
            no_human=no_human,
        )
        if build_result.get("status") != "ok":
            return {
                "status": "error",
                "topic": topic_bundle["topic"],
                "error": build_result.get("error", "failed to build publish request"),
            }

        post_result = await self.publish_blog_post(build_result["request"])
        return {
            "status": post_result.get("status", "error"),
            "topic": topic_bundle["topic"],
            "topic_candidates": topic_bundle.get("candidates", []),
            "generated_results": build_result.get("results", []),
            "publish_result": post_result,
        }


hermes_service = HermesService()
