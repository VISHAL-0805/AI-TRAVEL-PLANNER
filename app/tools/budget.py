import json
from langchain_core.tools import tool
from app.core.utils import get_currency_info, CURRENCY_SYMBOLS


COST_MULTIPLIERS = {
    "tokyo": 1.3, "london": 1.4, "paris": 1.35, "new york": 1.4,
    "zurich": 1.5, "singapore": 1.2, "bangkok": 0.6, "bali": 0.5,
    "hanoi": 0.45, "mexico city": 0.55, "istanbul": 0.6,
    "cairo": 0.5, "lisbon": 0.8, "prague": 0.7, "budapest": 0.65,
    "new delhi": 0.4, "mumbai": 0.45, "goa": 0.4, "jaipur": 0.4,
    "dubai": 1.2, "seoul": 0.9, "barcelona": 1.0, "rome": 1.0,
    "amman": 0.6, "jordan": 0.6, "marrakech": 0.5, "cape town": 0.55,
    "kuala lumpur": 0.5, "kathmandu": 0.35, "colombo": 0.4,
}


@tool
def allocate_budget(total_budget_usd: float, num_days: int, num_travelers: int, destination: str) -> str:
    """Allocate a travel budget across categories and days.
    Takes budget in USD and converts to the destination's local currency.
    Splits into accommodation, food, activities, transport, and miscellaneous."""

    dest_lower = destination.lower().strip()
    currency_code, exchange_rate, currency_symbol = get_currency_info(destination)
    multiplier = COST_MULTIPLIERS.get(dest_lower, 1.0)

    total_local = round(total_budget_usd * exchange_rate, 2)

    base_split = {
        "accommodation": 0.35,
        "food": 0.25,
        "activities": 0.20,
        "local_transport": 0.12,
        "miscellaneous": 0.08,
    }

    per_person_usd = total_budget_usd / num_travelers
    daily_usd = per_person_usd / num_days

    allocation = {}
    for category, ratio in base_split.items():
        daily_amount_usd = round(daily_usd * ratio, 2)
        daily_amount_local = round(daily_amount_usd * exchange_rate, 2)
        allocation[category] = {
            "daily_per_person": f"{currency_symbol}{daily_amount_local:,.2f} (~${daily_amount_usd} USD)",
            "total_per_person": f"{currency_symbol}{round(daily_amount_local * num_days, 2):,.2f}",
            "total_all_travelers": f"{currency_symbol}{round(daily_amount_local * num_days * num_travelers, 2):,.2f}",
        }

    result = {
        "destination": destination,
        "local_currency": currency_code,
        "currency_symbol": currency_symbol,
        "exchange_rate": f"1 USD = {exchange_rate} {currency_code}",
        "cost_level": "high" if multiplier > 1.1 else "moderate" if multiplier > 0.7 else "budget-friendly",
        "total_budget": f"{currency_symbol}{total_local:,.2f} (~${total_budget_usd:,.0f} USD)",
        "num_days": num_days,
        "num_travelers": num_travelers,
        "daily_budget_per_person": f"{currency_symbol}{round(daily_usd * exchange_rate, 2):,.2f} (~${round(daily_usd, 2)} USD)",
        "breakdown": allocation,
        "tip": _budget_tip(daily_usd, multiplier),
    }
    return json.dumps(result, indent=2)


def _budget_tip(daily_budget_usd: float, multiplier: float) -> str:
    adjusted = daily_budget_usd / multiplier
    if adjusted > 200:
        return "Generous budget — you can enjoy premium experiences and fine dining."
    elif adjusted > 100:
        return "Comfortable budget — mix of mid-range and occasional splurges."
    elif adjusted > 50:
        return "Moderate budget — prioritize must-see attractions, eat at local spots."
    else:
        return "Tight budget — focus on free attractions, street food, and hostels."
