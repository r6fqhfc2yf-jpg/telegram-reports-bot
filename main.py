# UPDATE_v10
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
    get_all_numbers, get_recent_logs, get_total_reports,
    add_email, get_all_emails, remove_email
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
WAITING_EMAIL_ADD = 10
WAITING_TARGET_EMAIL = 11


def is_admin(update: Update):
    admin_id = get_setting("admin_id")
    return str(update.effective_user.id) == admin_id


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_setting("admin_id") is None:
        set_setting("admin_id", str(update.effective_user.id))
        await update.message.reply_text("تم تعيين المسؤول.")

    if not is_admin(update):
        await update.message.reply_text("هذا البوت للمدير فقط.")
        return

    keyboard = [
        ["Account", "Cronologia"],
        ["Nuovo Report", "Stop"],
        ["Statistiche", "Help"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    numbers = get_all_numbers()
    emails = get_all_emails()
    status = "RUNNING" if engine.running else "STOPPED"
    text = "روبوت الإبلاغ\n\nالأرقام: " + str(len(numbers)) + "\nالإيميلات: " + str(len(emails)) + "\nالمجموع: " + str(get_total_reports()) + "\nالحالة: " + status
    await update.message.reply_text(text, reply_markup=reply_markup)


# ===== أوامر الأرقام =====
async def add_number_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.message.reply_text("أرسل رقم الهاتف (+964xxx):\n/cancel للإلغاء")
    return WAITING_PHONE


async def add_number_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not phone.startswith("+") or not phone[1:].isdigit():
        await update.message.reply_text("رقم غير صالح. حاول مرة أخرى:")
        return WAITING_PHONE

    await update.message.reply_text("إرسال الكود...")
    success, status, extra = await send_code(phone)

    if success:
        context.user_data["pending_phone"] = phone
        await update.message.reply_text("تم إرسال الكود. تحقق من تيليجرام. أدخل الكود:")
        return WAITING_CODE
    else:
        if status == "invalid_phone":
            await update.message.reply_text("رقم غير صالح.")
        elif status == "flood":
            await update.message.reply_text("FloodWait: " + str(extra) + "s")
        else:
            await update.message.reply_text("خطأ: " + str(extra))
        await start(update, context)
        return ConversationHandler.END


async def add_number_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    phone = context.user_data.get("pending_phone")

    if not phone:
        await update.message.reply_text("انتهت الجلسة.")
        await start(update, context)
        return ConversationHandler.END

    success, status, extra = await verify_code(phone, code)

    if success:
        await update.message.reply_text("تم تسجيل الدخول.\nالاسم: " + str(extra) + "\nالرقم: " + phone)
        await start(update, context)
        return ConversationHandler.END
    elif status == "needs_2fa":
        await update.message.reply_text("كلمة مرور 2FA مطلوبة:")
        return WAITING_2FA
    elif status == "invalid_code":
        await update.message.reply_text("كود خطأ. حاول مرة أخرى:")
        return WAITING_CODE
    else:
        await update.message.reply_text("خطأ: " + str(extra))
        await start(update, context)
        return ConversationHandler.END


async def add_number_2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    phone = context.user_data.get("pending_phone")
    success, status, extra = await verify_password_2fa(phone, password)
    if success:
        await update.message.reply_text("تم تسجيل الدخول: " + str(extra))
    else:
        await update.message.reply_text("خطأ: " + str(extra))
    await start(update, context)
    return ConversationHandler.END


async def list_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    numbers = get_all_numbers()
    if not numbers:
        await update.message.reply_text("لا توجد أرقام.")
        return
    text = "الأرقام (" + str(len(numbers)) + "):\n\n"
    for num in numbers:
        num_id, phone, session, active, sent, failed = num
        status = "OK" if active else "DEAD"
        text += "[" + status + "] " + phone + " sent:" + str(sent) + " failed:" + str(failed) + "\n"
    await update.message.reply_text(text)


async def new_report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    if engine.running:
        await update.message.reply_text("يعمل بالفعل.")
        return ConversationHandler.END
    await update.message.reply_text("أرسل رابط الهدف (@username أو https://t.me/xxx):")
    return WAITING_REPORT_LINK


async def new_report_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["report_link"] = update.message.text.strip()
    await update.message.reply_text("أرسل السبب (مثل: Child abuse):")
    return WAITING_REPORT_REASON


async def new_report_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["report_reason"] = update.message.text.strip()
    await update.message.reply_text("أرسل رسالة الإثبات (أو: لا):")
    return WAITING_REPORT_EVIDENCE


async def new_report_evidence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    evidence = update.message.text.strip()
    context.user_data["report_evidence"] = "" if evidence == "لا" else evidence
    await update.message.reply_text("كم بلاغاً لكل رقم؟ (1-1000):")
    return WAITING_REPORT_COUNT


async def new_report_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text.strip())
        if count < 1 or count > 1000:
            raise ValueError
    except:
        await update.message.reply_text("أدخل رقماً بين 1 و 1000:")
        return WAITING_REPORT_COUNT

    link = context.user_data.get("report_link")
    reason = context.user_data.get("report_reason")
    evidence = context.user_data.get("report_evidence")

    await update.message.reply_text("بدء الفيضان...")
    asyncio.create_task(engine.start(link, "other", reason + "\n\n" + evidence, count))
    await asyncio.sleep(1)
    await start(update, context)
    return ConversationHandler.END


async def cronologia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    logs = get_recent_logs(20)
    if not logs:
        await update.message.reply_text("لا يوجد سجل.")
        return
    text = "آخر 20 عملية:\n\n"
    for log in logs:
        phone, target, reason, status, ts = log
        icon = "OK" if status == "sent" else "FAIL"
        text += "[" + icon + "] " + phone + " -> " + target[:30] + "\n"
    await update.message.reply_text(text)


async def statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    status = "RUNNING" if engine.running else "STOPPED"
    emails = get_all_emails()
    text = "إحصائيات\n\nالإجمالي: " + str(get_total_reports()) + "\nناجح: " + str(engine.sent_total) + "\nفاشل: " + str(engine.failed_total) + "\nالإيميلات: " + str(len(emails)) + "\nالحالة: " + status
    await update.message.reply_text(text)


async def stop_flood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    engine.stop()
    await update.message.reply_text("تم الإيقاف.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start\n/addnumber\n/listnumbers\n/cronologia\n/stats\n/cancel\n\n"
        "/addemail - إضافة إيميلات\n/listemails - عرض الإيميلات\n/setemail - تحديد بريد الدعم\n/removeemail - حذف إيميل"
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = context.user_data.get("pending_phone")
    if phone:
        cancel_pending(phone)
    await update.message.reply_text("تم الإلغاء.")
    await start(update, context)
    return ConversationHandler.END


# ===== أوامر الإيميلات =====
async def add_email_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.message.reply_text(
        "أرسل الإيميلات بهذا الشكل (كل إيميل في سطر):\n\n"
        "email@example.com:password\n"
        "email2@gmail.com:app password\n\n"
        "/cancel للإلغاء"
    )
    return WAITING_EMAIL_ADD


async def add_email_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    lines = text.split("\n")

    added = 0
    failed = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if ":" in line:
            parts = line.split(":", 1)
        elif " " in line:
            parts = line.split(" ", 1)
        else:
            failed += 1
            continue

        email = parts[0].strip()
        password = parts[1].strip()

        if "@" not in email:
            failed += 1
            continue

        if add_email(email, password):
            added += 1
        else:
            failed += 1

    await update.message.reply_text(
        "✅ تم إضافة الإيميلات:\n"
        "المضاف: " + str(added) + "\n"
        "الفاشل/الموجود: " + str(failed)
    )
    await start(update, context)
    return ConversationHandler.END


async def set_target_email_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    current = get_setting("target_email", "abuse@telegram.org")
    await update.message.reply_text("الحالي: " + current + "\n\nأرسل بريد الدعم الجديد:")
    return WAITING_TARGET_EMAIL


async def set_target_email_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.text.strip()
    set_setting("target_email", target)
    await update.message.reply_text("تم تحديد بريد الدعم: " + target)
    await start(update, context)
    return ConversationHandler.END


async def list_emails(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    emails = get_all_emails()
    if not emails:
        await update.message.reply_text("لا توجد إيميلات.")
        return
    text = "الإيميلات (" + str(len(emails)) + "):\n\n"
    for em in emails:
        em_id, em_addr, active, sent, failed = em
        status = "OK" if active else "DEAD"
        text += "[" + status + "] " + em_addr + " sent:" + str(sent) + " failed:" + str(failed) + "\n"
    await update.message.reply_text(text)


async def remove_email_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    args = context.args
    if not args:
        await update.message.reply_text("الاستخدام: /removeemail email@example.com")
        return
    remove_email(args[0])
    await update.message.reply_text("تم الحذف: " + args[0])


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

    email_conv = ConversationHandler(
        entry_points=[CommandHandler("addemail", add_email_start)],
        states={
            WAITING_EMAIL_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_email_receive)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    target_email_conv = ConversationHandler(
        entry_points=[CommandHandler("setemail", set_target_email_start)],
        states={
            WAITING_TARGET_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_target_email_receive)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("listnumbers", list_numbers))
    app.add_handler(CommandHandler("cronologia", cronologia))
    app.add_handler(CommandHandler("stats", statistics))
    app.add_handler(CommandHandler("stop", stop_flood))
    app.add_handler(CommandHandler("listemails", list_emails))
    app.add_handler(CommandHandler("removeemail", remove_email_cmd))
    app.add_handler(add_conv)
    app.add_handler(report_conv)
    app.add_handler(email_conv)
    app.add_handler(target_email_conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))

    engine.set_bot(app)
    print("Bot is running.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
