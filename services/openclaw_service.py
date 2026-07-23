import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import database as db
from services.ai_quality_service import ai_quality_service
from services.blog_service import blog_service
from services.gemini_service import gemini_service
from app.routers.blog import BlogPostRequest, post_blog


class OpenClawService:
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
    def _select_topic_from_candidates(candidates: List[Dict[str, Any]], category: str) -> str:
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

    def _normalize_platforms(self, platforms: Any, fallback_language: str = "ko") -> List[Dict[str, str]]:
        items = platforms or []
        if isinstance(items, str):
            try:
                import json
                items = json.loads(items)
            except Exception:
                items = []

        normalized = []
        for item in items:
            if not isinstance(item, dict):
                continue
            platform = str(item.get("platform") or "wordpress").strip()
            target_id = str(item.get("target_id") or platform).strip()
            language = str(item.get("language") or fallback_language or "ko").strip()
            normalized.append({
                "platform": platform,
                "target_id": target_id,
                "language": language,
                "style": item.get("style", "info"),
                "user_notes": item.get("user_notes", ""),
                "category": item.get("category"),
            })
        return normalized

    @staticmethod
    def _campaign_ai_provider(campaign: Dict[str, Any]) -> str:
        provider = str(campaign.get("ai_provider") or "gemini").strip().lower()
        return provider if provider in ("gemini", "openai", "anthropic") else "gemini"

    @staticmethod
    def _campaign_ai_model(campaign: Dict[str, Any]) -> str:
        return str(campaign.get("ai_model") or "").strip()

    async def run_campaign(self, campaign_id: int) -> Dict[str, Any]:
        campaign = db.get_openclaw_campaign(campaign_id)
        if not campaign:
            return {"status": "error", "error": "campaign not found"}
        return await self.run_campaign_once(campaign)

    async def run_campaign_once(self, campaign: Dict[str, Any]) -> Dict[str, Any]:
        run_id = db.create_openclaw_run(campaign_id=campaign["id"])
        db.update_openclaw_run(
            run_id,
            status="running",
            current_stage="topic",
            started_at=datetime.utcnow().isoformat(timespec="seconds"),
        )

        try:
            topic = await self.generate_topic(run_id, campaign)
            db.update_openclaw_run(run_id, topic=topic, current_stage="draft")

            generation_result = await self.generate_variants(run_id, topic, campaign)
            if generation_result["status"] != "ok":
                db.update_openclaw_run(
                    run_id,
                    status="failed",
                    current_stage="draft",
                    error_message=generation_result.get("error", "variant generation failed"),
                    completed_at=datetime.utcnow().isoformat(timespec="seconds"),
                )
                return generation_result

            review = await self.review_variants(run_id, campaign)
            requires_approval = campaign.get("approval_mode", "auto") != "auto"
            if review.get("requires_approval") or requires_approval:
                db.update_openclaw_run(
                    run_id,
                    status="waiting_approval",
                    current_stage="approval",
                    approval_required=1,
                    summary_json=review,
                )
                return {
                    "status": "ok",
                    "run_id": run_id,
                    "campaign_id": campaign["id"],
                    "topic": topic,
                    "next_action": "approval",
                    "summary": review,
                }

            publish_result = await self.publish_run(run_id)
            run_status = publish_result.get("status", "failed")
            db.update_openclaw_run(
                run_id,
                status=run_status,
                current_stage="completed",
                approval_required=0,
                summary_json=publish_result,
                completed_at=datetime.utcnow().isoformat(timespec="seconds"),
            )
            return {
                "status": "ok",
                "run_id": run_id,
                "campaign_id": campaign["id"],
                "topic": topic,
                "next_action": "completed",
                "summary": publish_result,
            }
        except Exception as e:
            db.update_openclaw_run(
                run_id,
                status="failed",
                current_stage="error",
                error_message=str(e),
                completed_at=datetime.utcnow().isoformat(timespec="seconds"),
            )
            return {"status": "error", "run_id": run_id, "error": str(e)}

    async def generate_topic(self, run_id: int, campaign: Dict[str, Any]) -> str:
        category = str(campaign.get("category") or "IT").strip()
        provider = self._campaign_ai_provider(campaign)
        model = self._campaign_ai_model(campaign)
        topic_mode = str(campaign.get("topic_mode") or "trend").strip().lower()
        language = str(campaign.get("default_language") or "ko").strip()

        task_id = db.create_openclaw_task(
            run_id=run_id,
            task_type="topic",
            status="running",
            input_json={
                "category": category,
                "topic_mode": topic_mode,
                "language": language,
                "provider": provider,
                "model": model,
            },
        )

        prompt = f"""
You are a senior SEO strategist for blog automation.
Current date: {datetime.utcnow().date().isoformat()}
Category: {category}
Target language: {language}
Topic mode: {topic_mode}

Generate 5 highly clickable blog topic ideas for this campaign.
Return ONLY valid JSON array. Each object must contain:
- title: short, specific, and clickable
- reason: one short sentence explaining why it is timely

Example format:
[
  {{"title":"...", "reason":"..."}},
  {{"title":"...", "reason":"..."}}
]
"""

        try:
            raw = await gemini_service.generate_text(
                prompt,
                temperature=0.85,
                max_tokens=900,
                provider_override=provider,
                model_override=model,
            )
            candidates = self._extract_json_array(raw)
            topic = self._select_topic_from_candidates(candidates, category)
            db.update_openclaw_task(
                task_id,
                status="completed",
                output_json={"source": "ai", "topic": topic, "candidates": candidates, "raw": raw},
                error_message="",
            )
            return topic
        except Exception as e:
            fallback_topic = self._select_topic_from_candidates([], category)
            db.update_openclaw_task(
                task_id,
                status="failed",
                error_message=str(e),
                output_json={"source": "fallback", "topic": fallback_topic},
            )
            return fallback_topic

    async def generate_variants(self, run_id: int, topic: str, campaign: Dict[str, Any]) -> Dict[str, Any]:
        platforms = self._normalize_platforms(campaign.get("platforms_json"), campaign.get("default_language", "ko"))
        if not platforms:
            return {"status": "error", "error": "no target platforms configured"}

        task_id = db.create_openclaw_task(
            run_id=run_id,
            task_type="draft",
            status="running",
            input_json={"topic": topic, "platforms": platforms},
        )
        result = await blog_service.generate_independent_multi_language_blogs(
            topic=topic,
            platforms=platforms,
            source_content="",
            provider_override=self._campaign_ai_provider(campaign),
            model_override=self._campaign_ai_model(campaign),
        )

        if result.get("status") != "ok":
            db.update_openclaw_task(task_id, status="failed", error_message=result.get("error", "generation failed"), output_json=result)
            return result

        variants = []
        for item in result.get("results", []):
            target_id = item.get("target_id") or item.get("platform") or "wordpress"
            platform = next((p["platform"] for p in platforms if p["target_id"] == target_id), item.get("platform", "wordpress"))
            language = item.get("language") or next((p["language"] for p in platforms if p["target_id"] == target_id), campaign.get("default_language", "ko"))
            variant_id = db.create_content_variant(
                run_id=run_id,
                target_id=target_id,
                platform=platform,
                language=language,
                title=item.get("title", ""),
                summary=item.get("summary", ""),
                tags_json=item.get("tags", []),
                content_html=item.get("content", ""),
                images_json=[],
                publish_status="draft" if item.get("status") == "ok" else "failed",
                quality_report_json={"generation_status": item.get("status"), "generation_error": item.get("error", "")},
            )
            variants.append({
                "variant_id": variant_id,
                "target_id": target_id,
                "status": item.get("status"),
                "title": item.get("title", ""),
            })

        task_status = "completed" if any(v["status"] == "ok" for v in variants) else "failed"
        db.update_openclaw_task(task_id, status=task_status, output_json={"variants": variants, "raw": result})
        return {"status": "ok", "variants": variants}

    async def review_variants(self, run_id: int, campaign: Dict[str, Any]) -> Dict[str, Any]:
        variants = db.get_content_variants(run_id)
        min_score = int(campaign.get("quality_min_score") or 82)
        approval_mode = campaign.get("approval_mode", "auto")
        review_items = []
        approval_ids = []

        for variant in variants:
            if variant.get("publish_status") == "failed":
                continue

            task_id = db.create_openclaw_task(
                run_id=run_id,
                task_type="quality_review",
                target_id=variant["target_id"],
                status="running",
                input_json={"variant_id": variant["id"], "platform": variant["platform"], "language": variant["language"]},
            )
            quality = await ai_quality_service.review_and_improve(
                title=variant.get("title", ""),
                content=variant.get("content_html", ""),
                tags=variant.get("tags_json", []) or [],
                categories=[campaign.get("category")] if campaign.get("category") else [],
                summary=variant.get("summary", ""),
                platform=variant.get("platform", "wordpress"),
                language=variant.get("language", "ko"),
                provider_override=self._campaign_ai_provider(campaign),
                model_override=self._campaign_ai_model(campaign),
            )
            score = int(quality.get("score") or 0)
            db.update_content_variant(
                variant["id"],
                title=quality.get("title", variant.get("title", "")),
                summary=quality.get("summary", variant.get("summary", "")),
                tags_json=quality.get("tags", variant.get("tags_json", []) or []),
                content_html=quality.get("content", variant.get("content_html", "")),
                quality_score=score,
                quality_report_json=quality,
                publish_status="approved" if approval_mode == "auto" and score >= min_score else "pending_approval",
            )
            db.update_openclaw_task(task_id, status="completed", output_json={"score": score, "quality": quality})
            review_items.append({
                "target_id": variant["target_id"],
                "platform": variant["platform"],
                "language": variant["language"],
                "score": score,
            })

            if approval_mode != "auto" or score < min_score:
                approval_id = db.create_approval_queue_item(
                    run_id=run_id,
                    task_id=task_id,
                    target_id=variant["target_id"],
                    title=quality.get("title", variant.get("title", "")),
                    summary=quality.get("summary", variant.get("summary", "")),
                    content_html=quality.get("content", variant.get("content_html", "")),
                )
                approval_ids.append(approval_id)

        requires_approval = len(approval_ids) > 0
        return {
            "reviewed_count": len(review_items),
            "requires_approval": requires_approval,
            "approval_ids": approval_ids,
            "items": review_items,
        }

    async def publish_run(self, run_id: int) -> Dict[str, Any]:
        variants = db.get_content_variants(run_id)
        approved = [v for v in variants if v.get("publish_status") in ("approved", "pending_publish")]
        if not approved:
            return {"status": "failed", "error": "no approved variants to publish"}

        primary = approved[0]
        contents = {}
        metadata = {}
        platform_langs = {}
        platforms = []
        publish_task_ids = {}

        for variant in approved:
            target_id = variant["target_id"]
            platforms.append(target_id)
            contents[target_id] = variant.get("content_html", "")
            metadata[target_id] = {
                "title": variant.get("title", ""),
                "tags": variant.get("tags_json", []) or [],
                "summary": variant.get("summary", ""),
                "category": "",
            }
            platform_langs[target_id] = variant.get("language", "ko")
            publish_task_ids[target_id] = db.create_openclaw_task(
                run_id=run_id,
                task_type="publish",
                target_id=target_id,
                status="queued",
                input_json={"target_id": target_id, "platform": variant.get("platform", "wordpress")},
            )

        req = BlogPostRequest(
            title=primary.get("title", ""),
            content=primary.get("content_html", ""),
            tags=primary.get("tags_json", []) or [],
            categories=[],
            summary=primary.get("summary", ""),
            platforms=platforms,
            platform_langs=platform_langs,
            contents=contents,
            metadata=metadata,
        )
        result = await post_blog(req)
        results_map = result.get("results", {}) or {}

        for variant in approved:
            publish_result = results_map.get(variant["target_id"]) or results_map.get(variant["platform"]) or {}
            status = publish_result.get("status", "error")
            db.update_content_variant(
                variant["id"],
                publish_status="published" if status == "ok" else "failed",
                publish_url=publish_result.get("url", ""),
                publish_post_id=str(publish_result.get("post_id", "") or ""),
            )
            task_id = publish_task_ids.get(variant["target_id"])
            if task_id:
                db.update_openclaw_task(
                    task_id,
                    status="completed" if status == "ok" else "failed",
                    output_json=publish_result,
                    error_message="" if status == "ok" else str(publish_result.get("error", "")),
                )

        ok_count = len([1 for item in results_map.values() if isinstance(item, dict) and item.get("status") == "ok"])
        fail_count = len([1 for item in results_map.values() if isinstance(item, dict) and item.get("status") != "ok"])
        status = "completed" if fail_count == 0 else ("partial" if ok_count > 0 else "failed")
        return {
            "status": status,
            "success_count": ok_count,
            "failed_count": fail_count,
            "results": results_map,
        }

    async def approve_run_item(self, approval_id: int, reviewer: str = "user", note: str = "") -> Dict[str, Any]:
        approval = db.get_approval_queue_item(approval_id)
        if not approval:
            return {"status": "error", "error": "approval item not found"}
        if approval.get("status") != "pending":
            return {"status": "error", "error": "approval item already processed"}

        variants = db.get_content_variants(approval["run_id"])
        matched = next((v for v in variants if v["target_id"] == approval["target_id"]), None)
        if not matched:
            return {"status": "error", "error": "content variant not found"}

        db.update_approval_queue_item(
            approval_id,
            status="approved",
            reviewer=reviewer,
            review_note=note,
            approved_at=datetime.utcnow().isoformat(timespec="seconds"),
        )
        db.update_content_variant(matched["id"], publish_status="approved")

        pending = [item for item in db.get_approval_queue_items(status="pending") if item["run_id"] == approval["run_id"]]
        if pending:
            return {"status": "ok", "run_id": approval["run_id"], "pending_count": len(pending)}

        publish_result = await self.publish_run(approval["run_id"])
        db.update_openclaw_run(
            approval["run_id"],
            status=publish_result.get("status", "failed"),
            current_stage="completed",
            approval_required=0,
            summary_json=publish_result,
            completed_at=datetime.utcnow().isoformat(timespec="seconds"),
        )
        return {"status": "ok", "run_id": approval["run_id"], "published": True, "summary": publish_result}

    async def retry_run(self, run_id: int) -> Dict[str, Any]:
        run = db.get_openclaw_run(run_id)
        if not run:
            return {"status": "error", "error": "run not found"}

        if run.get("status") == "waiting_approval":
            pending = [item for item in db.get_approval_queue_items(status="pending") if item["run_id"] == run_id]
            if pending:
                return {"status": "error", "error": "run is waiting for approval"}

        variants = db.get_content_variants(run_id)
        publishable = []
        for variant in variants:
            variant_status = variant.get("publish_status")
            if variant_status in ("approved", "failed", "pending_publish", "published"):
                if variant_status == "failed":
                    db.update_content_variant(variant["id"], publish_status="approved")
                publishable.append(variant)

        if publishable:
            db.update_openclaw_run(
                run_id,
                status="running",
                current_stage="retry_publish",
                error_message="",
                completed_at=None,
            )
            publish_result = await self.publish_run(run_id)
            db.update_openclaw_run(
                run_id,
                status=publish_result.get("status", "failed"),
                current_stage="completed",
                approval_required=0,
                summary_json=publish_result,
                completed_at=datetime.utcnow().isoformat(timespec="seconds"),
            )
            return {"status": "ok", "run_id": run_id, "mode": "republish", "summary": publish_result}

        campaign_id = run.get("campaign_id")
        if not campaign_id:
            return {"status": "error", "error": "campaign not found for retry"}
        rerun_result = await self.run_campaign(campaign_id)
        return {"status": "ok", "run_id": run_id, "mode": "rerun_campaign", "rerun": rerun_result}

    async def retry_failed_runs(self, limit: int = 10, campaign_id: Optional[int] = None) -> Dict[str, Any]:
        runs = db.get_openclaw_runs(limit=limit, campaign_id=campaign_id)
        candidates = [run for run in runs if run.get("status") in ("failed", "partial")]
        results = []

        for run in candidates:
            retry_result = await self.retry_run(int(run["id"]))
            results.append({
                "run_id": run["id"],
                "status": retry_result.get("status", "error"),
                "mode": retry_result.get("mode", ""),
            })

        return {
            "status": "ok",
            "requested": len(candidates),
            "processed": len(results),
            "results": results,
        }

    def reject_run_item(self, approval_id: int, reviewer: str = "user", note: str = "") -> Dict[str, Any]:
        approval = db.get_approval_queue_item(approval_id)
        if not approval:
            return {"status": "error", "error": "approval item not found"}
        if approval.get("status") != "pending":
            return {"status": "error", "error": "approval item already processed"}

        db.update_approval_queue_item(
            approval_id,
            status="rejected",
            reviewer=reviewer,
            review_note=note,
        )
        variants = db.get_content_variants(approval["run_id"])
        matched = next((v for v in variants if v["target_id"] == approval["target_id"]), None)
        if matched:
            db.update_content_variant(matched["id"], publish_status="rejected")

        run_pending = [item for item in db.get_approval_queue_items(status="pending") if item["run_id"] == approval["run_id"]]
        if not run_pending:
            db.update_openclaw_run(
                approval["run_id"],
                status="failed",
                current_stage="approval",
                error_message="all approval items were processed without publish",
                completed_at=datetime.utcnow().isoformat(timespec="seconds"),
            )
        return {"status": "ok", "run_id": approval["run_id"], "pending_count": len(run_pending)}


openclaw_service = OpenClawService()

