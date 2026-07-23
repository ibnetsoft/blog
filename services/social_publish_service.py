import re
from typing import Any, Dict, List, Optional

import httpx

import database as db
from services.publish_utils import normalize_publish_result


class SocialPublishService:
    META_GRAPH_BASE = "https://graph.facebook.com/v23.0"
    TIKTOK_API_BASE = "https://open.tiktokapis.com"

    def _setting(self, key: str, default: str = "") -> str:
        value = db.get_global_setting(key, default)
        if isinstance(value, str):
            return value.strip()
        return str(value or default).strip()

    def _strip_html(self, html: str) -> str:
        text = re.sub(r"<style[\s\S]*?</style>", " ", html or "", flags=re.IGNORECASE)
        text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = text.replace("&nbsp;", " ")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _collect_image_urls(self, html: str) -> List[str]:
        urls = re.findall(r'<img\b[^>]*src=["\']([^"\']+)["\']', html or "", flags=re.IGNORECASE)
        public_urls = []
        for url in urls:
            if url.startswith("http://") or url.startswith("https://"):
                if url not in public_urls:
                    public_urls.append(url)
        return public_urls

    def _collect_video_urls(self, html: str) -> List[str]:
        urls = []
        patterns = [
            r'<video\b[^>]*src=["\']([^"\']+)["\']',
            r'<source\b[^>]*src=["\']([^"\']+)["\']',
            r'data-video-url=["\']([^"\']+)["\']',
        ]
        for pattern in patterns:
            for url in re.findall(pattern, html or "", flags=re.IGNORECASE):
                if (url.startswith("http://") or url.startswith("https://")) and url not in urls:
                    urls.append(url)
        return urls

    def _build_social_caption(
        self,
        title: str,
        html_content: str,
        tags: Optional[List[str]] = None,
        summary: Optional[str] = None,
        platform: str = "social",
    ) -> str:
        plain = self._strip_html(html_content)
        summary_text = (summary or "").strip()
        base = summary_text or plain

        if platform == "telegram":
            limit = 900
        elif platform == "instagram":
            limit = 2000
        elif platform == "facebook":
            limit = 4000
        else:
            limit = 3500

        hashtags = []
        for tag in tags or []:
            clean = re.sub(r"[^0-9A-Za-z가-힣_]", "", str(tag or "").strip())
            if clean:
                hashtags.append(f"#{clean}")
        hashtags = hashtags[:10]

        body = base[:limit].strip()
        caption_parts = [title.strip()] if title.strip() else []
        if body:
            caption_parts.append(body)
        if hashtags:
            caption_parts.append(" ".join(hashtags))
        return "\n\n".join(part for part in caption_parts if part)

    @staticmethod
    def _safe_json(response: httpx.Response) -> Dict[str, Any]:
        try:
            return response.json()
        except Exception:
            return {}

    @staticmethod
    def _meta_error_message(data: Dict[str, Any], fallback: str = "") -> str:
        error = data.get("error") or {}
        parts = []
        if error.get("message"):
            parts.append(str(error.get("message")))
        if error.get("type"):
            parts.append(f"type={error.get('type')}")
        if error.get("code") is not None:
            parts.append(f"code={error.get('code')}")
        if error.get("error_subcode") is not None:
            parts.append(f"subcode={error.get('error_subcode')}")
        if error.get("fbtrace_id"):
            parts.append(f"trace={error.get('fbtrace_id')}")
        return " | ".join(parts) or fallback

    @staticmethod
    def _tiktok_error_message(data: Dict[str, Any], fallback: str = "") -> str:
        error = data.get("error") or {}
        parts = []
        if error.get("message"):
            parts.append(str(error.get("message")))
        if error.get("code"):
            parts.append(f"code={error.get('code')}")
        if error.get("log_id"):
            parts.append(f"log_id={error.get('log_id')}")
        return " | ".join(parts) or fallback

    async def verify_facebook_connection(self) -> Dict[str, Any]:
        page_id = self._setting("facebook_page_id")
        access_token = self._setting("facebook_access_token")
        if not page_id or not access_token:
            return {"status": "error", "message": "Facebook Page ID 또는 Access Token이 설정되지 않았습니다."}

        async with httpx.AsyncClient(timeout=20) as client:
            try:
                response = await client.get(
                    f"{self.META_GRAPH_BASE}/{page_id}",
                    params={"fields": "id,name", "access_token": access_token},
                )
                data = self._safe_json(response)
                if response.is_success and data.get("id"):
                    return {"status": "ok", "message": f"Facebook 연결 성공: {data.get('name', data.get('id'))}"}
                return {
                    "status": "error",
                    "message": self._meta_error_message(data, response.text or "Facebook 연결 확인 실패"),
                }
            except Exception as e:
                return {"status": "error", "message": f"Facebook 연결 확인 실패: {e}"}

    async def verify_instagram_connection(self) -> Dict[str, Any]:
        account_id = self._setting("instagram_account_id")
        access_token = self._setting("instagram_access_token")
        if not account_id or not access_token:
            return {"status": "error", "message": "Instagram Account ID 또는 Access Token이 설정되지 않았습니다."}

        async with httpx.AsyncClient(timeout=20) as client:
            try:
                response = await client.get(
                    f"{self.META_GRAPH_BASE}/{account_id}",
                    params={"fields": "id,username", "access_token": access_token},
                )
                data = self._safe_json(response)
                if response.is_success and data.get("id"):
                    return {"status": "ok", "message": f"Instagram 연결 성공: {data.get('username', data.get('id'))}"}
                return {
                    "status": "error",
                    "message": self._meta_error_message(data, response.text or "Instagram 연결 확인 실패"),
                }
            except Exception as e:
                return {"status": "error", "message": f"Instagram 연결 확인 실패: {e}"}

    async def verify_tiktok_connection(self) -> Dict[str, Any]:
        access_token = self._setting("tiktok_access_token")
        if not access_token:
            return {"status": "error", "message": "TikTok Access Token이 설정되지 않았습니다."}

        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=20) as client:
            try:
                response = await client.post(
                    f"{self.TIKTOK_API_BASE}/v2/post/publish/creator_info/query/",
                    headers=headers,
                    json={},
                )
                data = self._safe_json(response)
                creator = data.get("data") or {}
                if response.is_success and not data.get("error"):
                    username = creator.get("creator_username") or creator.get("display_name") or "TikTok creator"
                    return {"status": "ok", "message": f"TikTok 연결 성공: {username}"}
                return {
                    "status": "error",
                    "message": self._tiktok_error_message(data, response.text or "TikTok 연결 확인 실패"),
                }
            except Exception as e:
                return {"status": "error", "message": f"TikTok 연결 확인 실패: {e}"}

    async def publish_facebook(
        self,
        title: str,
        html_content: str,
        tags: Optional[List[str]] = None,
        summary: Optional[str] = None,
        target_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        page_id = target_id or self._setting("facebook_page_id")
        access_token = self._setting("facebook_access_token")
        if not page_id or not access_token:
            return normalize_publish_result("facebook", {
                "status": "error",
                "error": "Facebook Page ID 또는 Access Token이 설정되지 않았습니다."
            })

        message = self._build_social_caption(title, html_content, tags, summary, platform="facebook")
        image_urls = self._collect_image_urls(html_content)

        async with httpx.AsyncClient(timeout=60) as client:
            try:
                if image_urls:
                    photo_payload = {
                        "url": image_urls[0],
                        "caption": message[:2200],
                        "access_token": access_token,
                    }
                    response = await client.post(f"{self.META_GRAPH_BASE}/{page_id}/photos", data=photo_payload)
                else:
                    feed_payload = {
                        "message": message,
                        "access_token": access_token,
                    }
                    response = await client.post(f"{self.META_GRAPH_BASE}/{page_id}/feed", data=feed_payload)

                data = self._safe_json(response)
                if response.is_success and data.get("id"):
                    return normalize_publish_result("facebook", {
                        "status": "ok",
                        "post_id": data.get("id"),
                        "url": f"https://www.facebook.com/{data.get('id')}",
                        "message": "Facebook 게시 완료"
                    })
                error_message = self._meta_error_message(data, response.text)
                return normalize_publish_result("facebook", {
                    "status": "error",
                    "status_code": response.status_code,
                    "error": error_message,
                })
            except Exception as e:
                return normalize_publish_result("facebook", {"status": "error", "error": str(e)})

    async def publish_instagram(
        self,
        title: str,
        html_content: str,
        tags: Optional[List[str]] = None,
        summary: Optional[str] = None,
        target_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        account_id = target_id or self._setting("instagram_account_id")
        access_token = self._setting("instagram_access_token")
        if not account_id or not access_token:
            return normalize_publish_result("instagram", {
                "status": "error",
                "error": "Instagram Account ID 또는 Access Token이 설정되지 않았습니다."
            })

        image_urls = self._collect_image_urls(html_content)
        if not image_urls:
            return normalize_publish_result("instagram", {
                "status": "error",
                "error": "Instagram 게시에는 공개 이미지 URL이 최소 1개 필요합니다. 이미지 업로드 후 다시 시도하세요."
            })

        caption = self._build_social_caption(title, html_content, tags, summary, platform="instagram")[:2200]

        async with httpx.AsyncClient(timeout=60) as client:
            try:
                create_payload = {
                    "image_url": image_urls[0],
                    "caption": caption,
                    "access_token": access_token,
                }
                create_res = await client.post(f"{self.META_GRAPH_BASE}/{account_id}/media", data=create_payload)
                create_data = self._safe_json(create_res)
                creation_id = create_data.get("id")
                if not create_res.is_success or not creation_id:
                    error_message = self._meta_error_message(
                        create_data,
                        create_res.text or "Instagram media container 생성 실패"
                    )
                    return normalize_publish_result("instagram", {
                        "status": "error",
                        "status_code": create_res.status_code,
                        "error": f"Instagram media 생성 실패: {error_message}",
                    })

                publish_payload = {
                    "creation_id": creation_id,
                    "access_token": access_token,
                }
                publish_res = await client.post(f"{self.META_GRAPH_BASE}/{account_id}/media_publish", data=publish_payload)
                publish_data = self._safe_json(publish_res)
                post_id = publish_data.get("id")
                if publish_res.is_success and post_id:
                    return normalize_publish_result("instagram", {
                        "status": "ok",
                        "post_id": post_id,
                        "url": f"https://www.instagram.com/p/{post_id}/",
                        "message": "Instagram 게시 완료"
                    })
                error_message = self._meta_error_message(
                    publish_data,
                    publish_res.text or "Instagram media_publish 실패"
                )
                return normalize_publish_result("instagram", {
                    "status": "error",
                    "status_code": publish_res.status_code,
                    "error": f"Instagram publish 실패: {error_message}",
                })
            except Exception as e:
                return normalize_publish_result("instagram", {"status": "error", "error": str(e)})

    async def publish_tiktok(
        self,
        title: str,
        html_content: str,
        tags: Optional[List[str]] = None,
        summary: Optional[str] = None,
        target_id: Optional[str] = None,
        video_urls: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        access_token = target_id or self._setting("tiktok_access_token")
        if not access_token:
            return normalize_publish_result("tiktok", {
                "status": "error",
                "error": "TikTok Access Token이 설정되지 않았습니다."
            })

        video_candidates = list(video_urls or [])
        for url in self._collect_video_urls(html_content):
            if url not in video_candidates:
                video_candidates.append(url)
        image_urls = self._collect_image_urls(html_content)

        caption = self._build_social_caption(title, html_content, tags, summary, platform="tiktok")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

        if video_candidates:
            payload = {
                "post_info": {
                    "title": title[:90],
                    "privacy_level": "SELF_ONLY",
                    "disable_comment": False,
                    "disable_duet": False,
                    "disable_stitch": False,
                    "video_cover_timestamp_ms": 1000,
                },
                "source_info": {
                    "source": "PULL_FROM_URL",
                    "video_url": video_candidates[0],
                },
                "post_mode": "DIRECT_POST",
            }
            endpoint = f"{self.TIKTOK_API_BASE}/v2/post/publish/video/init/"
            success_message = "TikTok 비디오 게시 요청 완료"
            missing_error = "TikTok 비디오 게시에는 공개 video URL이 필요합니다."
        else:
            if not image_urls:
                return normalize_publish_result("tiktok", {
                    "status": "error",
                    "error": "TikTok 포토 게시에는 공개 이미지 URL이 최소 1개 필요합니다. 또는 공개 video URL을 제공하세요."
                })
            payload = {
                "post_info": {
                    "title": title[:90],
                    "description": caption[:4000],
                    "privacy_level": "SELF_ONLY",
                    "disable_comment": False,
                    "disable_duet": False,
                    "disable_stitch": False,
                    "brand_content_toggle": False,
                    "brand_organic_toggle": False,
                },
                "source_info": {
                    "source": "PULL_FROM_URL",
                    "photo_images": image_urls[:35],
                    "photo_cover_index": 0,
                },
                "post_mode": "DIRECT_POST",
                "media_type": "PHOTO",
            }
            endpoint = f"{self.TIKTOK_API_BASE}/v2/post/publish/content/init/"
            success_message = "TikTok 포토 게시 요청 완료"
            missing_error = "TikTok 포토 게시에는 공개 이미지 URL이 필요합니다."

        async with httpx.AsyncClient(timeout=60) as client:
            try:
                response = await client.post(endpoint, headers=headers, json=payload)
                data = self._safe_json(response)
                publish_id = (
                    data.get("data", {}).get("publish_id")
                    or data.get("data", {}).get("share_url")
                    or data.get("publish_id")
                )
                error = data.get("error") or {}
                if response.is_success and (publish_id or not error):
                    return normalize_publish_result("tiktok", {
                        "status": "ok",
                        "post_id": str(publish_id or "pending"),
                        "url": data.get("data", {}).get("share_url", ""),
                        "message": success_message,
                    })
                error_message = self._tiktok_error_message(data, response.text or missing_error)
                return normalize_publish_result("tiktok", {
                    "status": "error",
                    "status_code": response.status_code,
                    "error": f"TikTok 게시 실패: {error_message}",
                })
            except Exception as e:
                return normalize_publish_result("tiktok", {"status": "error", "error": str(e)})

    def build_platform_asset(
        self,
        target_id: str,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        summary: Optional[str] = None,
        video_urls: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        platform = (target_id or "").split(":", 1)[0].lower()
        return {
            "platform": platform,
            "target_id": target_id,
            "title": title,
            "content": content,
            "summary": summary or "",
            "tags": tags or [],
            "caption": self._build_social_caption(title, content, tags, summary, platform=platform),
            "image_urls": self._collect_image_urls(content),
            "video_urls": list(video_urls or self._collect_video_urls(content)),
        }


social_publish_service = SocialPublishService()
