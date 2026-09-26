import threading
from typing import Optional
from app.models import PlanStatus


class PlanStore:
    """Thread-safe in-memory store for plan state.
    In production this would be backed by a database."""

    def __init__(self):
        self._plans: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(self, plan_id: str, request_data: dict) -> dict:
        plan = {
            "plan_id": plan_id,
            "status": PlanStatus.RESEARCHING,
            "request": request_data,
            "research_data": None,
            "draft_plan": None,
            "final_plan": None,
            "review_feedback": None,
            "error": None,
        }
        with self._lock:
            self._plans[plan_id] = plan
        return plan

    def get(self, plan_id: str) -> Optional[dict]:
        with self._lock:
            return self._plans.get(plan_id)

    def update(self, plan_id: str, **kwargs) -> Optional[dict]:
        with self._lock:
            plan = self._plans.get(plan_id)
            if plan:
                plan.update(kwargs)
            return plan

    def exists(self, plan_id: str) -> bool:
        with self._lock:
            return plan_id in self._plans


plan_store = PlanStore()
