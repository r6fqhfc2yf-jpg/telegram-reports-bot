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

    async def start(self, target_link, reason_key, custom_message, reports_per_number):
        print("=== ENGINE START ===")
        print("TARGET: " + target_link)
        print("REPORTS PER NUMBER: " + str(reports_per_number))

        self.running = True
        self.sent_total = 0
        self.failed_total = 0
        self.current_log = []

        numbers = get_active_numbers()

        if not numbers:
            self.current_log.append("No active numbers.")
            print("NO ACTIVE NUMBERS")
            self.running = False
            return

        print("NUMBERS FOUND: " + str(len(numbers)))

        for num in numbers:
            if not self.running:
                break

            num_id, phone, session_path = num
            print("=== PROCESSING: " + phone + " ===")
            self.current_log.append("Processing: " + phone)

            client = TelegramClient(session_path, API_ID, API_HASH)

            try:
                await client.connect()
                print("CONNECTED: " + phone)

                if not await client.is_user_authorized():
                    print("NOT AUTHORIZED: " + phone)
                    mark_number_dead(phone)
                    self.current_log.append("Dead: " + phone)
                    await client.disconnect()
                    continue

                print("AUTHORIZED: " + phone)

                # محاولة الوصول للكيان
                try:
                    entity = await client.get_entity(target_link)
                    print("ENTITY FOUND: " + str(entity.id))
                except Exception as e:
                    print("ERROR IN get_entity: " + str(e))
                    self.current_log.append("Cannot find target: " + str(e)[:80])
                    await client.disconnect()
                    self.running = False
                    return

                reason = REPORT_REASONS.get(reason_key, types.InputReportReasonOther())

                # إرسال البلاغات
                for i in range(reports_per_number):
                    if not self.running:
                        break

                    try:
                        # إرسال ReportRequest
                        await client(functions.messages.ReportRequest(
                            peer=entity,
                            id=[0],
                            reason=reason,
                            message=custom_message or ""
                        ))

                        self.sent_total += 1
                        increment_reports_sent(phone)
                        log_action(phone, target_link, reason_key, "sent", "")

                        print("✅ Report inviato con " + phone + " (#" + str(i + 1) + ")")
                        self.current_log.append("✅ Report inviato con " + phone)

                        await asyncio.sleep(2)

                    except FloodWaitError as e:
                        print("⚠️ FloodWait: " + str(e.seconds) + "s")
                        self.current_log.append("⚠️ FloodWait " + str(e.seconds) + "s")
                        await asyncio.sleep(min(e.seconds, 300))

                    except Exception as e:
                        err = str(e)[:80]
                        self.failed_total += 1
                        increment_reports_failed(phone)
                        log_action(phone, target_link, reason_key, "failed", err)
                        print("❌ ERROR: " + err)
                        self.current_log.append("❌ " + phone + ": " + err)

                await client.disconnect()
                print("DISCONNECTED: " + phone)

            except Exception as e:
                print("BIG ERROR: " + str(e))
                try:
                    await client.disconnect()
                except:
                    pass
                self.current_log.append("Error with " + phone + ": " + str(e)[:80])

        self.current_log.append("✅ Coda completata.")
        print("=== ENGINE END ===")
        self.running = False

    def stop(self):
        self.running = False

    def get_log(self):
        return "\n".join(self.current_log[-50:])


engine = ReportEngine()
FORCE_UPDATE#
