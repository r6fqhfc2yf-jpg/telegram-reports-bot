# report_engine.py
import asyncio
from telethon import TelegramClient, functions
from telethon.tl import types
from telethon.errors import (
    FloodWaitError,
    UserAlreadyParticipantError,
    ChannelPrivateError
)
from config import API_ID, API_HASH
from database import (
    get_active_numbers,
    increment_reports_sent,
    increment_reports_failed,
    mark_number_dead,
    log_action
)

# حالات الإبلاغ الرسمية في تيليجرام
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
        """
        target_link: رابط الكروب/القناة (مثل https://t.me/xxx)
        reason_key: child / violence / porn / spam / other
        custom_message: نص الدليل (رسالة المخالفة)
        reports_per_number: عدد البلاغات لكل رقم
        """
        self.running = True
        self.sent_total = 0
        self.failed_total = 0
        self.current_log = []

        numbers = get_active_numbers()

        if not numbers:
            self.current_log.append("❌ لا توجد أرقام نشطة.")
            self.running = False
            return

        for num in numbers:
            if not self.running:
                break

            num_id, phone, session_path = num

            self.current_log.append(f"🔄 معالجة الرقم: {phone}")

            for i in range(reports_per_number):
                if not self.running:
                    break

                success, msg = await self._do_report(
                    session_path, phone, target_link, reason_key, custom_message
                )

                if success:
                    self.sent_total += 1
                    increment_reports_sent(phone)
                    log_action(phone, target_link, reason_key, "sent", "")
                    self.current_log.append(f"✅ Report inviato con {phone}")
                else:
                    self.failed_total += 1
                    increment_reports_failed(phone)
                    log_action(phone, target_link, reason_key, "failed", msg)
                    self.current_log.append(f"❌ {phone} saltato: {msg[:80]}")

                # تأخير بسيط بين البلاغات
                await asyncio.sleep(2)

            # تأخير بين الأرقام
            await asyncio.sleep(3)

        self.current_log.append("✅ Coda completata.")
        self.running = False

    async def _do_report(self, session_path, phone, target_link, reason_key, custom_message):
        """تنفيذ الإبلاغ من رقم واحد"""
        client = TelegramClient(session_path, API_ID, API_HASH)

        try:
            await client.connect()

            # التحقق من تسجيل الدخول
            if not await client.is_user_authorized():
                await client.disconnect()
                mark_number_dead(phone)
                return False, "Not authorized"

            # جلب الكيان المستهدف
            try:
                entity = await client.get_entity(target_link)
            except Exception as e:
                await client.disconnect()
                return False, f"Target error: {str(e)[:80]}"

            # الحصول على آخر 5 رسائل للإبلاغ عنها
            messages = []
            try:
                async for msg in client.iter_messages(entity, limit=5):
                    messages.append(msg.id)
            except:
                pass

            if not messages:
                messages = [0]

            reason = REPORT_REASONS.get(reason_key, types.InputReportReasonOther())

            # إرسال الإبلاغ
            await client(functions.messages.ReportRequest(
                peer=entity,
                id=messages,
                reason=reason,
                message=custom_message or ""
            ))

            await client.disconnect()
            return True, "ok"

        except FloodWaitError as e:
            try:
                await client.disconnect()
            except:
                pass
            return False, f"FloodWait {e.seconds}s"

        except Exception as e:
            try:
                await client.disconnect()
            except:
                pass
            return False, str(e)[:100]

    def stop(self):
        self.running = False

    def get_log(self):
        return "\n".join(self.current_log[-30:])


# مثيل عام
engine = ReportEngine()
