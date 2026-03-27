from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
from services.blog_service import blog_service
from config import config
import database as db
import httpx
from urllib.parse import urlencode

router = APIRouter(prefix="/api/blog", tags=["Blog"])

class BlogMetadataAnalysisRequest(BaseModel):
    content: str

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


class BlogGenerateRequest(BaseModel):
    source_type: str
    source_value: str
    platform: str = "wordpress"
    blog_style: str = "review"
    language: str = "ko"
    user_notes: str = ""
 
class BlogTranslateRequest(BaseModel):
    title: str
    content: str
    target_language: str
    summary: Optional[str] = None
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
            raw_script=req.script
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
            user_notes=req.user_notes
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

@router.post("/generate-images")
async def generate_blog_images(req: BlogImageGenerateRequest):
    """기존 글(HTML/텍스트)에 어울리는 이미지를 자동 생성하여 삽입"""
    result = await blog_service.add_images_to_content(req.content, req.project_id, req.image_count)
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

    # 1. 사전 처리: 로컬 이미지(/output/)를 WP에 한 번만 업로드하여 공개 URL로 치환
    # 다중 콘텐츠가 있는 경우 각각에 대해 처리
    if req.contents:
        for p_id in req.contents:
            try:
                req.contents[p_id] = await blog_service.upload_local_images_to_public(req.contents[p_id])
            except Exception as e:
                print(f"[BlogPost] Image pre-upload error for {p_id}: {e}")
    else:
        try:
            req.content = await blog_service.upload_local_images_to_public(req.content)
            print(f"[BlogPost] Image pre-upload done (legacy)")
        except Exception as img_err:
            print(f"[BlogPost] Image pre-upload error: {img_err}")

    # 2. 플랫폼별 게시
    # 'wordpress' 처리
    if "wordpress" in platforms:
        try:
            # 탭별 독립 콘텐츠가 있으면 그것을 우선 사용
            if req.contents and "wordpress" in req.contents:
                final_content = req.contents["wordpress"]
                m = req.metadata.get("wordpress", {}) if req.metadata else {}
                final_title = m.get("title") or req.title
                final_tags = m.get("tags") or req.tags
                final_categories = m.get("category", "").split(',') if m.get("category") else req.categories
                final_summary = m.get("summary") or req.summary
                print(f"[BlogPost] Using direct HTML for WordPress")
            else:
                # 레거시: 번역 플로우
                target_lang = platform_langs.get("wordpress", "ko")
                final_title, final_content = req.title, req.content
                final_tags = req.tags
                final_categories = req.categories
                final_summary = req.summary
                
                if target_lang != "ko":
                    print(f"[BlogPost] Translating for WordPress to {target_lang}")
                    trans_res = await blog_service.translate_blog(req.title, req.content, target_lang, summary=req.summary)
                    if trans_res.get("status") == "ok":
                        final_title = trans_res["title"]
                        final_content = trans_res["content"]
                        final_summary = trans_res.get("summary")
                
            res = await blog_service.post_to_wordpress(
                title=final_title, 
                content=final_content, 
                tags=final_tags, 
                categories=final_categories,
                summary=final_summary
            )
            results["wordpress"] = res
        except Exception as e:
            results["wordpress"] = {"status": "error", "error": str(e)}

    # 'blogger' 처리 (다중 계정 선택 지원)
    # 0. 공통 이미지 추출 (워드프레스용 최종 본문에서 추출하거나 한 번만 수행)
    source_images = []
    if "wordpress" in platforms and req.contents and "wordpress" in req.contents:
        source_images = blog_service.extract_image_tags(req.contents["wordpress"])
    elif "wordpress" in platforms:
        source_images = blog_service.extract_image_tags(req.content) # req.content는 이미 upload_local 되어있음
    
    # platforms 리스트에 'blogger' (전체) 또는 'blogger:123' (개별) 형식이 포함될 수 있음
    selected_blogger_ids = []
    for p in platforms:
        if p == "blogger":
            accounts = db.get_blogger_accounts()
            selected_blogger_ids.extend([str(a["id"]) for a in accounts if a.get("refresh_token")])
        elif p.startswith("blogger:"):
            selected_blogger_ids.append(p.split(":")[1])

    if selected_blogger_ids:
        selected_blogger_ids = list(set(selected_blogger_ids))
        accounts = db.get_blogger_accounts()
        connected_accounts = [a for a in accounts if str(a.get("id")) in selected_blogger_ids and a.get("refresh_token")]
        
        if not connected_accounts:
            results["blogger"] = {"status": "error", "error": "선택된 계정 중 연동된 구글 블로그 계정이 없습니다."}
        else:
            for acc in connected_accounts:
                acc_id = acc["id"]
                acc_name = acc["name"]
                p_key = f"blogger:{acc_id}"
                
                try:
                    m = {} # 메타데이터 초기화
                    # 탭별 독립 콘텐츠가 있으면 그것을 우선 사용
                    if req.contents and p_key in req.contents:
                        final_content = req.contents[p_key]
                        
                        # [핵심] 일어/영어 직접 입력 탭인 경우 워드프레스 이미지만 삽입
                        if (acc.get("lang") or "ja") != "ko":
                            print(f"[BlogPost] Injecting source images into manual content for {acc_name}")
                            final_content = blog_service.inject_images_into_content(final_content, source_images)
                        
                        m = req.metadata.get(p_key, {}) if req.metadata else {}
                        final_title = m.get("title") or req.title
                        final_tags = m.get("tags") or req.tags
                        final_summary = m.get("summary") or req.summary
                    else:
                        # ... (이후 레거시 코드)
                        # 레거시: 번역 플로우
                        target_lang = platform_langs.get(f"blogger_{acc_id}") or acc.get("lang") or "ja"
                        final_title, final_content = req.title, req.content
                        final_tags = req.tags
                        final_summary = req.summary
                        
                        if target_lang != "ko":
                            trans_res = await blog_service.translate_blog(req.title, req.content, target_lang, summary=req.summary, category=req.categories[0] if req.categories else None)
                            if trans_res.get("status") == "ok":
                                final_title = trans_res["title"]
                                final_content = trans_res["content"]
                                final_summary = trans_res.get("summary")
                                final_category = trans_res.get("category")
                            else:
                                final_category = req.categories[0] if req.categories else ""
                        else:
                            final_category = req.categories[0] if req.categories else ""
                    
                    res = await blog_service.post_to_blogger(
                        title=final_title, 
                        content=final_content, 
                        tags=final_tags, 
                        account_id=acc_id,
                        summary=final_summary,
                        category=m.get("category") if (req.contents and p_key in req.contents) else final_category
                    )
                    results[f"blogger_{acc_id}"] = {**res, "account_name": acc_name}
                except Exception as e:
                    results[f"blogger_{acc_id}"] = {"status": "error", "error": str(e), "account_name": acc_name}

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
                url=res.get("url", "")
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
