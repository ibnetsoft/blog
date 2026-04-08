# services/publish_service.py - 원소스 멀티유즈 퍼블리시 서비스
import json
import re
from typing import Dict, Any, List, Optional
from services.gemini_service import gemini_service
from services.blog_service import blog_service
import database as db


class PublishService:
    def __init__(self):
        pass

    async def analyze_image_points(self, content: str, image_count: int = 0, no_human: bool = True) -> List[Dict]:
        """블로그 글 분석 → 이미지 삽입 위치 + 프롬프트 자동 생성"""
        # 글 길이에 따른 이미지 수 자동 결정
        if image_count <= 0:
            char_count = len(content)
            if char_count < 500:
                image_count = 2
            elif char_count < 1500:
                image_count = 3
            elif char_count < 3000:
                image_count = 5
            elif char_count < 5000:
                image_count = 8
            else:
                image_count = min(12, char_count // 500)

        # [FIX] 사람 유무에 따른 동적 규칙 적용
        human_rule = "7. **절대 금지**: 이미지에 사람(human), 인물의 얼굴, 신체 부위가 나타나지 않도록 하세요. 대신 상징적인 사물, 풍경 등으로만 표현하세요." if no_human else "7. **사람 허용**: 사람이 나타날 수 있으나, 주제와 관련이 있을 때만 자연스럽게 배치하세요. 불필요하게 팔이나 손이 붕 떠 있는 기괴한 연출은 금지합니다."

        prompt = f"""당신은 블로그 콘텐츠 전문가입니다. 아래 블로그 글을 분석하여 이미지를 삽입할 최적의 위치와 각 위치에 맞는 이미지 프롬프트를 생성하세요.

## 규칙
1. 이미지는 총 {image_count}장을 배치합니다.
2. 각 이미지는 **해당 문단의 실질적인 핵심 주제(Core Topic)**를 시각적으로 보여주어야 합니다.
3. **주의**: 글의 디자인 스타일(예: 미니멀, 프리미엄)이 아닌, **글의 내용(후티 반군, 정치, 경제 등)**에만 집중하여 이미지를 구상하십시오.
4. 이미지 프롬프트는 Imagen/DALL-E에서 생성할 수 있도록 영어로 작성합니다.
5. 비율은 16:9 (가로형, 블로그+영상 공용)
6. 사실적인 스타일 (photorealistic) 또는 전문적인 일러스트레이션.
{human_rule}

## 블로그 글:
{content[:8000]}

## 응답 형식 (반드시 JSON 배열만 반환):
[
  {{
    "position": 1,
    "after_paragraph": "이미지가 삽입될 위치 앞의 문단 첫 20자...",
    "prompt_ko": "한국어 이미지 설명",
    "prompt_en": "Detailed English prompt for image generation, photorealistic, 16:9 aspect ratio, high quality, ..."
  }}
]
"""
        try:
            result_text = await gemini_service.generate_text(prompt, temperature=0.3)
            # JSON 파싱
            json_match = re.search(r'\[[\s\S]*\]', result_text)
            if json_match:
                image_points = json.loads(json_match.group())
                return image_points
            return []
        except Exception as e:
            print(f"[PublishService] analyze_image_points error: {e}")
            return []

    def build_blog_html(self, content: str, images: List[Dict]) -> str:
        """블로그 글에 이미지를 삽입하여 HTML 생성 (기존 HTML 구조 보존 기능 포함)"""
        if not images:
            return content

        # 1. 플레이스홀더([[IMAGE_X]]) 치환 우선 처리
        processed_content = content
        used_indices = set()
        
        # 이미지 태그 생성 헬퍼 (프리미엄 스타일 + 레이아웃 보호 및 중앙 정렬 강화)
        def get_img_html(img_url, caption):
            cap_html = f'<figcaption style="margin-top:12px; color:#64748b; font-size:0.8rem; font-weight:500; text-align:center !important;">{caption}</figcaption>' if caption else ""
            return (
                f'\n<div class="premium-blog-image" style="display:flex !important; flex-direction:column !important; align-items:center !important; justify-content:center !important; margin:3.5rem auto !important; clear:both !important; width:100% !important;">'
                f'<figure style="display:block !important; margin:0 auto !important; max-width:88% !important; text-align:center !important;">'
                f'<img src="{img_url}" alt="{caption}" style="max-width:100% !important; width:100% !important; height:auto !important; border-radius:22px; box-shadow:0 18px 45px rgba(0,0,0,0.1); display:block !important; margin:0 auto !important;">'
                f'{cap_html}'
                f'</figure>'
                f'</div>\n'
            )

        for i, img in enumerate(images):
            placeholder = f"[[IMAGE_{i+1}]]"
            if placeholder in processed_content:
                img_url = img.get('image_url', '')
                caption = img.get('caption', img.get('prompt_ko', ''))
                processed_content = processed_content.replace(placeholder, get_img_html(img_url, caption))
                used_indices.add(i)

        # 남은 이미지(치환되지 않은 것) 필터링 및 정렬
        remaining_images = [img for i, img in enumerate(images) if i not in used_indices and img.get('image_url')]
        if not remaining_images:
            return processed_content

        sorted_images = sorted(remaining_images, key=lambda x: x.get('position', 0))

        # 2. 기존 HTML 여건에 따른 자동 삽입 (남은 이미지 대상)
        is_html = bool(re.search(r'<[a-z/!][\s\S]*?>', processed_content, re.IGNORECASE))
        
        if is_html:
            # HTML인 경우: 문단 사이 검출 후 삽입
            current_html = processed_content
            for img in reversed(sorted_images):
                img_url = img.get('image_url', '')
                caption = img.get('caption', img.get('prompt_ko', ''))
                after_text = img.get('after_paragraph', '').strip()
                img_html = get_img_html(img_url, caption)
                
                inserted = False
                if after_text and len(after_text) > 5:
                    pattern = re.escape(after_text[:30])
                    match = re.search(pattern, current_html)
                    if match:
                        end_tag_match = re.search(r'</(p|div|h[1-4]|section|article|blockquote|li)>', current_html[match.end():], re.IGNORECASE)
                        if end_tag_match:
                            insert_pos = match.end() + end_tag_match.end()
                            current_html = current_html[:insert_pos] + img_html + current_html[insert_pos:]
                            inserted = True
                
                if not inserted:
                    pos = img.get('position', 1)
                    p_matches = list(re.finditer(r'</(p|div|h[1-4]|li|section|article|blockquote)>|<br\s*/?>|\n\n', current_html, re.IGNORECASE))
                    if p_matches:
                        target_idx = min(len(p_matches) - 1, max(0, pos - 1))
                        insert_pos = p_matches[target_idx].end()
                        current_html = current_html[:insert_pos] + img_html + current_html[insert_pos:]
                    else:
                        current_html += img_html
            
            return current_html

        else:
            # 일반 텍스트인 경우: 문단 분리 수행
            paragraphs = processed_content.split('\n')
            html_parts = []
            img_ptr = 0

            for i, para in enumerate(paragraphs):
                para = para.strip()
                if not para: continue

                if bool(re.search(r'<[a-z/!][\s\S]*?>', para, re.IGNORECASE)):
                    html_parts.append(para)
                elif para.startswith('#'):
                    level = min(len(para) - len(para.lstrip('#')), 4)
                    text = para.lstrip('#').strip()
                    html_parts.append(f'<h{level}>{text}</h{level}>')
                else:
                    html_parts.append(f'<p>{para}</p>')

                if img_ptr < len(sorted_images):
                    if i + 1 >= sorted_images[img_ptr].get('position', 0):
                        img = sorted_images[img_ptr]
                        html_parts.append(get_img_html(img.get('image_url', ''), img.get('caption', '')))
                        img_ptr += 1

            while img_ptr < len(sorted_images):
                img = sorted_images[img_ptr]
                html_parts.append(get_img_html(img.get('image_url', ''), img.get('caption', '')))
                img_ptr += 1

            return '\n'.join(html_parts)

    async def post_to_blogs(
        self,
        session_id: int,
        title: str,
        html_content: str,
        tags: List[str] = None,
        platforms: List[str] = None
    ) -> Dict[str, Any]:
        """WordPress + Blogger 동시 게시"""
        platforms = platforms or ["wordpress", "blogger"]
        results = {}

        for platform in platforms:
            try:
                if platform == "wordpress":
                    res = await blog_service.post_to_wordpress(
                        title=title, content=html_content, tags=tags
                    )
                    results["wordpress"] = res
                    if res.get("status") == "ok":
                        db.update_publish_session(
                            session_id,
                            blog_wp_url=res.get("url", ""),
                            blog_wp_post_id=str(res.get("post_id", ""))
                        )
                elif platform == "blogger":
                    res = await blog_service.post_to_blogger(
                        title=title, content=html_content, tags=tags
                    )
                    results["blogger"] = res
                    if res.get("status") == "ok":
                        db.update_publish_session(
                            session_id,
                            blog_blogger_url=res.get("url", ""),
                            blog_blogger_post_id=str(res.get("post_id", ""))
                        )
            except Exception as e:
                results[platform] = {"status": "error", "error": str(e)}

        # 상태 업데이트
        any_ok = any(r.get("status") == "ok" for r in results.values())
        if any_ok:
            db.update_publish_session(session_id, step="blog_done")

        return results

    async def create_session_from_project(self, project_id: int) -> Optional[int]:
        """기존 프로젝트의 대본으로 퍼블리시 세션 생성"""
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT full_script FROM scripts WHERE project_id = ? ORDER BY id DESC LIMIT 1",
            (project_id,)
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        project = db.get_project(project_id)
        title = project.get("name", "무제") if project else "무제"
        content = row["full_script"]
        conn.close()

        session_id = db.create_publish_session(project_id, title, content)
        return session_id


publish_service = PublishService()
