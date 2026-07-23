import json
import re
from typing import Awaitable, Callable, Dict

import database as db
from config import config
from services.prompts import prompts


class GeminiBlogContentService:
    """Gemini 블로그 생성/메타데이터 책임 분리 서비스."""

    def __init__(
        self,
        generate_text_fn: Callable[..., Awaitable[str]],
        cultural_context_fn: Callable[[str], str],
        hooking_strategy_fn: Callable[[str], str],
    ):
        self._generate_text = generate_text_fn
        self._get_cultural_context = cultural_context_fn
        self._get_hooking_strategy = hooking_strategy_fn

    async def generate_blog_content(
        self,
        source_content: str,
        platform: str,
        blog_style: str,
        language: str = "ko",
        user_notes: str = "",
        category: str = None,
        provider_override: str = "",
        model_override: str = "",
    ) -> dict:
        """참고 자료를 바탕으로 블로그 포스팅 생성 (카테고리 템플릿 지원)."""
        target_category = category or "General"
        template_html = db.get_category_template(target_category)

        if not template_html:
            all_templates = db.get_all_category_templates()
            for cat_name, html in all_templates.items():
                if cat_name.lower() == target_category.lower():
                    template_html = html
                    target_category = cat_name
                    break
            if not template_html:
                template_html = db.get_category_template("General") or "<!-- No template found -->[[CONTENT]]"
                target_category = "General"

        bg_color = "#ffffff"
        text_color = "#1d1d1f"
        highlight_color = "#0071e3"
        card_bg = "rgba(255, 255, 255, 0.7)"
        card_border = "rgba(0, 0, 0, 0.05)"
        font_family = "'Outfit', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif"
        container_width = "850px"

        if language == "ja":
            bg_color = "#0a0707"
            text_color = "#ffffff"
            highlight_color = "#FF5252"
            card_bg = "transparent"
            card_border = "rgba(255, 255, 255, 0.05)"
        elif language == "en":
            bg_color = "#050505"
            text_color = "#ffffff"
            highlight_color = "#E0C068"
            card_bg = "transparent"
            card_border = "rgba(255, 255, 255, 0.05)"
        elif language == "ar":
            bg_color = "#0b100d"
            text_color = "#f8f9fa"
            highlight_color = "#C5A059"
            card_bg = "rgba(255, 255, 255, 0.02)"
            card_border = "rgba(255, 255, 255, 0.05)"
            font_family = "'Amiri', 'Inter', serif"
        elif language == "it":
            bg_color = "#050a14"
            text_color = "#ffffff"
            highlight_color = "#D4AF37"
            card_bg = "transparent"
            card_border = "rgba(255, 255, 255, 0.05)"

        theme_override = f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&family=Outfit:wght@400;600;800;900&family=Amiri:wght@400;700&display=swap');
        :root {{
            --bg-color: {bg_color} !important;
            --text-color: {text_color} !important;
            --highlight-color: {highlight_color} !important;
            --card-bg: {card_bg} !important;
            --card-border: {card_border} !important;
            --container-width: {container_width} !important;
        }}
        html, body {{
            background-color: var(--bg-color) !important;
            color: var(--text-color) !important;
            margin: 0; padding: 0;
            min-height: 100vh;
            font-family: {font_family} !important;
            direction: {"rtl" if language == "ar" else "ltr"} !important;
            text-align: {"right" if language == "ar" else "left"} !important;
        }}
    </style>
"""
        if "</head>" in template_html:
            template_html = template_html.replace("</head>", f"{theme_override}</head>")
        else:
            template_html = theme_override + template_html

        current_date = config.get_kst_time().strftime("%Y-%m-%d")
        cultural_context = self._get_cultural_context(language)
        hooking_strategy = self._get_hooking_strategy(language)

        prompt = prompts.GEMINI_GENERATE_BLOG.format(
            source_content=source_content[:15000],
            platform=platform,
            platform_guidance=prompts.get_platform_guidance(platform),
            category=target_category,
            blog_style=blog_style,
            target_language=language,
            cultural_context=cultural_context,
            hooking_strategy=hooking_strategy,
            user_notes=user_notes,
            category_template=template_html,
            current_date=current_date,
        )

        try:
            text = await self._generate_text(
                prompt,
                temperature=0.7,
                use_web_search=True,
                provider_override=provider_override,
                model_override=model_override,
            )
            title_match = re.search(r"<title>\s*(.*?)\s*(?:</title>|$)", text, re.DOTALL | re.IGNORECASE)
            tags_match = re.search(r"<tags>\s*(.*?)\s*(?:</tags>|$)", text, re.DOTALL | re.IGNORECASE)
            summary_match = re.search(r"<summary>\s*(.*?)\s*(?:</summary>|$)", text, re.DOTALL | re.IGNORECASE)
            content_match = re.search(r"<content>\s*(.*?)\s*(?:</content>|$)", text, re.DOTALL | re.IGNORECASE)

            if title_match or content_match:
                content_val = content_match.group(1).strip() if content_match else ""
                content_val = content_val.replace("[[CONTENT]]", "")
                content_val = re.sub(r"\[[^\]]{1,60}(?:Name|Tool|Product|Service|Brand|App|Platform|Generator)\s*\d*\]", "", content_val)
                content_val = re.sub(r"\[(?:제품명|서비스명|브랜드명|앱명|플랫폼명|도구명)\s*\d*\]", "", content_val)
                content_val = re.sub(r"\[{1,2}(?:IMAGE|이미지|사진|그림)[^\]]*\]{1,2}", "", content_val, flags=re.IGNORECASE)
                content_val = re.sub(r"\((?:이미지|사진|그림)\s*\d*\)", "", content_val, flags=re.IGNORECASE)
                if "<html" in content_val and "</html>" not in content_val:
                    content_val += "\n</body>\n</html>"

                clean_content = re.sub(r"<[^>]+>", " ", content_val)
                clean_content = re.sub(r"\s+", " ", clean_content).strip()
                if clean_content in {"...", "…"} or len(clean_content) < 600:
                    return {"error": "블로그 생성 실패: 본문이 너무 짧거나 축약되었습니다. 다시 생성해 주세요."}

                tags_str = tags_match.group(1) if tags_match else ""
                tags = [t.strip() for t in tags_str.split(",")] if tags_str else []
                final_title = title_match.group(1).strip() if title_match else "무제 (생성 중 끊김)"

                if language != "ko":
                    kr_pattern = re.compile(r"[\uAC00-\uD7A3\u3131-\u318E]+")
                    if kr_pattern.search(final_title):
                        final_title = kr_pattern.sub("", final_title).strip()
                        final_title = re.sub(r"^[ :\-?=]+|[ :\-?=]+$", "", final_title).strip()

                return {
                    "title": final_title,
                    "summary": summary_match.group(1).strip() if summary_match else "",
                    "tags": tags,
                    "content": content_val,
                }

            json_match = re.search(r"\{[\s\S]*\}", text)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except Exception:
                    pass
            return {"error": "블로그 생성 실패 (포맷 인식 불가)", "raw": text}
        except Exception as e:
            print(f"Blog Generation Error: {e}")
            return {"error": str(e)}

    async def analyze_blog_metadata(self, content: str, language: str = "ko") -> Dict[str, object]:
        """블로그 본문을 분석하여 제목/카테고리/태그/요약 추출."""
        clean_content = re.sub(r"<[^>]+>", "", content)[:10000]
        lang_name_map = {
            "ko": "Korean",
            "en": "English",
            "ja": "Japanese",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "vi": "Vietnamese",
            "it": "Italian",
            "ar": "Arabic",
        }
        target_lang_name = lang_name_map.get(language, language)

        prompt = prompts.GEMINI_EXTRACT_BLOG_METADATA.format(
            content=clean_content,
            current_date=config.get_kst_time().strftime("%Y-%m-%d"),
            hooking_strategy=self._get_hooking_strategy(language),
            target_language=target_lang_name,
        )

        try:
            text = await self._generate_text(
                prompt,
                temperature=0.7,
                provider_override=provider_override,
                model_override=model_override,
            )
            json_match = re.search(r"\{[\s\S]*\}", text)
            if json_match:
                data = json.loads(json_match.group())
                if isinstance(data.get("tags"), str):
                    data["tags"] = [t.strip() for t in data["tags"].split(",") if t.strip()]
                elif not data.get("tags"):
                    data["tags"] = []
                return data
        except Exception as e:
            print(f"Blog Metadata Analysis Error: {e}")

        return {"title": "분석 실패", "category": "", "tags": [], "summary": ""}
