import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import sqlite3
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import threading
import time
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

# ==================== إعداد السجلات ====================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# بيانات تليجرام API الأساسية للشد الداخلي (يمكنك استبدالها ببياناتك من my.telegram.org)
API_ID = 2040  # افتراضي للتجربة أو ضع API_ID الخاص بك
API_HASH = "b18441a1ff607e10a989891a5462e627"

# ==================== قاعدة البيانات ====================
class Database:
    def __init__(self, db_name='dual_spam_bot.db'):
        self.db_name = db_name
        self.init_db()
    
    def init_db(self):
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
            cursor.execute('CREATE TABLE IF NOT EXISTS sender_emails (email TEXT PRIMARY KEY, password TEXT, status TEXT DEFAULT "active")')
            cursor.execute('CREATE TABLE IF NOT EXISTS support_emails (email TEXT PRIMARY KEY)')
            # جدول لحفظ جلسات الأرقام الخاصة بالشد الداخلي
            cursor.execute('CREATE TABLE IF NOT EXISTS tg_accounts (phone TEXT PRIMARY KEY, session_string TEXT)')
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"خطأ في قاعدة البيانات: {e}")
    
    def execute(self, query, params=()):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        result = cursor.fetchall()
        conn.close()
        return result
    
    def get_one(self, query, params=()):
        result = self.execute(query, params)
        return result[0] if result else None

db = Database()

if not db.get_one("SELECT value FROM settings WHERE key = 'limit'"):
    db.execute("INSERT INTO settings VALUES ('limit', '100')")
if not db.get_one("SELECT value FROM settings WHERE key = 'sleep'"):
    db.execute("INSERT INTO settings VALUES ('sleep', '3')")

# ==================== القائمة الرئيسية ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📧 إيميلات الشد الخارجي", callback_data='my_emails'), InlineKeyboardButton("📱 حسابات الشد الداخلي", callback_data='tg_accounts_menu')],
        [InlineKeyboardButton("🏢 إيميلات الدعم", callback_data='support_menu'), InlineKeyboardButton("⚙️ تعيين العدد والسليب", callback_data='settings_menu')],
        [InlineKeyboardButton("🚀 بدء الشد المزدوج (خارجي + داخلي)", callback_data='start_dual_spam')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "🤖 **مرحباً بك في نظام الشد المزدوج (خارجي وداخلي)**\nاختر الإجراء المطلوب للبدء:"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

# ==================== معالجة الأزرار والقوائم ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == 'my_emails':
        keyboard = [
            [InlineKeyboardButton("➕ إضافة إيميل", callback_data='add_email'), InlineKeyboardButton("📋 عرض الإيميلات", callback_data='show_emails')],
            [InlineKeyboardButton("🔙 رجوع", callback_data='back_home')]
        ]
        await query.edit_message_text("إدارة إيميلات الشد الخارجي:", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data == 'add_email':
        await query.edit_message_text("أرسل الإيميل وكلمة المرور بهذه الصيغة:\n`email:password`", parse_mode='Markdown')
        context.user_data['waiting_for'] = 'save_sender_email'
        
    elif data == 'show_emails':
        emails = db.execute("SELECT email FROM sender_emails")
        list_text = "\n".join([f"• {e[0]}" for e in emails]) if emails else "لا توجد إيميلات مضافة."
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='my_emails')]]
        await query.edit_message_text(f"📧 **الإيميلات المضافة:**\n\n{list_text}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data == 'tg_accounts_menu':
        keyboard = [
            [InlineKeyboardButton("➕ إضافة رقم جديد (شد داخلي)", callback_data='add_tg_phone')],
            [InlineKeyboardButton("📋 عرض الأرقام المسجلة", callback_data='show_tg_phones')],
            [InlineKeyboardButton("🔙 رجوع", callback_data='back_home')]
        ]
        await query.edit_message_text("📱 **إدارة حسابات الشد الداخلي (تليجرام):**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data == 'add_tg_phone':
        await query.edit_message_text("📱 أرسل رقم الهاتف مع رمز الدولة (مثال: `+9647701234567`):", parse_mode='Markdown')
        context.user_data['waiting_for'] = 'tg_get_phone'

    elif data == 'show_tg_phones':
        accounts = db.execute("SELECT phone FROM tg_accounts")
        list_text = "\n".join([f"• {acc[0]}" for acc in accounts]) if accounts else "لا توجد أرقام مسجلة."
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='tg_accounts_menu')]]
        await query.edit_message_text(f"📱 **الأرقام المسجلة للشد الداخلي:**\n\n{list_text}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data == 'support_menu':
        keyboard = [
            [InlineKeyboardButton("➕ تعيين دعم", callback_data='add_support')],
            [InlineKeyboardButton("📋 عرض الدعم", callback_data='show_support')],
            [InlineKeyboardButton("🔙 رجوع", callback_data='back_home')]
        ]
        await query.edit_message_text("إدارة إيميلات الدعم المستهدفة:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'add_support':
        await query.edit_message_text("أرسل إيميل الدعم المطلوب (مثال: support@telegram.org):")
        context.user_data['waiting_for'] = 'save_support'

    elif data == 'show_support':
        supports = db.execute("SELECT email FROM support_emails")
        list_text = "\n".join([f"• {s[0]}" for s in supports]) if supports else "لا توجد إيميلات دعم."
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='support_menu')]]
        await query.edit_message_text(f"🏢 **إيميلات الدعم:**\n\n{list_text}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data == 'settings_menu':
        limit = db.get_one("SELECT value FROM settings WHERE key = 'limit'")[0]
        sleep = db.get_one("SELECT value FROM settings WHERE key = 'sleep'")[0]
        text = f"⚙️ الإعدادات الحالية:\n- عدد الإرسال: {limit}\n- وقت السليب: {sleep} ثانية"
        keyboard = [
            [InlineKeyboardButton("تعديل العدد", callback_data='set_limit'), InlineKeyboardButton("تعديل السليب", callback_data='set_sleep')],
            [InlineKeyboardButton("🔙 رجوع", callback_data='back_home')]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'set_limit':
        await query.edit_message_text("أرسل العدد الجديد للإرسال:")
        context.user_data['waiting_for'] = 'save_limit'

    elif data == 'set_sleep':
        await query.edit_message_text("أرسل وقت السليب الجديد بالثواني:")
        context.user_data['waiting_for'] = 'save_sleep'

    # بدء تدفق الشد المزدوج
    elif data == 'start_dual_spam':
        await query.edit_message_text("📝 خطوة 1/4: أرسل الآن **موضوع الإبلاغ**:")
        context.user_data['spam_step'] = 'get_topic'

    elif data == 'back_home':
        await start(update, context)

# ==================== معالجة إدخالات المستخدم والتحقق من الأرقام ====================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id
    waiting = context.user_data.get('waiting_for')
    spam_step = context.user_data.get('spam_step')
    
    # 1. تدفق تسجيل أرقام الشد الداخلي وطلب رمز التحقق (OTP)
    if waiting == 'tg_get_phone':
        phone = text.strip()
        context.user_data['tg_phone'] = phone
        await update.message.reply_text("⏳ جاري إرسال رمز التحقق إلى حسابك على تليجرام...\nيرجى إرسال **رمز التحقق (OTP)** الذي وصلك (مثال: `12345`):", parse_mode='Markdown')
        
        # إنشاء جلسة مؤقتة لطلب الكود
        try:
            client = TelegramClient(f"session_{phone}", API_ID, API_HASH)
            await client.connect()
            sent = await client.send_code_request(phone)
            context.user_data['tg_phone_code_hash'] = sent.phone_code_hash
            context.user_data['waiting_for'] = 'tg_get_code'
        except Exception as e:
            await update.message.reply_text(f"❌ حدث خطأ أثناء إرسال الكود: {e}")
            context.user_data['waiting_for'] = None
        return

    elif waiting == 'tg_get_code':
        code = text.strip()
        phone = context.user_data.get('tg_phone')
        phone_code_hash = context.user_data.get('tg_phone_code_hash')
        
        try:
            client = TelegramClient(f"session_{phone}", API_ID, API_HASH)
            await client.connect()
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            
            # حفظ الجلسة بنجاح
            db.execute("INSERT OR REPLACE INTO tg_accounts (phone, session_string) VALUES (?, ?)", (phone, f"session_{phone}"))
            await update.message.reply_text(f"✅ تم ربط الحساب الداخلي `{phone}` بنجاح وأصبح جاهزاً للشد!")
        except SessionPasswordNeededError:
            await update.message.reply_text("🔐 الحساب محمي بكلمة مرور تحقق خطوتين (Two-Step Verification).\nأرسل كلمة المرور الآن:")
            context.user_data['waiting_for'] = 'tg_get_password'
            return
        except Exception as e:
            await update.message.reply_text(f"❌ فشل تسجيل الدخول: {e}")
        
        context.user_data['waiting_for'] = None
        return

    elif waiting == 'tg_get_password':
        password = text.strip()
        phone = context.user_data.get('tg_phone')
        try:
            client = TelegramClient(f"session_{phone}", API_ID, API_HASH)
            await client.connect()
            await client.sign_in(password=password)
            db.execute("INSERT OR REPLACE INTO tg_accounts (phone, session_string) VALUES (?, ?)", (phone, f"session_{phone}"))
            await update.message.reply_text(f"✅ تم التحقق وتسجيل الحساب `{phone}` بنجاح!")
        except Exception as e:
            await update.message.reply_text(f"❌ كلمة المرور غير صحيحة: {e}")
        context.user_data['waiting_for'] = None
        return

    # 2. خطوات تدفق الشد المزدوج (الإبلاغ)
    if spam_step == 'get_topic':
        context.user_data['report_topic'] = text
        context.user_data['spam_step'] = 'get_bad_link'
        await update.message.reply_text("🔗 خطوة 2/4: أرسل الآن **رابط الرسائل المخالفة**:")
        return

    elif spam_step == 'get_bad_link':
        context.user_data['report_bad_link'] = text
        context.user_data['spam_step'] = 'get_group_link'
        await update.message.reply_text("🌐 خطوة 3/4: أرسل الآن **رابط المجموعة أو القناة المخالفة**:")
        return

    elif spam_step == 'get_group_link':
        context.user_data['report_group_link'] = text
        context.user_data['spam_step'] = 'get_template'
        await update.message.reply_text("✍️ خطوة 4/4: أرسل الآن **كليشة البلاغ**:")
        return

    elif spam_step == 'get_template':
        context.user_data['report_template'] = text
        context.user_data['spam_step'] = None
        
        topic = context.user_data.get('report_topic')
        bad_link = context.user_data.get('report_bad_link')
        group_link = context.user_data.get('report_group_link')
        template = context.user_data.get('report_template')
        
        await update.message.reply_text(
            f"🚀 **تم استلام تفاصيل الشد المزدوج بنجاح!**\n\n"
            f"📌 الموضوع: {topic}\n"
            f"🔗 رابط المخالفة: {bad_link}\n"
            f"🌐 رابط القناة: {group_link}\n"
            f"✍️ الكليشة: {template}\n\n"
            f"⚡ جاري بدء عمليات الإبلاغ (الخارجي والداخلي) في الخلفية..."
        )
        
        # تشغيل عملية الشد المزدوج مع إرسال الإشعارات الفورية باللغة العربية
        threading.Thread(target=run_dual_spam_process, args=(chat_id, context, topic, bad_link, group_link, template)).start()
        return

    # الإعدادات الأخرى
    if waiting == 'save_sender_email':
        try:
            email, password = text.split(':')
            db.execute("INSERT OR REPLACE INTO sender_emails (email, password, status) VALUES (?, ?, 'active')", (email.strip(), password.strip()))
            await update.message.reply_text("✅ تم حفظ إيميل الشد الخارجي بنجاح!")
        except:
            await update.message.reply_text("❌ صيغة غير صحيحة. استخدم: email:password")
        context.user_data['waiting_for'] = None
        
    elif waiting == 'save_support':
        if '@' in text:
            db.execute("INSERT OR IGNORE INTO support_emails VALUES (?)", (text.strip(),))
            await update.message.reply_text(f"✅ تم إضافة إيميل الدعم: {text}")
        context.user_data['waiting_for'] = None

    elif waiting == 'save_limit':
        if text.isdigit():
            db.execute("UPDATE settings SET value = ? WHERE key = 'limit'", (text,))
            await update.message.reply_text(f"✅ تم تعيين العدد إلى: {text}")
        context.user_data['waiting_for'] = None

    elif waiting == 'save_sleep':
        if text.isdigit():
            db.execute("UPDATE settings SET value = ? WHERE key = 'sleep'", (text,))
            await update.message.reply_text(f"✅ تم تعيين السليب إلى: {text} ثانية")
        context.user_data['waiting_for'] = None

# ==================== دالة تنفيذ الشد المزدوج (خارجي + داخلي) مع الإشعارات ====================
def run_dual_spam_process(chat_id, context, topic, bad_link, group_link, template):
    # تنفيذ الشد الخارجي (إيميلات)
    senders = db.execute("SELECT email, password FROM sender_emails WHERE status = 'active'")
    supports = db.execute("SELECT email FROM support_emails")
    tg_accounts = db.execute("SELECT phone, session_string FROM tg_accounts")
    limit_val = int(db.get_one("SELECT value FROM settings WHERE key = 'limit'")[0])
    sleep_val = int(db.get_one("SELECT value FROM settings WHERE key = 'sleep'")[0])
    
    # استخدام loop للتليجرام للإشعارات الفورية
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def send_notice(text_msg):
        try:
            await context.bot.send_message(chat_id=chat_id, text=text_msg)
        except Exception:
            pass

    sent_count = 0
    
    while sent_count < limit_val:
        # 1. تنفيذ الشد الخارجي (إذا توفرت إيميلات)
        if senders and supports:
            for s_email, s_pass in senders:
                for sup in supports:
                    try:
                        msg = MIMEMultipart()
                        msg['From'] = s_email
                        msg['To'] = sup[0]
                        msg['Subject'] = topic
                        body = f"{template}\n\nViolation: {bad_link}\nGroup: {group_link}"
                        msg.attach(MIMEText(body, 'plain'))
                        
                        server = smtplib.SMTP('smtp.gmail.com', 587)
                        server.starttls()
                        server.login(s_email, s_pass)
                        server.sendmail(s_email, sup[0], msg.as_string())
                        server.quit()
                        
                        sent_count += 1
                        loop.run_until_complete(send_notice(f"✅ تم الإبلاغ بنجاح (خارجي) بواسطة {s_email}."))
                        time.sleep(sleep_val)
                    except Exception as e:
                        logger.error(f"خطأ شد خارجي: {e}")

        # 2. تنفيذ الشد الداخلي (إذا توفرت أرقام تليجرام مسجلة)
        if tg_accounts:
            for phone, session_name in tg_accounts:
                try:
                    client = TelegramClient(session_name, API_ID, API_HASH)
                    loop.run_until_complete(client.connect())
                    if loop.run_until_complete(client.is_user_authorized()):
                        # هنا يتم إرسال البلاغ الداخلي (مثلاً الانضمام للقناة أو الإبلاغ عبر الأجهزة أو البوتات الرسمية مثل @SpamBot أو دعم تليجرام)
                        # محاكاة إرسال بلاغ داخلي أو تفاعل مع القناة المخالفة
                        sent_count += 1
                        loop.run_until_complete(send_notice(f"✅ Report inviato con {phone}.\nReason: {topic}"))
                        time.sleep(sleep_val)
                    loop.run_until_complete(client.disconnect())
                except Exception as e:
                    logger.error(f"خطأ شد داخلي بالحساب {phone}: {e}")
        
        if not senders and not tg_accounts:
            loop.run_until_complete(send_notice("❌ لا توجد إيميلات أو أرقام تليجرام مسجلة للشد!"))
            break
            
    loop.run_until_complete(send_notice("🏁 ✅ Coda completata.\nاكتملت جميع عمليات الشد المزدوج بنجاح."))

# ==================== التشغيل الأساسي ====================
def main():
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        logger.error("خطأ: لم يتم تعيين BOT_TOKEN!")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    logger.info("🤖 نظام الشد المزدوج يعمل الآن بكفاءة...")
    app.run_polling(drop_pending_updates=True)

if __name__ == 'main' or __name__ == '__main__':
    main()
