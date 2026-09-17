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
        self.progress_message = ""

    async def start(self, target_link, reason_key, custom_message, reports_per_number):
        self.running = True
        self.sent_total = 0
        self.failed_total = 0
        self.current_log = []

        numbers = get_active_numbers()

        if not numbers:
            self.current_log.append("No active numbers.")
            self.running = False
            return

        # جمع رسائل القناة مرة واحدة
        try:
            temp_client = TelegramClient("temp_session", API_ID, API_HASH)
            await temp_client.connect()
            entity = await temp_client.get_entity(target_link)

            all_messages = []
            async for msg in temp_client.iter_messages(entity, limit=5000):
                all_messages.append(msg.id)

            await temp_client.disconnect()

            if not all_messages:
                all_messages = [0]

            self.current_log.append("Found " + str(len(all_messages)) + " messages to report.")

        except Exception as e:
            self.current_log.append("Cannot read target: " + str(e)[:100])
            self.running = False
            return

        # لكل رقم
        for num in numbers:
            if not self.running:
                break

            num_id, phone, session_path = num
            self.current_log.append("Processing: " + phone)

            client = TelegramClient(session_path, API_ID, API_HASH)

            try:
                await client.connect()

                if not await client.is_user_authorized():
                    mark_number_dead(phone)
                    self.current_log.append("Dead: " + phone)
                    await client.disconnect()
                    continue

                entity = await client.get_entity(target_link)
                reason = REPORT_REASONS.get(reason_key, types.InputReportReasonOther())

                # إرسال 1000 بلاغ من هذا الرقم
                for i in range(reports_per_number):
                    if not self.running:
                        break

                    # اختيار رسالة عشوائية من القائمة
                    msg_id = all_messages[i % len(all_messages)]

                    try:
                        await client(functions.messages.ReportRequest(
                            peer=entity,
                            id=[msg_id],
                            reason=reason,
                            message=custom_message or ""
                        ))

                        self.sent_total += 1
                        increment_reports_sent(phone)
                        log_action(phone, target_link, reason_key, "sent", "")

                        # إشعار
                        self.current_log.append("✅ Report inviato con " + phone + " (#" + str(i + 1) + ")")
                        print("✅ Report inviato con " + phone)

                        # تأخير بين البلاغات
                        await asyncio.sleep(1.5)

                    except FloodWaitError as e:
                        self.current_log.append("⚠️ FloodWait " + str(e.seconds) + "s on " + phone)
                        print("⚠️ FloodWait: " + str(e.seconds) + "s")
                        await asyncio.sleep(min(e.seconds, 300))

                    except Exception as e:
                        err = str(e)[:80]
                        self.failed_total += 1
                        increment_reports_failed(phone)
                        log_action(phone, target_link, reason_key, "failed", err)
                        self.current_log.append("❌ " + phone + " saltato: " + err)
                        print("❌ " + phone + ": " + err)

                await client.disconnect()

            except Exception as e:
                try:
                    await client.disconnect()
                except:
                    pass
                self.current_log.append("Error with " + phone + ": " + str(e)[:80])

        self.current_log.append("✅ Coda completata.")
        self.running = False

    def stop(self):
        self.running = False

    def get_log(self):
        return "\n".join(self.current_log[-50:])


engine = ReportEngine()
#update
