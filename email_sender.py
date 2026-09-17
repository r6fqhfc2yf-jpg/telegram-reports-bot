# email_sender.py
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import os


async def send_email(
    sender_email, sender_password,
    target_email, subject, body,
    link=None, attachment_path=None
):
    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = target_email
        msg['Subject'] = subject

        full_body = body
        if link:
            full_body += f"\n\nLink: {link}"

        msg.attach(MIMEText(full_body, 'plain', 'utf-8'))

        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, 'rb') as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
            msg.attach(part)

        await aiosmtplib.send(
            msg,
            hostname="smtp.gmail.com",
            port=587,
            start_tls=True,
            username=sender_email,
            password=sender_password,
            timeout=15
        )
        return True, "sent"

    except Exception as e:
        return False, str(e)[:150]
