import asyncio
import json
import traceback
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from config import config
import database as db
from services.blog_service import blog_service
from services.gemini_service import gemini_service
from services.openclaw_service import openclaw_service
from services.publish_workflow_service import BlogPostRequest, publish_workflow_service


class SchedulerService:
    def __init__(self):
        self.is_running = False
        self.task = None
        self._running_campaigns = set()  # 현재 실행 중인 캠페인 ID 추적

    @staticmethod
    def _time_to_minutes(value: str) -> int:
        try:
            hour, minute = str(value).strip().split(":", 1)
            return int(hour) * 60 + int(minute)
        except Exception:
            return -1

    @staticmethod
    def _utc_to_kst_date(utc_str: str) -> str:
        if not utc_str:
            return ""
        try:
            dt_utc = datetime.strptime(utc_str.split(".")[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            kst_tz = timezone(timedelta(hours=9))
            dt_kst = dt_utc.astimezone(kst_tz)
            return dt_kst.strftime("%Y-%m-%d")
        except Exception:
            return utc_str[:10]

    @staticmethod
    def _resolve_timezone(name: str):
        tz_name = str(name or "Asia/Seoul").strip() or "Asia/Seoul"
        try:
            return ZoneInfo(tz_name)
        except Exception:
            return timezone(timedelta(hours=9))

    @staticmethod
    def _timestamp_to_date(value: str, tzinfo) -> str:
        if not value:
            return ""
        raw = str(value).strip()
        try:
            if "T" in raw:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            else:
                dt = datetime.strptime(raw.split(".")[0], "%Y-%m-%d %H:%M:%S")
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(tzinfo).strftime("%Y-%m-%d")
        except Exception:
            return raw[:10]

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.task = asyncio.create_task(self._scheduler_loop())
        print("[Scheduler] Background loop started")

    async def stop(self):
        self.is_running = False
        if self.task:
            self.task.cancel()
            print("[Scheduler] Background loop stopped")

    async def _scheduler_loop(self):
        while self.is_running:
            try:
                await self._run_openclaw_campaigns_if_due()
                await self._run_legacy_autopost_if_due()
            except Exception as e:
                print(f"[Scheduler] Loop error: {e}")
                traceback.print_exc()
            await asyncio.sleep(60)

    async def _run_openclaw_campaigns_if_due(self):
        campaigns = db.get_openclaw_campaigns(active_only=True)
        if not campaigns:
            return

        for campaign in campaigns:
            try:
                campaign_id = campaign["id"]

                # [보호 1] 메모리에서 이미 실행 중인 캠페인이면 스킵
                if campaign_id in self._running_campaigns:
                    continue

                # [보호 2] DB에 running/waiting_approval 상태의 run이 있으면 스킵
                active_runs = db.get_openclaw_runs(limit=1, campaign_id=campaign_id)
                _skip = False
                for r in active_runs:
                    if r.get("status") in ("running", "waiting_approval", "queued"):
                        _skip = True
                        break
                if _skip:
                    continue

                if (campaign.get("schedule_type") or "daily") != "daily":
                    continue

                campaign_tz = self._resolve_timezone(campaign.get("timezone"))
                campaign_now = datetime.now(campaign_tz)
                current_time_str = campaign_now.strftime("%H:%M")
                current_minutes = self._time_to_minutes(current_time_str)
                today_str = campaign_now.strftime("%Y-%m-%d")

                target_minutes = self._time_to_minutes(campaign.get("schedule_time") or "09:00")
                if target_minutes < 0 or current_minutes < target_minutes:
                    continue

                # [보호 3] 오늘 이미 실행된 run이 있으면 스킵 (completed_at 우선, 없으면 started_at)
                latest_run = db.get_latest_openclaw_run_for_campaign(campaign_id)
                if latest_run:
                    latest_ts = (
                        latest_run.get("completed_at")
                        or latest_run.get("started_at")
                        or latest_run.get("created_at", "")
                    )
                    latest_day = self._timestamp_to_date(latest_ts, campaign_tz)
                    if latest_day == today_str:
                        continue

                # 모든 보호 통과 → 실행
                self._running_campaigns.add(campaign_id)
                print(f"[Scheduler] OpenClaw due: id={campaign_id} name={campaign.get('name')}")
                await self._run_and_cleanup(campaign_id)
            except Exception as campaign_err:
                self._running_campaigns.discard(campaign["id"])
                print(f"[Scheduler] OpenClaw campaign error ({campaign.get('id')}): {campaign_err}")
                traceback.print_exc()

    async def _run_and_cleanup(self, campaign_id: int):
        """캠페인 실행 후 메모리에서 제거하는 래퍼"""
        try:
            await openclaw_service.run_campaign(campaign_id)
        finally:
            self._running_campaigns.discard(campaign_id)

    async def _run_legacy_autopost_if_due(self):
        enabled = db.get_global_setting("auto_post_enabled") == "true"
        if not enabled:
            return

        target_time = db.get_global_setting("auto_post_time") or "09:00"
        now = config.get_kst_time()
        current_time_str = now.strftime("%H:%M")
        current_minutes = self._time_to_minutes(current_time_str)
        target_minutes = self._time_to_minutes(target_time)
        today_str = now.strftime("%Y-%m-%d")
        last_run = db.get_global_setting("auto_post_last_run")

        if target_minutes >= 0 and current_minutes >= target_minutes and last_run != today_str:
            print(f"[Scheduler] Legacy auto-post due at {current_time_str}")
            asyncio.create_task(self._execute_auto_post())

    async def _execute_auto_post(self):
        try:
            print("[AutoPost] Starting legacy daily execution")
            category = db.get_global_setting("auto_post_category") or "FX 외환거래"

            print(f"[AutoPost] Fetching topic for category: {category}")
            provider = db.get_global_setting("ai_text_provider") or "gemini"
            model = db.get_global_setting("ai_text_model") or ""
            trends = await gemini_service.generate_general_blog_trends(category, provider_override=provider, model_override=model)
            if not trends:
                raise Exception("Failed to fetch trending topic.")

            topic = trends[0].get("title", "")
            print(f"[AutoPost] Selected topic: {topic}")

            platforms_json = db.get_global_setting("auto_post_platforms")
            if not platforms_json:
                print("[AutoPost] No platforms configured. Skipping execution.")
                return

            try:
                platforms = json.loads(platforms_json) if isinstance(platforms_json, str) else platforms_json
            except Exception:
                print("[AutoPost] Invalid auto_post_platforms JSON. Falling back to WordPress only.")
                platforms = [{"language": "ko", "platform": "wordpress", "target_id": "wordpress"}]
            if not platforms:
                print("[AutoPost] Target platform list is empty.")
                return

            print(f"[AutoPost] Generating localized blogs for {len(platforms)} platforms")
            res_multi = await blog_service.generate_independent_multi_language_blogs(
                topic=topic,
                platforms=platforms,
                source_content="",
            )
            if res_multi.get("status") != "ok":
                raise Exception(f"Failed to generate blogs: {res_multi.get('error')}")

            results = res_multi.get("results", [])
            req_contents = {}
            req_metadata = {}
            platform_langs = {}
            post_platforms = []
            social_assets = {}
            no_human = db.get_global_setting("auto_post_no_human") != "false"

            for item in results:
                if item.get("status") != "ok":
                    continue

                lang_content = item.get("content", "")
                target_id = item.get("target_id")
                lang = item.get("language", "ko")
                if not lang_content:
                    continue

                try:
                    img_res = await blog_service.add_images_to_content(
                        content=lang_content,
                        project_id=None,
                        image_count=2,
                        no_human=no_human,
                    )
                    req_contents[target_id] = img_res.get("content") if img_res.get("status") == "ok" and img_res.get("content") else lang_content
                except Exception as img_err:
                    print(f"[AutoPost] Image generation error for {target_id}: {img_err}")
                    req_contents[target_id] = lang_content

                req_metadata[target_id] = {
                    "title": item.get("title", ""),
                    "tags": item.get("tags", []),
                    "category": category,
                    "summary": item.get("summary", ""),
                }
                if item.get("platform") in ["facebook", "instagram", "tiktok", "telegram"]:
                    social_assets[target_id] = {
                        "caption": "\n\n".join(filter(None, [item.get("title", ""), item.get("summary", "")])),
                        "image_urls": [],
                        "video_urls": [],
                    }
                platform_langs[target_id] = lang
                post_platforms.append(target_id)

            if not req_contents:
                raise Exception("No generated content succeeded.")

            primary_target = "wordpress" if "wordpress" in req_contents else list(req_contents.keys())[0]
            primary_content = req_contents[primary_target]
            primary_meta = req_metadata[primary_target]

            post_req = BlogPostRequest(
                title=primary_meta["title"],
                content=primary_content,
                tags=primary_meta["tags"],
                categories=[category],
                summary=primary_meta["summary"],
                platforms=post_platforms,
                platform_langs=platform_langs,
                contents=req_contents,
                metadata=req_metadata,
                social_assets=social_assets,
            )

            post_res = await publish_workflow_service.publish_blog_post(post_req)
            results_map = post_res.get("results", {}) or {}
            ok_platforms = [name for name, res in results_map.items() if isinstance(res, dict) and res.get("status") == "ok"]
            failed_platforms = [name for name, res in results_map.items() if isinstance(res, dict) and res.get("status") != "ok"]
            retryable_platforms = [
                name for name, res in results_map.items()
                if isinstance(res, dict) and res.get("status") != "ok" and res.get("retryable")
            ]
            summary_payload = {
                "topic": topic,
                "status": post_res.get("status"),
                "success_count": len(ok_platforms),
                "failed_count": len(failed_platforms),
                "success_platforms": ok_platforms,
                "failed_platforms": failed_platforms,
                "retryable_platforms": retryable_platforms,
                "results": results_map,
            }

            if post_res.get("status") in ["ok", "partial"]:
                db.save_global_setting("auto_post_last_run", datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d"))
                summary_text = f"Auto-posted: {topic} | success {len(ok_platforms)} / failed {len(failed_platforms)}"
                if failed_platforms:
                    summary_text += f" | failed platforms: {', '.join(failed_platforms)}"
                self._log_job("SUCCESS" if not failed_platforms else "PARTIAL", summary_text, json.dumps(summary_payload, ensure_ascii=False))
            else:
                summary_text = f"Publish error: {post_res.get('error') or 'unknown'}"
                if failed_platforms:
                    summary_text += f" | failed platforms: {', '.join(failed_platforms)}"
                self._log_job("FAILED", summary_text, json.dumps(summary_payload, ensure_ascii=False))
        except Exception as e:
            print(f"[AutoPost] Fatal error: {e}")
            traceback.print_exc()
            self._log_job("ERROR", str(e), "")

    def _log_job(self, status: str, message: str, payload: str):
        try:
            conn = db.get_db()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO job_logs (platform, account_name, title, status, message, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("AutoPost", "System", "Daily Auto Post", status, message, payload),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[AutoPost] Failed to write log: {e}")


scheduler_service = SchedulerService()
