from datetime import datetime, date, timedelta
from collections import defaultdict


VALID_CATEGORIES = {"Food", "Travel", "Shopping", "Other"}


def normalize_category(category):
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

        "shopping": "Shopping",
        "clothes": "Shopping",
        "fashion": "Shopping",
        "amazon": "Shopping",
        "flipkart": "Shopping",

        "education": "Other",
        "health": "Other",
        "medical": "Other",
        "bills": "Other",
        "bill": "Other",
        "entertainment": "Other",
        "other": "Other",
    }

    return mapping.get(raw, "Other")


def safe_float(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_future_date(log_date):
    try:
        d = datetime.strptime(log_date, "%Y-%m-%d").date()
        return d > date.today()
    except Exception:
        return True


def get_month_bounds(target_date=None):
    target_date = target_date or date.today()
    start = target_date.replace(day=1)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1, day=1)
    else:
        next_month = start.replace(month=start.month + 1, day=1)
    return start, next_month - timedelta(days=1)


def get_monthly_spend(logs, target_date=None):
    target_date = target_date or date.today()
    start, end = get_month_bounds(target_date)

    total = 0
    for log in logs:
        try:
            d = datetime.strptime(log["log_date"], "%Y-%m-%d").date()
            if start <= d <= end:
                total += safe_float(log["amount"])
        except Exception:
            continue
    return round(total, 2)


def get_weekly_spend(logs, target_date=None):
    target_date = target_date or date.today()
    start = target_date - timedelta(days=6)
    total = 0

    for log in logs:
        try:
            d = datetime.strptime(log["log_date"], "%Y-%m-%d").date()
            if start <= d <= target_date:
                total += safe_float(log["amount"])
        except Exception:
            continue

    return round(total, 2)


def get_today_spend(logs, target_date=None):
    target_date = target_date or date.today()
    total = 0

    for log in logs:
        try:
            d = datetime.strptime(log["log_date"], "%Y-%m-%d").date()
            if d == target_date:
                total += safe_float(log["amount"])
        except Exception:
            continue

    return round(total, 2)


def can_add_expense(amount, monthly_income, logs):
    amount = safe_float(amount)
    monthly_income = safe_float(monthly_income)

    if amount <= 0:
        return False, "Expense amount must be greater than zero."

    if monthly_income <= 0:
        return False, "Please set your monthly income first."

    current_month_spend = get_monthly_spend(logs)
    remaining = monthly_income - current_month_spend

    if amount > remaining:
        return False, "This expense exceeds your available monthly limit."

    return True, "Allowed"


def budget_warning_level(monthly_income, monthly_spend):
    monthly_income = safe_float(monthly_income)
    monthly_spend = safe_float(monthly_spend)

    if monthly_income <= 0:
        return None

    used = (monthly_spend / monthly_income) * 100

    if used >= 100:
        return "critical"
    if used >= 90:
        return "danger"
    if used >= 80:
        return "warning"
    return None


def parse_voice_expense(text):
    if not text:
        return None

    raw = text.lower().strip()
    words = raw.split()

    amount = None
    for token in words:
        token = token.replace("₹", "").replace(",", "")
        try:
            amount = float(token)
            break
        except ValueError:
            continue

    if amount is None:
        return None

    category = "Other"
    if any(k in raw for k in ["food", "lunch", "dinner", "breakfast", "snack", "restaurant"]):
        category = "Food"
    elif any(k in raw for k in ["travel", "uber", "ola", "petrol", "fuel", "bus", "train", "cab"]):
        category = "Travel"
    elif any(k in raw for k in ["shopping", "shirt", "clothes", "amazon", "flipkart"]):
        category = "Shopping"

    log_date = str(date.today())
    if "yesterday" in raw:
        log_date = str(date.today() - timedelta(days=1))

    note = text.strip()

    return {
        "amount": round(amount, 2),
        "category": category,
        "log_date": log_date,
        "note": note,
    }


def compute_dashboard_metrics(user, logs):
    monthly_income = safe_float(user.get("monthly_income", 0))
    monthly_spend = get_monthly_spend(logs)
    weekly_spend = get_weekly_spend(logs)
    today_spend = get_today_spend(logs)
    remaining_budget = round(monthly_income - monthly_spend, 2)
    budget_used_percentage = round((monthly_spend / monthly_income) * 100, 1) if monthly_income > 0 else 0
    warning_level = budget_warning_level(monthly_income, monthly_spend)

    recent_logs = logs[:5]

    insights = []
    if monthly_income > 0:
        if budget_used_percentage >= 90:
            insights.append("You are very close to your monthly limit. Avoid non-essential spending now.")
        elif budget_used_percentage >= 80:
            insights.append("You have used over 80% of your budget. Spend carefully for the rest of the month.")
        else:
            insights.append("Your spending is still within a manageable range. Keep tracking regularly.")
    else:
        insights.append("Set your monthly income to unlock better budget analysis.")

    return {
        "monthly_income": round(monthly_income, 2),
        "monthly_spend": round(monthly_spend, 2),
        "weekly_spend": round(weekly_spend, 2),
        "today_spend": round(today_spend, 2),
        "remaining_budget": remaining_budget,
        "budget_used_percentage": budget_used_percentage,
        "warning_level": warning_level,
        "recent_logs": recent_logs,
        "insights": insights,
    }


def compute_analysis_summary(logs):
    total_logs = len(logs)
    filtered_spend = round(sum(safe_float(log["amount"]) for log in logs), 2)
    avg_expense = round(filtered_spend / total_logs, 2) if total_logs > 0 else 0

    category_totals = defaultdict(float)
    daily_totals = defaultdict(float)

    for log in logs:
        amount = safe_float(log["amount"])
        category = normalize_category(log.get("category", "Other"))
        log_date = log.get("log_date")

        category_totals[category] += amount
        daily_totals[log_date] += amount

    top_category = None
    if category_totals:
        top_category = max(category_totals, key=category_totals.get)

    trend = [
        {"label": k, "value": round(v, 2)}
        for k, v in sorted(daily_totals.items())
    ]

    category_breakdown = [
        {"label": k, "value": round(v, 2)}
        for k, v in category_totals.items()
    ]

    return {
        "filtered_spend": filtered_spend,
        "total_logs": total_logs,
        "avg_expense": avg_expense,
        "top_category": top_category,
        "trend": trend,
        "category_breakdown": category_breakdown,
    }