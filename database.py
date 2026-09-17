# database.py
import sqlite3
import datetime
from config import DATABASE_FILE


def init_db():
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT,
            active INTEGER DEFAULT 1,
            sent_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
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
        CREATE TABLE IF NOT EXISTS stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_email TEXT,
            target_email TEXT,
            status TEXT,
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


def add_account(email, password):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO accounts (email, password, added_at) VALUES (?, ?, ?)",
            (email, password, datetime.datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def get_active_accounts():
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("SELECT id, email, password FROM accounts WHERE active = 1")
    rows = c.fetchall()
    conn.close()
    return rows


def get_all_accounts():
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("SELECT id, email, active, sent_count, failed_count FROM accounts")
    rows = c.fetchall()
    conn.close()
    return rows


def mark_account_dead(email):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("UPDATE accounts SET active = 0 WHERE email = ?", (email,))
    conn.commit()
    conn.close()


def increment_sent(email):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("UPDATE accounts SET sent_count = sent_count + 1 WHERE email = ?", (email,))
    conn.commit()
    conn.close()


def increment_failed(email):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("UPDATE accounts SET failed_count = failed_count + 1 WHERE email = ?", (email,))
    conn.commit()
    conn.close()


def log_stat(account_email, target_email, status):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO stats (account_email, target_email, status, timestamp) VALUES (?, ?, ?, ?)",
        (account_email, target_email, status, datetime.datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_total_sent():
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM stats WHERE status = 'sent'")
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0
