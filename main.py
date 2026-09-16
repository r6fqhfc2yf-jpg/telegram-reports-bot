import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import BOT_TOKEN
from database import init_db, add_report, get_reports
from email_sender import send_report_email

# إعداد السجلات لمتابعة حالة البوت
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# تهيئة قاعدة البيانات عند الإقلاع
try:
    init_db()
except Exception as e:
    logger.error(f"خطأ في تهيئة قاعدة البيانات: {e}")

async def start(update: Update, context):
    keyboard = [[
        {'text': '📝 إبلاغ جديد', 'callback_data': 'new_report'},
        {'text': '⚡ تبليغ سبام سريع', 'callback_data': 'quick_spam'}
    ], [
        {'text': '🔐 تسجيل دخول', 'callback_data': 'login'},
        {'text': '👤 بيانات حسابي', 'callback_data': 'profile'}
    ]]
    
    await update.message.reply_text(
        '👋 مرحباً بك في بوت الإبلاغات!\n\nاختر ما تريد:',
        reply_markup={'inline_keyboard': keyboard}
    )

async def button_handler(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'new_report':
        await query.edit_message_text('📸 أرسل صورة الدليل:')
    elif query.data == 'quick_spam':
        await query.edit_message_text('🔗 أرسل الرابط أو اسم المستخدم:')
    elif query.data == 'login':
        await query.edit_message_text('🔐 أرسل كلمة المرور:')
    elif query.data == 'profile':
        await query.edit_message_text('👤 بيانات حسابك:\n\nID: 82625635')

async def photo_handler(update: Update, context):
    await update.message.reply_text('✅ تم استقبال الصورة!\n\nالآن أرسل موضوع الإبلاغ:')

async def message_handler(update: Update, context):
    await update.message.reply_text('✅ تم استقبال الرسالة!\n\nشكراً على إبلاغك! سيتم النظر فيه قريباً.')

def main():
    token = BOT_TOKEN or os.getenv("BOT_TOKEN")
    if not token:
        logger.error("خطأ: لم يتم تعيين BOT_TOKEN نهائياً!")
        return

    # بناء التطبيق بالطريقة الرسمية الحديثة
    app = Application.builder().token(token).build()

    # تسجيل الهاندلرات (Handlers) الخاصة بك
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("✅ البوت يعمل الآن...")
    
    # التشغيل بالطريقة الثابتة التي تمنع إغلاق الحاوية
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
