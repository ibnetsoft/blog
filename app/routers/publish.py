# app/routers/publish.py - 퍼블리시 허브 (원소스 멀티유즈 파이프라인)
import os
import shutil
import time
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional
from services.publish_service import publish_service
from services.blog_service import blog_service
from config import config
import database as db

router = APIRouter(prefix="/api/publish", tags=["Publish"])


class CreateSessionRequest(BaseModel):
    project_id: Optional[int] = None
    title: str = ""
    content: str = ""


class AnalyzeImagesRequest(BaseModel):
    session_id: int
    image_count: int = 0


class UpdateImageRequest(BaseModel):
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    caption: Optional[str] = None
    prompt_ko: Optional[str] = None
    prompt_en: Optional[str] = None
    status: Optional[str] = None


class PostBlogRequest(BaseModel):
    session_id: int
    platforms: List[str] = ["wordpress", "blogger"]
    tags: List[str] = []


class BuildHtmlRequest(BaseModel):
    session_id: int


class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    step: Optional[str] = None
    status: Optional[str] = None


# ==========================================
# 세션 관리
# ==========================================

@router.post("/sessions")
async def create_session(req: CreateSessionRequest):
    """퍼블리시 세션 생성"""
    try:
        if req.project_id and not req.content:
            # 프로젝트에서 대본 가져오기
            session_id = await publish_service.create_session_from_project(req.project_id)
            if not session_id:
                return {"status": "error", "error": "프로젝트에 대본이 없습니다."}
        else:
            if not req.content:
                return {"status": "error", "error": "내용을 입력해주세요."}
            project_id = req.project_id or 0
            session_id = db.create_publish_session(project_id, req.title, req.content)

        session = db.get_publish_session(session_id)
        return {"status": "ok", "session_id": session_id, "session": session}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/sessions")
async def list_sessions():
    """모든 퍼블리시 세션 목록"""
    try:
        sessions = db.get_all_publish_sessions()
        return {"status": "ok", "sessions": sessions}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/sessions/{session_id}")
async def get_session(session_id: int):
    """세션 상세 조회 (이미지 포함)"""
    try:
        session = db.get_publish_session(session_id)
        if not session:
            raise HTTPException(404, "세션을 찾을 수 없습니다.")
        images = db.get_publish_images(session_id)
        return {"status": "ok", "session": session, "images": images}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.put("/sessions/{session_id}")
async def update_session(session_id: int, req: UpdateSessionRequest):
    """세션 업데이트"""
    try:
        updates = {k: v for k, v in req.dict().items() if v is not None}
        if updates:
            db.update_publish_session(session_id, **updates)
        session = db.get_publish_session(session_id)
        return {"status": "ok", "session": session}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: int):
    """세션 삭제"""
    try:
        db.delete_publish_session(session_id)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ==========================================
# 이미지 포인트 분석 & 관리
# ==========================================

@router.post("/analyze-images")
async def analyze_images(req: AnalyzeImagesRequest):
    """글 분석 → 이미지 삽입 위치 + 프롬프트 자동 생성"""
    try:
        session = db.get_publish_session(req.session_id)
        if not session:
            return {"status": "error", "error": "세션을 찾을 수 없습니다."}

        content = session.get("content", "")
        if not content:
            return {"status": "error", "error": "세션에 내용이 없습니다."}

        # 기존 이미지 포인트 삭제
        existing = db.get_publish_images(req.session_id)
        for img in existing:
            db.delete_publish_image(img["id"])

        # AI 분석
        image_points = await publish_service.analyze_image_points(content, req.image_count)

        # DB 저장
        saved_images = []
        for i, point in enumerate(image_points):
            image_id = db.add_publish_image(
                session_id=req.session_id,
                position=point.get("position", i + 1),
                prompt_ko=point.get("prompt_ko", ""),
                prompt_en=point.get("prompt_en", "")
            )
            saved_images.append({
                "id": image_id,
                "position": point.get("position", i + 1),
                "prompt_ko": point.get("prompt_ko", ""),
                "prompt_en": point.get("prompt_en", ""),
                "status": "pending"
            })

        # 세션 스텝 업데이트
        db.update_publish_session(req.session_id, step="images")

        return {"status": "ok", "images": saved_images, "count": len(saved_images)}
    except Exception as e:
        print(f"[Publish] analyze_images error: {e}")
        return {"status": "error", "error": str(e)}


@router.get("/sessions/{session_id}/images")
async def get_images(session_id: int):
    """세션의 이미지 목록"""
    try:
        images = db.get_publish_images(session_id)
        return {"status": "ok", "images": images}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.put("/images/{image_id}")
async def update_image(image_id: int, req: UpdateImageRequest):
    """이미지 정보 업데이트 (URL, 캡션 등)"""
    try:
        updates = {k: v for k, v in req.dict().items() if v is not None}
        if updates:
            db.update_publish_image(image_id, **updates)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.delete("/images/{image_id}")
async def delete_image(image_id: int):
    """이미지 삭제"""
    try:
        db.delete_publish_image(image_id)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post("/images/{session_id}/add")
async def add_image_manually(session_id: int):
    """수동으로 이미지 슬롯 추가"""
    try:
        existing = db.get_publish_images(session_id)
        position = len(existing) + 1
        image_id = db.add_publish_image(
            session_id=session_id,
            position=position,
            prompt_ko="",
            prompt_en=""
        )
        return {"status": "ok", "image_id": image_id, "position": position}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ==========================================
# HTML 조립 & 블로그 게시
# ==========================================

@router.post("/build-html")
async def build_html(req: BuildHtmlRequest):
    """이미지가 삽입된 블로그 HTML 생성"""
    try:
        session = db.get_publish_session(req.session_id)
        if not session:
            return {"status": "error", "error": "세션을 찾을 수 없습니다."}

        images = db.get_publish_images(req.session_id)
        html = publish_service.build_blog_html(session["content"], images)

        # DB에 HTML 저장
        db.update_publish_session(req.session_id, content_html=html)

        return {"status": "ok", "html": html}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post("/post-blog")
async def post_blog(req: PostBlogRequest):
    """블로그 게시 (WordPress + Blogger)"""
    try:
        session = db.get_publish_session(req.session_id)
        if not session:
            return {"status": "error", "error": "세션을 찾을 수 없습니다."}

        # HTML이 없으면 먼저 빌드
        html_content = session.get("content_html")
        if not html_content:
            images = db.get_publish_images(req.session_id)
            html_content = publish_service.build_blog_html(session["content"], images)
            db.update_publish_session(req.session_id, content_html=html_content)

        title = session.get("title", "무제")
        results = await publish_service.post_to_blogs(
            session_id=req.session_id,
            title=title,
            html_content=html_content,
            tags=req.tags,
            platforms=req.platforms
        )

        all_ok = all(r.get("status") == "ok" for r in results.values())
        any_ok = any(r.get("status") == "ok" for r in results.values())

        return {
            "status": "ok" if all_ok else ("partial" if any_ok else "error"),
            "results": results
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ==========================================
# 이미지 파일 업로드
# ==========================================

@router.post("/upload-image/{session_id}/{image_id}")
async def upload_image_file(session_id: int, image_id: int, file: UploadFile = File(...)):
    """이미지 파일 업로드 → 로컬 저장 + DB 업데이트"""
    try:
        # 저장 디렉토리
        upload_dir = os.path.join(config.OUTPUT_DIR, "publish_images", str(session_id))
        os.makedirs(upload_dir, exist_ok=True)

        # 파일명 생성
        ext = os.path.splitext(file.filename)[1] or ".png"
        filename = f"img_{image_id}_{int(time.time())}{ext}"
        file_path = os.path.join(upload_dir, filename)

        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # 웹 경로
        web_url = f"/output/publish_images/{session_id}/{filename}"

        # DB 업데이트
        db.update_publish_image(image_id, image_url=web_url, status="done")

        return {"status": "ok", "image_url": web_url, "file_path": file_path}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post("/upload-image-wp/{session_id}")
async def upload_images_to_wordpress(session_id: int):
    """세션의 모든 로컬 이미지를 WordPress Media Library에 업로드하고 URL 교체"""
    try:
        images = db.get_publish_images(session_id)
        results = []

        for img in images:
            img_url = img.get("image_url", "")
            if not img_url or not img_url.startswith("/output/"):
                results.append({"id": img["id"], "status": "skip", "reason": "로컬 이미지 아님"})
                continue

            # 로컬 경로 변환
            local_path = os.path.join(config.OUTPUT_DIR, img_url.replace("/output/", ""))
            if not os.path.exists(local_path):
                results.append({"id": img["id"], "status": "error", "reason": "파일 없음"})
                continue

            # WordPress 업로드
            wp_result = await blog_service.upload_image_to_wordpress(local_path)
            if wp_result.get("status") == "ok":
                wp_url = wp_result.get("url", "")
                db.update_publish_image(img["id"], image_url=wp_url)
                results.append({"id": img["id"], "status": "ok", "wp_url": wp_url})
            else:
                results.append({"id": img["id"], "status": "error", "reason": wp_result.get("error", "")})

        return {"status": "ok", "results": results}
    except Exception as e:
        return {"status": "error", "error": str(e)}
