"""
블로그 앱 전용 데이터베이스
테이블: global_settings, publish_sessions, publish_images
"""
import sqlite3
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from config import config

DB_PATH = os.path.join(config.BASE_DIR, "blog_app.db")


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS global_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS publish_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            content_html TEXT,
            status TEXT DEFAULT 'draft',
            step TEXT DEFAULT 'content',
            blog_wp_url TEXT,
            blog_wp_post_id TEXT,
            blog_blogger_url TEXT,
            blog_blogger_post_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS blogger_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            blog_id TEXT,
            client_id TEXT,
            client_secret TEXT,
            refresh_token TEXT,
            lang TEXT DEFAULT 'ja',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS publish_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            position INTEGER DEFAULT 0,
            prompt_ko TEXT,
            prompt_en TEXT,
            image_url TEXT,
            video_url TEXT,
            local_path TEXT,
            caption TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES publish_sessions(id)
        );

        CREATE TABLE IF NOT EXISTS job_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT,
            account_name TEXT,
            title TEXT,
            status TEXT,
            message TEXT,
            url TEXT,
            payload TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS category_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name TEXT UNIQUE NOT NULL,
            template_html TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ai_quality_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT,
            language TEXT,
            original_title TEXT,
            improved_title TEXT,
            score INTEGER,
            issues TEXT,
            improvements TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS openclaw_campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            category TEXT,
            default_language TEXT DEFAULT 'ko',
            ai_provider TEXT DEFAULT 'gemini',
            ai_model TEXT DEFAULT 'gemini-3.5-flash',
            platforms_json TEXT NOT NULL,
            schedule_type TEXT DEFAULT 'daily',
            schedule_time TEXT DEFAULT '09:00',
            timezone TEXT DEFAULT 'Asia/Seoul',
            topic_mode TEXT DEFAULT 'trend',
            approval_mode TEXT DEFAULT 'auto',
            quality_min_score INTEGER DEFAULT 82,
            image_policy_json TEXT DEFAULT '{}',
            prompt_profile_json TEXT DEFAULT '{}',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS openclaw_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            topic TEXT,
            status TEXT DEFAULT 'queued',
            current_stage TEXT DEFAULT 'queued',
            approval_required INTEGER DEFAULT 0,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            error_message TEXT,
            summary_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (campaign_id) REFERENCES openclaw_campaigns(id)
        );

        CREATE TABLE IF NOT EXISTS openclaw_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            task_type TEXT NOT NULL,
            target_id TEXT,
            status TEXT DEFAULT 'queued',
            attempt_count INTEGER DEFAULT 0,
            max_attempts INTEGER DEFAULT 3,
            input_json TEXT,
            output_json TEXT,
            error_message TEXT,
            next_retry_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES openclaw_runs(id)
        );

        CREATE TABLE IF NOT EXISTS approval_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            task_id INTEGER,
            target_id TEXT,
            title TEXT,
            summary TEXT,
            content_html TEXT,
            status TEXT DEFAULT 'pending',
            reviewer TEXT,
            review_note TEXT,
            approved_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES openclaw_runs(id),
            FOREIGN KEY (task_id) REFERENCES openclaw_tasks(id)
        );

        CREATE TABLE IF NOT EXISTS content_variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            target_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            language TEXT NOT NULL,
            title TEXT,
            summary TEXT,
            tags_json TEXT,
            content_html TEXT,
            images_json TEXT,
            quality_score INTEGER,
            quality_report_json TEXT,
            publish_status TEXT DEFAULT 'draft',
            publish_url TEXT,
            publish_post_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES openclaw_runs(id)
        );
    """)

    # 기본 글로벌 설정 초기화
    defaults = [
        ("gemini", ""),
        ("openai_api_key", ""),
        ("anthropic_api_key", ""),
        ("ai_text_provider", "gemini"),
        ("ai_text_model", "gemini-3.5-flash"),
        ("wp_url", ""),
        ("wp_username", ""),
        ("wp_password", ""),
        ("blog_client_id", ""),
        ("blog_client_secret", ""),
        ("blog_id", ""),
        ("blog_refresh_token", ""),
        ("telegram_token", ""),
        ("telegram_chat_id", ""),
        ("telegram_channels", "[]"),
        ("facebook_page_id", ""),
        ("facebook_access_token", ""),
        ("instagram_account_id", ""),
        ("instagram_access_token", ""),
        ("tiktok_access_token", ""),
        ("auto_post_enabled", "false"),
        ("auto_post_time", "09:00"),
        ("auto_post_category", "IT, Tech, Trends"),
        ("auto_post_no_human", "true"),
        ("auto_post_platforms", '[{"language": "ko", "platform": "wordpress", "target_id": "wordpress"}]'),
        ("auto_open_published_posts", "true"),
        ("ai_quality_enabled", "true"),
        ("ai_quality_min_score", "82"),
    ]
    for key, val in defaults:
        cursor.execute(
            "INSERT OR IGNORE INTO global_settings (key, value) VALUES (?, ?)",
            (key, val)
        )

    # 기존 DB 마이그레이션: lang 컬럼이 없으면 추가
    try:
        cursor.execute("ALTER TABLE blogger_accounts ADD COLUMN lang TEXT DEFAULT 'ja'")
        conn.commit()
    except Exception:
        pass  # 이미 컬럼이 있으면 무시

    # job_logs 컬럼 추가 (payload)
    try:
        cursor.execute("ALTER TABLE job_logs ADD COLUMN payload TEXT")
        conn.commit()
    except Exception:
        pass

    # AI 품질 리뷰 테이블 추가
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_quality_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT,
                language TEXT,
                original_title TEXT,
                improved_title TEXT,
                score INTEGER,
                issues TEXT,
                improvements TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE publish_images ADD COLUMN video_url TEXT")
        conn.commit()
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE openclaw_campaigns ADD COLUMN ai_provider TEXT DEFAULT 'gemini'")
        conn.commit()
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE openclaw_campaigns ADD COLUMN ai_model TEXT DEFAULT 'gemini-3.5-flash'")
        conn.commit()
    except Exception:
        pass

    conn.commit()
    conn.close()


# ============ 글로벌 설정 ============

def save_global_setting(key: str, value: Any):
    conn = get_db()
    cursor = conn.cursor()
    json_val = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    cursor.execute("""
        INSERT INTO global_settings (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = CURRENT_TIMESTAMP
    """, (key, json_val))
    conn.commit()
    conn.close()


def get_global_setting(key: str, default: Any = None, value_type: str = None) -> Any:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM global_settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        val = row['value']
        try:
            parsed = json.loads(val)
        except:
            parsed = val
        if value_type == "bool":
            if isinstance(parsed, bool):
                return parsed
            if isinstance(parsed, str):
                return parsed.lower() in ('true', '1', 'yes')
            return bool(parsed)
        return parsed
    return default


def get_all_global_settings() -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM global_settings")
    rows = cursor.fetchall()
    conn.close()
    result = {}
    for row in rows:
        try:
            result[row['key']] = json.loads(row['value'])
        except:
            result[row['key']] = row['value']
    return result


# ============ 퍼블리시 세션 ============

def create_publish_session(project_id: int, title: str, content: str) -> int:
    """project_id 파라미터는 하위 호환용으로 유지 (무시됨)"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO publish_sessions (title, content, status, step)
        VALUES (?, ?, 'draft', 'content')
    """, (title, content))
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id


def get_publish_session(session_id: int) -> Optional[Dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM publish_sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_publish_sessions() -> List[Dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM publish_sessions ORDER BY updated_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_publish_session(session_id: int, **kwargs):
    if not kwargs:
        return
    conn = get_db()
    cursor = conn.cursor()
    allowed = {
        'title', 'content', 'content_html', 'status', 'step',
        'blog_wp_url', 'blog_wp_post_id', 'blog_blogger_url', 'blog_blogger_post_id'
    }
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        conn.close()
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [session_id]
    cursor.execute(f"""
        UPDATE publish_sessions SET {set_clause}, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, values)
    conn.commit()
    conn.close()


def delete_publish_session(session_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM publish_images WHERE session_id = ?", (session_id,))
    cursor.execute("DELETE FROM publish_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


# ============ 퍼블리시 이미지 ============

def add_publish_image(session_id: int, position: int, prompt_ko: str, prompt_en: str) -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO publish_images (session_id, position, prompt_ko, prompt_en)
        VALUES (?, ?, ?, ?)
    """, (session_id, position, prompt_ko, prompt_en))
    image_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return image_id


def get_publish_images(session_id: int) -> List[Dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM publish_images WHERE session_id = ? ORDER BY position",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_publish_image(image_id: int, **kwargs):
    if not kwargs:
        return
    conn = get_db()
    cursor = conn.cursor()
    allowed = {'position', 'prompt_ko', 'prompt_en', 'image_url', 'video_url', 'local_path', 'caption'}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        conn.close()
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [image_id]
    cursor.execute(f"UPDATE publish_images SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


def delete_publish_image(image_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM publish_images WHERE id = ?", (image_id,))
    conn.commit()
    conn.close()


# ============ 작업 로그 ============

def add_job_log(platform: str, account_name: str, title: str, status: str, message: str, url: str = "", payload: dict = None):
    conn = get_db()
    cursor = conn.cursor()
    payload_json = json.dumps(payload, ensure_ascii=False) if payload else None
    cursor.execute("""
        INSERT INTO job_logs (platform, account_name, title, status, message, url, payload)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (platform, account_name, title, status, message, url, payload_json))
    conn.commit()
    conn.close()


def get_job_logs(limit: int = 100) -> List[Dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM job_logs ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============ AI 품질 개선 로그 ============

def add_ai_quality_review(
    platform: str,
    language: str,
    original_title: str,
    improved_title: str,
    score: int,
    issues: Any = None,
    improvements: Any = None,
):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ai_quality_reviews (
            platform, language, original_title, improved_title, score, issues, improvements
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        platform,
        language,
        original_title,
        improved_title,
        int(score or 0),
        json.dumps(issues or [], ensure_ascii=False),
        json.dumps(improvements or [], ensure_ascii=False),
    ))
    conn.commit()
    conn.close()


def get_recent_ai_quality_reviews(limit: int = 20) -> List[Dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ai_quality_reviews ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============ 구글 블로거 계정 관리 ============

def get_blogger_accounts() -> List[Dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM blogger_accounts ORDER BY created_at ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_blogger_account(account_id: int) -> Optional[Dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM blogger_accounts WHERE id = ?", (account_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def create_blogger_account(name: str, blog_id: str = "", client_id: str = "", client_secret: str = "", lang: str = "ja") -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO blogger_accounts (name, blog_id, client_id, client_secret, lang)
        VALUES (?, ?, ?, ?, ?)
    """, (name, blog_id, client_id, client_secret, lang))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id


def update_blogger_account(account_id: int, **kwargs):
    if not kwargs:
        return
    conn = get_db()
    cursor = conn.cursor()
    allowed = {'name', 'blog_id', 'client_id', 'client_secret', 'refresh_token', 'lang', 'is_active'}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        conn.close()
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [account_id]
    cursor.execute(f"UPDATE blogger_accounts SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


def delete_blogger_account(account_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM blogger_accounts WHERE id = ?", (account_id,))
    conn.commit()
    conn.close()


# ============ 카테고리 템플릿 관리 ============

def save_category_template(category_name: str, template_html: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO category_templates (category_name, template_html, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(category_name) DO UPDATE SET
            template_html = excluded.template_html,
            updated_at = CURRENT_TIMESTAMP
    """, (category_name, template_html))
    conn.commit()
    conn.close()


def get_category_template(category_name: str) -> Optional[str]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT template_html FROM category_templates WHERE category_name = ?", (category_name,))
    row = cursor.fetchone()
    conn.close()
    return row['template_html'] if row else None


def get_all_category_templates() -> Dict[str, str]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT category_name, template_html FROM category_templates")
    rows = cursor.fetchall()
    conn.close()
    return {row['category_name']: row['template_html'] for row in rows}


# ============ 프로젝트 연동 스텁 (하위 호환) ============
# blog.py의 auto-process 엔드포인트가 호출하는 함수들
# 블로그 전용 앱에서는 프로젝트 개념이 없으므로 None 반환

def get_project_full(project_id: int) -> Optional[Dict]:
    """하위 호환 스텁 - 블로그 전용 앱에는 프로젝트가 없음"""
    return None

def get_script(project_id: int) -> Optional[Dict]:
    return None

def get_shorts(project_id: int) -> List[Dict]:
    return []


# ============ OpenClaw Campaigns ============

def create_openclaw_campaign(
    name: str,
    category: str,
    platforms_json: Any,
    default_language: str = "ko",
    ai_provider: str = "gemini",
    ai_model: str = "gemini-3.5-flash",
    schedule_type: str = "daily",
    schedule_time: str = "09:00",
    timezone: str = "Asia/Seoul",
    topic_mode: str = "trend",
    approval_mode: str = "auto",
    quality_min_score: int = 82,
    image_policy_json: Any = None,
    prompt_profile_json: Any = None,
    status: str = "active",
    is_active: int = 1,
) -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO openclaw_campaigns (
            name, status, category, default_language, ai_provider, ai_model, platforms_json, schedule_type,
            schedule_time, timezone, topic_mode, approval_mode, quality_min_score,
            image_policy_json, prompt_profile_json, is_active, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        name,
        status,
        category,
        default_language,
        ai_provider,
        ai_model,
        json.dumps(platforms_json, ensure_ascii=False) if not isinstance(platforms_json, str) else platforms_json,
        schedule_type,
        schedule_time,
        timezone,
        topic_mode,
        approval_mode,
        int(quality_min_score or 82),
        json.dumps(image_policy_json or {}, ensure_ascii=False) if not isinstance(image_policy_json, str) else image_policy_json,
        json.dumps(prompt_profile_json or {}, ensure_ascii=False) if not isinstance(prompt_profile_json, str) else prompt_profile_json,
        int(is_active),
    ))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id


def _deserialize_openclaw_row(row: Optional[sqlite3.Row]) -> Optional[Dict]:
    if not row:
        return None
    item = dict(row)
    for key in ("platforms_json", "image_policy_json", "prompt_profile_json", "summary_json", "tags_json", "images_json", "quality_report_json", "input_json", "output_json"):
        if key in item and item[key]:
            try:
                item[key] = json.loads(item[key])
            except Exception:
                pass
    return item


def get_openclaw_campaign(campaign_id: int) -> Optional[Dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM openclaw_campaigns WHERE id = ?", (campaign_id,))
    row = cursor.fetchone()
    conn.close()
    return _deserialize_openclaw_row(row)


def get_openclaw_campaigns(active_only: bool = False) -> List[Dict]:
    conn = get_db()
    cursor = conn.cursor()
    if active_only:
        cursor.execute("SELECT * FROM openclaw_campaigns WHERE is_active = 1 ORDER BY updated_at DESC, id DESC")
    else:
        cursor.execute("SELECT * FROM openclaw_campaigns ORDER BY updated_at DESC, id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [_deserialize_openclaw_row(r) for r in rows]


def update_openclaw_campaign(campaign_id: int, **kwargs):
    if not kwargs:
        return
    conn = get_db()
    cursor = conn.cursor()
    allowed = {
        'name', 'status', 'category', 'default_language', 'ai_provider', 'ai_model', 'platforms_json',
        'schedule_type', 'schedule_time', 'timezone', 'topic_mode',
        'approval_mode', 'quality_min_score', 'image_policy_json',
        'prompt_profile_json', 'is_active'
    }
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        conn.close()
        return
    json_fields = {'platforms_json', 'image_policy_json', 'prompt_profile_json'}
    normalized = {}
    for key, value in fields.items():
        if key in json_fields and not isinstance(value, str):
            normalized[key] = json.dumps(value, ensure_ascii=False)
        else:
            normalized[key] = value
    set_clause = ", ".join(f"{k} = ?" for k in normalized)
    values = list(normalized.values()) + [campaign_id]
    cursor.execute(f"""
        UPDATE openclaw_campaigns SET {set_clause}, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, values)
    conn.commit()
    conn.close()


# ============ OpenClaw Runs ============

def create_openclaw_run(campaign_id: int, topic: str = "", status: str = "queued", current_stage: str = "queued", approval_required: int = 0) -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO openclaw_runs (
            campaign_id, topic, status, current_stage, approval_required
        )
        VALUES (?, ?, ?, ?, ?)
    """, (campaign_id, topic, status, current_stage, int(approval_required)))
    run_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return run_id


def get_openclaw_run(run_id: int) -> Optional[Dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM openclaw_runs WHERE id = ?", (run_id,))
    row = cursor.fetchone()
    conn.close()
    return _deserialize_openclaw_row(row)


def get_openclaw_runs(limit: int = 50, campaign_id: Optional[int] = None) -> List[Dict]:
    conn = get_db()
    cursor = conn.cursor()
    if campaign_id:
        cursor.execute(
            "SELECT * FROM openclaw_runs WHERE campaign_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
            (campaign_id, limit),
        )
    else:
        cursor.execute("SELECT * FROM openclaw_runs ORDER BY created_at DESC, id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [_deserialize_openclaw_row(r) for r in rows]


def get_latest_openclaw_run_for_campaign(campaign_id: int) -> Optional[Dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM openclaw_runs WHERE campaign_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
        (campaign_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return _deserialize_openclaw_row(row)


def update_openclaw_run(run_id: int, **kwargs):
    if not kwargs:
        return
    conn = get_db()
    cursor = conn.cursor()
    allowed = {'topic', 'status', 'current_stage', 'approval_required', 'started_at', 'completed_at', 'error_message', 'summary_json'}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        conn.close()
        return
    if 'summary_json' in fields and not isinstance(fields['summary_json'], str):
        fields['summary_json'] = json.dumps(fields['summary_json'], ensure_ascii=False)
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [run_id]
    cursor.execute(f"UPDATE openclaw_runs SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


# ============ OpenClaw Tasks ============

def create_openclaw_task(
    run_id: int,
    task_type: str,
    target_id: str = "",
    status: str = "queued",
    attempt_count: int = 0,
    max_attempts: int = 3,
    input_json: Any = None,
    output_json: Any = None,
    error_message: str = "",
    next_retry_at: str = None,
) -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO openclaw_tasks (
            run_id, task_type, target_id, status, attempt_count, max_attempts,
            input_json, output_json, error_message, next_retry_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        run_id,
        task_type,
        target_id,
        status,
        int(attempt_count),
        int(max_attempts),
        json.dumps(input_json, ensure_ascii=False) if input_json is not None and not isinstance(input_json, str) else input_json,
        json.dumps(output_json, ensure_ascii=False) if output_json is not None and not isinstance(output_json, str) else output_json,
        error_message,
        next_retry_at,
    ))
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id


def get_openclaw_tasks(run_id: int) -> List[Dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM openclaw_tasks WHERE run_id = ? ORDER BY created_at ASC, id ASC", (run_id,))
    rows = cursor.fetchall()
    conn.close()
    return [_deserialize_openclaw_row(r) for r in rows]


def update_openclaw_task(task_id: int, **kwargs):
    if not kwargs:
        return
    conn = get_db()
    cursor = conn.cursor()
    allowed = {'status', 'attempt_count', 'max_attempts', 'input_json', 'output_json', 'error_message', 'next_retry_at'}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        conn.close()
        return
    for json_key in ('input_json', 'output_json'):
        if json_key in fields and fields[json_key] is not None and not isinstance(fields[json_key], str):
            fields[json_key] = json.dumps(fields[json_key], ensure_ascii=False)
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [task_id]
    cursor.execute(f"""
        UPDATE openclaw_tasks SET {set_clause}, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, values)
    conn.commit()
    conn.close()


# ============ OpenClaw Approvals ============

def create_approval_queue_item(
    run_id: int,
    task_id: Optional[int],
    target_id: str,
    title: str,
    summary: str,
    content_html: str,
    status: str = "pending",
) -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO approval_queue (
            run_id, task_id, target_id, title, summary, content_html, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (run_id, task_id, target_id, title, summary, content_html, status))
    approval_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return approval_id


def get_approval_queue_items(status: Optional[str] = None) -> List[Dict]:
    conn = get_db()
    cursor = conn.cursor()
    if status:
        cursor.execute("SELECT * FROM approval_queue WHERE status = ? ORDER BY created_at DESC, id DESC", (status,))
    else:
        cursor.execute("SELECT * FROM approval_queue ORDER BY created_at DESC, id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_approval_queue_item(approval_id: int) -> Optional[Dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM approval_queue WHERE id = ?", (approval_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_approval_queue_item(approval_id: int, **kwargs):
    if not kwargs:
        return
    conn = get_db()
    cursor = conn.cursor()
    allowed = {'status', 'reviewer', 'review_note', 'approved_at'}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        conn.close()
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [approval_id]
    cursor.execute(f"UPDATE approval_queue SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


# ============ OpenClaw Content Variants ============

def create_content_variant(
    run_id: int,
    target_id: str,
    platform: str,
    language: str,
    title: str,
    summary: str,
    tags_json: Any,
    content_html: str,
    images_json: Any = None,
    quality_score: Optional[int] = None,
    quality_report_json: Any = None,
    publish_status: str = "draft",
    publish_url: str = "",
    publish_post_id: str = "",
) -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO content_variants (
            run_id, target_id, platform, language, title, summary, tags_json,
            content_html, images_json, quality_score, quality_report_json,
            publish_status, publish_url, publish_post_id, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        run_id,
        target_id,
        platform,
        language,
        title,
        summary,
        json.dumps(tags_json or [], ensure_ascii=False) if not isinstance(tags_json, str) else tags_json,
        content_html,
        json.dumps(images_json or [], ensure_ascii=False) if not isinstance(images_json, str) else images_json,
        quality_score,
        json.dumps(quality_report_json or {}, ensure_ascii=False) if not isinstance(quality_report_json, str) else quality_report_json,
        publish_status,
        publish_url,
        publish_post_id,
    ))
    variant_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return variant_id


def get_content_variants(run_id: int) -> List[Dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM content_variants WHERE run_id = ? ORDER BY created_at ASC, id ASC", (run_id,))
    rows = cursor.fetchall()
    conn.close()
    return [_deserialize_openclaw_row(r) for r in rows]


def update_content_variant(variant_id: int, **kwargs):
    if not kwargs:
        return
    conn = get_db()
    cursor = conn.cursor()
    allowed = {
        'title', 'summary', 'tags_json', 'content_html', 'images_json',
        'quality_score', 'quality_report_json', 'publish_status',
        'publish_url', 'publish_post_id'
    }
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        conn.close()
        return
    for json_key in ('tags_json', 'images_json', 'quality_report_json'):
        if json_key in fields and fields[json_key] is not None and not isinstance(fields[json_key], str):
            fields[json_key] = json.dumps(fields[json_key], ensure_ascii=False)
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [variant_id]
    cursor.execute(f"""
        UPDATE content_variants SET {set_clause}, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, values)
    conn.commit()
    conn.close()


def load_settings_to_config():
    try:
        import os
        from config import config
        
        # Mapping from DB key to Config attribute and Env var name
        key_map = {
            'gemini': ('GEMINI_API_KEY', 'GEMINI_API_KEY'),
            'openai_api_key': ('OPENAI_API_KEY', 'OPENAI_API_KEY'),
            'anthropic_api_key': ('ANTHROPIC_API_KEY', 'ANTHROPIC_API_KEY'),
            'ai_text_provider': ('AI_TEXT_PROVIDER', 'AI_TEXT_PROVIDER'),
            'ai_text_model': ('AI_TEXT_MODEL', 'AI_TEXT_MODEL'),
            'blog_client_id': ('BLOG_CLIENT_ID', 'BLOG_CLIENT_ID'),
            'blog_client_secret': ('BLOG_CLIENT_SECRET', 'BLOG_CLIENT_SECRET'),
            'blog_id': ('BLOG_ID', 'BLOG_ID'),
            'wp_url': ('WP_URL', 'WP_URL'),
            'wp_username': ('WP_USERNAME', 'WP_USERNAME'),
            'wp_password': ('WP_PASSWORD', 'WP_PASSWORD'),
            'telegram_token': ('TELEGRAM_TOKEN', 'TELEGRAM_TOKEN'),
            'telegram_chat_id': ('TELEGRAM_CHAT_ID', 'TELEGRAM_CHAT_ID'),
            'telegram_channels': ('TELEGRAM_CHANNELS', 'TELEGRAM_CHANNELS'),
            'facebook_page_id': ('FACEBOOK_PAGE_ID', 'FACEBOOK_PAGE_ID'),
            'facebook_access_token': ('FACEBOOK_ACCESS_TOKEN', 'FACEBOOK_ACCESS_TOKEN'),
            'instagram_account_id': ('INSTAGRAM_ACCOUNT_ID', 'INSTAGRAM_ACCOUNT_ID'),
            'instagram_access_token': ('INSTAGRAM_ACCESS_TOKEN', 'INSTAGRAM_ACCESS_TOKEN'),
            'tiktok_access_token': ('TIKTOK_ACCESS_TOKEN', 'TIKTOK_ACCESS_TOKEN'),
        }
        
        for db_key, (config_attr, env_name) in key_map.items():
            val = get_global_setting(db_key, "")
            if val:
                if isinstance(val, (list, dict)):
                    import json
                    str_val = json.dumps(val, ensure_ascii=False)
                else:
                    str_val = str(val)
                setattr(config, config_attr, str_val)
                os.environ[env_name] = str_val
                
        print("[Database] Loaded global settings to config successfully")
    except Exception as e:
        print(f"[Database] Failed to load settings to config: {e}")


# 앱 시작 시 초기화
init_db()
load_settings_to_config()
