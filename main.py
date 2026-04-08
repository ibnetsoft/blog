"""
블로그 자동화 앱 - FastAPI 서버
"""
import sys
import os

# Windows cp949 이모지 출력 크래시 방지
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uvicorn
import webbrowser
import threading

from config import config
import database as db

# ==========================================
# App 초기화
# ==========================================
app = FastAPI(title="블로그 자동화", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=config.TEMPLATES_DIR)
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
app.mount("/output", StaticFiles(directory=config.OUTPUT_DIR), name="output")

# i18n
from services.i18n import Translator
app_lang = os.environ.get("APP_LANG", "ko")
translator = Translator(app_lang)
templates.env.globals['t'] = translator.t
templates.env.globals['current_lang'] = app_lang
templates.env.globals['app_mode'] = 'blog'
templates.env.globals['blog_only'] = True

# ==========================================
# 라우터 등록
# ==========================================
from app.routers import blog as blog_router
from app.routers import publish as publish_router

app.include_router(blog_router.router)
app.include_router(publish_router.router)


def get_project_output_dir(project_id: int = None):
    """
    프로젝트별 출력 디렉토리 경로 반환. 
    project_id가 0이거나 None이면 기본 'general' 디렉토리 사용.
    """
    sub_dir = f"project_{project_id}" if project_id and project_id > 0 else "general"
    abs_dir = os.path.join(config.OUTPUT_DIR, sub_dir)
    web_dir = f"/output/{sub_dir}"
    os.makedirs(abs_dir, exist_ok=True)
    return abs_dir, web_dir


# ==========================================
# 페이지 라우트
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return RedirectResponse(url="/blog-independent")



@app.get("/blog-independent", response_class=HTMLResponse)
async def page_blog_independent(request: Request):
    return templates.TemplateResponse("pages/blog_independent.html", {
        "request": request,
        "page": "blog-independent",
    })


@app.get("/settings", response_class=HTMLResponse)
async def page_settings(request: Request):
    return templates.TemplateResponse("pages/settings.html", {
        "request": request,
        "page": "settings",
    })


@app.get("/logs", response_class=HTMLResponse)
async def page_logs(request: Request):
    return templates.TemplateResponse("pages/logs.html", {
        "request": request,
        "page": "logs",
    })


@app.get("/publish-hub", response_class=HTMLResponse)
async def page_publish_hub(request: Request):
    return templates.TemplateResponse("pages/publish_hub.html", {
        "request": request,
        "page": "publish-hub",
    })


# ==========================================
# 설정 API
# ==========================================

class GlobalSettingsRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    blog_client_id: Optional[str] = None
    blog_client_secret: Optional[str] = None
    blog_id: Optional[str] = None
    wp_url: Optional[str] = None
    wp_username: Optional[str] = None
    wp_password: Optional[str] = None
    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_channels: Optional[Any] = None # List or JSON


@app.get("/api/settings/keys")
async def get_api_keys():
    return config.get_api_keys_status()


@app.post("/api/settings/keys")
async def save_api_keys(req: GlobalSettingsRequest):
    key_map = {
        'gemini_api_key': 'GEMINI_API_KEY',
        'blog_client_id': 'BLOG_CLIENT_ID',
        'blog_client_secret': 'BLOG_CLIENT_SECRET',
        'blog_id': 'BLOG_ID',
        'wp_url': 'WP_URL',
        'wp_username': 'WP_USERNAME',
        'wp_password': 'WP_PASSWORD',
        'telegram_token': 'TELEGRAM_TOKEN',
        'telegram_chat_id': 'TELEGRAM_CHAT_ID',
        'telegram_channels': 'TELEGRAM_CHANNELS',
    }
    db_key_map = {
        'gemini_api_key': 'gemini',
        'blog_client_id': 'blog_client_id',
        'blog_client_secret': 'blog_client_secret',
        'blog_id': 'blog_id',
        'wp_url': 'wp_url',
        'wp_username': 'wp_username',
        'wp_password': 'wp_password',
        'telegram_token': 'telegram_token',
        'telegram_chat_id': 'telegram_chat_id',
        'telegram_channels': 'telegram_channels',
    }
    for field, env_key in key_map.items():
        value = getattr(req, field, None)
        if value is not None:
            # 리스트나 딕셔너리인 경우 JSON 문자열로 변환하여 저장
            if isinstance(value, (list, dict)):
                import json
                save_value = json.dumps(value, ensure_ascii=False)
            else:
                save_value = str(value)
            
            config.update_api_key(env_key, save_value)
            db.save_global_setting(db_key_map[field], value)
    return {"status": "ok"}


@app.get("/api/settings/global")
async def get_global_settings():
    return db.get_all_global_settings()


@app.post("/api/settings/global")
async def update_global_setting(body: Dict[str, Any]):
    key = body.get("key")
    value = body.get("value")
    if not key:
        return JSONResponse(status_code=400, content={"error": "key required"})
    db.save_global_setting(key, value)
    return {"status": "ok"}


# ==========================================
# 헬스 체크
# ==========================================

@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "apis": {
            "gemini": bool(config.GEMINI_API_KEY),
            "wordpress": bool(config.WP_URL and config.WP_USERNAME),
            "blogger": bool(config.BLOG_CLIENT_ID),
        }
    }


# ==========================================
# 언어 전환
# ==========================================

@app.post("/api/language")
async def set_language(body: Dict[str, Any]):
    global app_lang, translator
    lang = body.get("lang", "ko")
    app_lang = lang
    translator = Translator(lang)
    templates.env.globals['t'] = translator.t
    templates.env.globals['current_lang'] = lang
    return {"status": "ok", "lang": lang}


# ==========================================
# 실행
# ==========================================

def start_browser():
    """서버 시작 후 브라우저 자동 오픈"""
    url = f"http://127.0.0.1:{config.PORT}"
    print(f"브라우저 오픈 시도: {url}")
    webbrowser.open(url)

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  🚀 SNS Studio - 블로그 자동화 시스템")
    print("-" * 60)
    print(f"  ● 접속 주소: http://127.0.0.1:{config.PORT}")
    print(f"  ● 환경 설정: {'디버그(DEBUG)' if config.DEBUG else '운영(PRODUCTION)'}")
    print(f"  ● 출력 경로: {config.OUTPUT_DIR}")
    print("-" * 60)
    print("  ※ 이미지가 업로드되지 않을 경우 브라우저 포트를 확인하세요!")
    print("=" * 60 + "\n")
    
    # 서버 실행 직전 타이머 작동 (2초 후 브라우저 오픈)
    threading.Timer(2.0, start_browser).start()
    
    # 실행 파일(.exe)에서는 reload=True가 동작하지 않으므로 강제 비활성화
    is_frozen = getattr(sys, 'frozen', False)
    
    uvicorn.run(
        "main:app" if not is_frozen else app,
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG and not is_frozen,
        workers=1,
    )
