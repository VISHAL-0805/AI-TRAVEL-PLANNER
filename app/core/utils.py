import re


CURRENCY_SYMBOLS = {
    "JPY": "¥", "CNY": "¥", "EUR": "€", "GBP": "£", "INR": "₹",
    "THB": "฿", "KRW": "₩", "TRY": "₺", "USD": "$", "CAD": "C$",
    "AUD": "A$", "SGD": "S$", "CHF": "CHF ", "MXN": "MX$",
    "IDR": "Rp", "VND": "₫", "CZK": "Kč", "HUF": "Ft",
    "AED": "AED ", "EGP": "E£", "JOD": "JOD ", "MAD": "MAD ",
    "ZAR": "R", "BRL": "R$", "PHP": "₱", "MYR": "RM",
    "NPR": "Rs", "LKR": "Rs", "PKR": "Rs",
}

DESTINATION_CURRENCY_MAP = {
    "tokyo": ("JPY", 149.5), "osaka": ("JPY", 149.5), "kyoto": ("JPY", 149.5),
    "london": ("GBP", 0.79), "manchester": ("GBP", 0.79),
    "paris": ("EUR", 0.92), "rome": ("EUR", 0.92), "berlin": ("EUR", 0.92),
    "amsterdam": ("EUR", 0.92), "barcelona": ("EUR", 0.92), "lisbon": ("EUR", 0.92),
    "athens": ("EUR", 0.92), "vienna": ("EUR", 0.92), "florence": ("EUR", 0.92),
    "prague": ("CZK", 23.4), "budapest": ("HUF", 365.0),
    "bangkok": ("THB", 35.5), "phuket": ("THB", 35.5), "chiang mai": ("THB", 35.5),
    "bali": ("IDR", 15700.0), "jakarta": ("IDR", 15700.0),
    "hanoi": ("VND", 24500.0), "ho chi minh": ("VND", 24500.0),
    "new delhi": ("INR", 83.5), "mumbai": ("INR", 83.5), "goa": ("INR", 83.5),
    "jaipur": ("INR", 83.5), "india": ("INR", 83.5), "delhi": ("INR", 83.5),
    "bangalore": ("INR", 83.5), "kolkata": ("INR", 83.5), "chennai": ("INR", 83.5),
    "istanbul": ("TRY", 32.5), "cairo": ("EGP", 30.9),
    "mexico city": ("MXN", 17.2), "cancun": ("MXN", 17.2),
    "singapore": ("SGD", 1.35), "dubai": ("AED", 3.67), "abu dhabi": ("AED", 3.67),
    "sydney": ("AUD", 1.53), "melbourne": ("AUD", 1.53),
    "toronto": ("CAD", 1.36), "vancouver": ("CAD", 1.36),
    "seoul": ("KRW", 1330.0), "zurich": ("CHF", 0.88),
    "beijing": ("CNY", 7.25), "shanghai": ("CNY", 7.25), "hong kong": ("HKD", 7.82),
    "new york": ("USD", 1.0), "los angeles": ("USD", 1.0),
    "san francisco": ("USD", 1.0), "chicago": ("USD", 1.0),
    "amman": ("JOD", 0.71), "jordan": ("JOD", 0.71), "petra": ("JOD", 0.71),
    "marrakech": ("MAD", 10.1), "morocco": ("MAD", 10.1),
    "cape town": ("ZAR", 18.5), "johannesburg": ("ZAR", 18.5),
    "sao paulo": ("BRL", 4.97), "rio de janeiro": ("BRL", 4.97),
    "manila": ("PHP", 56.5), "kuala lumpur": ("MYR", 4.65),
    "kathmandu": ("NPR", 133.5), "colombo": ("LKR", 325.0),
    "lahore": ("PKR", 278.0), "karachi": ("PKR", 278.0),
}


def get_currency_info(destination: str) -> tuple[str, float, str]:
    dest_lower = destination.lower().strip()
    code, rate = DESTINATION_CURRENCY_MAP.get(dest_lower, ("USD", 1.0))
    symbol = CURRENCY_SYMBOLS.get(code, code + " ")
    return code, rate, symbol


def format_local_price(usd_amount: float, rate: float, symbol: str) -> str:
    local = round(usd_amount * rate)
    if rate > 100:
        return f"{symbol}{local:,}"
    return f"{symbol}{round(usd_amount * rate, 2):,.2f}"


def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return text

    # don't mess with currency patterns like "¥5,225 (~$35 USD)" or "15 (~$15 USD)"
    # protect them first by replacing with placeholders
    currency_patterns = []

    def protect_currency(match):
        currency_patterns.append(match.group(0))
        return f"__CURRENCY_{len(currency_patterns) - 1}__"

    # protect patterns like "NUMBER (~$NUMBER USD)" or "SYMBOL+NUMBER (~$NUMBER USD)"
    text = re.sub(r'[\w¥€£₹฿₩₺$]+[\d,.]+ *\(~?\$[\d,.]+ *USD\)', protect_currency, text)

    # add space before ( if missing — but not after digits (currency amounts)
    text = re.sub(r'([a-zA-Z])\(', r'\1 (', text)
    # add space after ) if followed by a word
    text = re.sub(r'\)([a-zA-Z])', r') \1', text)
    # add space after . if followed by a letter (no space)
    text = re.sub(r'\.([A-Za-z])', r'. \1', text)
    # add space after , if followed by a letter (not digit — preserve "1,500")
    text = re.sub(r',([a-zA-Z])', r', \1', text)
    # fix stuck currency: $30USD -> $30 USD
    text = re.sub(r'(\$\d+)([A-Z])', r'\1 \2', text)
    # fix ~$30 with no space before (but not after currency symbols)
    text = re.sub(r'([a-zA-Z])(~\$)', r'\1 ~$', text)
    # fix double spaces
    text = re.sub(r' {2,}', ' ', text)

    # restore currency patterns
    for i, pattern in enumerate(currency_patterns):
        text = text.replace(f"__CURRENCY_{i}__", pattern)

    return text.strip()


def clean_plan_dict(data) -> any:
    if isinstance(data, str):
        return clean_text(data)
    elif isinstance(data, dict):
        return {k: clean_plan_dict(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_plan_dict(item) for item in data]
    return data
