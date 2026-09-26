import json
from datetime import datetime

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from app.tools.budget import allocate_budget
from app.tools.activities import recommend_activities
from app.core.config import GROQ_API_KEY


PLANNER_SYSTEM_PROMPT = """You are a travel itinerary planner. Using the destination research provided,
create a detailed day-by-day travel itinerary.

Your itinerary should include for each day:
- Morning, afternoon, and evening activities
- Restaurant/food suggestions for each meal
- Estimated costs per activity
- Transportation notes between locations

Use the allocate_budget tool to plan spending and recommend_activities to find suitable activities.

IMPORTANT: Return ONLY valid JSON, no extra text. Keep descriptions short (under 20 words each).
Use this exact structure:
{{
    "trip_title": "...",
    "destination": "...",
    "dates": {{"start": "...", "end": "..."}},
    "total_budget": 0,
    "daily_itinerary": [
        {{
            "day": 1,
            "date": "...",
            "theme": "...",
            "morning": {{"activity": "...", "cost": 0, "duration": "2 hrs"}},
            "afternoon": {{"activity": "...", "cost": 0, "duration": "3 hrs"}},
            "evening": {{"activity": "...", "cost": 0, "duration": "2 hrs"}},
            "meals": {{"breakfast": "...", "lunch": "...", "dinner": "..."}},
            "daily_total": 0
        }}
    ],
    "accommodation": {{"type": "...", "area": "...", "nightly_rate": 0}},
    "packing_tips": ["..."],
    "important_notes": ["..."]
}}

Make the plan realistic and within budget. Prioritize the traveler's stated interests."""


def create_planner_agent():
    llm = ChatGroq(
        model="openai/gpt-oss-120b",
        api_key=GROQ_API_KEY,
        temperature=0.4,
    )
    tools = [allocate_budget, recommend_activities]
    return llm.bind_tools(tools), tools


async def run_planner(request_data: dict, research_data: dict) -> dict:
    llm_with_tools, tools = create_planner_agent()
    tool_map = {t.name: t for t in tools}

    start = datetime.strptime(request_data["start_date"], "%Y-%m-%d")
    end = datetime.strptime(request_data["end_date"], "%Y-%m-%d")
    num_days = max((end - start).days, 1)
    avg_budget = (request_data["budget_min"] + request_data["budget_max"]) / 2

    user_msg = (
        f"Create a {num_days}-day itinerary based on this research:\n\n"
        f"{research_data.get('summary', 'No research available.')}\n\n"
        f"Trip details:\n"
        f"- Destination: {request_data['destination']}\n"
        f"- Dates: {request_data['start_date']} to {request_data['end_date']} ({num_days} days)\n"
        f"- Budget: ${request_data['budget_min']} - ${request_data['budget_max']} "
        f"(use ${avg_budget} as target)\n"
        f"- Interests: {', '.join(request_data.get('interests', ['general']))}\n"
        f"- Travelers: {request_data.get('num_travelers', 1)}\n\n"
        f"First use allocate_budget to plan spending, then recommend_activities to find things to do. "
        f"Then build the full day-by-day itinerary."
    )

    messages = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ]

    for _ in range(6):
        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)

        if not response.tool_calls:
            break

        for tc in response.tool_calls:
            tool_fn = tool_map.get(tc["name"])
            if tool_fn:
                result = await tool_fn.ainvoke(tc["args"])
                messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

    final_content = messages[-1].content if messages else "{}"

    plan = _parse_plan_json(final_content)
    return plan


def _parse_plan_json(content: str) -> dict:
    start_idx = content.find("{")
    if start_idx == -1:
        return {"raw_plan": content}

    end_idx = content.rfind("}") + 1
    json_str = content[start_idx:end_idx] if end_idx > start_idx else content[start_idx:]

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # try fixing truncated JSON by closing open brackets
    fixed = json_str
    open_braces = fixed.count("{") - fixed.count("}")
    open_brackets = fixed.count("[") - fixed.count("]")
    fixed += "]" * open_brackets + "}" * open_braces

    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        return {"raw_plan": content}
