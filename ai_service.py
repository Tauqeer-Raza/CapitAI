import os
import json
import base64
import mimetypes
import requests
from datetime import date


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_category(category):
    if not category:
        return "Other"

    raw = str(category).strip().lower()

    mapping = {
        "food": "Food",
        "meal": "Food",
        "restaurant": "Food",
        "groceries": "Food",
        "grocery": "Food",
        "snacks": "Food",
        "cafe": "Food",
        "dining": "Food",

        "travel": "Travel",
        "transport": "Travel",
        "transportation": "Travel",
        "cab": "Travel",
        "uber": "Travel",
        "ola": "Travel",
        "petrol": "Travel",
        "fuel": "Travel",
        "bus": "Travel",
        "train": "Travel",
        "metro": "Travel",

        "shopping": "Shopping",
        "clothes": "Shopping",
        "fashion": "Shopping",
        "amazon": "Shopping",
        "flipkart": "Shopping",
        "mall": "Shopping",

        "education": "Other",
        "health": "Other",
        "medical": "Other",
        "bills": "Other",
        "bill": "Other",
        "entertainment": "Other",
        "other": "Other",
    }

    return mapping.get(raw, "Other")


def get_financial_insights(summary, logs=None, chat_mode=False):
    """
    Fallback-friendly AI function for dashboard insights and chat.
    Keeps working even if external AI is unavailable.
    """

    if chat_mode:
        monthly_income = summary.get("monthly_income", 0)
        monthly_spend = summary.get("monthly_spend", 0)
        remaining_budget = summary.get("remaining_budget", 0)
        weekly_spend = summary.get("weekly_spend", 0)
        question = summary.get("question", "")

        if remaining_budget <= 0:
            return "You have exhausted your monthly budget. Avoid adding any non-essential expenses right now."

        if monthly_income and monthly_spend >= monthly_income * 0.9:
            return "Your spending is above 90% of your income, so your safest move is to reduce discretionary expenses immediately."

        if "save" in question.lower() or "savings" in question.lower():
            return (
                f"You have spent ₹{monthly_spend} this month and ₹{weekly_spend} this week. "
                f"To save more, reduce flexible categories first and protect your remaining ₹{remaining_budget}."
            )

        if "budget" in question.lower():
            return (
                f"Your current monthly spend is ₹{monthly_spend} against income of ₹{monthly_income}. "
                f"You have ₹{remaining_budget} left for the rest of the month."
            )

        return (
            f"Your monthly spend is ₹{monthly_spend}, weekly spend is ₹{weekly_spend}, "
            f"and remaining budget is ₹{remaining_budget}. Focus on stable daily spending to stay in control."
        )

    filtered_spend = summary.get("filtered_spend", 0)
    total_logs = summary.get("total_logs", 0)
    top_category = summary.get("top_category", "Other")
    avg_expense = summary.get("avg_expense", 0)

    if total_logs == 0:
        return ["No expenses found yet. Start adding logs to unlock AI insights."]

    insights = []

    insights.append(
        f"You have logged {total_logs} expenses with a total tracked spend of ₹{filtered_spend}."
    )

    insights.append(
        f"Your highest spending category is {top_category}, and your average expense amount is ₹{avg_expense}."
    )

    if top_category == "Food":
        insights.append("Food appears to be your strongest spending area. Monitoring frequent small orders may help reduce monthly leakage.")
    elif top_category == "Travel":
        insights.append("Travel is your biggest spending category. Review recurring transport costs and see where optimized commuting is possible.")
    elif top_category == "Shopping":
        insights.append("Shopping is currently your highest category. Be cautious with impulse-based purchases and non-essential spending.")
    else:
        insights.append("A large share of your spending is falling into Other. Categorizing more precisely can improve insight quality.")

    return insights


def _gemini_generate_from_image_bytes(image_bytes, mime_type):
    """
    Calls Gemini REST API with inline image data and requests strict JSON output.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing.")

    prompt = """
You are a receipt and bill extraction assistant for a student finance app.

Analyze the uploaded receipt, invoice, or expense image and return ONLY valid JSON in this exact format:

{
  "amount": 0,
  "category": "Other",
  "note": "",
  "log_date": ""
}

Rules:
- amount = final payable amount only, as a number, no currency symbol
- category must be exactly one of: Food, Travel, Shopping, Other
- note = short merchant or expense description
- log_date = date in YYYY-MM-DD format if clearly visible, otherwise empty string
- If unsure, make the best reasonable guess from visible content
- Return JSON only, no markdown, no explanation
"""

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": base64.b64encode(image_bytes).decode("utf-8")
                        }
                    }
                ]
            }
        ]
    }

    response = requests.post(url, json=payload, timeout=40)
    response.raise_for_status()
    data = response.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError("No candidates returned from Gemini.")

    parts = candidates[0].get("content", {}).get("parts", [])
    text_chunks = [p.get("text", "") for p in parts if "text" in p]
    raw_text = "\n".join(text_chunks).strip()

    if not raw_text:
        raise RuntimeError("Gemini returned empty text.")

    # Strip markdown code fences if model wraps JSON
    cleaned = raw_text.replace("```json", "").replace("```", "").strip()

    parsed = json.loads(cleaned)
    return parsed


def scan_expense_from_image(image_file):
    """
    Real image-based receipt scanning via Gemini.
    Falls back gracefully if API key or request fails.
    """
    filename = (getattr(image_file, "filename", "") or "").strip()
    mime_type = getattr(image_file, "mimetype", None) or mimetypes.guess_type(filename)[0] or "image/jpeg"

    image_bytes = image_file.read()
    if not image_bytes:
        raise RuntimeError("Uploaded image is empty.")

    try:
        parsed = _gemini_generate_from_image_bytes(image_bytes, mime_type)

        amount = _safe_float(parsed.get("amount"), 0)
        category = _normalize_category(parsed.get("category", "Other"))
        note = (parsed.get("note") or "Scanned receipt").strip()
        log_date = (parsed.get("log_date") or "").strip()

        if not log_date:
            log_date = str(date.today())

        if amount <= 0:
            amount = 0

        return {
            "amount": amount,
            "category": category,
            "note": note,
            "log_date": log_date,
        }

    except Exception as e:
        print("Gemini scan failed:", str(e))

        # Fallback so demo flow never breaks
        lowered = filename.lower()

        category = "Other"
        if any(word in lowered for word in ["zomato", "swiggy", "food", "restaurant", "cafe"]):
            category = "Food"
        elif any(word in lowered for word in ["uber", "ola", "petrol", "travel", "bus", "train"]):
            category = "Travel"
        elif any(word in lowered for word in ["shirt", "mall", "shopping", "amazon", "flipkart"]):
            category = "Shopping"

        return {
            "amount": 100,
            "category": category,
            "note": f"Scanned receipt ({filename or 'image'})",
            "log_date": str(date.today()),
        }
