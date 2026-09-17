# report_engine.py
import os
import asyncio
from telethon import TelegramClient, functions
from telethon.tl import types
from telethon.errors import FloodWaitError
from database import (
    get_active_numbers,
    increment_reports_sent,
    increment_reports_failed,
    mark_number_dead,
    log_action
)

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")

REPORT_REASONS = {
    "child": types.InputReportReasonChildAbuse(),
    "violence": types.InputReportReasonViolence(),
    "porn": types.InputReportReasonPornography(),
    "spam": types.InputReportReasonSpam(),
    "other": types.InputReportReasonOther(),
}


class ReportEngine:
    def __init__(self):
        self.running = False
        self.sent_total = 0
        self.failed_total = 0
        self.current_log = []
        self.bot_app = None

    def set_bot(self, bot_app):
        self.bot_app = bot_app

    async def send_status(self, text):
        if self.bot_app:
            try:
                admin_id = None
                from database import get_setting
                admin_id = get_setting("admin_id")
                if admin_id:
                    await self.bot_app.bot.send_message(chat_id=int(admin_id), text=text)
            except Exception as e:
                print("Cannot send status: " + str(e))

    async def start(self, target_link, reason_key, custom_message, reports_per_number):
        await self.send_status("🚀 بدء الإبلاغ\nالرابط: " + target_link + "\nالعدد: " + str(reports_per_number))

        self.running = True
        self.sent_total = 0
        self.failed_total = 0
        self.current_log = []

        numbers = get_active_numbers()

        if not numbers:
            await self.send_status("❌ لا توجد أرقام نشطة.")
            self.running = False
            return

        await self.send_status("📱 عدد الأرقام: " + str(len(numbers)))

        for num in numbers:
            if not self.running:
                break

            num_id, phone, session_path = num
            await self.send_status("🔄 معالجة: " + phone)

            client = TelegramClient(session_path, API_ID, API_HASH)

            try:
                await client.connect()

                if not await client.is_user_authorized():
                    await self.send_status("❌ الرقم غير مصرح: " + phone)
                    mark_number_dead(phone)
                    await client.disconnect()
                    continue

                # محاولة الوصول للكيان
                try:
                    entity = await client.get_entity(target_link)
                    await self.send_status("✅ تم الوصول للكيان: " + str(getattr(entity, 'id', 'unknown')))
                except Exception as e:
                    err = str(e)
                    await self.send_status("❌ فشل في الوصول للكيان:\n" + err[:400])
                    await client.disconnect()
                    self.running = False
                    return

                reason = REPORT_REASONS.get(reason_key, types.InputReportReasonOther())

                # إرسال البلاغات
                for i in range(reports_per_number):
                    if not self.running:
                        break

                    try:
                        await client(functions.messages.ReportRequest(
                            peer=entity,
                            id=[0],
                            reason=reason,
                            message=custom_message or ""
                        ))

                        self.sent_total += 1
                        increment_reports_sent(phone)
                        log_action(phone, target_link, reason_key, "sent", "")
                        await self.send_status("✅ Report inviato con " + phone + " (#" + str(i + 1) + ")")
                        await asyncio.sleep(2)

                    except FloodWaitError as e:
                        await self.send_status("⚠️ FloodWait: " + str(e.seconds) + "s")
                        await asyncio.sleep(min(e.seconds, 300))

                    except Exception as e:
                        err = str(e)[:150]
                        self.failed_total += 1
                        increment_reports_failed(phone)
                        log_action(phone, target_link, reason_key, "failed", err)
                        await self.send_status("❌ فشل الإبلاغ:\n" + err)

                await client.disconnect()

            except Exception as e:
                await self.send_status("❌ خطأ عام:\n" + str(e)[:300])
                try:
                    await client.disconnect()
                except:
                    pass

        await self.send_status("✅ Coda completata.\nنجح: " + str(self.sent_total) + "\nفشل: " + str(self.failed_total))
        self.running = False

    def stop(self):
        self.running = False

    def get_log(self):
        return "\n".join(self.current_log[-50:])


engine = ReportEngine()
# UPDATE_v1
