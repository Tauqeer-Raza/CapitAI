import os
import json
from datetime import date


def get_financial_insights(summary, logs=None, chat_mode=False):
    """
    Fallback-friendly AI function.
    You can later replace internals with Gemini/OpenAI safely.
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


def scan_expense_from_image(image_file):
    """
    Simple fallback parser for demo mode.
    For tomorrow's demo, this keeps the feature alive even without full OCR.
    You can later replace this with Gemini Vision / OCR pipeline.
    """

    filename = (getattr(image_file, "filename", "") or "").lower()

    category = "Other"
    note = "Scanned receipt"

    if any(word in filename for word in ["zomato", "swiggy", "food", "restaurant", "cafe"]):
        category = "Food"
    elif any(word in filename for word in ["uber", "ola", "petrol", "travel", "bus", "train"]):
        category = "Travel"
    elif any(word in filename for word in ["shirt", "mall", "shopping", "amazon", "flipkart"]):
        category = "Shopping"

    return {
        "amount": 100,
        "category": category,
        "note": note,
        "log_date": str(date.today()),
    }