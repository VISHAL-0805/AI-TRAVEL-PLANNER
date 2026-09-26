import asyncio
import uuid
from typing import TypedDict, Optional, Annotated

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

from app.agents.research import run_research
from app.agents.planner import run_planner
from app.models import PlanStatus, ReviewAction
from app.core.state import plan_store


class TravelState(TypedDict):
    plan_id: str
    request: dict
    research_data: Optional[dict]
    draft_plan: Optional[dict]
    review_action: Optional[str]
    review_feedback: Optional[str]
    review_modifications: Optional[dict]
    final_plan: Optional[dict]
    error: Optional[str]


async def research_node(state: TravelState) -> dict:
    plan_store.update(state["plan_id"], status=PlanStatus.RESEARCHING)
    try:
        research = await run_research(state["request"])
        plan_store.update(state["plan_id"], research_data=research)
        return {"research_data": research}
    except Exception as e:
        plan_store.update(state["plan_id"], status=PlanStatus.FAILED, error=str(e))
        return {"error": str(e)}


async def planning_node(state: TravelState) -> dict:
    plan_store.update(state["plan_id"], status=PlanStatus.PLANNING)
    try:
        plan = await run_planner(state["request"], state.get("research_data") or {})
        plan_store.update(state["plan_id"], draft_plan=plan, status=PlanStatus.AWAITING_REVIEW)
        return {"draft_plan": plan}
    except Exception as e:
        plan_store.update(state["plan_id"], status=PlanStatus.FAILED, error=str(e))
        return {"error": str(e)}


async def human_review_node(state: TravelState) -> dict:
    plan_store.update(state["plan_id"], status=PlanStatus.AWAITING_REVIEW)
    review = interrupt({
        "message": "Plan ready for review",
        "plan_id": state["plan_id"],
        "draft_plan": state.get("draft_plan"),
    })
    return {
        "review_action": review.get("action"),
        "review_feedback": review.get("feedback"),
        "review_modifications": review.get("modifications"),
    }


async def finalize_node(state: TravelState) -> dict:
    final = dict(state.get("draft_plan") or {})
    final["status"] = "approved"
    final["plan_id"] = state["plan_id"]
    plan_store.update(
        state["plan_id"],
        final_plan=final,
        status=PlanStatus.APPROVED,
    )
    return {"final_plan": final}


def route_after_review(state: TravelState) -> str:
    action = state.get("review_action", "")
    if action == ReviewAction.APPROVE:
        return "finalize"
    elif action == ReviewAction.REJECT:
        return "research"
    elif action == ReviewAction.MODIFY:
        return "planning"
    return "finalize"


def route_after_research(state: TravelState) -> str:
    if state.get("error"):
        return END
    return "planning"


def route_after_planning(state: TravelState) -> str:
    if state.get("error"):
        return END
    return "human_review"


def build_graph() -> StateGraph:
    builder = StateGraph(TravelState)

    builder.add_node("research", research_node)
    builder.add_node("planning", planning_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("finalize", finalize_node)

    builder.add_edge(START, "research")
    builder.add_conditional_edges("research", route_after_research, ["planning", END])
    builder.add_conditional_edges("planning", route_after_planning, ["human_review", END])
    builder.add_conditional_edges(
        "human_review",
        route_after_review,
        ["finalize", "research", "planning"],
    )
    builder.add_edge("finalize", END)

    return builder


checkpointer = MemorySaver()
graph = build_graph().compile(checkpointer=checkpointer)


async def start_workflow(plan_id: str, request_data: dict):
    config = {"configurable": {"thread_id": plan_id}}
    initial_state = {
        "plan_id": plan_id,
        "request": request_data,
        "research_data": None,
        "draft_plan": None,
        "review_action": None,
        "review_feedback": None,
        "review_modifications": None,
        "final_plan": None,
        "error": None,
    }
    try:
        await graph.ainvoke(initial_state, config=config)
    except Exception as e:
        plan_store.update(plan_id, status=PlanStatus.FAILED, error=str(e))


async def resume_workflow(plan_id: str, review_data: dict):
    config = {"configurable": {"thread_id": plan_id}}

    if review_data.get("action") == ReviewAction.REJECT:
        plan_store.update(plan_id, status=PlanStatus.REVISING)
    elif review_data.get("action") == ReviewAction.MODIFY:
        plan_store.update(plan_id, status=PlanStatus.REVISING)

    try:
        await graph.ainvoke(Command(resume=review_data), config=config)
    except Exception as e:
        plan_store.update(plan_id, status=PlanStatus.FAILED, error=str(e))
