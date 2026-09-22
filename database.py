# DB_v4
# database.py
import os
import sqlite3
import datetime

DATABASE_FILE = os.environ.get("DATABASE_FILE", "/app/data/database.db")


def init_db():
    # تأكد من وجود المجلد
    os.makedirs(os.path.dirname(DATABASE_FILE), exist_ok=True)
    
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE,
            session_file TEXT,
            active INTEGER DEFAULT 1,
            reports_sent INTEGER DEFAULT 0,
            reports_failed INTEGER DEFAULT 0,
            added_at TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT,
            target TEXT,
            reason TEXT,
            status TEXT,
            message TEXT,
            timestamp TEXT
        )
    ''')

    conn.commit()
    conn.close()


def set_setting(key, value):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def get_setting(key, default=None):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default


def add_number(phone, session_file):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO numbers (phone, session_file, added_at) VALUES (?, ?, ?)",
            (phone, session_file, datetime.datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def get_all_numbers():
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("SELECT id, phone, session_file, active, reports_sent, reports_failed FROM numbers ORDER BY id")
    rows = c.fetchall()
    conn.close()
    return rows


def get_active_numbers():
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("SELECT id, phone, session_file FROM numbers WHERE active = 1 ORDER BY id")
    rows = c.fetchall()
    conn.close()
    return rows


def remove_number(phone):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM numbers WHERE phone = ?", (phone,))
    conn.commit()
    conn.close()


def delete_number_permanently(phone):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM numbers WHERE phone = ?", (phone,))
    conn.commit()
    conn.close()


def mark_number_dead(phone):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("UPDATE numbers SET active = 0 WHERE phone = ?", (phone,))
    conn.commit()
    conn.close()


def increment_reports_sent(phone):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("UPDATE numbers SET reports_sent = reports_sent + 1 WHERE phone = ?", (phone,))
    conn.commit()
    conn.close()


def increment_reports_failed(phone):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("UPDATE numbers SET reports_failed = reports_failed + 1 WHERE phone = ?", (phone,))
    conn.commit()
    conn.close()


def log_action(phone, target, reason, status, message=""):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO logs (phone, target, reason, status, message, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (phone, target, reason, status, message, datetime.datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_recent_logs(limit=20):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("SELECT phone, target, reason, status, timestamp FROM logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows


def get_total_reports():
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM logs WHERE status = 'sent'")
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0
