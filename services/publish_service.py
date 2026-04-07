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

    async def analyze_image_points(self, content: str, image_count: int = 0) -> List[Dict]:
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

        prompt = f"""당신은 블로그 콘텐츠 전문가입니다. 아래 블로그 글을 분석하여 이미지를 삽입할 최적의 위치와 각 위치에 맞는 이미지 프롬프트를 생성하세요.

## 규칙
1. 이미지는 총 {image_count}장을 배치합니다.
2. 각 이미지는 해당 문단의 내용을 시각적으로 보여줄 수 있어야 합니다.
3. 이미지 프롬프트는 Imagen/DALL-E에서 생성할 수 있도록 영어로 작성합니다.
4. 비율은 16:9 (가로형, 블로그+영상 공용)
5. 사실적인 스타일 (photorealistic) 또는 전문적인 일러스트레이션.
6. **절대 금지**: 이미지에 사람(human), 인물의 얼굴, 신체 부위가 나타나지 않도록 하세요. 대신 사물, 풍경, 데이터 시각화, 테크놀로지 심볼 등으로 표현하세요.

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

        # 이미지가 URL을 가지고 있는지 필터링 및 정렬
        sorted_images = sorted(
            [img for img in images if img.get('image_url')],
            key=lambda x: x.get('position', 0)
        )
        if not sorted_images:
            return content

        # 1. 기존 HTML 여부 확인 (어떠한 태그라도 포함되어 있으면 HTML로 간주)
        is_html = bool(re.search(r'<[a-z/!][\s\S]*?>', content, re.IGNORECASE))
        
        if is_html:
            # HTML인 경우: 기존 구조를 건드리지 않고 문단 사이(보통 </p>나 <br> 뒤)에 삽입
            processed_content = content
            
            # 역순으로 삽입해야 인덱스가 틀어지지 않음
            for img in reversed(sorted_images):
                img_url = img.get('image_url', '')
                caption = img.get('caption', img.get('prompt_ko', ''))
                after_text = img.get('after_paragraph', '').strip()
                
                img_html = (
                    f'\n<div style="text-align:center !important; margin:3.5rem auto !important; width:100% !important; display:block !important; clear:both !important;">'
                    f'<img src="{img_url}" alt="{caption}" style="width:92% !important; max-width:800px !important; height:auto !important; border-radius:18px; box-shadow:0 20px 45px rgba(0,0,0,0.12); display:block !important; margin:0 auto !important;">'
                    f'</div>\n'
                )
                
                inserted = False
                if after_text and len(after_text) > 5:
                    pattern = re.escape(after_text[:30])
                    match = re.search(pattern, processed_content)
                    if match:
                        end_tag_match = re.search(r'</(p|div|h[1-4]|section|article|blockquote|li)>', processed_content[match.end():], re.IGNORECASE)
                        if end_tag_match:
                            insert_pos = match.end() + end_tag_match.end()
                            processed_content = processed_content[:insert_pos] + img_html + processed_content[insert_pos:]
                            inserted = True
                
                if not inserted:
                    pos = img.get('position', 1)
                    p_matches = list(re.finditer(r'</(p|div|h[1-4]|li|section|article|blockquote)>|<br\s*/?>|\n\n', processed_content, re.IGNORECASE))
                    if p_matches:
                        target_idx = min(len(p_matches) - 1, max(0, pos - 1))
                        insert_pos = p_matches[target_idx].end()
                        processed_content = processed_content[:insert_pos] + img_html + processed_content[insert_pos:]
                        inserted = True
                    else:
                        processed_content += img_html
                        inserted = True
            
            return processed_content

        else:
            # 2. 일반 텍스트인 경우: 기존 로직(문단 분리 및 태그 래핑) 수행
            # 만약 여기 들어왔는데도 태그가 발견되면 래핑을 건너뜀 (이중 안전장치)
            paragraphs = content.split('\n')
            html_parts = []
            image_idx = 0

            for i, para in enumerate(paragraphs):
                para = para.strip()
                if not para: continue

                # 이미 HTML 태그가 포함된 줄은 래핑하지 않음
                if bool(re.search(r'<[a-z/!][\s\S]*?>', para, re.IGNORECASE)):
                    html_parts.append(para)
                elif para.startswith('#'):
                    level = min(len(para) - len(para.lstrip('#')), 4)
                    text = para.lstrip('#').strip()
                    html_parts.append(f'<h{level}>{text}</h{level}>')
                else:
                    html_parts.append(f'<p>{para}</p>')

                if image_idx < len(sorted_images):
                    img = sorted_images[image_idx]
                    target_pos = img.get('position', image_idx + 1)
                    if i + 1 >= target_pos:
                        img_url = img.get('image_url', '')
                        caption = img.get('caption', img.get('prompt_ko', ''))
                        html_parts.append(
                            f'<figure style="text-align:center;margin:20px 0;">'
                            f'<img src="{img_url}" alt="{caption}" style="max-width:100%;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,0.1);">'
                            f'</figure>'
                        )
                        image_idx += 1

            while image_idx < len(sorted_images):
                img = sorted_images[image_idx]
                img_url = img.get('image_url', '')
                caption = img.get('caption', img.get('prompt_ko', ''))
                html_parts.append(
                    f'<figure style="text-align:center;margin:20px 0;">'
                    f'<img src="{img_url}" alt="{caption}" style="max-width:100%;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,0.1);">'
                    f'</figure>'
                )
                image_idx += 1

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
