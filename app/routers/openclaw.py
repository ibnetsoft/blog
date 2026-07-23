from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import database as db
from services.openclaw_service import openclaw_service


router = APIRouter(prefix="/api/openclaw", tags=["OpenClaw"])


class CampaignCreateRequest(BaseModel):
    name: str
    category: str = "IT"
    default_language: str = "ko"
    ai_provider: str = "gemini"
    ai_model: str = "gemini-3.5-flash"
    platforms: List[Dict[str, Any]]
    schedule_type: str = "daily"
    schedule_time: str = "09:00"
    timezone: str = "Asia/Seoul"
    topic_mode: str = "trend"
    approval_mode: str = "auto"
    quality_min_score: int = 82
    image_policy: Optional[Dict[str, Any]] = None
    prompt_profile: Optional[Dict[str, Any]] = None
    is_active: int = 1


class CampaignUpdateRequest(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    default_language: Optional[str] = None
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    platforms: Optional[List[Dict[str, Any]]] = None
    schedule_type: Optional[str] = None
    schedule_time: Optional[str] = None
    timezone: Optional[str] = None
    topic_mode: Optional[str] = None
    approval_mode: Optional[str] = None
    quality_min_score: Optional[int] = None
    image_policy: Optional[Dict[str, Any]] = None
    prompt_profile: Optional[Dict[str, Any]] = None
    is_active: Optional[int] = None


class ApprovalActionRequest(BaseModel):
    reviewer: str = "user"
    note: str = ""


@router.get("/campaigns")
async def list_campaigns(active_only: bool = False):
    campaigns = db.get_openclaw_campaigns(active_only=active_only)
    return {"status": "ok", "campaigns": campaigns}


@router.post("/campaigns")
async def create_campaign(req: CampaignCreateRequest):
    if not req.platforms:
        return {"status": "error", "error": "at least one target platform is required"}

    campaign_id = db.create_openclaw_campaign(
        name=req.name,
        category=req.category,
        default_language=req.default_language,
        ai_provider=req.ai_provider,
        ai_model=req.ai_model,
        platforms_json=req.platforms,
        schedule_type=req.schedule_type,
        schedule_time=req.schedule_time,
        timezone=req.timezone,
        topic_mode=req.topic_mode,
        approval_mode=req.approval_mode,
        quality_min_score=req.quality_min_score,
        image_policy_json=req.image_policy or {},
        prompt_profile_json=req.prompt_profile or {},
        is_active=req.is_active,
    )
    return {"status": "ok", "campaign_id": campaign_id, "campaign": db.get_openclaw_campaign(campaign_id)}


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: int):
    campaign = db.get_openclaw_campaign(campaign_id)
    if not campaign:
        raise HTTPException(404, "campaign not found")
    return {"status": "ok", "campaign": campaign}


@router.put("/campaigns/{campaign_id}")
async def update_campaign(campaign_id: int, req: CampaignUpdateRequest):
    campaign = db.get_openclaw_campaign(campaign_id)
    if not campaign:
        raise HTTPException(404, "campaign not found")

    updates = {}
    for key, value in req.dict().items():
        if value is None:
            continue
        if key == "platforms":
            updates["platforms_json"] = value
        elif key == "image_policy":
            updates["image_policy_json"] = value
        elif key == "prompt_profile":
            updates["prompt_profile_json"] = value
        else:
            updates[key] = value

    if updates:
        db.update_openclaw_campaign(campaign_id, **updates)
    return {"status": "ok", "campaign": db.get_openclaw_campaign(campaign_id)}


@router.post("/campaigns/{campaign_id}/toggle")
async def toggle_campaign(campaign_id: int):
    campaign = db.get_openclaw_campaign(campaign_id)
    if not campaign:
        raise HTTPException(404, "campaign not found")
    next_state = 0 if int(campaign.get("is_active", 1)) else 1
    db.update_openclaw_campaign(campaign_id, is_active=next_state, status="active" if next_state else "paused")
    return {"status": "ok", "campaign": db.get_openclaw_campaign(campaign_id)}


@router.post("/campaigns/{campaign_id}/run")
async def run_campaign(campaign_id: int):
    result = await openclaw_service.run_campaign(campaign_id)
    return result


@router.get("/runs")
async def list_runs(limit: int = 50, campaign_id: Optional[int] = None):
    runs = db.get_openclaw_runs(limit=limit, campaign_id=campaign_id)
    return {"status": "ok", "runs": runs}


@router.get("/runs/{run_id}")
async def get_run(run_id: int):
    run = db.get_openclaw_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")
    tasks = db.get_openclaw_tasks(run_id)
    variants = db.get_content_variants(run_id)
    approvals = [item for item in db.get_approval_queue_items() if item["run_id"] == run_id]
    return {
        "status": "ok",
        "run": run,
        "tasks": tasks,
        "variants": variants,
        "approvals": approvals,
    }


@router.post("/runs/{run_id}/retry")
async def retry_run(run_id: int):
    result = await openclaw_service.retry_run(run_id)
    return result


@router.post("/runs/retry-failed")
async def retry_failed_runs(limit: int = 10, campaign_id: Optional[int] = None):
    result = await openclaw_service.retry_failed_runs(limit=limit, campaign_id=campaign_id)
    return result


@router.get("/approvals")
async def list_approvals(status: Optional[str] = None):
    approvals = db.get_approval_queue_items(status=status)
    return {"status": "ok", "approvals": approvals}


@router.get("/dashboard/summary")
async def dashboard_summary():
    campaigns = db.get_openclaw_campaigns()
    runs = db.get_openclaw_runs(limit=20)
    pending_approvals = db.get_approval_queue_items(status="pending")
    latest_run = runs[0] if runs else None

    summary = {
        "campaign_count": len(campaigns),
        "active_campaign_count": len([c for c in campaigns if int(c.get("is_active", 1)) == 1]),
        "run_count": len(runs),
        "completed_count": len([r for r in runs if r.get("status") == "completed"]),
        "partial_count": len([r for r in runs if r.get("status") == "partial"]),
        "failed_count": len([r for r in runs if r.get("status") == "failed"]),
        "waiting_approval_count": len([r for r in runs if r.get("status") == "waiting_approval"]),
        "pending_approval_count": len(pending_approvals),
        "actionable_count": len([r for r in runs if r.get("status") in ("failed", "partial")]) + len(pending_approvals),
        "latest_run_at": latest_run.get("created_at") if latest_run else "",
        "latest_run_status": latest_run.get("status") if latest_run else "",
        "recent_runs": runs[:10],
    }
    return {"status": "ok", "summary": summary}


@router.post("/approvals/{approval_id}/approve")
async def approve_item(approval_id: int, req: ApprovalActionRequest):
    result = await openclaw_service.approve_run_item(approval_id, reviewer=req.reviewer, note=req.note)
    return result


@router.post("/approvals/{approval_id}/reject")
async def reject_item(approval_id: int, req: ApprovalActionRequest):
    result = openclaw_service.reject_run_item(approval_id, reviewer=req.reviewer, note=req.note)
    return result
