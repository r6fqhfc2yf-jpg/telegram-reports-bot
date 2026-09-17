# main.py
import asyncio
import logging
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)
from config import BOT_TOKEN
from database import (
    init_db, set_setting, get_setting,
    get_all_numbers, get_recent_logs, get_total_reports, remove_number
)
from session_manager import send_code, verify_code, verify_password_2fa, cancel_pending
from report_engine import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# حالات المحادثة
WAIT_PHONE = 1
WAIT_CODE = 2
WAIT_2FA = 3
WAIT_TARGET = 4
WAIT_REASON = 5
WAIT_EVIDENCE = 6
WAIT_COUNT = 7


# ═══════════════════ صلاحيات ═══════════════════
def is_admin(update: Update):
    admin_id = get_setting("admin_id")
    user_id = str(update.effective_user.id)
    if admin_id is None:
        set_setting("admin_id", user_id)
        return True
    return user_id == admin_id


# ═══════════════════ لوحة التحكم ═══════════════════
async def show_main_menu(update_or_query, context):
    keyboard = [
        ["👤 Account", "📜 Cronologia"],
        ["➕ Nuovo Report", "📊 Stats"],
        ["❓ Help"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    total_reports = get_total_reports()
    accounts = get_all_numbers()
    active = len([n for n in accounts if n[3] == 1])

    text = (
        f"🤖 **Report Bot Manager**\n\n"
        f"👥 الأرقام المضافة: {len('accounts)}\n"
        f"🟢 النشطة: {active}\n"
        f"📤 إجمالي التقارير: {total_reports}\n"
        f"🔄 الحالة: {'🟢 يعمل' if engine.running else '🔴 متوقف}\n\n"
        f"اختر من القائمة:"
    )

    if hasattr(update_or_query, 'message') and update_or_query.message:
        await update_or_query.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update_or_query.edit_message_text(text, parse_mode="Markdown")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ هذا البوت خاص بالمدير فقط.")
        return
    await show_main_menu(update, context)


# ═══════════════════ /addnumber - إضافة رقم ═══════════════════
async def add_number_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    await update.message.reply_text(
        "📱 أرسل رقم الهاتف بالتنسيق الدولي:\n"
        "مثال: `+9647712345678`\n\n"
        "أو /cancel للإلغاء",
        parse_mode="Markdown"
    )
    return WAIT_PHONE


async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not phone.startswith("+") or not phone[1:].isdigit():
        await update.message.reply_text("❌ الرقم غير صحيح. يجب أن يبدأ بـ + ثم أرقام:")
        return WAIT_PHONE

    await update.message.reply_text(f"⏳ جاري إرسال الكود إلى {phone}...")

    success, status, info = await send_code(phone)

    if success:
        context.user_data['pending_phone'] = phone
        await update.message.reply_text(
            f"✅ تم إرسال كود التحقق إلى {phone}\n\n"
            f"📨 افتح تيليجرام (محادثة Telegram الرسمية) وانسخ الكود.\n\n"
            f"📝 أرسل الكود هنا:"
        )
        return WAIT_CODE
    else:
        if status == "invalid_phone":
            await update.message.reply_text("❌ رقم غير صحيح.")
        elif status == "flood":
            await update.message.reply_text(f"⚠️ Flood Wait: انتظر {info} ثانية.")
        else:
            await update.message.reply_text(f"❌ خطأ: {info}")
        return ConversationHandler.END


async def receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().replace(" ", "")
    phone = context.user_data.get('pending_phone')

    if not phone:
        await update.message.reply_text("❌ انتهت الجلسة. ابدأ من جديد.")
        return ConversationHandler.END

    await update.message.reply_text("⏳ جاري التحقق...")

    success, status, info = await verify_code(phone, code)

    if success:
        await update.message.reply_text(f"✅ تم تسجيل الدخول: {phone}\n👤 {info}")
        context.user_data.pop('pending_phone', None)
        await show_main_menu(update, context)
        return ConversationHandler.END

    elif status == "needs_2fa":
        await update.message.reply_text("🔐 الرقم عليه كلمة مرور 2FA.\n📝 أرسل كلمة المرور:")
        return WAIT_2FA

    elif status == "invalid_code":
        await update.message.reply_text("❌ الكود غير صحيح. أعد الإرسال:")
        return WAIT_CODE

    else:
        await update.message.reply_text(f"❌ خطأ: {info}")
        cancel_pending(phone)
        context.user_data.pop('pending_phone', None)
        return ConversationHandler.END


async def receive_2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    phone = context.user_data.get('pending_phone')

    success, status, info = await verify_password_2fa(phone, password)

    if success:
        await update.message.reply_text(f"✅ تم تسجيل الدخول: {phone}")
        context.user_data.pop('pending_phone', None)
        await show_main_menu(update, context)
    else:
        await update.message.reply_text(f"❌ خطأ: {info}")
        context.user_data.pop('pending_phone', None)

    return ConversationHandler.END


# ═══════════════════ /listnumbers ═══════════════════
async def list_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    numbers = get_all_numbers()

    if not numbers:
        await update.message.reply_text("📭 لا توجد أرقام مضافة.")
        return

    text = f"📋 **الأرقام ({len(numbers)})**\n\n"
    for num in numbers:
        num_id, phone, session_file, active, sent, failed = num
        status = "🟢" if active else "💀"
        text += f"{status} `{phone}` | ✅{sent} ❌{failed}\n"

    await update.message.reply_text(text, parse_mode="Markdown")


# ═══════════════════ /remove ═══════════════════
async def remove_number_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    numbers = get_all_numbers()
    if not numbers:
        await update.message.reply_text("📭 لا توجد أرقام.")
        return

    keyboard = []
    for num in numbers:
        keyboard.append([InlineKeyboardButton(num[1], callback_data=f"del_{num[1]}")])

    await update.message.reply_text(
        "🗑️ اختر الرقم للحذف:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def remove_number_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    phone = query.data.replace("del_", "")
    remove_number(phone)
    await query.edit_message_text(f"✅ تم حذف {phone}")


# ═══════════════════ /report - بلاغ جديد ═══════════════════
async def report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if engine.running:
        await update.message.reply_text("⚠️ هناك عملية إبلاغ قيد التنفيذ.")
        return

    await update.message.reply_text(
        "➕ **بلاغ جديد**\n\n"
        "🔗 أرسل رابط الكروب/القناة المستهدف:\n"
        "مثال: `https://t.me/xxx` أو `@username`\n\n"
        "/cancel للإلغاء",
        parse_mode="Markdown"
    )
    return WAIT_TARGET


async def receive_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.text.strip()
    context.user_data['target'] = target

    keyboard = [
        [InlineKeyboardButton("👶 Child Abuse", callback_data="reason_child")],
        [InlineKeyboardButton("💥 Violence", callback_data="reason_violence")],
        [InlineKeyboardButton("🔞 Pornography", callback_data="reason_porn")],
        [InlineKeyboardButton("📢 Spam", callback_data="reason_spam")],
        [InlineKeyboardButton("📝 Other", callback_data="reason_other")],
    ]

    await update.message.reply_text(
        "📋 **اختر سبب الإبلاغ:**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return WAIT_REASON


async def receive_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    reason = query.data.replace("reason_", "")
    context.user_data['reason'] = reason

    await query.edit_message_text(
        f"✅ السبب: {reason}\n\n"
        f"📝 أرسل نص الدليل (رسالة المخالفة):\n"
        f"أو /skip للتخطي"
    )
    return WAIT_EVIDENCE


async def receive_evidence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    evidence = update.message.text.strip()
    if evidence == "/skip":
        evidence = ""
    context.user_data['evidence'] = evidence

    await update.message.reply_text(
        "🔢 كم عدد البلاغات لكل رقم؟\n"
        "مثال: `1` أو `3` أو `5`"
    )
    return WAIT_COUNT


async def receive_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text.strip())
        if count < 1 or count > 50:
            raise ValueError
    except:
        await update.message.reply_text("❌ أرسل رقماً بين 1 و 50:")
        return WAIT_COUNT

    target = context.user_data.get('target')
    reason = context.user_data.get('reason')
    evidence = context.user_data.get('evidence', '')

    await update.message.reply_text(
        f"🚀 **بدء الإبلاغ**\n\n"
        f"🎯 الهدف: {target}\n"
        f"📋 السبب: {reason}\n"
        f"🔢 العدد: {count} لكل رقم\n\n"
        f"سيبدأ الإرسال الآن...",
        parse_mode="Markdown"
    )

    asyncio.create_task(engine.start(target, reason, evidence, count))

    context.user_data.clear()
    return ConversationHandler.END


# ═══════════════════ السجل ═══════════════════
async def show_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    logs = get_recent_logs(20)

    if not logs:
        await update.message.reply_text("📭 لا توجد سجلات.")
        return

    text = "📜 **آخر العمليات:**\n\n"
    for log in logs:
        phone, target, reason, status, ts = log
        icon = "✅" if status == "sent" else "❌"
        text += f"{icon} `{phone}` → {target[:20]}\n"

    await update.message.reply_text(text, parse_mode="Markdown")


# ═══════════════════ الإحصائيات ═══════════════════
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    total = get_total_reports()
    numbers = get_all_numbers()
    active = len([n for n in numbers if n[3] == 1])

    text = (
        f"📊 **الإحصائيات**\n\n"
        f"👥 الأرقام: {len(numbers)} (نشطة: {active})\n"
        f"📤 إجمالي البلاغات: {total}\n"
        f"🔄 الجلسة الحالية: ✅{engine.sent_total} ❌{engine.failed_total}\n"
        f"⚙️ الحالة: {'🟢 يعمل' if engine.running else '🔴 متوقف'}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ═══════════════════ إيقاف ═══════════════════
async def stop_engine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    engine.stop()
    await update.message.reply_text("🛑 تم إيقاف الإبلاغ.")


# ═══════════════════ إلغاء ═══════════════════
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = context.user_data.get('pending_phone')
    if phone:
        cancel_pending(phone)
    context.user_data.clear()
    await update.message.reply_text("✅ تم الإلغاء.")
    await show_main_menu(update, context)
    return ConversationHandler.END


# ═══════════════════ الأزرار النصية ═══════════════════
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "👤 Account":
        numbers = get_all_numbers()
        text_out = f"👤 **إدارة الحسابات**\n\nالأرقام المضافة: {len(numbers)}\n\n"
        text_out += "استخدم:\n/addnumber - إضافة رقم\n/listnumbers - عرض الأرقام\n/remove - حذف رقم"
        await update.message.reply_text(text_out, parse_mode="Markdown")
    elif text == "📜 Cronologia":
        await show_logs(update, context)
    elif text == "➕ Nuovo Report":
        return await report_start(update, context)
    elif text == "📊 Stats":
        await show_stats(update, context)
    elif text == "❓ Help":
        await update.message.reply_text(
            "📖 **الأوامر:**\n\n"
            "/addnumber - إضافة رقم\n"
            "/listnumbers - عرض الأرقام\n"
            "/remove - حذف رقم\n"
            "/report - بلاغ جديد\n"
            "/stop - إيقاف\n"
            "/cancel - إلغاء",
            parse_mode="Markdown"
        )


# ═══════════════════ التشغيل ═══════════════════
def main():
    print("🚀 بدء Report Bot Manager...")
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # محادثة إضافة رقم
    conv_add = ConversationHandler(
        entry_points=[
            CommandHandler("addnumber", add_number_start),
            MessageHandler(filters.Regex("^👤 Account$"), add_number_start) if False else CommandHandler("_never_", add_number_start)
        ],
        states={
            WAIT_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_phone)],
            WAIT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_code)],
            WAIT_2FA: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_2fa)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # محادثة بلاغ جديد
    conv_report = ConversationHandler(
        entry_points=[CommandHandler("report", report_start)],
        states={
            WAIT_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_target)],
            WAIT_REASON: [CallbackQueryHandler(receive_reason, pattern="^reason_")],
            WAIT_EVIDENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_evidence)],
            WAIT_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_count)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_add)
    app.add_handler(conv_report)
    app.add_handler(CommandHandler("listnumbers", list_numbers))
    app.add_handler(CommandHandler("remove", remove_number_start))
    app.add_handler(CallbackQueryHandler(remove_number_callback, pattern="^del_"))
    app.add_handler(CommandHandler("stop", stop_engine))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))

    print("✅ البوت يعمل. أرسل /start على تيليجرام.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
