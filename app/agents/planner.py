import json
import logging
from datetime import datetime, timedelta

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from app.tools.budget import allocate_budget
from app.tools.activities import recommend_activities
from app.core.config import GROQ_API_KEY
from app.core.utils import get_currency_info, clean_plan_dict

logger = logging.getLogger(__name__)


PLANNER_SYSTEM_PROMPT_TEMPLATE = """You are a travel planner. Create a day-by-day itinerary as JSON.
Show costs in CURRENCY_PLACEHOLDER with USD equivalent. Use allocate_budget and recommend_activities tools first, then return JSON with: trip_title, destination, currency, dates, total_budget, daily_itinerary (each day has: day, date, theme, area, morning/afternoon/evening with activity+time+cost+duration+travel_from_previous, meals with breakfast/lunch/dinner suggestion+cost, daily_total), accommodation, packing_tips, important_notes. Return ONLY valid JSON."""


def create_planner_agent():
    llm = ChatGroq(
        model="openai/gpt-oss-120b",
        api_key=GROQ_API_KEY,
        temperature=0.4,
        max_tokens=2000,
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

    currency_code, exchange_rate, currency_symbol = get_currency_info(request_data["destination"])
    total_budget_local = f"{currency_symbol}{round(avg_budget * exchange_rate):,}"

    budget_str = f"{total_budget_local} (~${int(avg_budget)} USD)"
    prompt = PLANNER_SYSTEM_PROMPT_TEMPLATE.replace("CURRENCY_PLACEHOLDER", currency_code)

    research_summary = research_data.get('summary', 'No research available.')
    if len(research_summary) > 800:
        research_summary = research_summary[:800] + "..."

    user_msg = (
        f"Create a {num_days}-day itinerary for {request_data['destination']}.\n"
        f"Research: {research_summary}\n\n"
        f"Dates: {request_data['start_date']} to {request_data['end_date']}\n"
        f"Budget: {budget_str} (${request_data['budget_min']}-${request_data['budget_max']} USD)\n"
        f"Currency: {currency_code} (1 USD = {exchange_rate} {currency_code})\n"
        f"Interests: {', '.join(request_data.get('interests', ['general']))}\n"
        f"Travelers: {request_data.get('num_travelers', 1)}\n\n"
        f"Use allocate_budget and recommend_activities tools, then return the itinerary as JSON."
    )

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=user_msg),
    ]

    for _ in range(4):
        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)

        if not response.tool_calls:
            break

        for tc in response.tool_calls:
            tool_fn = tool_map.get(tc["name"])
            if tool_fn:
                try:
                    result = await tool_fn.ainvoke(tc["args"])
                    messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
                except Exception as e:
                    logger.warning(f"Tool {tc['name']} failed with args {tc['args']}: {e}")
                    messages.append(ToolMessage(content=f"Error: {e}", tool_call_id=tc["id"]))

    final_content = messages[-1].content if messages else ""

    if not final_content or len(final_content.strip()) < 50 or "{" not in final_content:
        logger.info("Planner returned empty/invalid content after tools, retrying with direct JSON request...")
        llm_no_tools = ChatGroq(
            model="openai/gpt-oss-120b",
            api_key=GROQ_API_KEY,
            temperature=0.3,
            max_tokens=4000,
        )

        tool_outputs = []
        for m in messages:
            if isinstance(m, ToolMessage):
                tool_outputs.append(m.content[:500])
        tool_context = "\n\n".join(tool_outputs) if tool_outputs else ""

        direct_prompt = (
            f"You are a travel planner. Return ONLY a valid JSON itinerary (no markdown, no explanation).\n\n"
            f"Trip: {num_days}-day trip to {request_data['destination']}\n"
            f"Dates: {request_data['start_date']} to {request_data['end_date']}\n"
            f"Budget: {budget_str}\n"
            f"Currency: {currency_code}\n"
            f"Travelers: {request_data.get('num_travelers', 1)}\n"
            f"Interests: {', '.join(request_data.get('interests', ['general']))}\n\n"
            f"Research findings:\n{research_summary}\n\n"
            f"Budget/activity data:\n{tool_context[:1500]}\n\n"
            f"Return JSON with these exact keys: trip_title, destination, currency, "
            f"dates (object with start, end), total_budget, daily_itinerary (array of day objects with "
            f"day, date, theme, area, morning, afternoon, evening, meals, daily_total), "
            f"accommodation (object), packing_tips (array), important_notes (array). "
            f"Each morning/afternoon/evening is an object with activity, time, cost, duration, travel_from_previous. "
            f"meals has breakfast, lunch, dinner, each with suggestion and cost. "
            f"All costs in {currency_code} with USD in parentheses like '0 {currency_code} (~$0 USD)'. "
            f"Start your response with {{ and end with }}."
        )

        followup = await llm_no_tools.ainvoke([HumanMessage(content=direct_prompt)])
        final_content = followup.content or ""

    logger.info(f"Planner raw output length: {len(final_content)}")
    logger.info(f"Planner raw output (first 500 chars): {final_content[:500]}")

    plan = _parse_plan_json(final_content)

    if not plan.get("daily_itinerary"):
        logger.warning("No daily_itinerary in response, filling with fallback itinerary")
        fallback = _build_fallback_plan(
            request_data, research_summary, num_days, currency_code, budget_str
        )
        for key, value in fallback.items():
            if not plan.get(key):
                plan[key] = value

    plan = _normalize_plan(plan, request_data, currency_code, budget_str)
    plan = clean_plan_dict(plan)
    plan["currency"] = currency_code
    plan["currency_symbol"] = currency_symbol
    plan["exchange_rate"] = exchange_rate
    return plan


def _normalize_plan(plan: dict, request_data: dict, currency_code: str, budget_str: str) -> dict:
    if not plan.get("daily_itinerary"):
        for alt_key in ["itinerary", "days", "day_by_day", "schedule", "plan"]:
            if plan.get(alt_key) and isinstance(plan[alt_key], list):
                plan["daily_itinerary"] = plan[alt_key]
                break

    if not plan.get("destination"):
        plan["destination"] = request_data.get("destination", "")

    dates = plan.get("dates", {})
    if isinstance(dates, dict):
        if "start_date" in dates and "start" not in dates:
            dates["start"] = dates["start_date"]
        if "end_date" in dates and "end" not in dates:
            dates["end"] = dates["end_date"]
        if not dates.get("start"):
            dates["start"] = request_data.get("start_date", "")
        if not dates.get("end"):
            dates["end"] = request_data.get("end_date", "")
        plan["dates"] = dates
    else:
        plan["dates"] = {"start": request_data.get("start_date", ""), "end": request_data.get("end_date", "")}

    plan["total_budget"] = _coerce_cost(plan.get("total_budget"), currency_code, budget_str)

    for day in plan.get("daily_itinerary", []):
        if not isinstance(day, dict):
            continue
        for period in ["morning", "afternoon", "evening"]:
            p = day.get(period)
            if isinstance(p, dict):
                _normalize_activity_block(p, currency_code)
            elif isinstance(p, list) and p:
                first = p[0] if isinstance(p[0], dict) else {"activity": str(p[0])}
                if isinstance(first, dict):
                    _normalize_activity_block(first, currency_code)
                day[period] = first
            elif isinstance(p, str):
                day[period] = {"activity": p, "time": "", "cost": "Free", "duration": "", "travel_from_previous": ""}

        meals = day.get("meals", {})
        if isinstance(meals, dict):
            for meal in ["breakfast", "lunch", "dinner"]:
                m = meals.get(meal)
                if isinstance(m, dict):
                    m["cost"] = _coerce_cost(m.get("cost"), currency_code, f"0 {currency_code}")

        day["daily_total"] = _coerce_cost(day.get("daily_total"), currency_code, "N/A")

    return plan


def _coerce_cost(value, currency_code: str, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return f"{value:,} {currency_code}"
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        amount = (
            value.get("amount_" + currency_code.lower())
            or value.get(currency_code)
            or value.get(currency_code.lower())
            or value.get("amount")
            or value.get("local")
            or value.get("total_" + currency_code)
            or value.get("total")
        )
        usd = (
            value.get("amount_usd")
            or value.get("USD_equivalent")
            or value.get("usd")
            or value.get("USD")
        )
        if amount and usd:
            return f"{amount:,} {currency_code} (~${usd:,} USD)" if isinstance(amount, (int, float)) else f"{amount} {currency_code} (~${usd} USD)"
        if amount:
            return f"{amount:,} {currency_code}" if isinstance(amount, (int, float)) else f"{amount} {currency_code}"
        return default
    return str(value)


def _normalize_activity_block(block: dict, currency_code: str):
    if not block.get("activity"):
        for alt in ["name", "description", "title", "activity_name"]:
            if block.get(alt):
                block["activity"] = block[alt]
                break
    if not block.get("time"):
        for alt in ["timing", "schedule", "time_slot"]:
            if block.get(alt):
                block["time"] = block[alt]
                break
    if not block.get("duration"):
        for alt in ["length", "hours"]:
            if block.get(alt):
                block["duration"] = str(block[alt])
                break
    if not block.get("travel_from_previous"):
        for alt in ["travel", "travel_time", "transport"]:
            if block.get(alt):
                block["travel_from_previous"] = block[alt]
                break
    block["cost"] = _coerce_cost(block.get("cost"), currency_code, f"0 {currency_code}")


def _build_fallback_plan(request_data, research_summary, num_days, currency_code, budget_str) -> dict:
    start = datetime.strptime(request_data["start_date"], "%Y-%m-%d")
    daily_itinerary = []
    for i in range(num_days):
        day_date = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        daily_itinerary.append({
            "day": i + 1,
            "date": day_date,
            "theme": f"Day {i + 1} Exploration",
            "area": "City Center",
            "morning": {
                "activity": f"Explore top attractions in {request_data['destination']}",
                "time": "9:00 AM - 12:00 PM",
                "cost": f"0 {currency_code} (~$0 USD)",
                "duration": "3 hrs",
                "travel_from_previous": "From hotel"
            },
            "afternoon": {
                "activity": "Local cultural experience and lunch",
                "time": "1:00 PM - 4:00 PM",
                "cost": f"0 {currency_code} (~$0 USD)",
                "duration": "3 hrs",
                "travel_from_previous": "Short walk"
            },
            "evening": {
                "activity": "Dinner and relaxation",
                "time": "6:00 PM - 9:00 PM",
                "cost": f"0 {currency_code} (~$0 USD)",
                "duration": "3 hrs",
                "travel_from_previous": "Local transit"
            },
            "meals": {
                "breakfast": {"suggestion": "Hotel breakfast or local cafe", "cost": f"0 {currency_code}"},
                "lunch": {"suggestion": "Local restaurant", "cost": f"0 {currency_code}"},
                "dinner": {"suggestion": "Traditional cuisine", "cost": f"0 {currency_code}"}
            },
            "daily_total": f"0 {currency_code}"
        })

    return {
        "trip_title": f"{request_data['destination'].title()} Trip",
        "destination": request_data['destination'],
        "currency": currency_code,
        "dates": {"start": request_data["start_date"], "end": request_data["end_date"]},
        "total_budget": budget_str,
        "daily_itinerary": daily_itinerary,
        "accommodation": {
            "type": "Mid-range hotel",
            "area": "City Center",
            "nightly_rate": f"0 {currency_code}"
        },
        "packing_tips": ["Comfortable walking shoes", "Weather-appropriate clothing", "Travel documents"],
        "important_notes": [
            f"Research summary: {research_summary[:300]}",
            "Note: AI-generated detailed itinerary unavailable due to rate limits. This is a template plan."
        ]
    }


def _parse_plan_json(content: str) -> dict:
    start_idx = content.find("{")
    if start_idx == -1:
        return {"raw_plan": content}

    json_str = content[start_idx:]

    end_idx = json_str.rfind("}") + 1
    candidate = json_str[:end_idx] if end_idx > 0 else json_str

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    fixed = _close_truncated_json(json_str)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    for cut_point in range(len(json_str), 0, -100):
        trimmed = json_str[:cut_point]
        last_comma = trimmed.rfind(",")
        if last_comma > 0:
            trimmed = trimmed[:last_comma]
        candidate = _close_truncated_json(trimmed)
        try:
            parsed = json.loads(candidate)
            if parsed.get("daily_itinerary") or parsed.get("trip_title"):
                return parsed
        except json.JSONDecodeError:
            continue

    return {"raw_plan": content}


def _close_truncated_json(s: str) -> str:
    in_string = False
    escape = False
    stack = []

    for ch in s:
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()

    result = s
    if in_string:
        result += '"'

    result = result.rstrip().rstrip(",")

    while stack:
        opener = stack.pop()
        result += "}" if opener == "{" else "]"

    return result
