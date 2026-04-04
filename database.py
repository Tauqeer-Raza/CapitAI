import sqlite3
from datetime import datetime, timedelta

DB_NAME = "finance_app.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            monthly_income REAL DEFAULT 0,
            savings_goal REAL DEFAULT 0,
            email_verified INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            log_date TEXT NOT NULL,
            note TEXT,
            source TEXT DEFAULT 'manual',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS otp_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            otp_code TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            is_used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


# -----------------------------
# User/Auth
# -----------------------------
def create_user(username, email, password):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (username, email, password)
        VALUES (?, ?, ?)
    """, (username, email, password))
    conn.commit()
    conn.close()


def get_user_by_email(email):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def verify_user_credentials(email, password):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM users
        WHERE email = ? AND password = ?
    """, (email, password))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def mark_email_verified(email):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET email_verified = 1
        WHERE email = ?
    """, (email,))
    conn.commit()
    conn.close()


def update_user_password(email, new_password):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET password = ?
        WHERE email = ?
    """, (new_password, email))
    conn.commit()
    conn.close()


def update_user_profile(user_id, username=None, email=None, monthly_income=None, savings_goal=None):
    conn = get_connection()
    cur = conn.cursor()

    existing = get_user_profile(user_id)
    if not existing:
        conn.close()
        return

    final_username = username if username is not None else existing["username"]
    final_email = email if email is not None else existing["email"]
    final_income = float(monthly_income) if monthly_income not in (None, "") else float(existing["monthly_income"] or 0)
    final_goal = float(savings_goal) if savings_goal not in (None, "") else float(existing["savings_goal"] or 0)

    cur.execute("""
        UPDATE users
        SET username = ?, email = ?, monthly_income = ?, savings_goal = ?
        WHERE id = ?
    """, (final_username, final_email, final_income, final_goal, user_id))

    conn.commit()
    conn.close()


def get_user_profile(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


# -----------------------------
# OTP
# -----------------------------
def store_otp(email, otp_code, expiry_minutes=10):
    conn = get_connection()
    cur = conn.cursor()

    expires_at = (datetime.now() + timedelta(minutes=expiry_minutes)).isoformat()

    cur.execute("""
        INSERT INTO otp_codes (email, otp_code, expires_at, is_used)
        VALUES (?, ?, ?, 0)
    """, (email, otp_code, expires_at))

    conn.commit()
    conn.close()


def verify_otp_code(email, otp_code):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM otp_codes
        WHERE email = ? AND otp_code = ? AND is_used = 0
        ORDER BY id DESC
        LIMIT 1
    """, (email, otp_code))
    row = cur.fetchone()

    if not row:
        conn.close()
        return False

    row = dict(row)
    expires_at = datetime.fromisoformat(row["expires_at"])

    if datetime.now() > expires_at:
        conn.close()
        return False

    cur.execute("""
        UPDATE otp_codes
        SET is_used = 1
        WHERE id = ?
    """, (row["id"],))
    conn.commit()
    conn.close()
    return True


# -----------------------------
# Expenses
# -----------------------------
def add_expense(user_id, amount, category, log_date, note="", source="manual"):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO expenses (user_id, amount, category, log_date, note, source)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, float(amount), category, log_date, note, source))
    conn.commit()
    conn.close()


def get_user_logs(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM expenses
        WHERE user_id = ?
        ORDER BY log_date DESC, id DESC
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_filtered_logs(user_id, from_date=None, to_date=None, category=None, source=None):
    conn = get_connection()
    cur = conn.cursor()

    query = "SELECT * FROM expenses WHERE user_id = ?"
    params = [user_id]

    if from_date:
        query += " AND log_date >= ?"
        params.append(from_date)

    if to_date:
        query += " AND log_date <= ?"
        params.append(to_date)

    if category:
        query += " AND category = ?"
        params.append(category)

    if source:
        query += " AND source = ?"
        params.append(source)

    query += " ORDER BY log_date DESC, id DESC"

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]