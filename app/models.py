from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class PlanStatus(str, Enum):
    RESEARCHING = "researching"
    PLANNING = "planning"
    AWAITING_REVIEW = "awaiting_review"
    REVISING = "revising"
    APPROVED = "approved"
    FAILED = "failed"


class ReviewAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"


class TravelRequest(BaseModel):
    destination: str = Field(..., min_length=1, description="Travel destination city or country")
    start_date: str = Field(..., description="Trip start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="Trip end date (YYYY-MM-DD)")
    budget_min: float = Field(..., gt=0, description="Minimum budget in USD")
    budget_max: float = Field(..., gt=0, description="Maximum budget in USD")
    interests: list[str] = Field(default_factory=list, description="List of interests like hiking, food, museums")
    num_travelers: int = Field(default=1, ge=1, description="Number of travelers")


class ReviewRequest(BaseModel):
    action: ReviewAction
    feedback: Optional[str] = Field(None, description="Feedback for reject or modify actions")
    modifications: Optional[dict] = Field(None, description="Specific changes for modify action")


class PlanResponse(BaseModel):
    plan_id: str
    status: PlanStatus
    message: str


class PlanStatusResponse(BaseModel):
    plan_id: str
    status: PlanStatus
    request: Optional[dict] = None
    draft_plan: Optional[dict] = None
    research_data: Optional[dict] = None
    message: str


class FinalPlanResponse(BaseModel):
    plan_id: str
    final_plan: dict
    request: dict
