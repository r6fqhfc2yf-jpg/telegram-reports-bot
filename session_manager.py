# SESSION_v4
# session_manager.py
import os
import json
import asyncio
from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    FloodWaitError
)
from database import add_number

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
SESSIONS_FOLDER = "/app/data/sessions"
PENDING_FILE = "/app/data/pending_logins.json"


def ensure_sessions_folder():
    os.makedirs(SESSIONS_FOLDER, exist_ok=True)


def get_session_path(phone):
    phone_clean = phone.replace("+", "").replace(" ", "")
    return os.path.join(SESSIONS_FOLDER, phone_clean)


def save_pending(phone, data):
    try:
        if os.path.exists(PENDING_FILE):
            with open(PENDING_FILE, 'r') as f:
                all_data = json.load(f)
        else:
            all_data = {}
        all_data[phone] = data
        with open(PENDING_FILE, 'w') as f:
            json.dump(all_data, f)
    except Exception as e:
        print("Error saving pending: " + str(e))


def load_pending(phone):
    try:
        if os.path.exists(PENDING_FILE):
            with open(PENDING_FILE, 'r') as f:
                all_data = json.load(f)
            return all_data.get(phone)
    except Exception as e:
        print("Error loading pending: " + str(e))
    return None


def remove_pending(phone):
    try:
        if os.path.exists(PENDING_FILE):
            with open(PENDING_FILE, 'r') as f:
                all_data = json.load(f)
            if phone in all_data:
                del all_data[phone]
            with open(PENDING_FILE, 'w') as f:
                json.dump(all_data, f)
    except Exception as e:
        print("Error removing pending: " + str(e))


async def send_code(phone):
    ensure_sessions_folder()
    session_path = get_session_path(phone)

    client = TelegramClient(session_path, API_ID, API_HASH)
    await client.connect()

    try:
        sent = await client.send_code_request(phone)
        save_pending(phone, {
            "phone_code_hash": sent.phone_code_hash,
            "session_path": session_path
        })
        await client.disconnect()
        return True, "sent", None
    except PhoneNumberInvalidError:
        await client.disconnect()
        return False, "invalid_phone", None
    except FloodWaitError as e:
        await client.disconnect()
        return False, "flood", e.seconds
    except Exception as e:
        await client.disconnect()
        return False, "error", str(e)[:150]


async def verify_code(phone, code):
    data = load_pending(phone)
    if not data:
        return False, "not_started", None

    session_path = data["session_path"]
    phone_code_hash = data["phone_code_hash"]

    client = TelegramClient(session_path, API_ID, API_HASH)
    await client.connect()

    try:
        await client.sign_in(
            phone=phone,
            code=code,
            phone_code_hash=phone_code_hash
        )
        me = await client.get_me()
        await client.disconnect()

        add_number(phone, session_path)
        remove_pending(phone)

        return True, "ok", me.first_name

    except SessionPasswordNeededError:
        await client.disconnect()
        return False, "needs_2fa", None

    except PhoneCodeInvalidError:
        await client.disconnect()
        return False, "invalid_code", None

    except Exception as e:
        try:
            await client.disconnect()
        except:
            pass
        return False, "error", str(e)[:150]


async def verify_password_2fa(phone, password):
    data = load_pending(phone)
    if not data:
        return False, "not_started", None

    session_path = data["session_path"]

    client = TelegramClient(session_path, API_ID, API_HASH)
    await client.connect()

    try:
        await client.sign_in(password=password)
        me = await client.get_me()
        await client.disconnect()

        add_number(phone, session_path)
        remove_pending(phone)

        return True, "ok", me.first_name

    except Exception as e:
        try:
            await client.disconnect()
        except:
            pass
        return False, "error", str(e)[:150]


def cancel_pending(phone):
    remove_pending(phone)
