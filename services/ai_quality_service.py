import json
import re
from typing import Any, Dict, List, Optional

import database as db
from services.gemini_service import gemini_service


class AIQualityService:
    def is_enabled(self) -> bool:
        return db.get_global_setting("ai_quality_enabled", "true", value_type="bool")

    def min_score(self) -> int:
        try:
            return int(db.get_global_setting("ai_quality_min_score", "82"))
        except Exception:
            return 82

    def build_learning_context(self, limit: int = 30) -> str:
        logs = db.get_job_logs(limit)
        reviews = db.get_recent_ai_quality_reviews(10)

        success_titles = []
        failures = []
        for log in logs:
            title = (log.get("title") or "").strip()
            platform = log.get("platform") or ""
            status = str(log.get("status") or "").lower()
            message = (log.get("message") or "").strip()
            if status in ("ok", "success") and title:
                success_titles.append(f"- {platform}: {title[:100]}")
            elif status in ("error", "failed", "fail") or message:
                failures.append(f"- {platform}: {message[:140]}")

        prior_improvements = []
        for review in reviews:
            improved = (review.get("improved_title") or "").strip()
            score = review.get("score")
            if improved:
                prior_improvements.append(f"- score {score}: {improved[:100]}")

        parts = []
        if success_titles:
            parts.append("Recent successful titles:\n" + "\n".join(success_titles[:8]))
        if failures:
            parts.append("Recent publishing issues to avoid:\n" + "\n".join(failures[:8]))
        if prior_improvements:
            parts.append("Recent AI improvements:\n" + "\n".join(prior_improvements[:8]))

        return "\n\n".join(parts) if parts else "No historical publishing data yet."

    @staticmethod
    def _clean_json_text(text: str) -> str:
        cleaned = (text or "").strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        match = re.search(r"\{[\s\S]*\}", cleaned)
        return match.group(0) if match else cleaned

    @staticmethod
    def _safe_tags(value: Any) -> List[str]:
        if isinstance(value, list):
            raw_tags = value
        elif isinstance(value, str):
            raw_tags = re.split(r"[,،]", value)
        else:
            raw_tags = []

        tags = []
        for tag in raw_tags:
            clean = re.sub(r"[\u200e\u200f\u202a-\u202e]", "", str(tag))
            clean = re.sub(r"[,،<>{}\[\]~]", " ", clean)
            clean = re.sub(r"\s+", " ", clean).strip()
            if clean and clean not in tags:
                tags.append(clean[:80])
        return tags[:8]

    async def review_and_improve(
        self,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        summary: Optional[str] = None,
        platform: str = "wordpress",
        language: str = "ko",
        provider_override: str = "",
        model_override: str = "",
    ) -> Dict[str, Any]:
        if not self.is_enabled():
            return {
                "status": "skipped",
                "title": title,
                "content": content,
                "tags": tags or [],
                "categories": categories or [],
                "summary": summary,
                "score": None,
                "issues": [],
                "improvements": [],
            }

        learning_context = self.build_learning_context()
        min_score = self.min_score()
        clean_text = re.sub(r"<[^>]+>", " ", content or "")
        clean_text = re.sub(r"\s+", " ", clean_text).strip()

        prompt = f"""You are an SEO editor and blog growth optimizer.
Review this post before publishing and improve it only when needed.

Platform: {platform}
Language: {language}
Minimum acceptable score: {min_score}

Historical learning context:
{learning_context}

Rules:
1. Return ONLY valid JSON.
2. Preserve the original language.
3. Keep factual meaning. Do not invent sources, claims, prices, dates, or results.
4. Improve click appeal, search intent alignment, readability, tags, and summary.
5. If the content already scores at least {min_score}, keep content mostly unchanged.
6. For Blogger tags, avoid commas inside labels, brackets, tildes, and invisible BiDi control characters.
7. For WordPress, prefer concise SEO-friendly title and focused tags.

JSON schema:
{{
  "score": 0-100,
  "issues": ["short issue"],
  "improvements": ["short improvement"],
  "title": "improved title",
  "summary": "improved summary or empty string",
  "tags": ["tag1", "tag2"],
  "categories": ["category1"],
  "content": "improved HTML/content"
}}

Original title:
{title}

Original summary:
{summary or ""}

Original tags:
{json.dumps(tags or [], ensure_ascii=False)}

Original categories:
{json.dumps(categories or [], ensure_ascii=False)}

Original content excerpt:
{clean_text[:7000]}
"""

        try:
            raw = await gemini_service.generate_text(
                prompt,
                temperature=0.25,
                max_tokens=12000,
                provider_override=provider_override,
                model_override=model_override,
            )
            data = json.loads(self._clean_json_text(raw))
        except Exception as e:
            print(f"[AIQuality] Review failed, using original content: {e}")
            return {
                "status": "error",
                "title": title,
                "content": content,
                "tags": tags or [],
                "categories": categories or [],
                "summary": summary,
                "score": None,
                "issues": [str(e)],
                "improvements": [],
            }

        improved = {
            "status": "ok",
            "title": (data.get("title") or title).strip(),
            "content": data.get("content") or content,
            "tags": self._safe_tags(data.get("tags") or tags or []),
            "categories": data.get("categories") or categories or [],
            "summary": data.get("summary") if data.get("summary") is not None else summary,
            "score": int(data.get("score") or 0),
            "issues": data.get("issues") or [],
            "improvements": data.get("improvements") or [],
        }

        if improved["score"] >= min_score and not improved["improvements"]:
            improved["title"] = title
            improved["content"] = content
            improved["tags"] = tags or []
            improved["categories"] = categories or []
            improved["summary"] = summary

        try:
            db.add_ai_quality_review(
                platform=platform,
                language=language,
                original_title=title,
                improved_title=improved["title"],
                score=improved["score"],
                issues=improved["issues"],
                improvements=improved["improvements"],
            )
        except Exception as log_err:
            print(f"[AIQuality] Failed to save review log: {log_err}")

        return improved


ai_quality_service = AIQualityService()
