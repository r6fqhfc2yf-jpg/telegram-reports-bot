Telegram Reports Bot

بوت تيليجرام لإرسال الإبلاغات والشكاوى

## الميزات

- ✅ إبلاغات 4 خطوات (صورة → موضوع → وصف → إيميل)
- ✅ تبليغ سبام سريع
- ✅ لوحة تحكم للمسؤولين
- ✅ إرسال إيميلات
- ✅ إدارة قاعدة بيانات

## التثبيت

```bash
pip install -r requirements.txt
```

## الإعدادات

حدث ملف `.env`:

```
BOT_TOKEN=your_bot_token
INITIAL_ADMINS=your_admin_id
DEFAULT_SENDER_EMAIL=your_email
DEFAULT_SENDER_PASSWORD=your_password
```

## التشغيل

```bash
python main.py
```

## المتطلبات

- Python 3.11+
- python-telegram-bot 20.1
- python-dotenv 1.0.0
