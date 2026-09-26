import json
from langchain_core.tools import tool


ACTIVITIES_DB = {
    "museums": [
        {"name": "National Museum", "type": "museum", "duration_hours": 3, "cost_usd": 15, "rating": 4.5},
        {"name": "Modern Art Gallery", "type": "museum", "duration_hours": 2, "cost_usd": 12, "rating": 4.3},
        {"name": "History Museum", "type": "museum", "duration_hours": 2.5, "cost_usd": 10, "rating": 4.4},
    ],
    "food": [
        {"name": "Local Food Market Tour", "type": "food", "duration_hours": 3, "cost_usd": 35, "rating": 4.7},
        {"name": "Cooking Class", "type": "food", "duration_hours": 4, "cost_usd": 50, "rating": 4.8},
        {"name": "Street Food Walking Tour", "type": "food", "duration_hours": 2.5, "cost_usd": 25, "rating": 4.6},
    ],
    "adventure": [
        {"name": "Guided Hiking Tour", "type": "adventure", "duration_hours": 5, "cost_usd": 45, "rating": 4.6},
        {"name": "Kayaking / Water Sports", "type": "adventure", "duration_hours": 3, "cost_usd": 40, "rating": 4.5},
        {"name": "Zip-lining Experience", "type": "adventure", "duration_hours": 2, "cost_usd": 55, "rating": 4.4},
    ],
    "culture": [
        {"name": "Temple / Landmark Tour", "type": "culture", "duration_hours": 3, "cost_usd": 20, "rating": 4.7},
        {"name": "Traditional Performance Show", "type": "culture", "duration_hours": 2, "cost_usd": 30, "rating": 4.5},
        {"name": "Local Neighborhood Walking Tour", "type": "culture", "duration_hours": 2.5, "cost_usd": 15, "rating": 4.6},
    ],
    "relaxation": [
        {"name": "Spa & Wellness Half-Day", "type": "relaxation", "duration_hours": 4, "cost_usd": 60, "rating": 4.8},
        {"name": "Beach / Park Day", "type": "relaxation", "duration_hours": 5, "cost_usd": 0, "rating": 4.5},
        {"name": "Sunset Cruise", "type": "relaxation", "duration_hours": 2, "cost_usd": 45, "rating": 4.7},
    ],
    "nightlife": [
        {"name": "Bar Hopping Tour", "type": "nightlife", "duration_hours": 3, "cost_usd": 40, "rating": 4.3},
        {"name": "Rooftop Dinner", "type": "nightlife", "duration_hours": 2.5, "cost_usd": 55, "rating": 4.6},
        {"name": "Live Music Venue", "type": "nightlife", "duration_hours": 3, "cost_usd": 25, "rating": 4.4},
    ],
    "shopping": [
        {"name": "Local Market & Souvenirs", "type": "shopping", "duration_hours": 2, "cost_usd": 10, "rating": 4.2},
        {"name": "Artisan Workshop Visit", "type": "shopping", "duration_hours": 1.5, "cost_usd": 20, "rating": 4.5},
    ],
}


@tool
def recommend_activities(destination: str, interests: list[str], num_days: int, daily_budget: float) -> str:
    """Recommend activities and restaurants based on traveler interests and budget.
    Returns a curated list of suggestions organized by interest category,
    filtered to fit within the daily activity budget."""

    matched = {}
    interest_map = {
        "hiking": "adventure", "outdoors": "adventure", "nature": "adventure",
        "food": "food", "cuisine": "food", "dining": "food", "restaurants": "food",
        "art": "museums", "museums": "museums", "history": "museums",
        "culture": "culture", "temples": "culture", "architecture": "culture",
        "beach": "relaxation", "spa": "relaxation", "relaxation": "relaxation",
        "nightlife": "nightlife", "bars": "nightlife", "party": "nightlife",
        "shopping": "shopping", "markets": "shopping",
    }

    categories_used = set()
    for interest in interests:
        category = interest_map.get(interest.lower().strip(), "culture")
        categories_used.add(category)

    if not categories_used:
        categories_used = {"culture", "food"}

    activity_budget = daily_budget * 0.20

    for cat in categories_used:
        items = ACTIVITIES_DB.get(cat, ACTIVITIES_DB["culture"])
        affordable = [a for a in items if a["cost_usd"] <= activity_budget * 1.5]
        if not affordable:
            affordable = items[:2]
        matched[cat] = affordable

    result = {
        "destination": destination,
        "daily_activity_budget": round(activity_budget, 2),
        "num_days": num_days,
        "recommendations_by_category": matched,
        "total_unique_activities": sum(len(v) for v in matched.values()),
    }
    return json.dumps(result, indent=2)
