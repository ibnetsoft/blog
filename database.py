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
    """)

    # 기본 글로벌 설정 초기화
    defaults = [
        ("gemini", ""),
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
    allowed = {'position', 'prompt_ko', 'prompt_en', 'image_url', 'local_path', 'caption'}
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


# 앱 시작 시 초기화
init_db()
