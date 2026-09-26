import json
from langchain_core.tools import tool


DESTINATION_CURRENCY = {
    "tokyo": ("JPY", 149.5), "osaka": ("JPY", 149.5), "kyoto": ("JPY", 149.5),
    "london": ("GBP", 0.79), "manchester": ("GBP", 0.79),
    "paris": ("EUR", 0.92), "rome": ("EUR", 0.92), "berlin": ("EUR", 0.92),
    "amsterdam": ("EUR", 0.92), "barcelona": ("EUR", 0.92), "lisbon": ("EUR", 0.92),
    "prague": ("CZK", 23.4), "budapest": ("HUF", 365.0),
    "bangkok": ("THB", 35.5), "phuket": ("THB", 35.5),
    "bali": ("IDR", 15700.0), "jakarta": ("IDR", 15700.0),
    "hanoi": ("VND", 24500.0), "ho chi minh": ("VND", 24500.0),
    "new delhi": ("INR", 83.5), "mumbai": ("INR", 83.5), "goa": ("INR", 83.5),
    "jaipur": ("INR", 83.5), "india": ("INR", 83.5),
    "istanbul": ("TRY", 32.5), "cairo": ("EGP", 30.9),
    "mexico city": ("MXN", 17.2), "cancun": ("MXN", 17.2),
    "singapore": ("SGD", 1.35), "dubai": ("AED", 3.67),
    "sydney": ("AUD", 1.53), "melbourne": ("AUD", 1.53),
    "toronto": ("CAD", 1.36), "vancouver": ("CAD", 1.36),
    "seoul": ("KRW", 1330.0), "zurich": ("CHF", 0.88),
    "new york": ("USD", 1.0), "los angeles": ("USD", 1.0), "san francisco": ("USD", 1.0),
}

COST_MULTIPLIERS = {
    "tokyo": 1.3, "london": 1.4, "paris": 1.35, "new york": 1.4,
    "zurich": 1.5, "singapore": 1.2, "bangkok": 0.6, "bali": 0.5,
    "hanoi": 0.45, "mexico city": 0.55, "istanbul": 0.6,
    "cairo": 0.5, "lisbon": 0.8, "prague": 0.7, "budapest": 0.65,
    "new delhi": 0.4, "mumbai": 0.45, "goa": 0.4, "jaipur": 0.4,
    "dubai": 1.2, "seoul": 0.9, "barcelona": 1.0, "rome": 1.0,
}


@tool
def allocate_budget(total_budget_usd: float, num_days: int, num_travelers: int, destination: str) -> str:
    """Allocate a travel budget across categories and days.
    Takes budget in USD and converts to the destination's local currency.
    Splits into accommodation, food, activities, transport, and miscellaneous."""

    dest_lower = destination.lower().strip()
    currency_code, exchange_rate = DESTINATION_CURRENCY.get(dest_lower, ("USD", 1.0))
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
            "daily_per_person": f"{daily_amount_local} {currency_code} (~${daily_amount_usd} USD)",
            "total_per_person": f"{round(daily_amount_local * num_days, 2)} {currency_code}",
            "total_all_travelers": f"{round(daily_amount_local * num_days * num_travelers, 2)} {currency_code}",
        }

    result = {
        "destination": destination,
        "local_currency": currency_code,
        "exchange_rate": f"1 USD = {exchange_rate} {currency_code}",
        "cost_level": "high" if multiplier > 1.1 else "moderate" if multiplier > 0.7 else "budget-friendly",
        "total_budget": f"${total_budget_usd} USD = {total_local} {currency_code}",
        "num_days": num_days,
        "num_travelers": num_travelers,
        "daily_budget_per_person": f"{round(daily_usd * exchange_rate, 2)} {currency_code} (~${round(daily_usd, 2)} USD)",
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
