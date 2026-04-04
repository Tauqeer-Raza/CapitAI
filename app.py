from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, date
from dotenv import load_dotenv
import os
import random
import smtplib
from email.mime.text import MIMEText
load_dotenv()

from database import (
    init_db,
    create_user,
    get_user_by_email,
    verify_user_credentials,
    update_user_profile,
    update_user_password,
    mark_email_verified,
    store_otp,
    verify_otp_code,
    get_user_profile,
    get_user_logs,
    add_expense,
    get_filtered_logs,
)

from logic import (
    compute_dashboard_metrics,
    compute_analysis_summary,
    parse_voice_expense,
    is_future_date,
    can_add_expense,
    normalize_category,
)

from ai_service import (
    get_financial_insights,
    scan_expense_from_image,
)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")

init_db()


# -----------------------------
# Helpers
# -----------------------------
def require_login():
    return session.get("user_id") is not None


def send_otp_email(to_email, otp_code):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM_EMAIL", smtp_username)

    subject = "Your CapitAI verification code"
    body = f"Your OTP code is: {otp_code}"

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = to_email

    try:
        with smtplib.SMTP(smtp_host, int(smtp_port), timeout=10) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)

        print("✅ OTP email sent")

    except Exception as e:
        print("❌ SMTP FAILED:", str(e))
        print(f"👉 DEMO OTP for {to_email}: {otp_code}")


def generate_otp():
    return str(random.randint(100000, 999999))


# -----------------------------
# Auth Routes
# -----------------------------
@app.route("/")
def home():
    if require_login():
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if require_login():
        return redirect(url_for("dashboard"))

    error = None
    success = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = verify_user_credentials(email, password)
        if not user:
            error = "Invalid email or password."
            return render_template("login.html", error=error, success=success)

        if not user.get("email_verified"):
            otp = generate_otp()
            store_otp(email, otp)
            try:
                send_otp_email(email, otp)
            except Exception:
                error = "Your email is not verified, and OTP email could not be sent. Check SMTP settings."
                return render_template("login.html", error=error, success=success)

            return redirect(url_for("verify_otp", email=email))

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        return redirect(url_for("dashboard"))

    return render_template("login.html", error=error, success=success)


@app.route("/register", methods=["GET", "POST"])
def register():
    if require_login():
        return redirect(url_for("dashboard"))

    error = None
    success = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not email or not password or not confirm_password:
            error = "All fields are required."
            return render_template("register.html", error=error, success=success)

        if password != confirm_password:
            error = "Passwords do not match."
            return render_template("register.html", error=error, success=success)

        existing = get_user_by_email(email)
        if existing:
            error = "An account with this email already exists."
            return render_template("register.html", error=error, success=success)

        create_user(username, email, password)

        otp = generate_otp()
        store_otp(email, otp)

        try:
            send_otp_email(email, otp)
            success = "Account created. OTP sent to your email."
        except Exception:
            error = "Account created, but OTP email could not be sent. Check SMTP settings."
            return render_template("register.html", error=error, success=success)

        return redirect(url_for("verify_otp", email=email))

    return render_template("register.html", error=error, success=success)


@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    error = None
    success = None
    email = request.args.get("email") or request.form.get("email")

    if request.method == "POST":
        otp = request.form.get("otp", "").strip()
        if not email or not otp:
            error = "Email and OTP are required."
            return render_template(
                "verify_otp.html",
                error=error,
                success=success,
                email=email,
                resend_url=url_for("resend_otp", email=email) if email else None
            )

        valid = verify_otp_code(email, otp)
        if not valid:
            error = "Invalid or expired OTP."
            return render_template(
                "verify_otp.html",
                error=error,
                success=success,
                email=email,
                resend_url=url_for("resend_otp", email=email) if email else None
            )

        mark_email_verified(email)
        success = "Email verified successfully. Please login."
        return render_template("login.html", success=success, error=None)

    return render_template(
        "verify_otp.html",
        error=error,
        success=success,
        email=email,
        resend_url=url_for("resend_otp", email=email) if email else None
    )


@app.route("/resend-otp")
def resend_otp():
    email = request.args.get("email", "").strip().lower()
    if not email:
        return redirect(url_for("register"))

    otp = generate_otp()
    store_otp(email, otp)
    try:
        send_otp_email(email, otp)
    except Exception:
        return render_template(
            "verify_otp.html",
            error="Could not resend OTP. Check SMTP settings.",
            success=None,
            email=email,
            resend_url=url_for("resend_otp", email=email)
        )

    return render_template(
        "verify_otp.html",
        success="A new OTP has been sent.",
        error=None,
        email=email,
        resend_url=url_for("resend_otp", email=email)
    )


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    error = None
    success = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = get_user_by_email(email)

        if not user:
            error = "No account found with this email."
            return render_template("forgot_password.html", error=error, success=success)

        otp = generate_otp()
        store_otp(email, otp)

        try:
            send_otp_email(email, otp)
        except Exception:
            error = "OTP email could not be sent. Check SMTP settings."
            return render_template("forgot_password.html", error=error, success=success)

        return redirect(url_for("reset_password", email=email))

    return render_template("forgot_password.html", error=error, success=success)


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    error = None
    success = None
    email = request.args.get("email") or request.form.get("email")

    if request.method == "POST":
        otp = request.form.get("otp", "").strip()
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not email or not otp or not new_password or not confirm_password:
            error = "All fields are required."
            return render_template("reset_password.html", error=error, success=success, email=email)

        if new_password != confirm_password:
            error = "Passwords do not match."
            return render_template("reset_password.html", error=error, success=success, email=email)

        valid = verify_otp_code(email, otp)
        if not valid:
            error = "Invalid or expired OTP."
            return render_template("reset_password.html", error=error, success=success, email=email)

        update_user_password(email, new_password)
        success = "Password reset successful. Please login."
        return render_template("login.html", success=success, error=None)

    return render_template("reset_password.html", error=error, success=success, email=email)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# -----------------------------
# Dashboard
# -----------------------------
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if not require_login():
        return redirect(url_for("login"))

    user_id = session["user_id"]
    error = None
    success = None
    scan_preview = session.get("scan_preview")

    if request.method == "POST":
        action = request.form.get("action")

        if action == "set_income":
            monthly_income = request.form.get("monthly_income", "0").strip()
            savings_goal = request.form.get("savings_goal", "0").strip()
            update_user_profile(user_id, monthly_income=monthly_income, savings_goal=savings_goal)
            success = "Income and savings goal updated."

        elif action == "confirm_scanned_expense":
            amount = float(request.form.get("amount", 0))
            category = normalize_category(request.form.get("category", "Other"))
            log_date = request.form.get("log_date")
            note = request.form.get("note", "").strip()

            if is_future_date(log_date):
                error = "Future expense dates are not allowed."
            else:
                user = get_user_profile(user_id)
                if not user:
                    session.clear()
                    return redirect(url_for("login"))
                logs = get_user_logs(user_id)

                allowed, message = can_add_expense(amount, user.get("monthly_income", 0), logs)
                if not allowed:
                    error = message
                else:
                    add_expense(user_id, amount, category, log_date, note, "image")
                    session.pop("scan_preview", None)
                    scan_preview = None
                    success = "Scanned expense saved successfully."

        elif action == "discard_scanned_expense":
            session.pop("scan_preview", None)
            scan_preview = None
            success = "Scanned preview discarded."

        elif action == "add_expense":
            amount = float(request.form.get("amount", 0))
            category = normalize_category(request.form.get("category", "Other"))
            log_date = request.form.get("log_date")
            note = request.form.get("note", "").strip()

            if is_future_date(log_date):
                error = "Future expense dates are not allowed."
            else:
                user = get_user_profile(user_id)
                if not user:
                    session.clear()
                    return redirect(url_for("login"))
                logs = get_user_logs(user_id)

                allowed, message = can_add_expense(amount, user.get("monthly_income", 0), logs)
                if not allowed:
                    error = message
                else:
                    add_expense(user_id, amount, category, log_date, note, "manual")
                    success = "Expense added successfully."

        elif action == "voice_log":
            voice_text = request.form.get("voice_text", "").strip()
            parsed = parse_voice_expense(voice_text)

            if not parsed:
                error = "Could not understand the voice expense. Try a simpler sentence."
            else:
                amount = parsed["amount"]
                category = normalize_category(parsed["category"])
                log_date = parsed["log_date"]
                note = parsed.get("note", "Voice log")

                if is_future_date(log_date):
                    error = "Future expense dates are not allowed."
                else:
                    user = get_user_profile(user_id)
                    logs = get_user_logs(user_id)

                    allowed, message = can_add_expense(amount, user.get("monthly_income", 0), logs)
                    if not allowed:
                        error = message
                    else:
                        add_expense(user_id, amount, category, log_date, note, "voice")
                        success = "Voice expense logged successfully."

        elif action == "scan_expense_image":
            image = request.files.get("receipt_image")
            if not image or image.filename == "":
                error = "Please choose an image to scan."
            else:
                try:
                    parsed = scan_expense_from_image(image)
                    amount = float(parsed.get("amount", 0))
                    category = normalize_category(parsed.get("category", "Other"))
                    log_date = parsed.get("log_date") or str(date.today())
                    note = parsed.get("note", "Scanned receipt")

                    if is_future_date(log_date):
                        error = "Future expense dates are not allowed."
                    else:
                        session["scan_preview"] = {
                            "amount": round(amount, 2),
                            "category": category,
                            "log_date": log_date,
                            "note": note,
                        }
                        scan_preview = session.get("scan_preview")
                        success = "Scan complete. Please review and confirm before saving."

                except Exception:
                    error = "Image scan failed. Please try another image."

    user = get_user_profile(user_id)
    if not user:
        session.clear()
        return redirect(url_for("login"))
    logs = get_user_logs(user_id)
    metrics = compute_dashboard_metrics(user, logs)

    return render_template(
        "dashboard.html",
        error=error,
        success=success,
        metrics=metrics,
        monthly_income=user.get("monthly_income", 0),
        savings_goal=user.get("savings_goal", 0),
        today=str(date.today()),
        scan_preview=scan_preview,
    )


# -----------------------------
# Analysis
# -----------------------------
@app.route("/analysis")
def analysis():
    if not require_login():
        return redirect(url_for("login"))

    user_id = session["user_id"]

    from_date = request.args.get("from_date", "").strip()
    to_date = request.args.get("to_date", "").strip()
    category = request.args.get("category", "").strip()
    source = request.args.get("source", "").strip()

    logs = get_filtered_logs(
        user_id=user_id,
        from_date=from_date or None,
        to_date=to_date or None,
        category=category or None,
        source=source or None,
    )

    summary = compute_analysis_summary(logs)
    insights = get_financial_insights(summary, logs)

    trend_labels = [item["label"] for item in summary.get("trend", [])]
    trend_values = [item["value"] for item in summary.get("trend", [])]
    category_labels = [item["label"] for item in summary.get("category_breakdown", [])]
    category_values = [item["value"] for item in summary.get("category_breakdown", [])]

    return render_template(
        "analysis.html",
        logs=logs,
        summary=summary,
        insights=insights,
        trend_labels=trend_labels,
        trend_values=trend_values,
        category_labels=category_labels,
        category_values=category_values,
    )


# -----------------------------
# Profile
# -----------------------------
@app.route("/profile", methods=["GET", "POST"])
def profile():
    if not require_login():
        return redirect(url_for("login"))

    user_id = session["user_id"]
    error = None
    success = None

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update_profile":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip().lower()
            monthly_income = request.form.get("monthly_income", "0").strip()
            savings_goal = request.form.get("savings_goal", "0").strip()

            update_user_profile(
                user_id,
                username=username,
                email=email,
                monthly_income=monthly_income,
                savings_goal=savings_goal
            )
            session["username"] = username
            success = "Profile updated successfully."

        elif action == "change_password":
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")

            user = get_user_profile(user_id)
            if not user:
                session.clear()
                return redirect(url_for("login"))
            valid = verify_user_credentials(user["email"], current_password)

            if not valid:
                error = "Current password is incorrect."
            elif new_password != confirm_password:
                error = "New passwords do not match."
            else:
                update_user_password(user["email"], new_password)
                success = "Password updated successfully."

    user = get_user_profile(user_id)
    if not user:
        session.clear()
        return redirect(url_for("login"))
    return render_template("profile.html", user=user, error=error, success=success)


# -----------------------------
# Chatbot
# -----------------------------
@app.route("/chatbot", methods=["POST"])
def chatbot():
    if not require_login():
        return jsonify({"reply": "Please login first."}), 401

    user_id = session["user_id"]
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()

    user = get_user_profile(user_id)
    logs = get_user_logs(user_id)
    metrics = compute_dashboard_metrics(user, logs)

    if not message:
        return jsonify({"reply": "Please type a message."})

    try:
        reply = get_financial_insights(
            {
                "monthly_income": metrics.get("monthly_income", 0),
                "monthly_spend": metrics.get("monthly_spend", 0),
                "remaining_budget": metrics.get("remaining_budget", 0),
                "weekly_spend": metrics.get("weekly_spend", 0),
                "budget_used_percentage": metrics.get("budget_used_percentage", 0),
                "question": message,
            },
            logs,
            chat_mode=True
        )
        if isinstance(reply, list):
            reply = reply[0] if reply else "I could not generate an insight right now."
    except Exception:
        reply = (
            "Based on your current spending pattern, focus on keeping daily discretionary "
            "expenses lower and try to preserve more budget for the rest of the month."
        )

    return jsonify({"reply": reply})


if __name__ == "__main__":
    app.run(debug=True)
