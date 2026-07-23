"""
블로그 자동화 앱 설정
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # AI
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    AI_TEXT_PROVIDER = os.getenv("AI_TEXT_PROVIDER", "gemini")
    AI_TEXT_MODEL = os.getenv("AI_TEXT_MODEL", os.getenv("GEMINI_TEXT_MODEL", "gemini-3.5-flash"))
    GEMINI_TEXT_FALLBACK_MODELS = os.getenv(
        "GEMINI_TEXT_FALLBACK_MODELS",
        "gemini-3.1-pro-preview,gemini-3-flash-preview,gemini-3.1-flash-lite,gemini-2.5-flash"
    )
    AI_TEXT_MODEL_OPTIONS = {
        "openai": [
            {"id": "gpt-5.5", "label": "GPT-5.5"},
            {"id": "gpt-5.4", "label": "GPT-5.4"},
            {"id": "gpt-5.4-mini", "label": "GPT-5.4 Mini"},
        ],
        "anthropic": [
            {"id": "claude-fable-5", "label": "Claude Fable 5"},
            {"id": "claude-opus-4-8", "label": "Claude Opus 4.8"},
            {"id": "claude-sonnet-4-6", "label": "Claude Sonnet 4.6"},
        ],
        "gemini": [
            {"id": "gemini-3.5-flash", "label": "Gemini 3.5 Flash"},
            {"id": "gemini-3.1-pro-preview", "label": "Gemini 3.1 Pro Preview"},
            {"id": "gemini-3-flash-preview", "label": "Gemini 3 Flash Preview"},
        ],
    }

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

    # Social publish
    FACEBOOK_PAGE_ID: str = os.getenv("FACEBOOK_PAGE_ID", "")
    FACEBOOK_ACCESS_TOKEN: str = os.getenv("FACEBOOK_ACCESS_TOKEN", "")
    INSTAGRAM_ACCOUNT_ID: str = os.getenv("INSTAGRAM_ACCOUNT_ID", "")
    INSTAGRAM_ACCESS_TOKEN: str = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    TIKTOK_ACCESS_TOKEN: str = os.getenv("TIKTOK_ACCESS_TOKEN", "")

    # 서버 설정
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "8000"))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"

    # API URLs
    GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent"

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
            'GEMINI_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY',
            'AI_TEXT_PROVIDER', 'AI_TEXT_MODEL', 'GEMINI_TEXT_FALLBACK_MODELS',
            'BLOG_CLIENT_ID', 'BLOG_CLIENT_SECRET', 'BLOG_ID',
            'WP_URL', 'WP_USERNAME', 'WP_PASSWORD',
            'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID', 'TELEGRAM_CHANNELS',
            'FACEBOOK_PAGE_ID', 'FACEBOOK_ACCESS_TOKEN',
            'INSTAGRAM_ACCOUNT_ID', 'INSTAGRAM_ACCESS_TOKEN',
            'TIKTOK_ACCESS_TOKEN'
        ]
        if key_name not in valid_keys:
            return False
        setattr(cls, key_name, value)
        os.environ[key_name] = value
        env_path = os.path.join(cls.BASE_DIR, '.env')
        temp_path = env_path + '.tmp'
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
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.writelines(env_lines)
        os.replace(temp_path, env_path)
        return True

    @staticmethod
    def mask_key(key: str) -> str:
        if not key:
            return ""
        key = str(key).strip()
        if not key:
            return ""

        if key.startswith("sk-ant-"):
            return "sk-ant-" + ("*" * 32)
        if key.startswith("sk-"):
            return "sk-" + ("*" * 32)
        if key.startswith("AIza"):
            return "AIza" + ("*" * 28)

        prefix = key[:4] if len(key) >= 4 else key[:1]
        return prefix + ("*" * 32)

    @classmethod
    def get_api_keys_status(cls):
        def public_secret(value: str):
            return {"set": bool(value), "masked": cls.mask_key(value), "value": ""}

        def public_value(value: str):
            return {"set": bool(value), "masked": value, "value": value}

        try:
            import database as db
            auto_settings = {
                "auto_post_enabled": db.get_global_setting("auto_post_enabled", "false"),
                "auto_post_time": db.get_global_setting("auto_post_time", "09:00"),
                "auto_post_category": db.get_global_setting("auto_post_category", "IT, Tech, Trends"),
                "auto_post_no_human": db.get_global_setting("auto_post_no_human", "true"),
                "auto_post_platforms": db.get_global_setting(
                    "auto_post_platforms",
                    '[{"language": "ko", "platform": "wordpress", "target_id": "wordpress"}]'
                ),
                "auto_open_published_posts": db.get_global_setting("auto_open_published_posts", "true"),
                "ai_quality_enabled": db.get_global_setting("ai_quality_enabled", "true"),
                "ai_quality_min_score": db.get_global_setting("ai_quality_min_score", "82"),
            }
        except Exception:
            auto_settings = {}

        status = {
            "gemini": public_secret(cls.GEMINI_API_KEY),
            "openai": public_secret(cls.OPENAI_API_KEY),
            "anthropic": public_secret(cls.ANTHROPIC_API_KEY),
            "ai_text_provider": public_value(cls.AI_TEXT_PROVIDER),
            "ai_text_model": public_value(cls.AI_TEXT_MODEL),
            "ai_text_model_options": {"set": True, "value": cls.AI_TEXT_MODEL_OPTIONS},
            "blog_client_id": public_value(cls.BLOG_CLIENT_ID),
            "blog_client_secret": public_secret(cls.BLOG_CLIENT_SECRET),
            "blog_id": public_value(cls.BLOG_ID),
            "wp_url": public_value(cls.WP_URL),
            "wp_username": public_value(cls.WP_USERNAME),
            "wp_password": public_secret(cls.WP_PASSWORD),
            "telegram_token": public_secret(cls.TELEGRAM_TOKEN),
            "telegram_chat_id": public_value(cls.TELEGRAM_CHAT_ID),
            "telegram_channels": {"set": bool(cls.TELEGRAM_CHANNELS), "value": cls.TELEGRAM_CHANNELS},
            "facebook_page_id": public_value(cls.FACEBOOK_PAGE_ID),
            "facebook_access_token": public_secret(cls.FACEBOOK_ACCESS_TOKEN),
            "instagram_account_id": public_value(cls.INSTAGRAM_ACCOUNT_ID),
            "instagram_access_token": public_secret(cls.INSTAGRAM_ACCESS_TOKEN),
            "tiktok_access_token": public_secret(cls.TIKTOK_ACCESS_TOKEN),
        }
        for key, value in auto_settings.items():
            status[key] = {"set": value not in (None, ""), "value": value}
        return status

    @classmethod
    def get_kst_time(cls):
        from datetime import datetime, timezone, timedelta
        kst = timezone(timedelta(hours=9))
        return datetime.now(kst)


config = Config()
config.setup_directories()
