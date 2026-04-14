from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
from services.blog_service import blog_service
from services.source_service import source_service
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
    client_id = acc.get("client_id") or config.BLOG_CLIENT_ID
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

class BlogPostRequest(BaseModel):
    title: str
    content: str
    tags: List[str] = []
    categories: List[str] = []
    summary: Optional[str] = None
    platforms: List[str] = ["wordpress"]
    platform_langs: dict = {}  # e.g. {"wordpress": "ko", "blogger_1": "ja", "blogger_2": "en"}
    contents: Optional[dict] = None  # e.g. {"wordpress": "html...", "blogger_1": "html..."}
    metadata: Optional[dict] = None  # e.g. {"wordpress": {"title": "...", "tags": [], ...}}


class BlogAutoProcessRequest(BaseModel):
    platform: str = "wordpress"
    blog_style: str = "review"
    language: str = "ko"
    user_notes: str = ""
    category: Optional[str] = None
    script: Optional[str] = None

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
    result = await blog_service.analyze_metadata(req.content)
    return result

@router.post("/post")
async def post_blog(req: BlogPostRequest):
    """블로그 게시 (워드프레스/다중 Blogger 계정 및 언어별 번역 지원)"""
    results = {}
    platforms = req.platforms or ["wordpress"]
    platform_langs = req.platform_langs or {}
    processed_content = req.content # 대표 본문 (텔레그램 등에서 사용)

    # 1. 사전 처리: 로컬 이미지(/output/)를 WP에 한 번만 업로드하여 공개 URL로 치환 (모든 탭 공통)
    # 탭별 독립 콘텐츠(req.contents)가 있는 경우와 기본 본문(req.content) 모두 처리
    if req.contents:
        for p_id in req.contents:
            try:
                # 모든 탭의 로컬 경로를 WP URL로 미리 치환
                req.contents[p_id] = await blog_service.upload_local_images_to_public(req.contents[p_id])
            except Exception as e:
                print(f"[BlogPost] Image pre-upload error for {p_id}: {e}")
    
    # 기본 본문도 치환 (Blogger 번역용 원본으로 사용될 수 있음)
    try:
        req.content = await blog_service.upload_local_images_to_public(req.content)
        processed_content = req.content
        print(f"[BlogPost] Primary content image pre-upload done")
    except Exception as img_err:
        print(f"[BlogPost] Primary image pre-upload error: {img_err}")

    # 2. 플랫폼별 게시
    # [하이브리드 게시 엔진: 워드프레스 선행 + 다국어 병렬]
    # 1. 워드프레스 선제 게시 (모든 포스팅의 영구 이미지 URL 기준점 확보)
    source_images = []
    if "wordpress" in platforms:
        try:
            print(f"[BlogPost] Step 1: Posting to WordPress First (Image URL Base)...")
            # 탭별 독립 콘텐츠가 있으면 그것을 우선 사용
            if req.contents and "wordpress" in req.contents:
                final_content = req.contents["wordpress"]
                m = req.metadata.get("wordpress", {}) if req.metadata else {}
                final_title = m.get("title") or req.title
                final_tags = m.get("tags") or req.tags
                final_categories = m.get("category", "").split(',') if m.get("category") else req.categories
                final_summary = m.get("summary") or req.summary
            else:
                final_content = req.content
                final_title = req.title
                final_tags = req.tags
                final_categories = req.categories
                final_summary = req.summary

            # 워드프레스 게시 전 본문의 로컬 이미지들을 워드프레스 미디어 라이브러리로 확실히 변환
            final_content = await blog_service.upload_local_images_to_public(final_content)
            
            w_res = await blog_service.post_to_wordpress(
                title=final_title, 
                content=final_content, 
                tags=final_tags, 
                categories=final_categories,
                summary=final_summary
            )
            
            # 리트라이용 페이로드 저장
            w_res["payload"] = {
                "title": final_title,
                "content": final_content,
                "tags": final_tags,
                "categories": final_categories,
                "summary": final_summary
            }
            results["wordpress"] = w_res

            # 워드프레스 게시 성공 시 본문에서 최종 WP URL 이미지들 추출 (중요!)
            if w_res.get("status") == "ok":
               source_images = blog_service.extract_image_tags(final_content)
               print(f"[BlogPost] WP Success! Global images extracted: {len(source_images)}")
        except Exception as e:
            print(f"[BlogPost] WordPress posting failed (Step 1): {e}")
            results["wordpress"] = {"status": "error", "error": str(e)}

    # WP 게시 후에도 이미지가 없으면 기본 본문에서 추출 시도 (Fallback)
    if not source_images:
        source_images = blog_service.extract_image_tags(req.content)

    # 2. 다국어 Blogger 계정 병렬 게시 (비동기 엔진 가동)
    selected_blogger_ids = []
    for p in platforms:
        if p == "blogger":
            accounts = db.get_blogger_accounts()
            selected_blogger_ids.extend([str(a["id"]) for a in accounts if a.get("refresh_token")])
        elif p.startswith("blogger:"):
            selected_blogger_ids.append(p.split(":")[1])
        elif p.startswith("blogger_"):
            selected_blogger_ids.append(p.split("_")[1])

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
                p_key = f"blogger_{acc_id}" # use underscore for key consistency
                
                try:
                    target_lang = platform_langs.get(f"blogger:{acc_id}") or platform_langs.get(p_key) or acc.get("lang") or "ja"
                    print(f"[Parallel] Posting {acc_name} ({target_lang})...")

                    if req.contents and (f"blogger:{acc_id}" in req.contents or p_key in req.contents):
                        f_content = req.contents.get(f"blogger:{acc_id}") or req.contents.get(p_key)
                        m_data = (req.metadata.get(f"blogger:{acc_id}") or req.metadata.get(p_key, {})) if req.metadata else {}
                        f_title = m_data.get("title") or req.title
                        f_tags = m_data.get("tags") or req.tags
                        f_summary = m_data.get("summary") or req.summary
                        f_category = m_data.get("category") or (req.categories[0] if req.categories else "")
                        
                        if source_images:
                            f_content = blog_service.inject_images_into_content(f_content, source_images)
                    else:
                        # 실시간 번역 모드
                        f_title, f_content = req.title, req.content
                        f_tags, f_summary = req.tags, req.summary
                        if target_lang != "ko":
                            trans = await blog_service.translate_blog(req.title, req.content, target_lang, summary=req.summary)
                            if trans.get("status") == "ok":
                                f_title, f_content = trans["title"], trans["content"]
                                f_summary = trans.get("summary")
                        f_category = req.categories[0] if req.categories else ""
                        if source_images:
                            f_content = blog_service.inject_images_into_content(f_content, source_images)

                    res = await blog_service.post_to_blogger(
                        title=f_title, content=f_content, tags=f_tags, account_id=acc_id,
                        summary=f_summary, category=f_category, image_tags=source_images
                    )
                    
                    # 리트라이용 페이로드 저장
                    res["payload"] = {
                        "title": f_title,
                        "content": f_content,
                        "tags": f_tags,
                        "account_id": acc_id,
                        "summary": f_summary,
                        "category": f_category,
                        "image_tags": source_images
                    }
                    
                    print(f"[Parallel] {acc_name} DONE: {res.get('status')}")
                    return p_key, {**res, "account_name": acc_name}
                except Exception as e:
                    print(f"[Parallel] {acc_name} FAILED: {e}")

            # 7개(?) 이상의 계정을 동시에 병렬 실행
            print(f"[BlogPost] Step 2: Parallel posting to {len(connected_accounts)} Blogger accounts...")
            parallel_results = await asyncio.gather(*[post_single_blogger(acc) for acc in connected_accounts])
            for key, val in parallel_results:
                results[key] = val

    # 'telegram' 처리

    # 'telegram' 처리
    # platforms list에서 'telegram' 또는 'telegram:{chat_id}' 형식을 모두 찾음
    tg_selected = [p for p in platforms if p == "telegram" or p.startswith("telegram:")]
    
    if tg_selected:
        try:
            from services.telegram_service import telegram_service
            import re
            import json
            from database import get_global_setting
            
            # 텔레그램용 요약 메시지 생성 (HTML 태그 제거)
            clean_text = re.sub(r'<[^>]+>', '', processed_content)
            # 불필요한 공백/줄바꿈 정리
            clean_text = re.sub(r'\n\s*\n', '\n', clean_text).strip()
            summary = clean_text[:300] + "..." if len(clean_text) > 300 else clean_text
            
            # 본문에 포함된 첫 번째 이미지 추출 시도 (공개 URL)
            img_match = re.search(r'<img [^>]*src="([^"]+)"[^>]*>', processed_content)
            first_img = img_match.group(1) if img_match else None
            
            tg_text = f"<b>{req.title}</b>\n\n{summary}"
            
            # 다중 채널 방송 설정 로드
            channels_raw = get_global_setting("telegram_channels", "[]")
            if isinstance(channels_raw, str):
                try: all_channels = json.loads(channels_raw)
                except: all_channels = []
            else:
                all_channels = channels_raw or []
                
            # 기본 Chat ID도 포함 (하위 호환)
            default_chat_id = get_global_setting("telegram_chat_id", "")
            if default_chat_id and not any(str(c.get('chat_id')) == str(default_chat_id) for c in all_channels):
                all_channels.insert(0, {"name": "기본 그룹", "chat_id": default_chat_id})

            # 선택된 채널 필터링
            target_chat_ids = []
            for p in tg_selected:
                if p == "telegram":
                    # 레거시 혹은 전체 선택 대응: 모든 채널 추가
                    for c in all_channels:
                        if c.get('chat_id') not in target_chat_ids:
                            target_chat_ids.append(c.get('chat_id'))
                elif p.startswith("telegram:"):
                    c_id = p.split(":", 1)[1]
                    if c_id not in target_chat_ids:
                        target_chat_ids.append(c_id)

            if not target_chat_ids:
                results["telegram"] = {"status": "error", "error": "선택된 텔레그램 채널이 없습니다."}
            else:
                tg_statuses = []
                for c_id in target_chat_ids:
                    if not c_id: continue
                    
                    if first_img:
                        res = await telegram_service.send_photo(first_img, tg_text, chat_id=c_id)
                    else:
                        res = await telegram_service.send_message(tg_text, chat_id=c_id)
                    tg_statuses.append(res.get("status") == "ok")
                
                if all(tg_statuses):
                    results["telegram"] = {"status": "ok", "account_name": f"텔레그램({len(tg_statuses)}개 채널)"}
                elif any(tg_statuses):
                    results["telegram"] = {"status": "ok", "account_name": f"텔레그램(일부 성공: {sum(tg_statuses)}/{len(tg_statuses)})"}
                else:
                    results["telegram"] = {"status": "error", "error": "모든 텔레그램 채널 전송 실패"}
        except Exception as e:
            err_msg = f"Telegram Broadcast Error: {str(e)}"
            results["telegram"] = {"status": "error", "error": err_msg}

    # 3. 로그 저장
    for p_key, res in results.items():
        try:
            p_name = res.get("account_name", p_key)
            db.add_job_log(
                platform=p_key,
                account_name=p_name,
                title=req.title,
                status=res.get("status", "error"),
                message=res.get("error", res.get("message", "")),
                url=res.get("url", ""),
                payload=res.get("payload")
            )
        except Exception as log_err:
            print(f"[LogSave] Error: {log_err}")

    any_ok = any(r.get("status") == "ok" for r in results.values())
    all_ok = all(r.get("status") == "ok" for r in results.values())

    return {
        "status": "ok" if all_ok else ("partial" if any_ok else "error"),
        "results": results
    }


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
        client_id = (acc or {}).get("client_id") or config.BLOG_CLIENT_ID
        client_secret = (acc or {}).get("client_secret") or config.BLOG_CLIENT_SECRET
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
            result = await blog_service.post_to_wordpress(
                title=payload["title"],
                content=payload["content"],
                tags=payload.get("tags", []),
                categories=payload.get("categories", []),
                summary=payload.get("summary")
            )
        elif platform.startswith("blogger"):
            result = await blog_service.post_to_blogger(
                title=payload["title"],
                content=payload["content"],
                tags=payload.get("tags", []),
                account_id=payload["account_id"],
                summary=payload.get("summary"),
                category=payload.get("category"),
                image_tags=payload.get("image_tags", [])
            )
        
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
