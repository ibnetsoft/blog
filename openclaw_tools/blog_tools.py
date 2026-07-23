import os
import json
import logging
from typing import List, Optional

try:
    from services.blog_service import blog_service
    from services.publish_service import publish_service
    _NATIVE = True
except ImportError:
    _NATIVE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def publish_approved_post(title: str, content: str, tags: List[str], target_platform: str) -> str:
    """
    OpenClaw 에이전트 또는 디스코드 봇이 승인된 포스트를 최종 발행할 때 호출하는 래퍼 함수입니다.

    Args:
        title (str): 블로그 포스트 제목
        content (str): 블로그 본문 (HTML)
        tags (List[str]): 포스트에 적용할 태그 목록
        target_platform (str): 발행할 플랫폼 ('wordpress', 'blogger' 등)

    Returns:
        str: 발행된 포스트의 URL
    """
    logger.info(f"Publishing post '{title}' to {target_platform}...")

    if not _NATIVE:
        raise RuntimeError(
            "Native publish modules not available. "
            "Ensure this is run from the blog_app project root."
        )

    platform = target_platform.lower()

    if platform == "wordpress":
        result = publish_service.publish_to_wordpress(
            title=title,
            content=content,
            tags=tags,
            categories=[],
        )
        return result.get("url", "")
    elif platform == "blogger":
        # Blogger는 계정 선택이 필요하므로 첫 번째 활성 계정 사용
        import database as db
        accounts = db.get_blogger_accounts()
        if not accounts:
            raise ValueError("No active Blogger accounts found.")
        account = accounts[0]
        result = publish_service.publish_to_blogger(
            title=title,
            content=content,
            tags=tags,
            blog_id=account.get("blog_id", ""),
            refresh_token=account.get("refresh_token", ""),
        )
        return result.get("url", "")
    else:
        raise ValueError(f"지원하지 않는 플랫폼입니다: {target_platform}")


def reject_post(reason: str, workspace_dir: str = "") -> None:
    """
    사용자가 발행을 반려했을 때, OpenClaw 에이전트에게 반려 사유를 전달하기 위해
    상태 파일(status.json)을 업데이트합니다.

    Args:
        reason (str): 반려 사유
        workspace_dir (str): 프로젝트 워크스페이스 경로
    """
    if not workspace_dir:
        workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    status_file = os.path.join(workspace_dir, "status.json")
    status_data = {
        "status": "rejected",
        "feedback": reason,
        "updated_at": __import__("datetime").datetime.utcnow().isoformat(timespec="seconds"),
    }

    try:
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump(status_data, f, ensure_ascii=False, indent=4)
        logger.info(f"[System] OpenClaw rejection saved. (reason: {reason})")
    except Exception as e:
        logger.error(f"상태 파일 저장 중 오류 발생: {e}")