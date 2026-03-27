"""
블로그 자동화 앱 설정
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # AI
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    # Google Blogger OAuth2
    BLOG_CLIENT_ID: str = os.getenv("BLOG_CLIENT_ID", "")
    BLOG_CLIENT_SECRET: str = os.getenv("BLOG_CLIENT_SECRET", "")
    BLOG_ID: str = os.getenv("BLOG_ID", "")

    # WordPress
    WP_URL: str = os.getenv("WP_URL", "")
    WP_USERNAME: str = os.getenv("WP_USERNAME", "")
    WP_PASSWORD: str = os.getenv("WP_PASSWORD", "")
    
    # Telegram SNS
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    TELEGRAM_CHANNELS: str = os.getenv("TELEGRAM_CHANNELS", "[]") # New: JSON List

    # 서버 설정
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "8000"))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"

    # API URLs
    GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

    # 경로 설정
    import sys
    if getattr(sys, 'frozen', False):
        RESOURCE_DIR = sys._MEIPASS
        BASE_DIR = os.path.dirname(sys.executable)
    else:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        RESOURCE_DIR = BASE_DIR

    TEMPLATES_DIR = os.path.join(RESOURCE_DIR, "templates")
    STATIC_DIR = os.path.join(RESOURCE_DIR, "static")
    OUTPUT_DIR = os.path.join(BASE_DIR, "output")
    LOG_DIR = os.path.join(BASE_DIR, "logs")

    @classmethod
    def setup_directories(cls):
        for d in [cls.OUTPUT_DIR, cls.LOG_DIR]:
            os.makedirs(d, exist_ok=True)

    @classmethod
    def update_api_key(cls, key_name: str, value: str):
        valid_keys = [
            'GEMINI_API_KEY', 'BLOG_CLIENT_ID', 'BLOG_CLIENT_SECRET', 'BLOG_ID',
            'WP_URL', 'WP_USERNAME', 'WP_PASSWORD',
            'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID', 'TELEGRAM_CHANNELS'
        ]
        if key_name not in valid_keys:
            return False
        setattr(cls, key_name, value)
        os.environ[key_name] = value
        env_path = os.path.join(cls.BASE_DIR, '.env')
        env_lines = []
        key_exists = False
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith(f'{key_name}='):
                        env_lines.append(f'{key_name}={value}\n')
                        key_exists = True
                    else:
                        env_lines.append(line)
        if not key_exists:
            env_lines.append(f'{key_name}={value}\n')
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(env_lines)
        return True

    @staticmethod
    def mask_key(key: str) -> str:
        if not key:
            return ""
        if len(key) <= 8:
            return "*" * len(key)
        return f"{key[:4]}****{key[-4:]}"

    @classmethod
    def get_api_keys_status(cls):
        return {
            "gemini": {"set": bool(cls.GEMINI_API_KEY), "masked": cls.mask_key(cls.GEMINI_API_KEY), "value": cls.GEMINI_API_KEY},
            "blog_client_id": {"set": bool(cls.BLOG_CLIENT_ID), "masked": cls.mask_key(cls.BLOG_CLIENT_ID), "value": cls.BLOG_CLIENT_ID},
            "blog_client_secret": {"set": bool(cls.BLOG_CLIENT_SECRET), "masked": cls.mask_key(cls.BLOG_CLIENT_SECRET), "value": cls.BLOG_CLIENT_SECRET},
            "blog_id": {"set": bool(cls.BLOG_ID), "masked": cls.BLOG_ID, "value": cls.BLOG_ID},
            "wp_url": {"set": bool(cls.WP_URL), "masked": cls.WP_URL, "value": cls.WP_URL},
            "wp_username": {"set": bool(cls.WP_USERNAME), "masked": cls.WP_USERNAME, "value": cls.WP_USERNAME},
            "wp_password": {"set": bool(cls.WP_PASSWORD), "masked": cls.mask_key(cls.WP_PASSWORD), "value": cls.WP_PASSWORD},
            "telegram_token": {"set": bool(cls.TELEGRAM_TOKEN), "masked": cls.mask_key(cls.TELEGRAM_TOKEN), "value": cls.TELEGRAM_TOKEN},
            "telegram_chat_id": {"set": bool(cls.TELEGRAM_CHAT_ID), "masked": cls.TELEGRAM_CHAT_ID, "value": cls.TELEGRAM_CHAT_ID},
            "telegram_channels": {"set": bool(cls.TELEGRAM_CHANNELS), "value": cls.TELEGRAM_CHANNELS},
        }

    @classmethod
    def get_kst_time(cls):
        from datetime import datetime, timezone, timedelta
        kst = timezone(timedelta(hours=9))
        return datetime.now(kst)


config = Config()
config.setup_directories()
