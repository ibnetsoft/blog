import re
from typing import List, Optional

from pydantic import BaseModel

import database as db
from services.ai_quality_service import ai_quality_service
from services.blog_service import blog_service
from services.publish_utils import (
    normalize_publish_result,
    open_published_urls,
    run_with_backoff,
    validate_blog_post_payload,
    validate_publish_html,
)
from services.social_publish_service import social_publish_service


class BlogPostRequest(BaseModel):
    title: str
    content: str
    tags: List[str] = []
    categories: List[str] = []
    summary: Optional[str] = None
    platforms: List[str] = ["wordpress"]
    platform_langs: dict = {}
    contents: Optional[dict] = None
    metadata: Optional[dict] = None
    social_assets: Optional[dict] = None


class PublishWorkflowService:
    async def publish_blog_post(self, req: BlogPostRequest) -> dict:
        results = {}
        quality_reviews = {}
        platforms = req.platforms or ["wordpress"]
        platform_langs = req.platform_langs or {}
        payload_validation = validate_blog_post_payload(req.title, req.content, platforms)
        html_validation = validate_publish_html(req.content)
        validation_errors = payload_validation["errors"] + html_validation["errors"]
        validation_warnings = payload_validation["warnings"] + html_validation["warnings"]
        if validation_errors:
            return {
                "status": "error",
                "error": "invalid publish payload",
                "errors": validation_errors,
                "warnings": validation_warnings,
            }

        processed_content = req.content
        social_assets = req.social_assets or {}

        if req.contents:
            for platform_id in req.contents:
                try:
                    req.contents[platform_id] = await blog_service.upload_local_images_to_public(req.contents[platform_id])
                except Exception as e:
                    print(f"[BlogPost] Image pre-upload error for {platform_id}: {e}")

        try:
            req.content = await blog_service.upload_local_images_to_public(req.content)
            processed_content = req.content
            print("[BlogPost] Primary content image pre-upload done")
        except Exception as img_err:
            print(f"[BlogPost] Primary image pre-upload error: {img_err}")

        source_images = []
        if "wordpress" in platforms:
            try:
                print("[BlogPost] Step 1: Posting to WordPress First (Image URL Base)...")
                if req.contents and "wordpress" in req.contents:
                    final_content = req.contents["wordpress"]
                    metadata = req.metadata.get("wordpress", {}) if req.metadata else {}
                    final_title = metadata.get("title") or req.title
                    final_tags = metadata.get("tags") or req.tags
                    final_categories = metadata.get("category", "").split(",") if metadata.get("category") else req.categories
                    final_summary = metadata.get("summary") or req.summary
                else:
                    final_content = req.content
                    final_title = req.title
                    final_tags = req.tags
                    final_categories = req.categories
                    final_summary = req.summary

                final_content = await blog_service.upload_local_images_to_public(final_content)

                quality = await ai_quality_service.review_and_improve(
                    title=final_title,
                    content=final_content,
                    tags=final_tags,
                    categories=final_categories,
                    summary=final_summary,
                    platform="wordpress",
                    language=platform_langs.get("wordpress", "ko"),
                )
                quality_reviews["wordpress"] = {
                    "status": quality.get("status"),
                    "score": quality.get("score"),
                    "issues": quality.get("issues", []),
                    "improvements": quality.get("improvements", []),
                    "original_title": final_title,
                    "improved_title": quality.get("title", final_title),
                }
                final_title = quality.get("title", final_title)
                final_content = quality.get("content", final_content)
                final_tags = quality.get("tags", final_tags)
                final_categories = quality.get("categories", final_categories)
                final_summary = quality.get("summary", final_summary)

                async def _post_wp():
                    return await blog_service.post_to_wordpress(
                        title=final_title,
                        content=final_content,
                        tags=final_tags,
                        categories=final_categories,
                        summary=final_summary,
                    )

                wp_result = await run_with_backoff(_post_wp, platform="wordpress", max_attempts=3, base_delay=1.0)
                wp_result["payload"] = {
                    "title": final_title,
                    "content": final_content,
                    "tags": final_tags,
                    "categories": final_categories,
                    "summary": final_summary,
                }
                results["wordpress"] = wp_result

                if wp_result.get("status") == "ok":
                    source_images = blog_service.extract_image_tags(final_content)
                    print(f"[BlogPost] WP Success! Global images extracted: {len(source_images)}")
            except Exception as e:
                print(f"[BlogPost] WordPress posting failed (Step 1): {e}")
                results["wordpress"] = {"status": "error", "error": str(e)}

        all_source_images = []
        all_source_images.extend(blog_service.extract_image_tags(req.content))
        if "wordpress" in results and results["wordpress"].get("status") == "ok":
            wp_payload = results["wordpress"].get("payload", {})
            all_source_images.extend(blog_service.extract_image_tags(wp_payload.get("content", "")))

        if req.contents:
            for content_html in req.contents.values():
                all_source_images.extend(blog_service.extract_image_tags(content_html))

        unique_images = {}
        for tag in all_source_images:
            match = re.search(r'src="([^"]+)"', tag)
            if match:
                url = match.group(1)
                if url not in unique_images:
                    unique_images[url] = tag

        source_images = list(unique_images.values())
        print(f"[BlogPost] Global image pool updated: {len(source_images)} unique images available for all blogs.")

        social_target_ids = [
            p for p in platforms
            if p in ("facebook", "instagram", "tiktok")
            or p.startswith("facebook:")
            or p.startswith("instagram:")
            or p.startswith("tiktok:")
        ]

        selected_blogger_ids = []
        for platform in platforms:
            if platform == "blogger":
                accounts = db.get_blogger_accounts()
                selected_blogger_ids.extend([str(a["id"]) for a in accounts if a.get("refresh_token")])
            elif platform.startswith("blogger:"):
                selected_blogger_ids.append(platform.split(":")[1])
            elif platform.startswith("blogger_"):
                selected_blogger_ids.append(platform.split("_")[1])

        if selected_blogger_ids:
            import asyncio

            selected_blogger_ids = list(set(selected_blogger_ids))
            accounts = db.get_blogger_accounts()
            connected_accounts = [a for a in accounts if str(a.get("id")) in selected_blogger_ids and a.get("refresh_token")]

            if not connected_accounts:
                results["blogger"] = {"status": "error", "error": "연동된 구글 블로그 계정이 없습니다."}
            else:
                async def post_single_blogger(acc):
                    acc_id = acc["id"]
                    acc_name = acc["name"]
                    platform_key = f"blogger_{acc_id}"
                    try:
                        target_lang = platform_langs.get(f"blogger:{acc_id}") or platform_langs.get(platform_key) or acc.get("lang") or "ja"
                        print(f"[Parallel] Posting {acc_name} ({target_lang})...")

                        if req.contents and (f"blogger:{acc_id}" in req.contents or platform_key in req.contents):
                            final_content = req.contents.get(f"blogger:{acc_id}") or req.contents.get(platform_key)
                            metadata = (req.metadata.get(f"blogger:{acc_id}") or req.metadata.get(platform_key, {})) if req.metadata else {}
                            final_title = metadata.get("title") or req.title
                            final_tags = metadata.get("tags") or req.tags
                            final_summary = metadata.get("summary") or req.summary
                            final_category = metadata.get("category") or (req.categories[0] if req.categories else "")
                            if source_images:
                                final_content = blog_service.inject_images_into_content(final_content, source_images)
                        else:
                            final_title, final_content = req.title, req.content
                            final_tags, final_summary = req.tags, req.summary
                            if target_lang != "ko":
                                translation = await blog_service.translate_blog(req.title, req.content, target_lang, summary=req.summary)
                                if translation.get("status") == "ok":
                                    final_title, final_content = translation["title"], translation["content"]
                                    final_summary = translation.get("summary")
                            final_category = req.categories[0] if req.categories else ""
                            if source_images:
                                final_content = blog_service.inject_images_into_content(final_content, source_images)

                        quality = await ai_quality_service.review_and_improve(
                            title=final_title,
                            content=final_content,
                            tags=final_tags,
                            categories=[final_category] if final_category else [],
                            summary=final_summary,
                            platform=platform_key,
                            language=target_lang,
                        )
                        quality_reviews[platform_key] = {
                            "status": quality.get("status"),
                            "score": quality.get("score"),
                            "issues": quality.get("issues", []),
                            "improvements": quality.get("improvements", []),
                            "original_title": final_title,
                            "improved_title": quality.get("title", final_title),
                        }
                        final_title = quality.get("title", final_title)
                        final_content = quality.get("content", final_content)
                        final_tags = quality.get("tags", final_tags)
                        final_summary = quality.get("summary", final_summary)
                        improved_categories = quality.get("categories") or ([final_category] if final_category else [])
                        final_category = improved_categories[0] if improved_categories else final_category

                        async def _post_blogger():
                            return await blog_service.post_to_blogger(
                                title=final_title,
                                content=final_content,
                                tags=final_tags,
                                account_id=acc_id,
                                summary=final_summary,
                                category=final_category,
                                image_tags=source_images,
                            )

                        result = await run_with_backoff(_post_blogger, platform=platform_key, max_attempts=5, base_delay=6.0, max_delay=60.0)
                        result["payload"] = {
                            "title": final_title,
                            "content": final_content,
                            "tags": final_tags,
                            "account_id": acc_id,
                            "summary": final_summary,
                            "category": final_category,
                            "image_tags": source_images,
                        }
                        print(f"[BloggerPost] {acc_name} DONE: {result.get('status')}")
                        return platform_key, {**result, "account_name": acc_name}
                    except Exception as e:
                        print(f"[BloggerPost] {acc_name} FAILED: {e}")
                        return platform_key, {
                            "status": "error",
                            "account_name": acc_name,
                            "error": str(e),
                            "error_type": "unknown",
                            "retryable": False,
                        }

                print(f"[BlogPost] Step 2: Sequential posting to {len(connected_accounts)} Blogger accounts...")
                blogger_results = []
                for index, account in enumerate(connected_accounts):
                    if index > 0:
                        await asyncio.sleep(3)
                    blogger_results.append(await post_single_blogger(account))
                for item in blogger_results:
                    if isinstance(item, Exception):
                        key = f"blogger_unknown_{len(results)}"
                        results[key] = {
                            "status": "error",
                            "error": str(item),
                            "error_type": "unknown",
                            "retryable": False,
                        }
                        continue
                    key, value = item
                    results[key] = value

        telegram_targets = [p for p in platforms if p == "telegram" or p.startswith("telegram:")]
        if telegram_targets:
            try:
                import json
                from services.telegram_service import telegram_service

                clean_text = re.sub(r"<[^>]+>", "", processed_content)
                clean_text = re.sub(r"\n\s*\n", "\n", clean_text).strip()
                summary = clean_text[:300] + "..." if len(clean_text) > 300 else clean_text
                image_match = re.search(r'<img [^>]*src="([^"]+)"[^>]*>', processed_content)
                first_img = image_match.group(1) if image_match else None
                telegram_text = f"<b>{req.title}</b>\n\n{summary}"

                channels_raw = db.get_global_setting("telegram_channels", "[]")
                if isinstance(channels_raw, str):
                    try:
                        all_channels = json.loads(channels_raw)
                    except Exception:
                        all_channels = []
                else:
                    all_channels = channels_raw or []

                default_chat_id = db.get_global_setting("telegram_chat_id", "")
                if default_chat_id and not any(str(c.get("chat_id")) == str(default_chat_id) for c in all_channels):
                    all_channels.insert(0, {"name": "기본 그룹", "chat_id": default_chat_id})

                target_chat_ids = []
                for platform in telegram_targets:
                    if platform == "telegram":
                        for channel in all_channels:
                            if channel.get("chat_id") not in target_chat_ids:
                                target_chat_ids.append(channel.get("chat_id"))
                    elif platform.startswith("telegram:"):
                        chat_id = platform.split(":", 1)[1]
                        if chat_id not in target_chat_ids:
                            target_chat_ids.append(chat_id)

                if not target_chat_ids:
                    results["telegram"] = {"status": "error", "error": "선택된 텔레그램 채널이 없습니다."}
                else:
                    statuses = []
                    for chat_id in target_chat_ids:
                        if not chat_id:
                            continue
                        if first_img:
                            result = await telegram_service.send_photo(first_img, telegram_text, chat_id=chat_id)
                        else:
                            result = await telegram_service.send_message(telegram_text, chat_id=chat_id)
                        statuses.append(result.get("status") == "ok")

                    if all(statuses):
                        results["telegram"] = {"status": "ok", "account_name": f"텔레그램({len(statuses)}개 채널)"}
                    elif any(statuses):
                        results["telegram"] = {"status": "ok", "account_name": f"텔레그램(일부 성공: {sum(statuses)}/{len(statuses)})"}
                    else:
                        results["telegram"] = {"status": "error", "error": "모든 텔레그램 채널 전송 실패"}
            except Exception as e:
                results["telegram"] = {"status": "error", "error": f"Telegram Broadcast Error: {e}"}

        if social_target_ids:
            import asyncio

            async def post_social_target(target_id: str):
                platform_name, _, configured_target = target_id.partition(":")
                platform_name = platform_name.lower()
                content_key = target_id if req.contents and target_id in req.contents else platform_name
                metadata_key = target_id if req.metadata and target_id in req.metadata else platform_name
                social_key = target_id if social_assets and target_id in social_assets else platform_name

                platform_content = (req.contents or {}).get(content_key) or req.content
                platform_meta = (req.metadata or {}).get(metadata_key, {}) if req.metadata else {}
                asset = social_assets.get(social_key, {}) if social_assets else {}
                title = platform_meta.get("title") or req.title
                summary = platform_meta.get("summary") or req.summary
                tags = platform_meta.get("tags") or req.tags

                if asset.get("caption"):
                    summary = asset.get("caption")
                if asset.get("image_urls") and "<img" not in platform_content:
                    image_html = "".join([f'<img src="{url}" alt="social asset">' for url in asset.get("image_urls", [])])
                    platform_content = image_html + "\n" + platform_content

                if platform_name == "facebook":
                    result = await social_publish_service.publish_facebook(
                        title=title,
                        html_content=platform_content,
                        tags=tags,
                        summary=summary,
                        target_id=configured_target or None,
                    )
                elif platform_name == "instagram":
                    result = await social_publish_service.publish_instagram(
                        title=title,
                        html_content=platform_content,
                        tags=tags,
                        summary=summary,
                        target_id=configured_target or None,
                    )
                elif platform_name == "tiktok":
                    result = await social_publish_service.publish_tiktok(
                        title=title,
                        html_content=platform_content,
                        tags=tags,
                        summary=summary,
                        target_id=configured_target or None,
                        video_urls=asset.get("video_urls") or [],
                    )
                else:
                    result = {"status": "error", "error": f"지원하지 않는 소셜 플랫폼입니다: {target_id}"}

                return target_id.replace(":", "_"), result

            social_results = await asyncio.gather(*[post_social_target(target_id) for target_id in social_target_ids])
            for key, value in social_results:
                results[key] = value

        results = {platform: normalize_publish_result(platform, result) for platform, result in results.items()}

        for platform_key, result in results.items():
            try:
                platform_name = result.get("account_name", platform_key)
                db.add_job_log(
                    platform=platform_key,
                    account_name=platform_name,
                    title=req.title,
                    status=result.get("status", "error"),
                    message=result.get("error", result.get("message", "")),
                    url=result.get("url", ""),
                    payload=result.get("payload"),
                )
            except Exception as log_err:
                print(f"[LogSave] Error: {log_err}")

        any_ok = any(r.get("status") == "ok" for r in results.values())
        all_ok = all(r.get("status") == "ok" for r in results.values())
        opened_urls = open_published_urls(results, context="blog-post")

        return {
            "status": "ok" if all_ok else ("partial" if any_ok else "error"),
            "results": results,
            "warnings": validation_warnings,
            "opened_urls": opened_urls,
            "quality_reviews": quality_reviews,
        }


publish_workflow_service = PublishWorkflowService()
