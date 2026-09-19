# session_manager.py
import os
import asyncio
from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    FloodWaitError
)
from config import API_ID, API_HASH, SESSIONS_FOLDER
from database import add_number


# تخزين مؤقت لحالة تسجيل الدخول لكل رقم
pending_logins = {}


def ensure_sessions_folder():
    if not os.path.exists(SESSIONS_FOLDER):
        os.makedirs(SESSIONS_FOLDER)


def get_session_path(phone):
    phone_clean = phone.replace("+", "").replace(" ", "")
    return os.path.join(SESSIONS_FOLDER, phone_clean)


async def send_code(phone):
    """المرحلة 1: إرسال كود التحقق إلى الرقم"""
    ensure_sessions_folder()
    session_path = get_session_path(phone)

    client = TelegramClient(session_path, API_ID, API_HASH)
    await client.connect()

    try:
        sent = await client.send_code_request(phone)
        # حفظ الجلسة والكود في الذاكرة
        pending_logins[phone] = {
            "client": client,
            "phone_code_hash": sent.phone_code_hash,
            "session_path": session_path
        }
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
    """المرحلة 2: تأكيد الكود وتسجيل الدخول"""
    if phone not in pending_logins:
        return False, "not_started", None

    data = pending_logins[phone]
    client = data["client"]
    session_path = data["session_path"]

    try:
        await client.sign_in(
            phone=phone,
            code=code,
            phone_code_hash=data["phone_code_hash"]
        )
        me = await client.get_me()
        await client.disconnect()

        # حفظ الرقم في قاعدة البيانات
        add_number(phone, session_path)

        # إزالة من الذاكرة
        del pending_logins[phone]

        return True, "ok", me.first_name

    except SessionPasswordNeededError:
        # الرقم عليه كلمة مرور 2FA
        return False, "needs_2fa", None

    except PhoneCodeInvalidError:
        return False, "invalid_code", None

    except Exception as e:
        try:
            await client.disconnect()
        except:
            pass
        return False, "error", str(e)[:150]


async def verify_password_2fa(phone, password):
    """المرحلة 3 (اختيارية): كلمة مرور 2FA"""
    if phone not in pending_logins:
        return False, "not_started", None

    data = pending_logins[phone]
    client = data["client"]
    session_path = data["session_path"]

    try:
        await client.sign_in(password=password)
        me = await client.get_me()
        await client.disconnect()

        add_number(phone, session_path)
        del pending_logins[phone]

        return True, "ok", me.first_name

    except Exception as e:
        try:
            await client.disconnect()
        except:
            pass
        return False, "error", str(e)[:150]


def cancel_pending(phone):
    """إلغاء عملية تسجيل معلقة"""
    if phone in pending_logins:
        try:
            asyncio.create_task(pending_logins[phone]["client"].disconnect())
        except:
            pass
        del pending_logins[phone]
# BOT_v2
