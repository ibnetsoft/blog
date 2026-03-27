import httpx
import os
from typing import Dict, Any, Optional

class TelegramService:
    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token
        self.chat_id = chat_id

    async def send_message(self, text: str, token: str = None, chat_id: str = None) -> Dict[str, Any]:
        """텔레그램 채팅방으로 메시지 전송"""
        t = token or self.token
        c = chat_id or self.chat_id
        
        if not t or not c:
            # DB가 아닌 환경변수 등에서 로드 시도 가능 (추후 확장)
            from database import get_global_setting
            t = t or get_global_setting("telegram_token", "")
            c = c or get_global_setting("telegram_chat_id", "")

        if not t or not c:
            return {"status": "error", "error": "텔레그램 설정(Token, Chat ID)이 되어있지 않습니다. 설정 페이지에서 입력해주세요."}

        url = f"https://api.telegram.org/bot{t}/sendMessage"
        payload = {
            "chat_id": c,
            "text": text,
            "parse_mode": "HTML"
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                res = await client.post(url, data=payload)
                if res.status_code == 200:
                    return {"status": "ok", "data": res.json()}
                else:
                    return {"status": "error", "error": f"Telegram API Error ({res.status_code}): {res.text}"}
            except Exception as e:
                return {"status": "error", "error": str(e)}

    async def send_photo(self, photo_url: str, caption: str = "", token: str = None, chat_id: str = None) -> Dict[str, Any]:
        """이미지와 함께 메시지 전송"""
        t = token or self.token
        c = chat_id or self.chat_id

        if not t or not c:
            from database import get_global_setting
            t = t or get_global_setting("telegram_token", "")
            c = c or get_global_setting("telegram_chat_id", "")

        if not t or not c:
            return {"status": "error", "error": "텔레그램 설정(Token, Chat ID)이 되어있지 않습니다."}

        # Telegram은 로컬 파일을 직접 보낼 수도 있지만, 여기서는 URL(공개된 이미지) 기반 전송 권장
        url = f"https://api.telegram.org/bot{t}/sendPhoto"
        payload = {
            "chat_id": c,
            "photo": photo_url,
            "caption": caption,
            "parse_mode": "HTML"
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                res = await client.post(url, data=payload)
                if res.status_code == 200:
                    return {"status": "ok", "data": res.json()}
                else:
                    # 사진 전송 실패 시 텍스트라도 보냄
                    print(f"[Telegram] Photo send failed, trying text only: {res.text}")
                    return await self.send_message(f"{caption}\n\n(이미지 전송 실패)", t, c)
            except Exception as e:
                return {"status": "error", "error": str(e)}

telegram_service = TelegramService()
