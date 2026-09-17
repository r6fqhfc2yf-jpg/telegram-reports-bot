# main.py
import os
import logging
import asyncio
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from database import (
    init_db, set_setting, get_setting,
    get_all_numbers, get_recent_logs, get_total_reports
)
from session_manager import (
    send_code, verify_code, verify_password_2fa, cancel_pending
)
from report_engine import engine

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

WAITING_PHONE = 1
WAITING_CODE = 2
WAITING_2FA = 3
WAITING_REPORT_LINK = 4
WAITING_REPORT_REASON = 5
WAITING_REPORT_EVIDENCE = 6
WAITING_REPORT_COUNT = 7


def is_admin(update: Update):
    admin_id = get_setting("admin_id")
    return str(update.effective_user.id) == admin_id


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_setting("admin_id") is None:
        set_setting("admin_id", str(update.effective_user.id))
        await update.message.reply_text("Admin set.")

    if not is_admin(update):
        await update.message.reply_text("This bot is for admin only.")
        return

    keyboard = [
        ["Account", "Cronologia"],
        ["Nuovo Report", "Stop"],
        ["Statistiche", "Help"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    numbers = get_all_numbers()
    status = "RUNNING" if engine.running else "STOPPED"
    text = "Report Bot\n\nNumbers: " + str(len(numbers)) + "\nTotal: " + str(get_total_reports()) + "\nStatus: " + status
    await update.message.reply_text(text, reply_markup=reply_markup)


async def add_number_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.message.reply_text("Send phone number (+964xxx):\n/cancel to abort")
    return WAITING_PHONE


async def add_number_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not phone.startswith("+") or not phone[1:].isdigit():
        await update.message.reply_text("Invalid number. Try again:")
        return WAITING_PHONE

    await update.message.reply_text("Sending code...")
    success, status, extra = await send_code(phone)

    if success:
        context.user_data["pending_phone"] = phone
        await update.message.reply_text("Code sent. Check Telegram. Enter code:")
        return WAITING_CODE
    else:
        if status == "invalid_phone":
            await update.message.reply_text("Invalid phone.")
        elif status == "flood":
            await update.message.reply_text("FloodWait: " + str(extra) + "s")
        else:
            await update.message.reply_text("Error: " + str(extra))
        await start(update, context)
        return ConversationHandler.END


async def add_number_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    phone = context.user_data.get("pending_phone")

    if not phone:
        await update.message.reply_text("Session lost.")
        await start(update, context)
        return ConversationHandler.END

    success, status, extra = await verify_code(phone, code)

    if success:
        await update.message.reply_text("Login OK.\nName: " + str(extra) + "\nPhone: " + phone)
        await start(update, context)
        return ConversationHandler.END
    elif status == "needs_2fa":
        await update.message.reply_text("2FA password required:")
        return WAITING_2FA
    elif status == "invalid_code":
        await update.message.reply_text("Wrong code. Try again:")
        return WAITING_CODE
    else:
        await update.message.reply_text("Error: " + str(extra))
        await start(update, context)
        return ConversationHandler.END


async def add_number_2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    phone = context.user_data.get("pending_phone")
    success, status, extra = await verify_password_2fa(phone, password)
    if success:
        await update.message.reply_text("Login OK: " + str(extra))
    else:
        await update.message.reply_text("Error: " + str(extra))
    await start(update, context)
    return ConversationHandler.END


async def list_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    numbers = get_all_numbers()
    if not numbers:
        await update.message.reply_text("No numbers.")
        return
    text = "Numbers (" + str(len(numbers)) + "):\n\n"
    for num in numbers:
        num_id, phone, session, active, sent, failed = num
        status = "OK" if active else "DEAD"
        text += "[" + status + "] " + phone + " sent:" + str(sent) + " failed:" + str(failed) + "\n"
    await update.message.reply_text(text)


async def new_report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    if engine.running:
        await update.message.reply_text("Already running.")
        return ConversationHandler.END
    await update.message.reply_text("Send target link (@username or https://t.me/xxx):")
    return WAITING_REPORT_LINK


async def new_report_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["report_link"] = update.message.text.strip()
    await update.message.reply_text("Send reason (e.g. Child abuse):")
    return WAITING_REPORT_REASON


async def new_report_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["report_reason"] = update.message.text.strip()
    await update.message.reply_text("Send evidence message (or: no):")
    return WAITING_REPORT_EVIDENCE


async def new_report_evidence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    evidence = update.message.text.strip()
    context.user_data["report_evidence"] = "" if evidence == "no" else evidence
    await update.message.reply_text("How many reports per number? (1-50):")
    return WAITING_REPORT_COUNT


async def new_report_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text.strip())
        if count < 1 or count > 50:
            raise ValueError
    except:
        await update.message.reply_text("Enter number 1-50:")
        return WAITING_REPORT_COUNT

    link = context.user_data.get("report_link")
    reason = context.user_data.get("report_reason")
    evidence = context.user_data.get("report_evidence")

    await update.message.reply_text("Starting flood...")
    asyncio.create_task(engine.start(link, "other", reason + "\n\n" + evidence, count))
    await asyncio.sleep(1)
    await start(update, context)
    return ConversationHandler.END


async def cronologia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    logs = get_recent_logs(20)
    if not logs:
        await update.message.reply_text("No logs.")
        return
    text = "Recent 20:\n\n"
    for log in logs:
        phone, target, reason, status, ts = log
        icon = "OK" if status == "sent" else "FAIL"
        text += "[" + icon + "] " + phone + " -> " + target[:30] + "\n"
    await update.message.reply_text(text)


async def statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    status = "RUNNING" if engine.running else "STOPPED"
    text = "Stats\n\nTotal: " + str(get_total_reports()) + "\nSession OK: " + str(engine.sent_total) + "\nSession Failed: " + str(engine.failed_total) + "\nStatus: " + status
    await update.message.reply_text(text)


async def stop_flood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    engine.stop()
    await update.message.reply_text("Stopped.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/start\n/addnumber\n/listnumbers\n/cronologia\n/stats\n/cancel")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = context.user_data.get("pending_phone")
    if phone:
        cancel_pending(phone)
    await update.message.reply_text("Cancelled.")
    await start(update, context)
    return ConversationHandler.END


async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Account":
        await list_numbers(update, context)
    elif text == "Cronologia":
        await cronologia(update, context)
    elif text == "Nuovo Report":
        return await new_report_start(update, context)
    elif text == "Stop":
        await stop_flood(update, context)
    elif text == "Statistiche":
        await statistics(update, context)
    elif text == "Help":
        await help_command(update, context)


def main():
    print("Starting Report Bot...")
    init_db()

    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN not set!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    add_conv = ConversationHandler(
        entry_points=[CommandHandler("addnumber", add_number_start)],
        states={
            WAITING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_number_phone)],
            WAITING_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_number_code)],
            WAITING_2FA: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_number_2fa)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    report_conv = ConversationHandler(
        entry_points=[
            CommandHandler("newreport", new_report_start),
            MessageHandler(filters.Regex("^Nuovo Report$"), new_report_start),
        ],
        states={
            WAITING_REPORT_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_report_link)],
            WAITING_REPORT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_report_reason)],
            WAITING_REPORT_EVIDENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_report_evidence)],
            WAITING_REPORT_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_report_count)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("listnumbers", list_numbers))
    app.add_handler(CommandHandler("cronologia", cronologia))
    app.add_handler(CommandHandler("stats", statistics))
    app.add_handler(CommandHandler("stop", stop_flood))
    app.add_handler(add_conv)
    app.add_handler(report_conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))

    print("Bot is running.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
    ‏# update
