# ENGINE_v5
# report_engine.py
import os
import re
import asyncio
from telethon import TelegramClient, functions
from telethon.tl import types
from telethon.errors import FloodWaitError, UserBannedInChannelError
from database import (
    get_active_numbers,
    increment_reports_sent,
    increment_reports_failed,
    mark_number_dead,
    delete_number_permanently,
    log_action,
    get_setting
)

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")


def parse_link(link):
    link = link.strip()
    match = re.match(r'https?://t\.me/([^/]+)/(\d+)', link)
    if match:
        return match.group(1), int(match.group(2))
    match = re.match(r'https?://t\.me/([^/]+)$', link)
    if match:
        return match.group(1), 0
    if link.startswith('@'):
        return link[1:], 0
    return link, 0


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
                admin_id = get_setting("admin_id")
                if admin_id:
                    await self.bot_app.bot.send_message(chat_id=int(admin_id), text=text)
            except:
                pass

    async def start(self, target_link, reason_key, custom_message, reports_per_number):
        await self.send_status("Starting reports...")
        self.running = True
        self.sent_total = 0
        self.failed_total = 0
        self.current_log = []

        channel, msg_id = parse_link(target_link)
        await self.send_status("Channel: " + channel + " | Msg: " + str(msg_id))

        numbers = get_active_numbers()
        if not numbers:
            await self.send_status("No active numbers.")
            self.running = False
            return

        await self.send_status("Numbers: " + str(len(numbers)))

        for num in numbers:
            if not self.running:
                break

            num_id, phone, session_path = num
            await self.send_status("Processing: " + phone)

            client = TelegramClient(session_path, API_ID, API_HASH)

            try:
                await client.connect()
                if not await client.is_user_authorized():
                    await self.send_status("Number BANNED, deleting: " + phone)
                    delete_number_permanently(phone)
                    await client.disconnect()
                    continue

                try:
                    entity = await client.get_entity(channel)
                    await self.send_status("Target found.")
                except Exception as e:
                    await self.send_status("Target error: " + str(e)[:200])
                    await client.disconnect()
                    self.running = False
                    return

                messages = []
                if msg_id > 0:
                    messages = [msg_id]
                else:
                    try:
                        async for msg in client.iter_messages(entity, limit=5):
                            messages.append(msg.id)
                    except:
                        pass
                    if not messages:
                        messages = [0]

                for i in range(reports_per_number):
                    if not self.running:
                        break
                    try:
                        m = messages[i % len(messages)]

                        await client(functions.messages.ReportRequest(
                            entity,
                            [m],
                            types.InputReportReasonChildAbuse(),
                            custom_message or ""
                        ))

                        self.sent_total += 1
                        increment_reports_sent(phone)
                        log_action(phone, target_link, reason_key, "sent", "")
                        await self.send_status("Report inviato con " + phone + " (#" + str(i + 1) + ")")

                        # تأخير 3.5 ثواني بين البلاغات
                        await asyncio.sleep(3.5)

                    except FloodWaitError as e:
                        await self.send_status("FloodWait " + str(e.seconds) + "s")
                        await asyncio.sleep(min(e.seconds, 300))

                    except UserBannedInChannelError:
                        await self.send_status("Number banned from channel, deleting: " + phone)
                        delete_number_permanently(phone)
                        break

                    except Exception as e:
                        err = str(e)[:200]
                        self.failed_total += 1
                        increment_reports_failed(phone)
                        log_action(phone, target_link, reason_key, "failed", err)
                        await self.send_status("Failed: " + err)

                await client.disconnect()

            except Exception as e:
                await self.send_status("Error: " + str(e)[:200])
                try:
                    await client.disconnect()
                except:
                    pass

        await self.send_status("Done. Success: " + str(self.sent_total) + " Failed: " + str(self.failed_total))
        self.running = False

    def stop(self):
        self.running = False


engine = ReportEngine()
