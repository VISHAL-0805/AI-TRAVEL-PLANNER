import uuid
import asyncio
import logging
from datetime import datetime

from fastapi import FastAPI, HTTPException
from app.models import (
    TravelRequest,
    ReviewRequest,
    ReviewAction,
    PlanResponse,
    PlanStatusResponse,
    FinalPlanResponse,
    PlanStatus,
)
from app.core.state import plan_store
from app.core.graph import start_workflow, resume_workflow

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="AI Travel Planner",
    description="Multi-agent travel planning system with human-in-the-loop approval",
    version="1.0.0",
)


@app.get("/")
async def root():
    return {"service": "AI Travel Planner", "version": "1.0.0", "docs": "/docs"}


@app.post("/plan", response_model=PlanResponse)
async def create_plan(request: TravelRequest):
    start = datetime.strptime(request.start_date, "%Y-%m-%d")
    end = datetime.strptime(request.end_date, "%Y-%m-%d")
    if end <= start:
        raise HTTPException(status_code=400, detail="end_date must be after start_date")

    if request.budget_max < request.budget_min:
        raise HTTPException(status_code=400, detail="budget_max must be >= budget_min")

    plan_id = str(uuid.uuid4())
    request_data = request.model_dump()
    plan_store.create(plan_id, request_data)

    asyncio.create_task(_run_workflow(plan_id, request_data))

    return PlanResponse(
        plan_id=plan_id,
        status=PlanStatus.RESEARCHING,
        message="Travel plan created. Research is starting. Poll GET /plan/{id} for status.",
    )


async def _run_workflow(plan_id: str, request_data: dict):
    try:
        logger.info(f"Starting workflow for plan {plan_id}")
        await start_workflow(plan_id, request_data)
        logger.info(f"Workflow completed for plan {plan_id}")
    except Exception as e:
        logger.error(f"Workflow failed for plan {plan_id}: {e}")
        plan_store.update(plan_id, status=PlanStatus.FAILED, error=str(e))


@app.get("/plan/{plan_id}", response_model=PlanStatusResponse)
async def get_plan_status(plan_id: str):
    plan = plan_store.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    return PlanStatusResponse(
        plan_id=plan_id,
        status=plan["status"],
        request=plan["request"],
        draft_plan=plan.get("draft_plan"),
        research_data=plan.get("research_data"),
        message=_status_message(plan["status"], plan.get("error")),
    )


@app.post("/plan/{plan_id}/review", response_model=PlanResponse)
async def submit_review(plan_id: str, review: ReviewRequest):
    plan = plan_store.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    if plan["status"] != PlanStatus.AWAITING_REVIEW:
        raise HTTPException(
            status_code=409,
            detail=f"Plan is in '{plan['status']}' state, not ready for review",
        )

    if review.action in (ReviewAction.REJECT, ReviewAction.MODIFY) and not review.feedback:
        raise HTTPException(
            status_code=400,
            detail="Feedback is required when rejecting or modifying a plan",
        )

    review_data = {
        "action": review.action,
        "feedback": review.feedback,
        "modifications": review.modifications,
    }
    plan_store.update(plan_id, review_feedback=review_data)

    asyncio.create_task(_resume_workflow(plan_id, review_data))

    if review.action == ReviewAction.APPROVE:
        msg = "Plan approved. Finalizing..."
    elif review.action == ReviewAction.REJECT:
        msg = "Plan rejected. Re-researching with your feedback..."
    else:
        msg = "Plan modification requested. Revising..."

    return PlanResponse(
        plan_id=plan_id,
        status=PlanStatus.REVISING if review.action != ReviewAction.APPROVE else PlanStatus.APPROVED,
        message=msg,
    )


async def _resume_workflow(plan_id: str, review_data: dict):
    try:
        logger.info(f"Resuming workflow for plan {plan_id}")
        await resume_workflow(plan_id, review_data)
        logger.info(f"Workflow resumed and completed for plan {plan_id}")
    except Exception as e:
        logger.error(f"Resume failed for plan {plan_id}: {e}")
        plan_store.update(plan_id, status=PlanStatus.FAILED, error=str(e))


@app.get("/plan/{plan_id}/final", response_model=FinalPlanResponse)
async def get_final_plan(plan_id: str):
    plan = plan_store.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    if plan["status"] != PlanStatus.APPROVED:
        raise HTTPException(
            status_code=409,
            detail=f"Plan is not finalized yet. Current status: {plan['status']}",
        )

    if not plan.get("final_plan"):
        raise HTTPException(status_code=409, detail="Final plan is still being generated")

    return FinalPlanResponse(
        plan_id=plan_id,
        final_plan=plan["final_plan"],
        request=plan["request"],
    )


def _status_message(status: PlanStatus, error: str | None = None) -> str:
    messages = {
        PlanStatus.RESEARCHING: "Researching your destination...",
        PlanStatus.PLANNING: "Building your itinerary...",
        PlanStatus.AWAITING_REVIEW: "Draft plan ready. Submit your review at POST /plan/{id}/review",
        PlanStatus.REVISING: "Revising the plan based on your feedback...",
        PlanStatus.APPROVED: "Plan finalized. Retrieve it at GET /plan/{id}/final",
        PlanStatus.FAILED: f"Something went wrong: {error or 'unknown error'}",
    }
    return messages.get(status, "Unknown status")
