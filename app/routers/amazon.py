from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from services.amazon_service import amazon_service
from services.gemini_service import gemini_service
from services.blog_service import blog_service
from services.ai_quality_service import ai_quality_service
from services.publish_utils import normalize_publish_result, open_published_urls, run_with_backoff, validate_blog_post_payload, validate_publish_html
import database as db

router = APIRouter(prefix="/api/amazon", tags=["Amazon"])

class AmazonAnalyzeRequest(BaseModel):
    url: str

class AmazonGenerateRequest(BaseModel):
    product_data: Dict[str, Any]
    languages: List[str]
    affiliate_id: Optional[str] = ""

@router.get("/trends")
async def get_amazon_trends():
    """AI가 분석한 현재 인기 상품 및 추천 키워드 반환"""
    from services.gemini_service import gemini_service
    trends = await gemini_service.generate_amazon_trends()
    return {"status": "ok", "trends": trends}

@router.post("/analyze")
async def analyze_product(req: AmazonAnalyzeRequest):
    res = await amazon_service.fetch_product_details(req.url)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

@router.post("/generate")
async def generate_amazon_blogs(req: AmazonGenerateRequest):
    """연동된 모든 블로그의 언어에 맞춰 독립적인 설득형 리뷰 자동 생성"""
    try:
        results = []
        product = req.product_data
        
        # [자동화] 연동된 모든 블로그 언어 추출 (중복 제거)
        target_languages = set()
        
        # 1. 워드프레스 기본 언어 (보통 한국어)
        target_languages.add("ko")
        
        # 2. 구글 블로거 연동 계정들에서 언어 추출
        blogger_accounts = db.get_blogger_accounts()
        for acc in blogger_accounts:
            if acc.get('lang'):
                target_languages.add(acc['lang'])
                
        if not target_languages:
            target_languages = {"ko", "en"} # 폴백

        from services.gemini_service import gemini_service
        gs = gemini_service # singleton
        
        for lang in target_languages:
            try:
                print(f"[AmazonRouter] Generating review for {lang}...")
                # 1. Gemini로 리뷰 본문 생성
                content = await gs.generate_amazon_review(
                    product_data=product,
                    language=lang
                )
                
                # 2. 메타데이터(제목, 태그 등) 생성
                meta = await blog_service.analyze_metadata(content, lang)
                
                # 3. 제휴 링크 삽입 및 국가별 도메인 로컬라이징
                base_url = product['url']
                
                # 언어별 아마존 도메인 매핑
                domain_map = {
                    "ja": "amazon.co.jp",
                    "es": "amazon.es",
                    "fr": "amazon.fr",
                    "de": "amazon.de",
                    "it": "amazon.it",
                    "en": "amazon.com",
                    "ko": "amazon.com", # 한국은 보통 .com 사용
                }
                
                target_domain = domain_map.get(lang, "amazon.com")
                
                # 도메인 교체 로직 (ASIN 유지)
                import re
                # amazon.com/dp/B0... 또는 amazon.com/gp/product/B0... 패턴 대응
                localized_url = re.sub(r'amazon\.[a-z\.]+', target_domain, base_url)
                
                affiliate_url = localized_url
                if req.affiliate_id:
                    sep = "&" if "?" in affiliate_url else "?"
                    affiliate_url += f"{sep}tag={req.affiliate_id}"
                
                # 4. 이미지 HTML 상단 삽입 (제휴 링크 포함)
                image_html = f"""<div style="text-align: center; margin-bottom: 30px;">
        <a href="{affiliate_url}" target="_blank" rel="nofollow">
            <img src="{product.get('image_url')}" alt="{product['title']}" style="max-width: 100%; height: auto; border-radius: 16px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04);">
        </a>
    </div>\n\n"""

                # 본문 가공 (Premium CSS 주입)
                style_tag = """<style>
    .premium-review-wrapper { background-color: #f1f5f9; padding: 40px 10px; }
    .premium-review { font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.8; color: #334155 !important; max-width: 850px; margin: 0 auto; padding: 40px; background: #ffffff; border-radius: 2rem; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); }
    .premium-review h1 { font-size: 2.5rem; font-weight: 800; color: #0f172a !important; margin-bottom: 0.5rem; text-align: center; line-height: 1.2; }
    .premium-review .subtitle { font-size: 1.2rem; color: #64748b !important; text-align: center; margin-bottom: 3rem; font-style: italic; }
    .premium-review section { margin-bottom: 3.5rem; }
    .premium-review .content-card { background: #f8fafc; border-radius: 1.5rem; padding: 2.5rem; border: 1px solid #e2e8f0; }
    .premium-review h2 { font-size: 1.7rem; font-weight: 700; color: #1e293b !important; margin-bottom: 1.5rem; border-bottom: 4px solid #f97316; display: inline-block; padding-bottom: 0.3rem; }
    .premium-review h3 { font-size: 1.3rem; font-weight: 700; color: #1e293b !important; margin-bottom: 1.2rem; }
    .premium-review p { margin-bottom: 1.3rem; font-size: 1.05rem; }
    .premium-review .pros-cons-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-top: 1.5rem; }
    .premium-review .pros { background: #f0fdf4; padding: 1.8rem; border-radius: 1.2rem; border-top: 6px solid #22c55e; }
    .premium-review .cons { background: #fef2f2; padding: 1.8rem; border-radius: 1.2rem; border-top: 6px solid #ef4444; }
    .premium-review .feature-box { background: #eff6ff; padding: 1.8rem; border-radius: 1.2rem; border-left: 6px solid #3b82f6; margin: 2rem 0; }
    .premium-review ul { padding-left: 1.5rem; }
    .premium-review li { margin-bottom: 0.8rem; font-size: 1rem; }
    .premium-review .cta-section { text-align: center; background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%); padding: 3rem; border-radius: 1.5rem; margin-top: 2rem; }
    .product-main-img { display: block; margin: 0 auto 3rem auto; max-width: 100%; border-radius: 1.5rem; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }
    @media (max-width: 640px) {
        .premium-review { padding: 25px 15px; border-radius: 1rem; }
        .premium-review .pros-cons-grid { grid-template-columns: 1fr; }
        .premium-review h1 { font-size: 1.8rem; }
    }
</style>\n"""
                # 마크다운인 경우 HTML로 변환 (Blogger 등 HTML 필수 플랫폼 대응)
                import markdown
                # 간단한 휴리스틱: 전체 텍스트 중 HTML 태그 비중이 낮거나 마크다운 기호가 있으면 변환
                if "<div" not in content and "<h1" not in content and ("**" in content or "##" in content):
                    try:
                        content = markdown.markdown(content, extensions=['extra', 'nl2br'])
                    except Exception as e:
                        print(f"[Markdown Conversion Error]: {e}")

                # 이미지를 감싸는 div 추가 (CSS 클래스 적용)
                image_wrapped = f'<div class="product-main-img-container" style="text-align:center;">{image_html}</div>'
                full_content = style_tag + f'<div class="premium-review-wrapper"><div class="premium-review">{image_wrapped}{content}</div></div>'
                
                # 본문 하단 제휴 링크 추가
                link_text = {
                    "ko": "👉 상품 자세히 보기 및 구매하기",
                    "en": "👉 View Details and Buy on Amazon",
                    "ja": "👉 商品の詳細과 구매はこちら",
                    "es": "👉 Ver detalles y comprar en Amazon",
                    "fr": "👉 Voir les détails et acheter sur Amazon",
                    "de": "👉 Details anzeigen und bei Amazon kaufen",
                }.get(lang, "👉 Click here to buy")
                
                full_content += f"\n\n<hr style='margin: 40px 0;'>\n\n<div style='text-align: center;'>\n  <h3><a href='{affiliate_url}' target='_blank' rel='nofollow' style='color: #f97316; text-decoration: none;'>{link_text}</a></h3>\n  <p style='font-size: 0.8rem; color: #6b7280;'>{affiliate_url}</p>\n</div>"
                
                results.append({
                    "language": lang,
                    "title": meta.get("title") or product['title'],
                    "content": full_content,
                    "tags": meta.get("tags", []),
                    "category": meta.get("category", "Shopping"),
                    "summary": meta.get("summary", ""),
                    "affiliate_url": affiliate_url,
                    "image_url": product.get("image_url")
                })
            except Exception as e:
                print(f"[AmazonRouter] Error for {lang}: {e}")
                results.append({
                    "language": lang,
                    "status": "error",
                    "error": str(e)
                })
        
        return {"status": "ok", "results": results}
    except Exception as ge:
        print(f"[AmazonRouter] Fatal Global Error: {ge}")
        return {"status": "error", "error": f"시스템 오류: {str(ge)}"}

class AmazonPublishRequest(BaseModel):
    posts: List[Dict[str, Any]]  # List of {language, title, content, tags, category, summary}

@router.post("/publish")
async def publish_amazon_blogs(req: AmazonPublishRequest):
    """생성된 리뷰들을 각 언어에 맞는 블로그 플랫폼에 게시"""
    publish_results = []
    
    if not req.posts:
        return {"status": "error", "error": "No posts to publish"}

    # 0. 게시 입력 검증 (언어별 게시물 단위)
    for post in req.posts:
        post_title = post.get("title", "")
        post_content = post.get("content", "")
        payload_validation = validate_blog_post_payload(post_title, post_content, ["wordpress", "blogger"])
        html_validation = validate_publish_html(post_content)
        validation_errors = payload_validation["errors"] + html_validation["errors"]
        validation_warnings = payload_validation["warnings"] + html_validation["warnings"]
        if validation_errors:
            return {
                "status": "error",
                "error": "invalid publish payload",
                "language": post.get("language"),
                "errors": validation_errors,
                "warnings": validation_warnings,
            }

    # 1. 워드프레스 게시
    wp_post = next((p for p in req.posts if p['language'] == 'ko'), req.posts[0])
    quality_reviews = {}
    try:
        print(f"[AmazonPublish] Starting WordPress post: {wp_post['title']}")
        wp_quality = await ai_quality_service.review_and_improve(
            title=wp_post["title"],
            content=wp_post["content"],
            tags=wp_post.get("tags", []),
            categories=[wp_post.get("category", "Shopping")],
            summary=wp_post.get("summary"),
            platform="wordpress",
            language=wp_post.get("language", "ko"),
        )
        quality_reviews["wordpress"] = {
            "status": wp_quality.get("status"),
            "score": wp_quality.get("score"),
            "issues": wp_quality.get("issues", []),
            "improvements": wp_quality.get("improvements", []),
            "original_title": wp_post["title"],
            "improved_title": wp_quality.get("title", wp_post["title"]),
        }
        async def _post_wp():
            return await blog_service.post_to_wordpress(
                title=wp_quality.get("title", wp_post["title"]),
                content=wp_quality.get("content", wp_post["content"]),
                tags=wp_quality.get("tags", wp_post.get("tags", [])),
                categories=wp_quality.get("categories", [wp_post.get("category", "Shopping")]),
                summary=wp_quality.get("summary", wp_post.get("summary"))
            )
        wp_res = await run_with_backoff(_post_wp, platform="wordpress", max_attempts=3, base_delay=1.0)
        normalized_wp = normalize_publish_result("wordpress", wp_res)
        db.add_job_log(
            "WordPress",
            "Global",
            wp_post['title'],
            "success" if normalized_wp.get("status") == "ok" else "error",
            normalized_wp.get("error") or normalized_wp.get("message") or "게시 성공",
            normalized_wp.get("url"),
        )
        publish_results.append({"platform": "WordPress", **normalized_wp})
    except Exception as e:
        print(f"[AmazonPublish] WordPress Error: {e}")
        db.add_job_log("WordPress", "Global", wp_post['title'], "error", str(e))
        publish_results.append({"platform": "WordPress", "status": "error", "error": str(e)})

    # 2. 구글 블로거 게시
    blogger_accounts = db.get_blogger_accounts()
    if not blogger_accounts:
        print("[AmazonPublish] No Blogger accounts found in DB")
        
    for acc in blogger_accounts:
        acc_lang = acc.get('lang', 'en')
        matched_post = next((p for p in req.posts if p['language'] == acc_lang), None)
        
        if not matched_post:
            matched_post = next((p for p in req.posts if p['language'] == 'en'), req.posts[0])
            
        try:
            print(f"[AmazonPublish] Posting to Blogger ({acc['name']}, {acc_lang}): {matched_post['title']}")
            p_key = f"blogger:{acc['id']}"
            b_quality = await ai_quality_service.review_and_improve(
                title=matched_post["title"],
                content=matched_post["content"],
                tags=matched_post.get("tags", []),
                categories=[matched_post.get("category", "Shopping")],
                summary=matched_post.get("summary"),
                platform=p_key,
                language=acc_lang,
            )
            quality_reviews[p_key] = {
                "status": b_quality.get("status"),
                "score": b_quality.get("score"),
                "issues": b_quality.get("issues", []),
                "improvements": b_quality.get("improvements", []),
                "original_title": matched_post["title"],
                "improved_title": b_quality.get("title", matched_post["title"]),
            }
            async def _post_blogger():
                return await blog_service.post_to_blogger(
                    account_id=acc['id'],
                    title=b_quality.get("title", matched_post["title"]),
                    content=b_quality.get("content", matched_post["content"]),
                    tags=b_quality.get("tags", matched_post.get("tags", []))
                )
            b_res = await run_with_backoff(_post_blogger, platform=f"blogger:{acc['id']}", max_attempts=3, base_delay=1.0)
            normalized_blogger = normalize_publish_result(f"blogger:{acc['id']}", b_res)
            db.add_job_log(
                "Blogger",
                acc['name'],
                matched_post['title'],
                "success" if normalized_blogger.get("status") == "ok" else "error",
                normalized_blogger.get("error") or normalized_blogger.get("message") or "게시 성공",
                normalized_blogger.get("url"),
            )
            publish_results.append({
                "platform": f"Blogger ({acc['name']})", 
                **normalized_blogger
            })
        except Exception as e:
            print(f"[AmazonPublish] Blogger Error ({acc['name']}): {e}")
            db.add_job_log(f"Blogger", acc['name'], matched_post['title'], "error", str(e))
            publish_results.append({
                "platform": f"Blogger ({acc['name']})", 
                "status": "error", 
                "error": str(e)
            })

    any_ok = any(r.get("status") == "ok" for r in publish_results)
    all_ok = all(r.get("status") == "ok" for r in publish_results)
    opened_urls = open_published_urls(publish_results, context="amazon-publish")
    return {
        "status": "ok" if all_ok else ("partial" if any_ok else "error"),
        "results": publish_results,
        "opened_urls": opened_urls,
        "quality_reviews": quality_reviews,
    }
