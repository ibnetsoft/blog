import os
import asyncio
import logging
from typing import List

import discord
from discord.ext import commands
from fastapi import FastAPI, HTTPException
import uvicorn
from pydantic import BaseModel
from dotenv import load_dotenv

from openclaw_tools.blog_tools import publish_approved_post, reject_post

# ---------------------------------------------------------
# 환경 변수 및 설정 (No Hardcoding)
# ---------------------------------------------------------
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", "D:\\Projects\\BLOG\\blog_app")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# FastAPI 설정 및 모델
# ---------------------------------------------------------
from main import app


class DraftPayload(BaseModel):
    title: str
    content: str
    tags: List[str]
    suggested_platform: str

# ---------------------------------------------------------
# 디스코드 UI 컴포넌트 (Human-in-the-Loop)
# ---------------------------------------------------------
class RejectModal(discord.ui.Modal, title='포스트 반려 사유 입력'):
    reason = discord.ui.TextInput(
        label='반려 사유를 입력하세요',
        style=discord.TextStyle.paragraph,
        placeholder='예: 제목이 너무 깁니다. 태그를 수정해주세요.',
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        # 디스코드 3초 타임아웃 방지를 위한 defer 호출
        await interaction.response.defer()
        
        # OpenClaw로 반려 상태 전달 (status.json 작성)
        reject_post(reason=self.reason.value, workspace_dir=WORKSPACE_DIR)
        
        await interaction.followup.send(
            f"✅ 포스트가 반려되었습니다. OpenClaw 에이전트에게 재작성을 요청했습니다.\n**사유:** {self.reason.value}",
            ephemeral=False
        )

class BlogApprovalView(discord.ui.View):
    def __init__(self, title: str, content: str, tags: List[str], platform: str):
        super().__init__(timeout=None) # 뷰 타임아웃 비활성화
        self.draft_title = title
        self.draft_content = content
        self.draft_tags = tags
        self.target_platform = platform

    @discord.ui.button(label="즉시 발행 (Approve)", style=discord.ButtonStyle.green, custom_id="btn_approve")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 디스코드 3초 타임아웃 방지를 위한 defer 호출
        await interaction.response.defer()
        
        try:
            # openclaw_tools.blog_tools를 통해 core 모듈 호출
            url = publish_approved_post(
                title=self.draft_title,
                content=self.draft_content,
                tags=self.draft_tags,
                target_platform=self.target_platform
            )
            
            # 발행 완료 후 모든 버튼 비활성화 처리
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)
            
            await interaction.followup.send(f"🎉 성공적으로 발행되었습니다!\n🔗 URL: {url}")
            
        except Exception as e:
            logger.error(f"발행 중 오류 발생: {e}")
            await interaction.followup.send(f"❌ 발행 중 오류가 발생했습니다: {e}", ephemeral=True)

    @discord.ui.button(label="반려 / 재작성 (Reject)", style=discord.ButtonStyle.danger, custom_id="btn_reject")
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Modal 팝업을 띄워 사용자로부터 상세 사유를 입력받음
        await interaction.response.send_modal(RejectModal())
        
        # 버튼을 비활성화하여 중복 반려를 방지
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

# ---------------------------------------------------------
# 디스코드 봇 설정
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    logger.info("Discord Bot is ready.")

# ---------------------------------------------------------
# FastAPI 엔드포인트 연동 (Webhook)
# ---------------------------------------------------------
@app.post("/v1/draft")
async def receive_draft(payload: DraftPayload):
    """
    OpenClaw 에이전트로부터 초안 데이터를 POST 방식으로 수신받아 
    디스코드 채널에 임베드(Embed) 형태로 전송합니다.
    """
    if not DISCORD_CHANNEL_ID:
        raise HTTPException(status_code=500, detail="DISCORD_CHANNEL_ID 환경 변수가 설정되지 않았습니다.")
        
    channel = bot.get_channel(int(DISCORD_CHANNEL_ID))
    if not channel:
        raise HTTPException(status_code=404, detail="디스코드 채널을 찾을 수 없거나 봇이 채널에 접근할 수 없습니다.")

    # Embed 메시지 구성
    embed = discord.Embed(
        title="📝 새로운 블로그 포스트 초안 도착",
        description=f"**제목:** {payload.title}\n\n**본문 미리보기:**\n{payload.content[:500]}...",
        color=discord.Color.blue()
    )
    embed.add_field(name="태그", value=", ".join(payload.tags), inline=False)
    embed.add_field(name="발행 플랫폼", value=payload.suggested_platform, inline=False)
    
    # 동적 UI View 컴포넌트 생성 (승인/반려 버튼 포함)
    view = BlogApprovalView(
        title=payload.title,
        content=payload.content,
        tags=payload.tags,
        platform=payload.suggested_platform
    )
    
    # 비동기 루프 안심 실행 (FastAPI 스레드 -> Discord asyncio 루프)
    asyncio.run_coroutine_threadsafe(
        channel.send(embed=embed, view=view),
        bot.loop
    )
    
    return {"status": "success", "message": "초안이 디스코드 채널로 성공적으로 전송되었습니다."}

# ---------------------------------------------------------
# 통합 실행자 (Uvicorn + Discord Bot)
# ---------------------------------------------------------
async def main():
    if not DISCORD_BOT_TOKEN:
        logger.warning("DISCORD_BOT_TOKEN 환경 변수가 설정되지 않았습니다. (테스트 환경에서는 무시할 수 있습니다.)")

    from config import config as app_config
    # FastAPI 서버를 비동기 태스크로 실행하기 위한 Uvicorn 설정
    uvicorn_config = uvicorn.Config(app=app, host=app_config.HOST, port=app_config.PORT, log_level="info")
    server = uvicorn.Server(uvicorn_config)
    
    # 디스코드 봇과 FastAPI 서버를 동시에 비동기 루프에 등록하여 병렬 실행
    if DISCORD_BOT_TOKEN:
        await asyncio.gather(
            bot.start(DISCORD_BOT_TOKEN),
            server.serve()
        )
    else:
        logger.info("Starting FastAPI server without Discord Bot due to missing Token.")
        await server.serve()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("System shutting down...")
