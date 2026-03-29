import os
import json
import httpx
from typing import Optional, Dict, Any, List
from services.source_service import source_service
from services.gemini_service import gemini_service
import database as db
from config import config

class BlogService:
    async def process_blog_automation_v2(
        self,
        project_id: Optional[int],
        platform: str = "wordpress",
        blog_style: str = "info",
        language: str = "ko",
        user_notes: str = "",
        raw_script: str = None
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
                user_notes=user_notes
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

    async def add_images_to_content(self, content: str, project_id: Optional[int] = None, image_count: int = 2) -> Dict[str, Any]:
        """기존 내용(HTML/텍스트)을 분석하여 어울리는 이미지를 생성하고 삽입"""
        try:
            from services.publish_service import publish_service
            # 1. 이미지 포인트 분석 (publish_service 연동)
            image_points = await publish_service.analyze_image_points(content)
            
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
                            prompt=prompt, aspect_ratio="16:9", num_images=1
                        )
                        if image_bytes_list:
                            img_bytes = image_bytes_list[0]
                            file_prefix = f"blog_img_{project_id}" if project_id else "blog_img_raw"
                            filename = f"{file_prefix}_{int(time.time())}_{i}.png"
                            save_path = os.path.join(abs_dir, filename)
                            web_url = f"{web_dir}/{filename}"
                            
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
        user_notes: str = ""
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
                user_notes=user_notes
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
        platforms: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """주제 하나로 여러 언어의 블로그 포스팅을 각각 독립적으로 병렬 생성"""
        import asyncio
        
        async def generate_single(config: Dict[str, str]):
            lang = config.get("language", "ko")
            plat = config.get("platform", "wordpress")
            style = config.get("style", "info")
            user_notes = config.get("user_notes", "")
            
            # 독립적 생성을 위해 주제(topic)를 소스로 사용
            res = await self.generate_blog_from_source(
                source_type="text",
                source_value=topic,
                platform=plat,
                blog_style=style,
                language=lang,
                user_notes=user_notes
            )
            res["language"] = lang
            res["target_id"] = config.get("target_id") # 프론트엔드 탭 매칭용
            return res

        try:
            print(f"[BlogService] Starting independent multi-generation for topic: {topic[:30]}...")
            tasks = [generate_single(p) for p in platforms]
            results = await asyncio.gather(*tasks)
            
            return {
                "status": "ok",
                "results": results
            }
        except Exception as e:
            print(f"generate_independent_multi_language_blogs Error: {e}")
            return {"status": "error", "error": str(e)}

    async def upload_local_images_to_public(self, content: str) -> str:
        """본문 내 로컬 이미지(/output/)를 WordPress에 업로드하여 공개 URL로 일괄 치환.
        모든 플랫폼에서 재사용 가능한 공개 URL을 반환."""
        import re
        import urllib.parse

        img_pattern = re.compile(r'<img [^>]*src="(/output/[^"]+)"[^>]*>')
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

            # 이미지는 라우터(post_blog)에서 사전 업로드 완료됨 → content에 공개 URL 포함
            processed_content = content

            # <style> 블록이 포함된 HTML은 WordPress 블록 에디터의 Custom HTML 블록으로 감싸기
            # WordPress REST API가 <style> 태그를 strip하지 않도록 보호
            import re
            if re.search(r'<style[\s\S]*?</style>', processed_content, re.IGNORECASE):
                # Gutenberg Custom HTML 블록으로 래핑
                processed_content = f'<!-- wp:html -->\n{processed_content}\n<!-- /wp:html -->'

            payload = {
                "title": title,
                "content": processed_content,
                "status": "publish",
                "categories": categories or []
            }
            if summary:
                payload["excerpt"] = summary

            # 카테고리 처리 (워드프레스는 ID 배열을 받으므로, 문자열인 경우 이름으로 매칭 시도 가능하지만 
            # 여기서는 간단히 카테고리 이름을 본문 하단에 표시하여 SEO 지원)
            if categories and any(isinstance(c, str) for c in categories):
                payload["categories"] = [] # ID가 아니면 비움
                cat_text = "\n\nCategory: " + ", ".join([str(c) for c in categories])
                payload["content"] += cat_text
            
            # 태그 처리 (워드프레스는 태그 ID 배열을 받음)
            tag_ids = []
            if tags:
                try:
                    # 간단하게 태그를 이름으로 게시하고 싶지만 WP REST API는 ID만 받으므로
                    # 태그 이름들을 content 하단에 해시태그로 추가하거나, 추후 태그 생성 로직 추가 가능
                    footer_tags = "\n\n" + " ".join([f"#{t}" for t in tags])
                    payload["content"] += footer_tags
                except:
                    pass

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

            async with httpx.AsyncClient(follow_redirects=True) as client:
                res = await client.post(endpoint, content=image_data, headers=headers, timeout=60)
                if res.status_code in [200, 201]:
                    data = res.json()
                    return {
                        "status": "ok",
                        "media_id": data.get("id"),
                        "url": data.get("source_url", data.get("guid", {}).get("rendered", "")),
                    }
                else:
                    return {"status": "error", "error": f"WordPress 이미지 업로드 실패 ({res.status_code}): {res.text[:200]}"}

        except Exception as e:
            print(f"upload_image_to_wordpress Error: {e}")
            return {"status": "error", "error": str(e)}
    def prepare_html_for_blogger(self, content: str, summary: str = None) -> str:
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
/* Blogger: JS 없이도 모든 요소 강제 표시 */
.bp-wrap * {
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
.bp-wrap [data-aos] {
  opacity: 1 !important;
  transform: none !important;
  visibility: visible !important;
  transition: none !important;
  animation: none !important;
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
            result_parts.append(f'<div style="display:none;">{summary}</div>')
            
        result_parts.append(f'{body_content.strip()}\n</div>')
        
        result = "\n".join(result_parts)
        print(f"[Blogger Prep] Done: {len(content)} → {len(result)} chars, styles={len(style_blocks)}, links={len(link_tags)}")
        return result

    async def post_to_blogger(
        self,
        title: str,
        content: str,
        tags: List[str] = None,
        account_id: int = None,
        summary: str = None,
        category: str = None
    ) -> Dict[str, Any]:
        """구글 블로그(Blogger)에 글 게시 - 계정별 또는 전역 설정 사용"""
        try:
            if account_id:
                # DB에서 해당 계정 정보 가져오기
                acc = db.get_blogger_account(account_id)
                if not acc:
                    return {"status": "error", "error": f"Blogger 계정(id={account_id})을 찾을 수 없습니다."}
                blog_id = acc.get("blog_id") or config.BLOG_ID or db.get_global_setting("blog_id", "")
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

            # Blogger용 HTML 전처리 제거 (사용자 요청: 원본 그대로 포스팅)
            # content = self.prepare_html_for_blogger(content, summary=summary)
            html_content = content


            # Blogger API v3: Sanitize labels and simplify payload to avoid 400 errors
            full_labels = []
            if isinstance(tags, list):
                full_labels.extend(tags)
            elif isinstance(tags, str):
                full_labels.extend([t.strip() for t in tags.split(',') if t.strip()])
            
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
                    clean_label = label.replace(',', ' ').strip()
                    # Remove problematic HTML-like characters from labels
                    for char in '<>{}[]~':
                        clean_label = clean_label.replace(char, '')
                    
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
                    print(f"[Blogger] ERROR {res.status_code}: {error_msg}")
                    print(f"[Blogger] Payload: {json.dumps(payload, ensure_ascii=False)[:500]}...")
                    
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
            "vi": "Vietnamese", "zh": "Chinese", "es": "Spanish"
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
                translated_title = re.sub(r'^\[.*?\]\s*', '', translated_title)
                translated_title = re.sub(r'^(Title|제목|タイトル|翻訳)\s*[:：]\s*', '', translated_title, flags=re.IGNORECASE)
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
                new_tags = translated_tags.strip().strip('"').strip("'")
                new_tags = re.sub(r'^(Tags|태그|タグ|翻訳|Keywords)\s*[:：]\s*', '', new_tags, flags=re.IGNORECASE)
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

        content_prompt = f"""You are a professional translator. Translate ALL Korean text in the following HTML into {target_name}.

RULES:
1. Translate ALL human-readable Korean text into {target_name} (including text in <table>, <th>, <td>, headings, paragraphs, spans, etc.)
2. Keep ALL HTML tags, attributes, and structure EXACTLY as they are.
3. NEVER modify any style="..." attributes. Keep them byte-for-byte identical.
4. NEVER modify any class="..." attributes. Keep them byte-for-byte identical.
5. NEVER modify any data-* attributes or id attributes.
6. Keep ALL __PRESERVE_X__ placeholders EXACTLY as they are. Do NOT translate or modify them.
7. Keep emoji, numbers, proper nouns (person names, team names) as-is or transliterate them naturally.
8. Do NOT wrap output in markdown code blocks.
9. Output ONLY the translated HTML. No explanations, no labels.

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
        """HTML에서 <img> 태그들을 추출하여 리스트로 반환"""
        import re
        if not html_content:
            return []
        # 다양한 형식의 img 태그 추출 (div.separator로 감싸진 것 포함)
        tags = re.findall(r'<div[^>]*class="separator"[^>]*>[\s\S]*?</div>|<div[^>]*>\s*<img[^>]*>\s*</div>|<figure[^>]*>.*?</figure>|<img[^>]*>', html_content, re.IGNORECASE | re.DOTALL)
        return [t.strip() for t in tags]

    def inject_images_into_content(self, target_content: str, image_tags: List[str]) -> str:
        """대상 본문에 이미지 태그들을 하단에 추가 (중복 방지)"""
        if not image_tags:
            return target_content
        
        # 이미 포함된 이미지 URL 확인 (간단한 검색)
        final_content = target_content or ""
        for tag in image_tags:
            # 태그 내의 src 추출 시도
            import re
            src_match = re.search(r'src="([^"]+)"', tag)
            if src_match:
                src = src_match.group(1)
                if src in final_content:
                    continue # 이미 존재하면 건너뜀
            
            # 하단에 추가
            final_content += f"\n<p></p>\n{tag}"
            
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


