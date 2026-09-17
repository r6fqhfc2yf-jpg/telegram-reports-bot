# main.py
import logging
import asyncio
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from config import BOT_TOKEN
from database import (
    init_db, set_setting, get_setting,
    add_account, get_all_accounts,
    get_total_sent
)
from flood_engine import flood

logging.basicConfig(level=logging.INFO)

WAITING_EMAIL_ACC = 1
WAITING_PASS_ACC = 2
WAITING_TARGET = 3
WAITING_SUBJECT = 4
WAITING_BODY = 5
WAITING_LINK = 6
WAITING_ATTACHMENT = 7


def is_admin(update: Update):
    admin_id = get_setting("admin_id")
    return str(update.effective_user.id) == admin_id


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_setting("admin_id") is None:
        set_setting("admin_id", str(update.effective_user.id))
        await update.message.reply_text("Admin set.")

    if not is_admin(update):
        await update.message.reply_text("This bot is for the admin only.")
        return

    keyboard = [
        ["Add Account", "Accounts"],
        ["Target Email", "Message"],
        ["Start Flood", "Stop Flood"],
        ["Stats", "Help"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    text = f"""
Abuse Reporter Bot

Target: {get_setting('target_email', 'not set')}
Accounts: {len(get_all_accounts())}
Sent: {get_total_sent()}
Status: {'RUNNING' if flood.running else 'STOPPED'}
    """
    await update.message.reply_text(text, reply_markup=reply_markup)


async def add_acc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    await update.message.reply_text("Send the account email (or /cancel):")
    return WAITING_EMAIL_ACC


async def add_acc_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['acc_email'] = update.message.text.strip()
    await update.message.reply_text("Send the App Password:")
    return WAITING_PASS_ACC


async def add_acc_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    email = context.user_data.get('acc_email')
    if add_account(email, password):
        await update.message.reply_text(f"Added: {email}")
    else:
        await update.message.reply_text("Account already exists.")
    await start(update, context)
    return ConversationHandler.END


async def set_target_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    await update.message.reply_text("Send the target email (or /cancel):")
    return WAITING_TARGET


async def set_target_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_setting("target_email", update.message.text.strip())
    await update.message.reply_text("Target email saved.")
    await start(update, context)
    return ConversationHandler.END


async def set_message_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    await update.message.reply_text("Send the Subject:")
    return WAITING_SUBJECT


async def set_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_setting("subject", update.message.text.strip())
    await update.message.reply_text("Send the Body:")
    return WAITING_BODY


async def set_body(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_setting("body", update.message.text)
    await update.message.reply_text("Send the Link (or: no):")
    return WAITING_LINK


async def set_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    set_setting("link", "" if link == "no" else link)
    await update.message.reply_text("Send the Evidence (photo/file), or: no")
    return WAITING_ATTACHMENT


async def set_attachment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text and update.message.text.strip() == "no":
        set_setting("attachment", "")
        await update.message.reply_text("Saved without attachment.")
    elif update.message.document:
        file = await update.message.document.get_file()
        path = f"attachment_{update.message.document.file_name}"
        await file.download_to_drive(path)
        set_setting("attachment", path)
        await update.message.reply_text(f"Evidence saved: {path}")
    elif update.message.photo:
        file = await update.message.photo[-1].get_file()
        path = "attachment_photo.jpg"
        await file.download_to_drive(path)
        set_setting("attachment", path)
        await update.message.reply_text("Photo saved.")
    else:
        await update.message.reply_text("Send a photo/file or: no")
    await start(update, context)
    return ConversationHandler.END


async def start_flood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if flood.running:
        await update.message.reply_text("Already running!")
        return
    if not get_all_accounts():
        await update.message.reply_text("Add accounts first.")
        return
    asyncio.create_task(flood.start())
    await update.message.reply_text("Flood started!")


async def stop_flood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    flood.stop()
    await update.message.reply_text("Flood stopped.")


async def show_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    accounts = get_all_accounts()
    if not accounts:
        await update.message.reply_text("No accounts.")
        return
    text = f"Accounts ({len(accounts)}):\n\n"
    for acc in accounts:
        acc_id, email, active, sent, failed = acc
        status = "OK" if active else "DEAD"
        text += f"[{status}] {email} | sent:{sent} failed:{failed}\n"
    await update.message.reply_text(text)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    text = f"""
Stats

Target: {get_setting('target_email', 'not set')}
Total sent: {get_total_sent()}
Session success: {flood.sent_total}
Session failed: {flood.failed_total}
Status: {'RUNNING' if flood.running else 'STOPPED'}
    """
    await update.message.reply_text(text)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    await start(update, context)
    return ConversationHandler.END


async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Add Account":
        return await add_acc_start(update, context)
    elif text == "Target Email":
        return await set_target_start(update, context)
    elif text == "Message":
        return await set_message_start(update, context)
    elif text == "Accounts":
        return await show_accounts(update, context)
    elif text == "Start Flood":
        return await start_flood(update, context)
    elif text == "Stop Flood":
        return await stop_flood(update, context)
    elif text == "Stats":
        return await stats(update, context)
    elif text == "Help":
        await update.message.reply_text("Use the buttons to control.")


def main():
    print("Starting Abuse Reporter Bot...")
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    conv_add = ConversationHandler(
        entry_points=[CommandHandler("addaccount", add_acc_start)],
        states={
            WAITING_EMAIL_ACC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_acc_email)],
            WAITING_PASS_ACC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_acc_password)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    conv_target = ConversationHandler(
        entry_points=[CommandHandler("settarget", set_target_start)],
        states={WAITING_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_target_receive)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    conv_message = ConversationHandler(
        entry_points=[CommandHandler("setmessage", set_message_start)],
        states={
            WAITING_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_subject)],
            WAITING_BODY: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_body)],
            WAITING_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_link)],
            WAITING_ATTACHMENT: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, set_attachment),
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_attachment),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_add)
    app.add_handler(conv_target)
    app.add_handler(conv_message)
    app.add_handler(CommandHandler("listaccounts", show_accounts))
    app.add_handler(CommandHandler("startflood", start_flood))
    app.add_handler(CommandHandler("stopflood", stop_flood))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))

    print("Bot is running. Send /start on Telegram.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
