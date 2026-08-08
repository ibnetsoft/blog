from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
from services.blog_service import blog_service
from services.ai_quality_service import ai_quality_service
from services.source_service import source_service
from services.publish_utils import (
    normalize_publish_result,
    open_published_urls,
    run_with_backoff,
    validate_blog_post_payload,
    validate_publish_html,
)
from services.publish_workflow_service import BlogPostRequest, publish_workflow_service
from services.social_publish_service import social_publish_service
from config import config
import database as db
import httpx
import os
import uuid
from urllib.parse import urlencode
from fastapi import UploadFile, File

router = APIRouter(prefix="/api/blog", tags=["Blog"])

class BlogMetadataAnalysisRequest(BaseModel):
    content: str
    language: Optional[str] = "ko"

class IndependentBlogGenerateRequest(BaseModel):
    topic: str
    platforms: List[dict]
    category: Optional[str] = None
    source_content: Optional[str] = "" # NotebookLM 스타일 학습 자료 통합본

BLOGGER_SCOPES = "https://www.googleapis.com/auth/blogger"

def _get_redirect_uri(port: int = None):
    p = port or config.PORT
    return f"http://127.0.0.1:{p}/api/blog/oauth/callback"

REDIRECT_URI = _get_redirect_uri()


# ============ 구글 블로거 다중 계정 API ============

class BloggerAccountCreate(BaseModel):
    name: str
    blog_id: str = ""
    client_id: str = ""
    client_secret: str = ""
    lang: str = "ja"

class BloggerAccountUpdate(BaseModel):
    name: Optional[str] = None
    blog_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    lang: Optional[str] = None
    is_active: Optional[int] = None


@router.get("/accounts")
async def list_blogger_accounts():
    accounts = db.get_blogger_accounts()
    # refresh_token은 유출 방지를 위해 bool로만 노출
    for a in accounts:
        a["connected"] = bool(a.get("refresh_token"))
        a.pop("refresh_token", None)
        a.pop("client_secret", None)
    return {"accounts": accounts}


@router.post("/accounts")
async def create_blogger_account(req: BloggerAccountCreate):
    new_id = db.create_blogger_account(
        name=req.name,
        blog_id=req.blog_id,
        client_id=req.client_id,
        client_secret=req.client_secret,
        lang=req.lang
    )
    return {"id": new_id, "status": "created"}


@router.put("/accounts/{account_id}")
async def update_blogger_account(account_id: int, req: BloggerAccountUpdate):
    acc = db.get_blogger_account(account_id)
    if not acc:
        raise HTTPException(404, "계정을 찾을 수 없습니다.")
    updates = {k: v for k, v in req.dict().items() if v is not None}
    db.update_blogger_account(account_id, **updates)
    return {"status": "updated"}


@router.delete("/accounts/{account_id}")
async def delete_blogger_account(account_id: int):
    db.delete_blogger_account(account_id)
    return {"status": "deleted"}


@router.get("/accounts/{account_id}/oauth/start")
async def account_oauth_start(account_id: int):
    """특정 계정의 Google OAuth 연동 시작"""
    acc = db.get_blogger_account(account_id)
    if not acc:
        raise HTTPException(404, "계정을 찾을 수 없습니다.")
    client_id = acc.get("client_id") or config.BLOG_CLIENT_ID or db.get_global_setting("blog_client_id", "")
    if not client_id:
        raise HTTPException(400, "Client ID가 설정되지 않았습니다.")
    params = urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": BLOGGER_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": str(account_id),
    })
    return RedirectResponse(url=f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@router.get("/accounts/{account_id}/status")
async def account_oauth_status(account_id: int):
    acc = db.get_blogger_account(account_id)
    if not acc:
        raise HTTPException(404, "계정을 찾을 수 없습니다.")
    connected = bool(acc.get("refresh_token"))
    return {"connected": connected, "name": acc["name"], "blog_id": acc.get("blog_id")}


# ============ NotebookLM 스타일 소스 추출 API ============

class SourceExtractRequest(BaseModel):
    type: str # 'url', 'youtube', 'file'
    value: str # URL 또는 파일 경로

@router.post("/extract-source")
async def extract_source(req: SourceExtractRequest):
    """URL, 유튜브, 파일에서 텍스트 추출"""
    result = await source_service.extract_content(req.type, req.value)
    return result

@router.post("/upload-source-file")
async def upload_source_file(file: UploadFile = File(...)):
    """학습용 파일(PDF, TXT) 업로드 및 경로 반환"""
    try:
        os.makedirs("temp_sources", exist_ok=True)
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ['.pdf', '.txt', '.md']:
            return {"status": "error", "message": "지원하지 않는 파일 형식입니다. (PDF, TXT만 가능)"}
        
        file_path = os.path.join("temp_sources", f"{uuid.uuid4()}{ext}")
        with open(file_path, "wb") as f:
            f.write(await file.read())
            
        return {"status": "ok", "file_path": file_path, "original_name": file.filename}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============ 블로그 생성 API ============

class BlogGenerateRequest(BaseModel):
    source_type: str
    source_value: str
    platform: str = "wordpress"
    blog_style: str = "review"
    language: str = "ko"
    user_notes: str = ""
    category: Optional[str] = None
 
class BlogTranslateRequest(BaseModel):
    title: str
    content: Optional[str] = ""
    target_language: str
    summary: Optional[str] = None
    tags: Optional[str] = None
    category: Optional[str] = None
    skip_content: Optional[bool] = False
 
class BlogImagePromptRequest(BaseModel):
    project_id: int

class BlogAutoProcessRequest(BaseModel):
    platform: str = "wordpress"
    blog_style: str = "review"
    language: str = "ko"
    user_notes: str = ""
    category: Optional[str] = None
    script: Optional[str] = None

@router.get("/trends")
async def get_general_blog_trends(category: str = "General"):
    """일반 블로그 카테고리별 인기 추천 주제 반환"""
    from services.gemini_service import gemini_service
    # Recommendation chips are a helper, not the main writing flow. Keep this
    # endpoint instant and independent from paid AI keys so a bad Claude/OpenAI
    # key cannot block the page.
    trends = gemini_service.fallback_general_blog_trends(category)
    return {"status": "ok", "trends": trends, "source": "local"}

@router.post("/auto-process/{project_id}")
async def auto_process_blog(project_id: int, req: BlogAutoProcessRequest):
    """프로젝트 데이터를 기반으로 제목, 본문, 이미지를 자동으로 생성 및 구성 (project_id=0이면 req.script 사용)"""
    try:
        result = await blog_service.process_blog_automation_v2(
            project_id=project_id if project_id > 0 else None,
            platform=req.platform,
            blog_style=req.blog_style,
            language=req.language,
            user_notes=req.user_notes,
            raw_script=req.script,
            category=req.category
        )
        return result
    except Exception as e:
        return {"status": "error", "error": str(e)}

@router.post("/generate")
async def generate_blog(req: BlogGenerateRequest):
    """AI 블로그 콘텐츠 생성"""
    try:
        result = await blog_service.generate_blog_from_source(
            source_type=req.source_type,
            source_value=req.source_value,
            platform=req.platform,
            blog_style=req.blog_style,
            language=req.language,
            user_notes=req.user_notes,
            category=req.category
        )
        return result
    except Exception as e:
        print(f"Blog generate error: {e}")
        return {"status": "error", "error": str(e)}
 
@router.post("/translate")
async def translate_blog(req: BlogTranslateRequest):
    """블로그 콘텐츠 번역"""
    try:
        result = await blog_service.translate_blog(
            title=req.title,
            content=req.content,
            target_language=req.target_language,
            summary=req.summary,
            tags=req.tags,
            category=req.category,
            skip_content=req.skip_content
        )
        return result
    except Exception as e:
        print(f"Blog translate error: {e}")
        return {"status": "error", "error": str(e)}
 
@router.post("/generate-image-prompt")
async def generate_image_prompt(req: BlogImagePromptRequest):
    """블로그 내용을 분석하여 최적의 이미지 생성 프롬프트 제안"""
    try:
        # 프로젝트에서 대본/내용 가져오기
        full_data = db.get_project_full(req.project_id)
        content = full_data.get('script', '')
        if not content:
            return {"status": "error", "error": "블로그 내용이 없습니다."}
             
        prompt = await blog_service.generate_image_prompt_from_content(content)
        return {"status": "ok", "prompt": prompt}
    except Exception as e:
        return {"status": "error", "error": str(e)}

class BlogImageGenerateRequest(BaseModel):
    content: str
    project_id: Optional[int] = None
    image_count: int = 2
    no_human: bool = True # [추가] 사람 제거 옵션

@router.post("/generate-images")
async def generate_blog_images(req: BlogImageGenerateRequest):
    """기존 글(HTML/텍스트)에 어울리는 이미지를 자동 생성하여 삽입"""
    result = await blog_service.add_images_to_content(req.content, req.project_id, req.image_count, req.no_human)
    return result

@router.post("/analyze-metadata")
async def analyze_blog_metadata(req: BlogMetadataAnalysisRequest):
    """블로그 본문 분석하여 메태데이터 추출"""
    result = await blog_service.analyze_metadata(req.content, language=req.language)
    return result

@router.post("/post")
async def post_blog(req: BlogPostRequest):
    """블로그 게시 (워드프레스/다중 Blogger 계정 및 언어별 번역 지원)"""
    return await publish_workflow_service.publish_blog_post(req)


# =============================================
# Google Blogger OAuth2 인증 플로우
# =============================================

@router.get("/oauth/start")
async def blogger_oauth_start():
    """구글 블로그 OAuth2 인증 시작 - Google 로그인 페이지로 리다이렉트"""
    client_id = config.BLOG_CLIENT_ID or db.get_global_setting("blog_client_id", "")
    if not client_id:
        raise HTTPException(400, "Google Blog Client ID가 설정되지 않았습니다.")

    params = urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": BLOGGER_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
    })
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"
    return RedirectResponse(url=auth_url)


@router.get("/oauth/callback")
async def blogger_oauth_callback(request: Request):
    """Google OAuth2 콜백 - state에 account_id가 있으면 해당 계정에 저장"""
    code = request.query_params.get("code")
    error = request.query_params.get("error")
    state = request.query_params.get("state", "")  # account_id or ""

    def _err_page(msg):
        return HTMLResponse(f"""<html><body style="background:#0f172a;color:#f87171;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;">
        <div style="text-align:center;"><h2>인증 실패</h2><p>{msg}</p>
        <p><a href="/settings" style="color:#60a5fa;">설정으로 돌아가기</a></p></div></body></html>""")

    if error:
        return _err_page(error)
    if not code:
        return _err_page("인증 코드가 없습니다.")

    # 계정별 client_id/secret 결정
    account_id = int(state) if state.isdigit() else None
    if account_id:
        acc = db.get_blogger_account(account_id)
        client_id = (acc or {}).get("client_id") or config.BLOG_CLIENT_ID or db.get_global_setting("blog_client_id", "")
        client_secret = (acc or {}).get("client_secret") or config.BLOG_CLIENT_SECRET or db.get_global_setting("blog_client_secret", "")
    else:
        client_id = config.BLOG_CLIENT_ID or db.get_global_setting("blog_client_id", "")
        client_secret = config.BLOG_CLIENT_SECRET or db.get_global_setting("blog_client_secret", "")

    async with httpx.AsyncClient() as client:
        res = await client.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code"
        })

    if res.status_code != 200:
        return _err_page(res.text)

    token_data = res.json()
    refresh_token = token_data.get("refresh_token", "")

    if refresh_token:
        if account_id:
            db.update_blogger_account(account_id, refresh_token=refresh_token)
            print(f"[Blogger OAuth] Account {account_id} refresh token saved")
        else:
            db.save_global_setting("blog_refresh_token", refresh_token)
            print(f"[Blogger OAuth] Global refresh token saved")

    return HTMLResponse("""<html><body style="background:#0f172a;color:#10b981;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;">
    <div style="text-align:center;">
        <h1 style="font-size:48px;margin-bottom:20px;">✅</h1>
        <h2>구글 블로그 연동 완료!</h2>
        <p style="color:#94a3b8;margin-top:10px;">설정 페이지에서 연동 상태를 확인하세요.</p>
        <script>setTimeout(() => window.close() || (window.location='/settings'), 2000);</script>
        <p style="margin-top:20px;"><a href="/settings" style="color:#60a5fa;text-decoration:none;padding:10px 20px;border:1px solid #60a5fa;border-radius:8px;">설정으로 돌아가기</a></p>
    </div></body></html>""")


@router.get("/oauth/status")
async def blogger_oauth_status():
    """구글 블로그 OAuth 연동 상태 확인"""
    refresh_token = db.get_global_setting("blog_refresh_token", "")
    has_token = bool(refresh_token)

    if has_token:
        # 토큰이 유효한지 테스트
        client_id = config.BLOG_CLIENT_ID or db.get_global_setting("blog_client_id", "")
        client_secret = config.BLOG_CLIENT_SECRET or db.get_global_setting("blog_client_secret", "")
        if client_id and client_secret:
            try:
                async with httpx.AsyncClient() as client:
                    res = await client.post("https://oauth2.googleapis.com/token", data={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token"
                    })
                    if res.status_code == 200:
                        return {"status": "ok", "connected": True, "message": "구글 블로그 연동됨"}
                    else:
                        return {"status": "ok", "connected": False, "message": "토큰 만료 - 재인증 필요"}
            except Exception:
                pass

    return {"status": "ok", "connected": False, "message": "연동되지 않음 - OAuth 인증 필요"}


@router.get("/logs")
async def get_logs(limit: int = 100):
    """작업 로그 조회"""
    logs = db.get_job_logs(limit)
    return {"status": "ok", "logs": logs}


@router.get("/quality-insights")
async def get_quality_insights(limit: int = 20):
    """AI 품질 개선 이력과 최근 게시 로그 기반 학습 요약"""
    reviews = db.get_recent_ai_quality_reviews(limit)
    return {
        "status": "ok",
        "enabled": ai_quality_service.is_enabled(),
        "min_score": ai_quality_service.min_score(),
        "learning_context": ai_quality_service.build_learning_context(),
        "reviews": reviews,
    }


@router.post("/logs/{log_id}/retry")
async def retry_log(log_id: int):
    """실패한 로그 재시도"""
    import json
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM job_logs WHERE id = ?", (log_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="로그를 찾을 수 없습니다.")
    
    if not row['payload']:
        raise HTTPException(status_code=400, detail="재시도할 데이터(payload)가 없습니다.")

    try:
        payload = json.loads(row['payload'])
        platform = row['platform']
        
        result = {"status": "error", "error": f"지원하지 않는 플랫폼: {platform}"}

        if platform == "wordpress":
            async def _retry_wp():
                return await blog_service.post_to_wordpress(
                    title=payload["title"],
                    content=payload["content"],
                    tags=payload.get("tags", []),
                    categories=payload.get("categories", []),
                    summary=payload.get("summary")
                )
            result = await run_with_backoff(_retry_wp, platform=platform, max_attempts=3, base_delay=1.0)
        elif platform.startswith("blogger"):
            async def _retry_blogger():
                return await blog_service.post_to_blogger(
                    title=payload["title"],
                    content=payload["content"],
                    tags=payload.get("tags", []),
                    account_id=payload["account_id"],
                    summary=payload.get("summary"),
                    category=payload.get("category"),
                    image_tags=payload.get("image_tags", [])
                )
            result = await run_with_backoff(_retry_blogger, platform=platform, max_attempts=3, base_delay=1.0)
        
        # 새 로그 추가
        p_name = result.get("account_name", row['account_name'])
        db.add_job_log(
            platform=platform,
            account_name=p_name,
            title=payload["title"],
            status=result.get("status", "error"),
            message=result.get("error", result.get("message", "")),
            url=result.get("url", ""),
            payload=payload # 동일 페이로드 유지
        )

        result["opened_urls"] = open_published_urls(result, context="retry-post")
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


@router.post("/generate-independent")
async def generate_independent_multi(req: IndependentBlogGenerateRequest):
    """주제 하나로 여러 언어의 블로그 포스팅을 각각 독립적으로 병렬 생성"""
    if not req.topic:
        raise HTTPException(status_code=400, detail="주제가 없습니다.")
    
    # NotebookLM 스타일 학습 자료(source_content) 전달
    res = await blog_service.generate_independent_multi_language_blogs(
        topic=req.topic,
        platforms=req.platforms,
        source_content=req.source_content # 추가됨
    )
    return res

@router.post("/upload-image")
async def upload_blog_image(file: UploadFile = File(...)):
    """로컬 이미지를 업로드하여 워드프레스 미디어 라이브러리에 저장하고 HTML 반환"""
    try:
        import os
        import uuid
        import shutil
        from services.blog_service import blog_service
        
        print(f"[API] Image upload started: {file.filename}")
        
        # 1. 임시 저장
        temp_dir = "temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        ext = os.path.splitext(file.filename)[1].lower()
        if not ext: ext = ".png"
        
        temp_path = os.path.join(temp_dir, f"{uuid.uuid4()}{ext}")
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 2. WordPress 미디어 라이브러리 업로드
        print(f"  - Uploading to WordPress Media Library...")
        wp_res = await blog_service.upload_image_to_wordpress(temp_path)
        
        # 3. 임시 파일 삭제
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        if wp_res.get("status") == "ok":
            img_url = wp_res["url"]
            print(f"  - Upload Success: {img_url}")
            # 프리미엄 이미지 HTML 생성 (Blogger/WP 공용 레이아웃)
            img_html = (
                f'\n<div class="premium-blog-image" style="display:flex !important; flex-direction:column !important; align-items:center !important; justify-content:center !important; margin:3.5rem auto !important; clear:both !important; width:100% !important;">'
                f'<figure style="display:block !important; margin:0 auto !important; max-width:88% !important; text-align:center !important;">'
                f'<img src="{img_url}" alt="Uploaded Image" style="max-width:100% !important; width:100% !important; height:auto !important; border-radius:22px; box-shadow:0 18px 45px rgba(0,0,0,0.1); display:block !important; margin:0 auto !important;">'
                f'</figure>'
                f'</div>\n'
            )
            return {"status": "ok", "url": img_url, "html": img_html}
        else:
            err_msg = wp_res.get("error", "이미지 업로드 실패")
            print(f"  - Upload Failed: {err_msg}")
            return {"status": "error", "error": err_msg}
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[API] Upload critical error: {e}")
        return {"status": "error", "error": f"서버 내부 오류: {str(e)}"}
