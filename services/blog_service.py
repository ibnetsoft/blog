import os
import re
import json
import httpx
import asyncio
from typing import Optional, Dict, Any, List
from services.source_service import source_service
from services.gemini_service import gemini_service
import database as db
from config import config

class BlogService:
    async def check_all_api_connections(self) -> Dict[str, Any]:
        """모든 플랫폼의 연동 상태를 실시간으로 체크"""
        results = {
            "gemini": {"status": "ok", "message": "연결됨"},
            "wordpress": {"status": "ok", "message": "연결됨"},
            "blogger": {"status": "ok", "message": "연결됨"},
            "telegram": {"status": "ok", "message": "연결됨"}
        }

        # 1. Gemini 체크 (단순히 키가 있는지 확인)
        if not config.GEMINI_API_KEY:
             results["gemini"] = {"status": "error", "message": "API 키가 설정되지 않았습니다."}
        
        # 2. WordPress 체크
        wp_res = await self.verify_wordpress_connection()
        if wp_res["status"] != "ok":
            results["wordpress"] = wp_res

        # 3. Blogger 체크 (계정별 실시간 체크)
        accounts = db.get_blogger_accounts()
        if accounts:
            active_accounts = [acc for acc in accounts if acc.get('is_active', 1)]
            if not active_accounts:
                results["blogger"] = {"status": "error", "message": "활성화된 Blogger 계정이 없습니다."}
            else:
                failing_accounts = []
                for acc in active_accounts:
                    res = await self.verify_blogger_connection(acc['id'])
                    if res["status"] != "ok":
                        failing_accounts.append(f"{acc['name']}({acc['lang']}): {res['message']}")
                
                if failing_accounts:
                    results["blogger"] = {
                        "status": "error", 
                        "message": "일부 계정 연동 오류: " + ", ".join(failing_accounts)
                    }
        else:
            # 계정이 하나도 없는 경우 전역 설정 체크 (하위 호환)
            blogger_res = await self.verify_blogger_connection()
            if blogger_res["status"] != "ok":
                results["blogger"] = blogger_res
            
        # 4. Telegram 체크
        if not config.TELEGRAM_TOKEN:
            results["telegram"] = {"status": "error", "message": "토큰이 설정되지 않았습니다."}

        return results

    async def verify_blogger_connection(self, account_id: int = None) -> Dict[str, str]:
        """Blogger 연동(Access Token 갱신)이 실제로 유효한지 확인"""
        try:
            if account_id:
                acc = db.get_blogger_account(account_id)
                if not acc:
                    return {"status": "error", "message": f"계정(ID:{account_id})을 찾을 수 없습니다."}
                client_id = acc.get("client_id") or config.BLOG_CLIENT_ID
                client_secret = acc.get("client_secret") or config.BLOG_CLIENT_SECRET
                refresh_token = acc.get("refresh_token", "")
            else:
                client_id = config.BLOG_CLIENT_ID or db.get_global_setting("blog_client_id", "")
                client_secret = config.BLOG_CLIENT_SECRET or db.get_global_setting("blog_client_secret", "")
                refresh_token = db.get_global_setting("blog_refresh_token", "")

            if not refresh_token:
                return {"status": "error", "message": "Refresh Token이 없습니다. 재연동이 필요합니다."}
            
            if not client_id or not client_secret:
                return {"status": "error", "message": "클라이언트 ID/비밀번호 설정이 누락되었습니다."}

            token = await self._refresh_access_token(client_id, client_secret, refresh_token)
            if token:
                return {"status": "ok", "message": "연결됨"}
            else:
                return {"status": "error", "message": "Google 인증 토큰 갱신 실패 (만료되었거나 권한이 취소됨)"}
        except Exception as e:
            return {"status": "error", "message": f"오류: {str(e)}"}

    async def verify_wordpress_connection(self) -> Dict[str, str]:
        """WordPress API 연동 유효성 확인"""
        try:
            import base64
            wp_url = config.WP_URL or db.get_global_setting("wp_url", "")
            username = config.WP_USERNAME or db.get_global_setting("wp_username", "")
            password = config.WP_PASSWORD or db.get_global_setting("wp_password", "")

            if not wp_url or not username or not password:
                return {"status": "error", "message": "워드프레스 설정 정보가 부족합니다."}

            wp_url = wp_url.rstrip('/')
            endpoint = f"{wp_url}/index.php?rest_route=/wp/v2/users/me"
            
            auth_str = f"{username}:{password}"
            auth_base64 = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
            headers = {"Authorization": f"Basic {auth_base64}"}

            async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
                res = await client.get(endpoint, headers=headers, timeout=10)
                if res.status_code == 200:
                    return {"status": "ok", "message": "연결됨"}
                elif res.status_code == 401:
                    return {"status": "error", "message": "워드프레스 인증 실패 (아이디/앱 비밀번호 확인)"}
                else:
                    return {"status": "error", "message": f"워드프레스 연결 실패 ({res.status_code})"}
        except Exception as e:
            return {"status": "error", "message": f"연결 오류: {str(e)}"}

    async def process_blog_automation_v2(
        self,
        project_id: Optional[int],
        platform: str = "wordpress",
        blog_style: str = "info",
        language: str = "ko",
        user_notes: str = "",
        raw_script: str = None,
        category: str = None
    ) -> Dict[str, Any]:
        """프로젝트 데이터를 기반으로 제목, 본문, 이미지를 자동으로 생성 및 구성 (다중 이미지 지원)"""
        try:
            # 1. 프로젝트 데이터(대본) 로드 또는 직접 입력 사용
            if project_id:
                script_data = db.get_script(project_id)
                if not script_data or not script_data.get("full_script"):
                    shorts_data = db.get_shorts(project_id)
                    if shorts_data and shorts_data.get("shorts_data"):
                        scenes = shorts_data.get("shorts_data", {}).get("scenes", [])
                        if not scenes and isinstance(shorts_data.get("shorts_data"), list):
                            scenes = shorts_data.get("shorts_data")
                        script = "\n".join([(s.get("narration") or s.get("dialogue") or "") for s in scenes])
                    else:
                        return {"status": "error", "error": "대본이 없습니다. 먼저 대본을 생성해주세요."}
                else:
                    script = script_data["full_script"]
            elif raw_script:
                script = raw_script
            else:
                return {"status": "error", "error": "처리할 대본(script) 또는 프로젝트 ID가 없습니다."}

            # 2. 블로그 본문 및 제목 생성 (Gemini)
            blog_result = await self.generate_blog_from_source(
                source_type="text",
                source_value=script,
                platform=platform,
                blog_style=blog_style,
                language=language,
                user_notes=user_notes,
                category=category
            )

            if blog_result["status"] != "ok":
                return blog_result

            title = blog_result["title"]
            content = blog_result["content"]
            tags = blog_result.get("tags", [])

            # 3. 이미지 삽입 포인트 및 프롬프트 분석 (publish_service 연동)
            from services.publish_service import publish_service
            # 글 길이에 따라 자동으로 이미지 개수 결정 및 위치/프롬프트 추출
            image_points = await publish_service.analyze_image_points(content)
            
            # 4. 이미지 생성 및 저장
            generated_images = []
            final_images_data = [] # build_blog_html용 데이터

            if image_points:
                from main import get_project_output_dir
                import time
                abs_dir, web_dir = get_project_output_dir(project_id)
                
                print(f"[BlogAuto] Generating {len(image_points)} images...")
                
                for i, point in enumerate(image_points):
                    try:
                        # 각 포인트의 영문 프롬프트로 이미지 생성
                        prompt = point.get("prompt_en")
                        if not prompt:
                            continue
                        
                        # [사람 제외 규칙] 인물이 나오지 않도록 프롬프트 보강
                        prompt += ", no humans, no people, photorealistic, professional style, architectural or product photography focus"
                            
                        image_bytes_list = await gemini_service.generate_image(
                            prompt=prompt,
                            aspect_ratio="16:9",
                            num_images=1
                        )

                        if image_bytes_list:
                            img_bytes = image_bytes_list[0]
                            file_prefix = f"blog_img_{project_id}" if project_id else "blog_img_raw"
                            filename = f"{file_prefix}_{int(time.time())}_{i}.png"
                            save_path = os.path.join(abs_dir, filename)
                            web_url = f"{web_dir}/{filename}"
                            
                            # [최적화] 서버 측 리사이징 (800px 축소)
                            try:
                                from PIL import Image
                                import io
                                img = Image.open(io.BytesIO(img_bytes))
                                if img.width > 800:
                                    new_height = int(img.height * (800 / img.width))
                                    # 명칭 호환성 유지 (LANCZOS)
                                    resample_filter = getattr(Image, 'Resampling', Image).LANCZOS
                                    img = img.resize((800, new_height), resample_filter)
                                    print(f"  - Image {i+1} Resized to 800px")
                                img.save(save_path, "PNG", optimize=True)
                            except Exception as resize_err:
                                print(f"  - Resize failed, saving original: {resize_err}")
                                with open(save_path, "wb") as f:
                                    f.write(img_bytes)
                            
                            generated_images.append(web_url)
                            # publish_service의 build_blog_html 규격에 맞게 데이터 저장
                            final_images_data.append({
                                "image_url": web_url,
                                "position": point.get("position", i + 1),
                                "caption": point.get("prompt_ko", ""),
                                "prompt_ko": point.get("prompt_ko", "")
                            })
                            print(f"  - Image {i+1} generated: {web_url}")
                    except Exception as img_err:
                        print(f"  - Image {i+1} generation failed: {img_err}")

            # 5. 본문에 이미지 지능적 삽입 (publish_service 활용)
            final_content = content
            if final_images_data:
                final_content = publish_service.build_blog_html(content, final_images_data)
            else:
                # 이미지 생성 실패 시 원문 그대로 (HTML 태그 등 보정만 수행)
                final_content = publish_service.build_blog_html(content, [])

            return {
                "status": "ok",
                "title": title,
                "content": final_content,
                "tags": tags,
                "images": generated_images
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e)}

    async def add_images_to_content(self, content: str, project_id: Optional[int] = None, image_count: int = 2, no_human: bool = True) -> Dict[str, Any]:
        """기존 내용(HTML/텍스트)을 분석하여 어울리는 이미지를 생성하고 삽입"""
        try:
            from services.publish_service import publish_service
            # 1. 이미지 포인트 분석 (publish_service 연동)
            image_points = await publish_service.analyze_image_points(content, image_count=image_count, no_human=no_human)
            
            # 2. 이미지 생성 및 저장
            generated_images = []
            final_images_data = []
            
            if image_points:
                from main import get_project_output_dir
                import time
                abs_dir, web_dir = get_project_output_dir(project_id)
                
                # 요청된 이미지 수만큼 조절
                image_points = image_points[:image_count]
                
                print(f"[BlogAuto] Image-Only: Generating {len(image_points)} images (requested: {image_count})...")
                
                for i, point in enumerate(image_points):
                    try:
                        prompt = point.get("prompt_en")
                        if not prompt: continue
                            
                        image_bytes_list = await gemini_service.generate_image(
                            prompt=prompt, aspect_ratio="16:9", num_images=1, no_human=no_human
                        )
                        if image_bytes_list:
                            img_bytes = image_bytes_list[0]
                            file_prefix = f"blog_img_{project_id}" if project_id else "blog_img_raw"
                            filename = f"{file_prefix}_{int(time.time())}_{i}.png"
                            save_path = os.path.join(abs_dir, filename)
                            web_url = f"{web_dir}/{filename}"
                            
                            # [최적화] 서버 측 리사이징 (800px 축소)
                            try:
                                from PIL import Image
                                import io
                                img = Image.open(io.BytesIO(img_bytes))
                                if img.width > 800:
                                    new_height = int(img.height * (800 / img.width))
                                    img = img.resize((800, new_height), Image.Resampling.LANCZOS)
                                    print(f"[BlogService] Image Resized to 800px")
                                img.save(save_path, "PNG", optimize=True)
                            except Exception as resize_err:
                                print(f"[BlogService] Resize failed, saving original: {resize_err}")
                                with open(save_path, "wb") as f: f.write(img_bytes)
                            
                            # 즉시 WordPress에 업로드하여 공개 URL 확보 (Blogger에서도 사용 가능)
                            public_url = web_url  # fallback
                            try:
                                upload_res = await self.upload_image_to_wordpress(save_path, filename)
                                if upload_res.get("status") == "ok" and upload_res.get("url"):
                                    public_url = upload_res["url"]
                                    print(f"  - Image {i+1} uploaded to WP: {public_url}")
                                else:
                                    print(f"  - Image {i+1} WP upload failed, using local: {web_url}")
                            except Exception as wp_err:
                                print(f"  - Image {i+1} WP upload error: {wp_err}, using local: {web_url}")
                            
                            generated_images.append(public_url)
                            final_images_data.append({
                                "image_url": public_url,
                                "position": point.get("position", i + 1),
                                "caption": point.get("prompt_ko", ""),
                                "prompt_ko": point.get("prompt_ko", "")
                            })
                            print(f"  - Image {i+1} generated: {public_url}")
                    except Exception as img_err:
                        print(f"  - Image {i+1} generation failed: {img_err}")

            # 3. 본문에 이미지 지능적 삽입
            final_content = publish_service.build_blog_html(content, final_images_data)
            
            return {
                "status": "ok",
                "content": final_content,
                "images": generated_images
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e)}

    def __init__(self):
        pass

    async def generate_blog_from_source(
        self, 
        source_type: str, 
        source_value: str, 
        platform: str, 
        blog_style: str, 
        language: str = "ko",
        user_notes: str = "",
        category: str = None
    ) -> Dict[str, Any]:
        """소스로부터 블로그 포스팅 생성 핵심 로직"""
        try:
            # 1. 소스 내용 추출
            content_data = {}
            if source_type == "youtube":
                content_data = await source_service.extract_text_from_youtube(source_value)
            elif source_type == "url":
                content_data = await source_service.extract_text_from_url(source_value)
            elif source_type == "text":
                content_data = {"title": "사용자 입력 텍스트", "content": source_value}
            else:
                return {"status": "error", "error": f"지원하지 않는 소스 유형입니다: {source_type}"}
    
            if not content_data.get("content"):
                return {"status": "error", "error": "소스에서 내용을 추출하지 못했습니다."}
    
            # 2. 블로그 생성 (Gemini)
            blog_data = await gemini_service.generate_blog_content(
                source_content=content_data["content"],
                platform=platform,
                blog_style=blog_style,
                language=language,
                user_notes=user_notes,
                category=category
            )

            if "error" in blog_data:
                return {"status": "error", "error": blog_data["error"]}

            return {
                "status": "ok",
                "title": blog_data.get("title"),
                "content": blog_data.get("content"),
                "tags": blog_data.get("tags", []),
                "summary": blog_data.get("summary"),
                "source_title": content_data.get("title")
            }

        except Exception as e:
            print(f"BlogService Error: {e}")
            return {"status": "error", "error": str(e)}

    async def generate_independent_multi_language_blogs(
        self,
        topic: str,
        platforms: List[Dict[str, str]],
        source_content: str = ""
    ) -> Dict[str, Any]:
        """[Localized Adaptation] 각 언어별 실정에 맞게 독립적으로 블로그 생성 (단순 번역이 아닌 원본 소스 기반 현지화)"""
        import asyncio
        
        # 1. 소스 내용 준비
        final_source = source_content if source_content and len(source_content.strip()) > 10 else topic
        
        # 2. 각 플랫폼/언어별 독립 생성 헬퍼
        async def generate_single(cfg: Dict[str, str]):
            lang = cfg.get("language", "ko")
            print(f"[BlogService] Generating localized content for {lang} context...")
            try:
                # 번역(translate_blog)이 아닌 원본 소스로부터 직접 생성(generate_blog_from_source)
                # 이를 통해 각 나라 실정에 맞는 독립적인 글이 생성됩니다.
                res = await self.generate_blog_from_source(
                    source_type="text",
                    source_value=final_source,
                    platform=cfg.get("platform", "wordpress"),
                    blog_style=cfg.get("style", "info"),
                    language=lang,
                    user_notes=cfg.get("user_notes", ""),
                    category=cfg.get("category")
                )
                res["language"] = lang
                res["target_id"] = cfg.get("target_id")
                return res
            except Exception as e:
                return {
                    "status": "error",
                    "language": lang,
                    "target_id": cfg.get("target_id"),
                    "error": str(e)
                }

        # 3. 모든 언어 병렬 생성 실행
        results = []
        if platforms:
            results = await asyncio.gather(*[generate_single(p) for p in platforms])

        return {"status": "ok", "results": results}


    async def upload_local_images_to_public(self, content: str) -> str:
        """본문 내 로컬 이미지(/output/)를 WordPress에 업로드하여 공개 URL로 일괄 치환.
        모든 플랫폼에서 재사용 가능한 공개 URL을 반환."""
        import re
        import urllib.parse

        # 로컬 이미지 경로 (/output/ 또는 output/) 및 다양한 따옴표 대응
        img_pattern = re.compile(r'<img [^>]*src=["\']?(/output/[^"\'>]+|output/[^"\'>]+)["\']?[^>]*>')
        matches = img_pattern.findall(content)

        if not matches:
            return content

        processed = content
        uploaded_cache = {}
        failed_paths = []

        for local_path in matches:
            if local_path in uploaded_cache:
                processed = processed.replace(local_path, uploaded_cache[local_path])
                continue

            decoded_path = urllib.parse.unquote(local_path)
            if decoded_path.startswith("/output/"):
                rel_path = decoded_path[8:]
                abs_path = os.path.join(config.OUTPUT_DIR, rel_path)

                if os.path.exists(abs_path):
                    print(f"[ImageUpload] Uploading: {abs_path}")
                    upload_res = await self.upload_image_to_wordpress(abs_path)
                    if upload_res["status"] == "ok":
                        public_url = upload_res["url"]
                        uploaded_cache[local_path] = public_url
                        processed = processed.replace(local_path, public_url)
                        print(f"[ImageUpload] OK → {public_url}")
                    else:
                        print(f"[ImageUpload] FAIL: {upload_res.get('error')}")
                        failed_paths.append(local_path)
                else:
                    print(f"[ImageUpload] File not found: {abs_path}")
                    failed_paths.append(local_path)
            else:
                failed_paths.append(local_path)

        # 업로드 실패한 이미지 태그 제거 (깨진 아이콘 방지)
        for fp in failed_paths:
            processed = re.sub(
                r'<div[^>]*>\s*<img[^>]*src="' + re.escape(fp) + r'"[^>]*>\s*</div>',
                '', processed
            )
            processed = re.sub(
                r'<img[^>]*src="' + re.escape(fp) + r'"[^>]*>',
                '', processed
            )

        return processed

    def extract_body_content(self, html_content: str) -> str:
        """HTML 문서에서 body 태그 또는 <html> 태그를 안전하게 걷어내고 본문만 추출 (WordPress 레이아웃 보호)"""
        import re
        
        # 1. 스타일(style) 태그 보존을 위해 별도 추출
        style_match = re.search(r'(<style[\s\S]*?</style>)', html_content, re.IGNORECASE)
        styles = style_match.group(1) if style_match else ""
        
        # 2. <body> 태그 내부 추출
        body_match = re.search(r'<body[^>]*>([\s\S]*?)</body>', html_content, re.IGNORECASE)
        if body_match:
            content = body_match.group(1).strip()
            return f"{styles}\n{content}"
        
        # 3. <body>가 없으면 <html>, <head> 등만 단순 제거 (위태로운 div 정규식 제거)
        clean_content = re.sub(r'<!DOCTYPE[^>]*>|<html>|</html>|<head>[\s\S]*?</head>|<body>|</body>', '', html_content, flags=re.IGNORECASE).strip()
            
        return f"{styles}\n{clean_content}"

    async def post_to_wordpress(
        self,
        title: str,
        content: str,
        tags: List[str] = None,
        categories: List[str] = None,
        summary: str = None
    ) -> Dict[str, Any]:
        """워드프레스에 글 게시"""
        try:
            import base64
            from config import config
            wp_url = config.WP_URL.rstrip('/')
            username = config.WP_USERNAME
            password = config.WP_PASSWORD

            if not wp_url or not username or not password:
                # DB에서 다시 로드 시도
                wp_url = db.get_global_setting("wp_url", "").rstrip('/')
                username = db.get_global_setting("wp_username", "")
                password = db.get_global_setting("wp_password", "")

            if not wp_url:
                wp_url = ""
            
            endpoint = f"{wp_url.rstrip('/')}/index.php?rest_route=/wp/v2/posts"
            
            # Basic Auth Header
            auth_str = f"{username}:{password}"
            auth_bytes = auth_str.encode("utf-8")
            auth_base64 = base64.b64encode(auth_bytes).decode("utf-8")
            headers = {
                "Authorization": f"Basic {auth_base64}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            # 1. 이미지 및 리소스 업로드 (로컬 경로 /output/ 이미지를 공개 URL로 치환)
            content = await self.upload_local_images_to_public(content)
            
            # [FIX] 워드프레스 레이아웃 깨짐 방지: <html>, <body> 태그 등이 있으면 본문만 추출
            processed_content = self.extract_body_content(content)

            # 2. 카테고리/태그 메타데이터 생성 (SEO 및 정보 제공용)
            meta_footer = ""
            if categories and any(isinstance(c, str) for c in categories):
                meta_footer += "\n\n<p><strong>Category:</strong> " + ", ".join([str(c) for c in categories]) + "</p>"
            
            if tags:
                meta_footer += "\n\n<p><strong>Tags:</strong> " + " ".join([f"#{t}" for t in tags]) + "</p>"

            # [FIX] 스타일이 있는 경우 Gutenberg HTML 블록으로 감싸기 (메타데이터 포함)
            import re
            if re.search(r'<style[\s\S]*?</style>', processed_content, re.IGNORECASE):
                # 스타일과 본문, 그리고 메타데이터를 모두 블록 안에 넣음
                processed_content = f'<!-- wp:html -->\n{processed_content}{meta_footer}\n<!-- /wp:html -->'
            else:
                # 스타일이 없으면 일반 텍스트로 추가
                processed_content += meta_footer

            payload = {
                "title": title,
                "content": processed_content,
                "status": "publish",
                "categories": [] # ID가 아닌 경우 비움
            }
            if summary:
                payload["excerpt"] = summary

            async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
                res = await client.post(endpoint, json=payload, headers=headers, timeout=30)

                if res.status_code in [200, 201]:
                    data = res.json()
                    post_id = data.get("id")
                    url = data.get("link")
                    return {
                        "status": "ok", 
                        "post_id": post_id, 
                        "url": url,
                        "message": "워드프레스에 성공적으로 게시되었습니다."
                    }
                else:
                    try:
                        error_data = res.json()
                        err_code = error_data.get("code", "unknown")
                        err_msg = error_data.get("message", res.text)
                        
                        full_error = f"워드프레스 API 오류({res.status_code}): {err_msg} [{err_code}]"
                        if res.status_code == 401:
                            full_error += "\n(아이디가 'admin'이 맞는지, 앱 비밀번호에 공백이 포함되었는지 확인하세요.)"
                        elif res.status_code == 403:
                            full_error += "\n(보안 플러그인에 의해 차단되었을 수 있습니다. index.php 우회 방식을 적용했습니다.)"
                    except:
                        full_error = f"워드프레스 응답 오류({res.status_code}): {res.text[:200]}"
                    
                    return {"status": "error", "error": full_error}


        except Exception as e:
            print(f"post_to_wordpress Error: {e}")
            return {"status": "error", "error": str(e)}

    async def upload_image_to_wordpress(self, image_path: str, filename: str = None) -> Dict[str, Any]:
        """이미지를 WordPress Media Library에 업로드하고 URL 반환"""
        try:
            import base64
            wp_url = config.WP_URL
            username = config.WP_USERNAME
            password = config.WP_PASSWORD

            if not (wp_url and username and password):
                # DB에서 다시 로드 시도
                wp_url = db.get_global_setting("wp_url", "")
                username = db.get_global_setting("wp_username", "")
                password = db.get_global_setting("wp_password", "")

            if not (wp_url and username and password):
                return {"status": "error", "error": "워드프레스 설정(URL, 사용자명, 앱 비밀번호)이 되어있지 않습니다. 설정 페이지에서 '저장' 버튼을 눌러주세요."}
            
            wp_url = wp_url.rstrip('/')
            endpoint = f"{wp_url}/index.php?rest_route=/wp/v2/media"
            auth_str = f"{username}:{password}"
            auth_base64 = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")


            if not filename:
                filename = os.path.basename(image_path)

            # MIME type 감지
            ext = os.path.splitext(filename)[1].lower()
            mime_map = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.webp': 'image/webp'}
            mime_type = mime_map.get(ext, 'image/png')

            with open(image_path, 'rb') as f:
                image_data = f.read()

            headers = {
                "Authorization": f"Basic {auth_base64}",
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": mime_type
            }

            max_retries = 3
            last_error = ""

            for attempt in range(max_retries):
                try:
                    async with httpx.AsyncClient(follow_redirects=True) as client:
                        res = await client.post(endpoint, content=image_data, headers=headers, timeout=120)
                        if res.status_code in [200, 201]:
                            data = res.json()
                            print(f"[WordPress] Image upload success on attempt {attempt + 1}")
                            return {
                                "status": "ok",
                                "media_id": data.get("id"),
                                "url": data.get("source_url", data.get("guid", {}).get("rendered", "")),
                            }
                        else:
                            last_error = f"WordPress 이미지 업로드 실패 ({res.status_code}): {res.text[:200]}"
                            print(f"[WordPress] Upload failed (attempt {attempt + 1}): {last_error}")
                except Exception as e:
                    last_error = str(e)
                    print(f"[WordPress] Upload error (attempt {attempt + 1}): {last_error}")
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(2) # 2초 대기 후 재시도

            return {"status": "error", "error": f"WordPress 업로드 최종 실패 ({max_retries}회 시도): {last_error}"}

        except Exception as e:
            print(f"upload_image_to_wordpress Error: {e}")
            return {"status": "error", "error": str(e)}
    def prepare_html_for_blogger(self, content: str, summary: str = None, image_tags: List[str] = None) -> str:
        """전체 HTML 문서를 Blogger 포스트용으로 변환.
        - body/html/:root 스타일을 .bp-wrap 래퍼로 스코핑
        - <script> 제거 (Blogger API가 제거함)
        - JS 의존 애니메이션(opacity:0) 오버라이드하여 콘텐츠 항상 표시
        - summary를 본문의 맨 앞에 보이지 않게 삽입 (SEO용)"""
        import re
        
        # 전체 HTML 문서가 아니면 그대로 반환
        if not re.search(r'<html|<!DOCTYPE', content, re.IGNORECASE):
            return content
        
        print("[Blogger Prep] Full HTML document detected, processing...")
        
        # 1. <style> 블록 추출
        style_blocks = re.findall(r'<style[^>]*>([\s\S]*?)</style>', content, re.IGNORECASE)
        
        # 2. <link> 태그 추출 (Google Fonts 등)
        link_tags = re.findall(r'<link[^>]*(?:stylesheet|font|preconnect)[^>]*>', content, re.IGNORECASE)
        
        # 3. <body> 내용만 추출
        body_match = re.search(r'<body[^>]*>([\s\S]*)</body>', content, re.IGNORECASE)
        if body_match:
            body_content = body_match.group(1)
        else:
            # body 태그가 없으면 head/html 래퍼만 제거
            body_content = content
            for tag in ['<!DOCTYPE[^>]*>', '</?html[^>]*>', '<head[\\s\\S]*?</head>', '</?body[^>]*>']:
                body_content = re.sub(tag, '', body_content, flags=re.IGNORECASE)
        
        # 4. <script> 블록 제거 (Blogger API가 제거하므로, JS 의존 기능이 안 돌아감)
        body_content = re.sub(r'<script[\s\S]*?</script>', '', body_content, flags=re.IGNORECASE)
        
        # 4.5 인라인 style에서 opacity:0, transform 제거 (JS 없이도 보이도록)
        # opacity: 0 → 제거
        body_content = re.sub(r'opacity\s*:\s*0\s*;?', '', body_content)
        # transform: translateY(...) 등 → 제거
        body_content = re.sub(r'transform\s*:\s*[^;\"]+;?', '', body_content)
        # visibility: hidden → 제거
        body_content = re.sub(r'visibility\s*:\s*hidden\s*;?', '', body_content)
        # 빈 style="" 속성 정리
        body_content = re.sub(r'\s*style\s*=\s*"\s*"', '', body_content)
        
        # 5. CSS 스코핑
        scoped_css = ""
        for css in style_blocks:
            # :root, html, body 셀렉터 → .bp-wrap
            css = re.sub(r':root\s*\{', '.bp-wrap {', css)
            css = re.sub(r'(?<![.\w-])html\s*\{', '.bp-wrap {', css)
            css = re.sub(r'(?<![.\w-])html\s*,', '.bp-wrap,', css)
            css = re.sub(r'(?<![.\w-])body\s*\{', '.bp-wrap {', css)
            css = re.sub(r'(?<![.\w-])body\s*,', '.bp-wrap,', css)
            
            # *, *::before, *::after 전역 리셋 → .bp-wrap 내부로 스코핑
            css = re.sub(r'(?m)^\s*\*\s*([,{])', r'.bp-wrap * \1', css)
            
            # CSS 내 opacity:0 / visibility:hidden → 강제 표시 (JS 없이)
            css = re.sub(r'opacity\s*:\s*0\s*;', 'opacity: 1;', css)
            css = re.sub(r'visibility\s*:\s*hidden\s*;', 'visibility: visible;', css)
            
            scoped_css += css + "\n"
        
        # 6. 섹션 가시성 스타일 추가 (JS 없이도 표시되도록)
        force_visible = """
/* Blogger: JS 없이도 모든 요소 강제 표시 및 레이아웃 확보 */
.bp-wrap {
  display: block !important;
  min-height: auto !important;
  visibility: visible !important;
  opacity: 1 !important;
  position: relative !important;
  width: 100% !important;
  max-width: 820px !important; /* [Fix] 820px로 본문 영역 제한하여 중앙 정렬 유도 */
  margin: 0 auto !important;
  padding: 1.5rem 0 !important;
  background-color: transparent !important;
  box-sizing: border-box !important;
  overflow: visible !important;
  z-index: 1 !important;
}
.bp-wrap * {
  box-sizing: border-box !important;
  max-width: 100% !important;
}
.bp-wrap figure, .bp-wrap div.premium-blog-image, .bp-wrap div[style*="text-align:center"] {
  display: flex !important;
  flex-direction: column !important;
  align-items: center !important;
  justify-content: center !important;
  text-align: center !important;
  margin: 3.5rem auto !important;
  width: 100% !important;
  clear: both !important;
}
.bp-wrap img {
  display: block !important;
  width: 85% !important; /* [Fix] 너무 큰 이미지 크기 85%로 축소 */
  max-width: 680px !important; /* [Fix] 절대적인 너비 680px로 제한 */
  height: auto !important;
  margin: 0 auto !important;
  border-radius: 20px !important;
  box-shadow: 0 15px 45px rgba(0,0,0,0.08) !important;
  object-fit: contain !important;
}
/* 가독성 패치: 배경과 글자색의 선명한 대비(Contrast) 확보 */
.bp-wrap {
  color: #333333 !important; /* 기본 글자색: 어두운 회색 */
}

/* [Fix] Blogger 다크 테마 대응: 흰색 배경 위에서 흰색 글씨(테마 기본값)가 보이는 문제 강제 해결 */
.bp-wrap p, .bp-wrap h1, .bp-wrap h2, .bp-wrap h3, .bp-wrap h4, .bp-wrap h5, .bp-wrap h6,
.bp-wrap span, .bp-wrap li, .bp-wrap a, .bp-wrap b, .bp-wrap strong, .bp-wrap em, .bp-wrap i {
  color: #333333 !important;
}

/* 1. 배경이 어두운 섹션 정밀 탐지 및 흰색 글씨 강제 (우리 툴이 생성한 어두운 섹션 전용) */
.bp-wrap [style*="background-color: rgb(17, 17, 17)"],
.bp-wrap [style*="background: rgb(17, 17, 17)"],
.bp-wrap [style*="background-color: #111"],
.bp-wrap [style*="background: #111"],
.bp-wrap [style*="background: #000"],
.bp-wrap [style*="background-color: #000"],
.bp-wrap [style*="background-color: rgb(17, 17, 17)"] *,
.bp-wrap [style*="background: rgb(17, 17, 17)"] *,
.bp-wrap [style*="background-color: #111"] *,
.bp-wrap [style*="background: #111"] *,
.bp-wrap [style*="background: #000"] *,
.bp-wrap [style*="background-color: #000"] *,
.bp-wrap .dark-mode, .bp-wrap .dark-mode *, 
.bp-wrap [class*="hero"][style*="background"], .bp-wrap [class*="hero"][style*="background"] *,
.bp-wrap [class*="card"][style*="background-color"], .bp-wrap [class*="card"][style*="background-color"] * {
  color: #ffffff !important;
}

/* 2. 어두운 배경 내부의 텍스트 요소들 명시 보정 */
.bp-wrap [style*="background"] h1, .bp-wrap [style*="background"] h2, .bp-wrap [style*="background"] h3,
.bp-wrap [style*="background"] p, .bp-wrap [style*="background"] span,
.bp-wrap [style*="background"] li, .bp-wrap [style*="background"] a, 
.bp-wrap [class*="hero"][style*="background"] h1,
.bp-wrap [class*="hero"][style*="background"] p {
  color: #ffffff !important;
  text-shadow: 0 1px 2px rgba(0,0,0,0.3) !important;
}

/* 3. 예외: 배경이 투명하거나 밝은 톤인 클래스는 다시 어두운 글씨로 */
.bp-wrap [class*="hero"]:not([style*="background"]),
.bp-wrap [class*="card"]:not([style*="background"]) {
  color: #222222 !important;
}

/* 4. Blogger 본문의 모든 텍스트 변수(테마 변수) 강제 오버라이드 */
.bp-wrap {
  --text-color: #333333 !important;
  --body-text: #333333 !important;
  --title-color: #222222 !important;
}

/* 레이아웃 구조용 요소들만 block 강제 */
.bp-wrap div, .bp-wrap section, .bp-wrap p, .bp-wrap h1, .bp-wrap h2, .bp-wrap h3, .bp-wrap h4, .bp-wrap h5, .bp-wrap h6 {
  display: block;
  opacity: 1 !important;
  visibility: visible !important;
}
/* 뱃지, 버튼, 아이콘 등 인라인 요소들은 원래 크기 유지 (절대 늘어나지 않도록 고정) */
.bp-wrap span, .bp-wrap a, .bp-wrap img, .bp-wrap b, .bp-wrap i, .bp-wrap strong, .bp-wrap em, .bp-wrap small,
.bp-wrap [class*="badge"], .bp-wrap [class*="tag"], .bp-wrap [class*="button"], .bp-wrap [class*="btn"], 
.bp-wrap [class*="chip"], .bp-wrap [class*="pill"], .bp-wrap .deal-badge, .bp-wrap .buy-button {
  display: inline-block !important;
  width: auto !important;
  max-width: fit-content !important;
  opacity: 1 !important;
  visibility: visible !important;
}
.bp-wrap .section,
.bp-wrap section,
.bp-wrap [class*="fade"],
.bp-wrap [class*="slide"],
.bp-wrap [class*="animate"],
.bp-wrap [class*="reveal"],
.bp-wrap [class*="hidden"],
.bp-wrap [data-aos],
.bp-wrap [class*="hero"],
.bp-wrap [class*="feature"] {
  opacity: 1 !important;
  transform: none !important;
  visibility: visible !important;
  transition: none !important;
  animation: none !important;
  display: block !important;
  min-height: auto !important;
}
.bp-wrap .container, .bp-wrap .content-card, .bp-wrap article {
  max-width: 780px !important; /* [Fix] .bp-wrap 내부의 요소에만 엄격하게 적용 */
  width: 94% !important;
  margin: 0 auto !important;
  padding: 2.5rem 2rem !important;
  background-color: #ffffff !important;
  border-radius: 24px !important;
  box-shadow: 0 10px 40px rgba(0,0,0,0.05) !important;
}
"""
        scoped_css += force_visible
        
        # 7. 최종 조립
        result_parts = []
        for link in link_tags:
            result_parts.append(link)
        if scoped_css.strip():
            result_parts.append(f"<style>\n{scoped_css}</style>")
        
        # 7. 본문 래퍼 시작
        result_parts.append('<div class="bp-wrap">')
        
        # 8. 요약문(summary) 삽입 (SEO 최적화 및 레이아웃 구조 보호)
        # 중요: 스타일 태그 뒤, 본문 래퍼 내부의 맨 앞에 배치하여 스타일이 무시되지 않도록 함
        if summary:
            summary_html = f'<div style="display:none; overflow:hidden; width:0; height:0; max-height:0; max-width:0; opacity:0;">{summary}</div>\n'
            result_parts.append(summary_html)
            
        body_to_inject = body_content
        # 8.5 이미지 사후 주입 (이미지 유실 방지 최종 단계)
        if image_tags:
            body_to_inject = self.inject_images_into_content(body_to_inject, image_tags)
            
        result_parts.append(body_to_inject)
        result_parts.append('</div>') # .bp-wrap close
        
        final_html = "\n".join(result_parts)
        print(f"[Blogger Prep] Final HTML length: {len(final_html)}")
        return final_html

    async def post_to_blogger(
        self,
        title: str,
        content: str,
        tags: List[str] = None,
        account_id: int = None,
        summary: str = None,
        category: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """구글 블로그(Blogger)에 글 게시 - 계정별 또는 전역 설정 사용"""
        try:
            print(f"[Blogger] --- Post Request Start ---")
            print(f"[Blogger] Target Account: {account_id}, Title: {title[:30]}")
            if account_id:
                # DB에서 해당 계정 정보 가져오기
                acc = db.get_blogger_account(account_id)
                if not acc:
                    print(f"[Blogger] ERROR: Account ID {account_id} not found in DB")
                    return {"status": "error", "error": f"Blogger 계정(id={account_id})을 찾을 수 없습니다."}
                blog_id = acc.get("blog_id")
                print(f"[Blogger] Found Blog ID in DB: {blog_id}")
                if not blog_id:
                    blog_id = config.BLOG_ID or db.get_global_setting("blog_id", "")
                    print(f"[Blogger] Fallback to Global Blog ID: {blog_id}")
                
                client_id = acc.get("client_id") or config.BLOG_CLIENT_ID or db.get_global_setting("blog_client_id", "")
                client_secret = acc.get("client_secret") or config.BLOG_CLIENT_SECRET or db.get_global_setting("blog_client_secret", "")
                refresh_token = acc.get("refresh_token", "")
            else:
                # 전역 설정(config / DB) 사용 (기존 방식)
                blog_id = config.BLOG_ID or db.get_global_setting("blog_id", "")
                client_id = config.BLOG_CLIENT_ID or db.get_global_setting("blog_client_id", "")
                client_secret = config.BLOG_CLIENT_SECRET or db.get_global_setting("blog_client_secret", "")
                refresh_token = None  # _get_blogger_access_token에서 DB에서 로드

            if not blog_id:
                return {"status": "error", "error": "블로그 ID가 설정되지 않았습니다. (설정 → API 설정)"}

            if not client_id or not client_secret:
                return {"status": "error", "error": "Google Blog API 클라이언트 ID/비밀번호가 설정되지 않았습니다."}

            # 1. Access Token 획득
            if account_id and refresh_token:
                access_token = await self._refresh_access_token(client_id, client_secret, refresh_token)
            else:
                access_token = await self._get_blogger_access_token(client_id, client_secret)

            if not access_token:
                return {"status": "error", "error": "Blogger 인증 실패. 설정 페이지의 'Google 블로그 연동' (OAuth) 버튼을 눌러 인증을 완료해주세요. (Refresh Token이 없습니다.)"}

            # 2. Blogger API v3로 포스트 게시
            endpoint = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts/"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            # 1. 이미지 및 리소스 업로드 (Blogger는 로컬 경로를 인식할 수 없으므로 WP 미디어 라이브러리로 업로드 후 URL 치환)
            content = await self.upload_local_images_to_public(content)

            # 2. Blogger용 HTML 전처리 및 게시글 준비 (이미지 누락 방지를 위해 image_tags 전달)
            content = self.prepare_html_for_blogger(content, summary=summary, image_tags=kwargs.get("image_tags"))
            html_content = content


            # Blogger API v3: Sanitize labels and simplify payload to avoid 400 errors
            full_labels = []
            if isinstance(tags, list):
                full_labels.extend(tags)
            elif isinstance(tags, str):
                # 영어 쉼표(,)와 아랍어 쉼표(،) 모두 지원
                full_labels.extend([t.strip() for t in re.split(r'[,،]', tags) if t.strip()])
            
            if category:
                # 카테고리(단일/콤마구상)를 라벨 목록에 추가
                cats = [c.strip() for c in category.split(',') if c.strip()]
                for c in cats:
                    if c not in full_labels:
                        full_labels.append(c)

            safe_labels = []
            if full_labels:
                for label in full_labels:
                    if not label: continue
                    # Remove characters that Blogger might reject as invalid arguments
                    # Commas are strictly forbidden within a single label string in some API contexts
                    # 영어 쉼표와 아랍어 쉼표 모두 공백으로 제거 (Blogger 라벨은 쉼표 불허)
                    clean_label = re.sub(r'[,،]', ' ', label)
                    
                    # BiDi 제어 문자 및 기타 비인쇄 문자 제거 (아랍어 번역 시 혼입 가능성)
                    clean_label = re.sub(r'[\u200e\u200f\u202a-\u202e]', '', clean_label)
                    
                    # Remove problematic HTML-like characters from labels
                    for char in '<>{}[]~':
                        clean_label = clean_label.replace(char, '')
                    
                    # 연속된 공백 정리
                    clean_label = re.sub(r'\s+', ' ', clean_label).strip()
                    
                    if len(clean_label) > 200: # Blogger limit
                        clean_label = clean_label[:197] + "..."
                    
                    if clean_label and clean_label not in safe_labels:
                        safe_labels.append(clean_label)

            payload = {
                "title": title.strip() or "Untitled Post",
                "content": html_content
            }
            
            # (이전의 display:none 요약문 결합 로직은 prepare_html_for_blogger 내부로 이동됨)

            if safe_labels:
                payload["labels"] = safe_labels

            print(f"[Blogger] Posting: account_id={account_id}, blog_id={blog_id}, title='{title[:50]}', content_len={len(html_content)}, labels={safe_labels}")
            async with httpx.AsyncClient() as client:
                res = await client.post(endpoint, json=payload, headers=headers, timeout=60)

                if res.status_code in [200, 201]:
                    data = res.json()
                    return {
                        "status": "ok",
                        "post_id": data.get("id"),
                        "url": data.get("url"),
                        "message": "구글 블로그에 성공적으로 게시되었습니다."
                    }
                else:
                    try:
                        error_data = res.json()
                        error_msg = error_data.get("error", {}).get("message", res.text)
                    except Exception:
                        error_msg = res.text
                    
                    # 400 에러 등에 대한 상세 로그
                    print(f"[Blogger] ERROR {res.status_code} on blog_id={blog_id}: {error_msg}")
                    print(f"[Blogger] Payload Keys: {list(payload.keys())}")
                    if "labels" in payload:
                        print(f"[Blogger] Labels count: {len(payload['labels'])}, labels: {payload['labels']}")
                    
                    full_error = f"Blogger 게시 실패 ({res.status_code}): {error_msg}"
                    if res.status_code == 400:
                        full_error += " (팁: 태그에 잘못된 문자가 포함되어 있거나 본문이 너무 길 수 있습니다. 태그를 정리해 보세요.)"
                    return {"status": "error", "error": full_error}

        except Exception as e:
            print(f"post_to_blogger Error: {e}")
            return {"status": "error", "error": str(e)}


    async def _get_blogger_access_token(self, client_id: str, client_secret: str) -> Optional[str]:
        """저장된 refresh_token으로 access_token 갱신"""
        try:
            # DB에 저장된 refresh_token 조회
            refresh_token = db.get_global_setting("blog_refresh_token", "")
            if not refresh_token:
                # token 파일에서 로드 시도
                token_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "blog_token.json")
                if os.path.exists(token_path):
                    with open(token_path, "r") as f:
                        token_data = json.load(f)
                        refresh_token = token_data.get("refresh_token", "")
                        if not refresh_token:
                            return None

            if not refresh_token:
                return None

            # Google OAuth2 token refresh
            async with httpx.AsyncClient() as client:
                res = await client.post("https://oauth2.googleapis.com/token", data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token"
                })

                if res.status_code == 200:
                    data = res.json()
                    return data.get("access_token")
                else:
                    print(f"Token refresh failed: {res.status_code} {res.text}")
                    return None

        except Exception as e:
            print(f"_get_blogger_access_token Error: {e}")
            return None

    async def _refresh_access_token(self, client_id: str, client_secret: str, refresh_token: str) -> Optional[str]:
        """refresh_token을 직접 받아 access_token 갱신 (계정별 처리용)"""
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post("https://oauth2.googleapis.com/token", data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token"
                })
                if res.status_code == 200:
                    return res.json().get("access_token")
                else:
                    print(f"[Blogger] Token refresh failed: {res.status_code} {res.text}")
                    return None
        except Exception as e:
            print(f"_refresh_access_token Error: {e}")
            return None

    async def translate_blog(self, title: str, content: str, target_language: str, summary: str = None, tags: str = None, category: str = None, skip_content: bool = False) -> Dict[str, Any]:
        """블로그 제목과 본문을 다른 언어로 번역 (HTML 구조/CSS 완벽 보존, 텍스트만 번역)"""
        import re

        lang_names = {
            "ko": "Korean", "en": "English", "ja": "Japanese",
            "vi": "Vietnamese", "zh": "Chinese",
            "es": "Spanish", "de": "German", "fr": "French",
            "it": "Italian", "pt": "Portuguese", "id": "Indonesian", "ar": "Arabic"
        }
        target_name = lang_names.get(target_language, target_language)

        from services.gemini_service import GeminiService
        gemini = GeminiService()

        # ── 2단계: 제목 번역 ──
        new_title = title
        if title and title.strip():
            title_prompt = f"Translate the following blog title into {target_name}. Detect the source language and translate to {target_name}. Output ONLY the translated text.\n\nTitle: {title}"
            try:
                translated_title = await gemini.generate_text(title_prompt, temperature=0.1, max_tokens=256)
                translated_title = translated_title.strip().strip('"').strip("'")
                
                # 불필요한 노이즈 제거 로직 강화
                noise_patterns = [
                    r'^Source\s*language\s*[:：]\s*.*?\n',
                    r'^Detected\s*language\s*[:：]\s*.*?\n',
                    r'^Translated\s*to\s*.*?\n',
                    r'^\[.*?\]\s*',
                    r'^(Title|제목|タイトル|翻訳)\s*[:：]\s*'
                ]
                for pattern in noise_patterns:
                    translated_title = re.sub(pattern, '', translated_title, flags=re.IGNORECASE)
                
                translated_title = translated_title.strip()
                if translated_title and translated_title != title:
                    new_title = translated_title
            except Exception as te:
                print(f"[Translate] Title translation error: {te}")

        # ── 2.2단계: 카테고리 번역 ──
        new_category = category
        if category and category.strip():
            cat_prompt = f"Translate the following blog category into {target_name}. Detect source language automatically. Output ONLY the translated category.\n\nCategory: {category}"
            try:
                translated_cat = await gemini.generate_text(cat_prompt, temperature=0.1, max_tokens=128)
                new_category = translated_cat.strip().strip('"').strip("'")
            except Exception as ce:
                print(f"[Translate] Category translation error: {ce}")

        # ── 2.5단계: 요약 번역 ──
        new_summary = summary
        if summary and summary.strip():
            summary_prompt = f"Translate the following blog summary/description into {target_name}. Detect source language. Output ONLY translated text.\n\nSummary: {summary}"
            try:
                translated_summary = await gemini.generate_text(summary_prompt, temperature=0.2, max_tokens=512)
                new_summary = translated_summary.strip()
            except Exception as se:
                print(f"[Translate] Summary translation error: {se}")

        # ── 2.7단계: 태그 번역 ──
        new_tags = tags
        if tags and tags.strip():
            tags_prompt = f"Translate the following blog markers/keywords/tags into {target_name}. Detect source language. Output ONLY the translated tags separated by commas.\n\nTags: {tags}"
            try:
                translated_tags = await gemini.generate_text(tags_prompt, temperature=0.1, max_tokens=256)
                translated_tags = translated_tags.strip().strip('"').strip("'")
                
                # 불필요한 노이즈 제거 로직 강화 (Source language: Korean 등)
                noise_patterns = [
                    r'Source\s*language\s*[:：]\s*[^\n,]*',
                    r'Detected\s*language\s*[:：]\s*[^\n,]*',
                    r'Translated\s*to\s*[^\n,]*',
                    r'^(Tags|태그|タグ|翻訳|Keywords)\s*[:：]\s*'
                ]
                for pattern in noise_patterns:
                    translated_tags = re.sub(pattern, '', translated_tags, flags=re.IGNORECASE).strip()
                
                # 콤마로 시작하거나 끝나는 경우 클리닝
                new_tags = translated_tags.strip(',').strip()
            except Exception as tg_err:
                print(f"[Translate] Tags translation error: {tg_err}")

        # ── 3단계: 본문 번역 (skip_content인 경우 여기서 즉시 반환 - 중요!) ──
        if skip_content:
            print(f"[Translate] Metadata only translation done for {target_name}.")
            return {
                "status": "ok",
                "title": new_title,
                "content": content,
                "summary": new_summary,
                "tags": new_tags,
                "category": new_category
            }

        # ── 1단계: 보존할 블록을 플레이스홀더로 치환 (번역할 때만 수행) ──
        preserve_store = {}
        counter = [0]
        def make_placeholder(match):
            key = f"__PRESERVE_{counter[0]}__"
            preserve_store[key] = match.group(0)
            counter[0] += 1
            return key

        safe_content = content
        safe_content = re.sub(r'<style[\s\S]*?</style>', make_placeholder, safe_content, flags=re.IGNORECASE)
        safe_content = re.sub(r'<head[\s\S]*?</head>', make_placeholder, safe_content, flags=re.IGNORECASE)
        safe_content = re.sub(r'<!DOCTYPE[^>]*>', make_placeholder, safe_content, flags=re.IGNORECASE)
        safe_content = re.sub(r'<html[^>]*>', make_placeholder, safe_content, flags=re.IGNORECASE)
        safe_content = re.sub(r'</html>', make_placeholder, safe_content, flags=re.IGNORECASE)
        safe_content = re.sub(r'<body[^>]*>', make_placeholder, safe_content, flags=re.IGNORECASE)
        safe_content = re.sub(r'</body>', make_placeholder, safe_content, flags=re.IGNORECASE)
        safe_content = re.sub(r'<script[\s\S]*?</script>', make_placeholder, safe_content, flags=re.IGNORECASE)
        safe_content = re.sub(r'<link[^>]*>', make_placeholder, safe_content, flags=re.IGNORECASE)
        safe_content = re.sub(r'<svg[\s\S]*?</svg>', make_placeholder, safe_content, flags=re.IGNORECASE)
        safe_content = re.sub(
            r'<div[^>]*class="separator"[^>]*>[\s\S]*?</div>|'
            r'<div[^>]*>\s*<img[^>]*>\s*</div>|'
            r'<figure[^>]*>.*?</figure>|'
            r'<img[^>]*>',
            make_placeholder, safe_content, flags=re.DOTALL
        )

        lang_guides = {
            "ja": "자연스럽고 세련된 일본어 경어체(Desu/Masu)를 사용하세요.",
            "en": "Professional, minimalist, and engaging standard English.",
            "ar": "Modern Standard Arabic with a professional and authoritative tone. Ensure correct grammar.",
            "it": "Sophisticated and elegant Italian. Use an engaging tone for premium lifestyle/design content."
        }
        lang_extra = lang_guides.get(target_language.lower(), "")

        content_prompt = f"""You are a professional translator and editor. Translate ALL Korean text in the following HTML into {target_name}.

RULES:
1. Translate ALL human-readable Korean text into {target_name}. {lang_extra}
2. Keep ALL HTML tags, classes, and structure EXACTLY as they are.
3. NEVER modify style attributes or class names.
4. Keep emoji, numbers, and __PRESERVE_X__ placeholders identical.
5. High Quality: Ensure the translation is natural for a premium blog post.
6. Output ONLY translated HTML. No talk.

HTML TO TRANSLATE:
{safe_content}"""

        print(f"[Translate] Translating content to {target_name}, content_len={len(safe_content)}")
        translated_content = await gemini.generate_text(content_prompt, temperature=0.3, max_tokens=32768)

        if not translated_content or len(translated_content.strip()) < 10:
            print(f"[Translate] ERROR: Empty or too short response from Gemini")
            return {"status": "error", "error": "번역 결과가 비어있습니다. Gemini API를 확인해주세요."}

        new_content = translated_content.strip()
        new_content = re.sub(r'^```html?\s*\n?', '', new_content)
        new_content = re.sub(r'\n?```\s*$', '', new_content)

        restore_keys = list(preserve_store.keys())
        restore_keys.reverse()
        for _pass in range(3):
            for key in restore_keys:
                new_content = new_content.replace(key, preserve_store[key])
            if '__PRESERVE_' not in new_content:
                break

        if new_content == content and target_language != 'ko':
            print(f"[Translate] ERROR: Content unchanged - translation failed")
            return {"status": "error", "error": f"{target_name} 번역에 실패했습니다. 내용이 변경되지 않았습니다."}

        print(f"[Translate] Done. new_title='{new_title[:50]}', new_content_len={len(new_content)}")

        return {
            "status": "ok",
            "title": new_title,
            "content": new_content,
            "summary": new_summary,
            "tags": new_tags,
            "category": new_category
        }

    def extract_image_tags(self, html_content: str) -> List[str]:
        """HTML에서 <img> 태그들을 추출하여 리스트로 반환 (캡션 그룹 포함)"""
        import re
        if not html_content:
            return []
        
        # 1. 캡션이나 레이아웃용 div/figure로 감싸진 태그 우선 추출
        # <div class="separator">...</div>, <figure>...</figure> 등
        patterns = [
            r'<div[^>]*class="separator"[^>]*>[\s\S]*?</div>',
            r'<div[^>]*style="text-align: center;"[^>]*>\s*<img[^>]*>[\s\S]*?</div>',
            r'<figure[^>]*>[\s\S]*?</figure>',
            r'<img[^>]*>'
        ]
        
        combined_pattern = '|'.join(patterns)
        tags = re.findall(combined_pattern, html_content, re.IGNORECASE | re.DOTALL)
        
        # 중복 제거 (내용 기준)
        seen = set()
        unique_tags = []
        for t in tags:
            stripped = t.strip()
            if stripped and stripped not in seen:
                unique_tags.append(stripped)
                seen.add(stripped)
                
        return unique_tags

    def inject_images_into_content(self, target_content: str, image_tags: List[str]) -> str:
        """대상 본문에 이미지 태그들을 하단에 추가 (중복 방지 강화)"""
        if not image_tags:
            return target_content
        
        final_content = target_content or ""
        import re
        
        for tag in image_tags:
            # 태그 내의 src(URL) 추출
            src_match = re.search(r'src="([^"]+)"', tag)
            if src_match:
                src = src_match.group(1)
                # 본문에 이미 해당 주소가 있는지 확인 (쿼리스트링 제외하고 체크)
                src_base = src.split('?')[0]
                if src_base in final_content:
                    print(f"[ImageInject] Skipping duplicate: {src_base}")
                    continue 
            
            # 본문에 이미 해당 태그 내용이 완전히 포함되어 있는지 확인
            if tag in final_content:
                continue

            # 하단에 여백과 함께 추가
            final_content += f"\n<p>&nbsp;</p>\n{tag}\n<p>&nbsp;</p>"
            
        return final_content

    async def generate_image_prompt_from_content(self, content: str) -> str:
        """블로그 본문을 요약하여 이미지 생성을 위한 고품질 영어 프롬프트 생성 (인포그래픽 스타일)"""
        from services.gemini_service import GeminiService
        gemini = GeminiService()
        
        prompt = f"""
        당신은 블로그 비주얼 디렉터이자 인포그래픽 디자이너입니다. 
        아래 블로그 본문의 핵심 내용을 파악하고, 이 글의 주제를 시각화할 수 있는 '이미지 생성형 AI용 고품질 영어 프롬프트'를 하나만 작성해주세요.
        
        [지침]
        1. 스타일: 반드시 'Professional Infographic style'로 작성하세요.
        2. 구성: 만약 스포츠 경기나 국가 대항전 내용이라면, 양 팀의 'Team Emblems' 또는 'National Flags'가 세련되고 고급스럽게(premium layout) 배치되도록 묘사하세요.
        3. 시각 요소: 데이터 차트, 분석 아이콘, 현대적인 그래픽 요소가 포함된 디자인이어야 합니다.
        4. 미적 키워드: 'Professional infographic, premium design, clean layout, vector art, 3D icons, high resolution, soft studio lighting'을 포함하세요.
        5. 오직 영어 프롬프트 텍스트만 반환하세요.
        
        [블로그 본문 발췌]
        {content[:3000]}
        """
        
        result = await gemini.generate_text(prompt, temperature=0.7)
        return result.strip()

    async def analyze_metadata(self, content: str) -> Dict[str, Any]:
        """블로그 본문 분석하여 메태데이터 추출"""
        from services.gemini_service import gemini_service
        res = await gemini_service.analyze_blog_metadata(content)
        if isinstance(res, dict):
            res["status"] = "ok"
        return res


blog_service = BlogService()


