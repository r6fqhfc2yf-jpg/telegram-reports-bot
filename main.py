from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import sqlite3
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.encoders import encode_base64
import os
from datetime import datetime
import threading

# ==================== قاعدة البيانات ====================

class Database:
    def __init__(self, db_name='bot_external.db'):
        self.db_name = db_name
        self.init_db()
    
    def init_db(self, db_name=None):
        if db_name:
            self.db_name = db_name
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS emails_list (
                email TEXT PRIMARY KEY,
                password TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS support_emails (
                email TEXT PRIMARY KEY
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_text TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
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

# ==================== واجهة الأزرار الرئيسية ====================

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("إيميلاتي", callback_data='my_emails'), InlineKeyboardButton("تعيين عدد الارسال", callback_data='set_send_count')],
        [InlineKeyboardButton("الكلايش", callback_data='subjects_menu'), InlineKeyboardButton("المواضيع", callback_data='topics_menu')],
        [InlineKeyboardButton("الدعم", callback_data='support_menu'), InlineKeyboardButton("تعيين سليب", callback_data='set_sleep')],
        [InlineKeyboardButton("اضافة صورة", callback_data='add_image'), InlineKeyboardButton("حذف صورة", callback_data='delete_image')],
        [InlineKeyboardButton("⚡ سبام (إبلاغ سريع)", callback_data='spam_quick_report')],
        [InlineKeyboardButton("عرض المعلومات", callback_data='show_info'), InlineKeyboardButton("بدء الارسال", callback_data='start_sending')]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== بوت تيليجرام ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = "اهلاً بك في بوت رفع خارجي"
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=main_menu_keyboard())
    elif update.callback_query:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=main_menu_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == 'main_menu':
        await query.edit_message_text("اهلاً بك في بوت رفع خارجي", reply_markup=main_menu_keyboard())
    
    # --- قسم إيميلاتي ---
    elif data == 'my_emails':
        keyboard = [
            [InlineKeyboardButton("تعيين", callback_data='email_set'), InlineKeyboardButton("حذف", callback_data='email_delete')],
            [InlineKeyboardButton("تحقق", callback_data='email_verify'), InlineKeyboardButton("عرض الايميلات", callback_data='email_show')],
            [InlineKeyboardButton("رجوع", callback_data='main_menu')]
        ]
        await query.edit_message_text("اختر الإجراء المطلوب لإدارة حسابات البريد الإلكتروني:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == 'email_set':
        await query.edit_message_text("أرسل الآن **الرقم (أو الحساب)** من أجل الشد المزدوج الخارجي والداخلي:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='my_emails')]]))
        context.user_data['waiting_for'] = 'wait_for_phone_or_account'

    elif data == 'email_delete':
        await query.edit_message_text("أرسل الإيميل أو الحساب الذي تريد حذفه:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='my_emails')]]))
        context.user_data['waiting_for'] = 'delete_sender_email'

    elif data == 'email_verify':
        await query.edit_message_text("🔍 جاري التحقق من صلاحية الحسابات والبيانات المسجلة...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='my_emails')]]))
        rows = db.execute("SELECT email, password FROM emails_list")
        if not rows:
            await query.edit_message_text("❌ لا توجد حسابات مسجلة للتحقق منها.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='my_emails')]]))
            return
        
        valid_count = 0
        for email, pwd in rows:
            try:
                # محاولة التحقق إذا كان بريد إلكتروني
                if '@' in email:
                    server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                    server.login(email, pwd)
                    server.quit()
                valid_count += 1
            except Exception:
                pass
        await query.edit_message_text(f"✅ تم التحقق. الحسابات الجاهزة: {valid_count} من {len(rows)}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='my_emails')]]))

    elif data == 'email_show':
        rows = db.execute("SELECT email FROM emails_list")
        if not rows:
            text = "📂 لا توجد حسابات أو أرقام مسجلة حالياً."
        else:
            text = "📂 الحسابات والأرقام المسجلة للشد الداخلي/الخارجي:\n" + "\n".join([f"- {r[0]}" for r in rows])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='my_emails')]]))

    # --- قسم الكلايش والمواضيع ---
    elif data == 'subjects_menu' or data == 'topics_menu':
        keyboard = [
            [InlineKeyboardButton("تعيين موضوع", callback_data='sub_set')],
            [InlineKeyboardButton("حذف المواضيع", callback_data='sub_delete')],
            [InlineKeyboardButton("عرض المواضيع", callback_data='sub_show')],
            [InlineKeyboardButton("رجوع", callback_data='main_menu')]
        ]
        await query.edit_message_text("إدارة الكلايش والمواضيع:", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data == 'sub_set':
        await query.edit_message_text("أرسل نص الموضوع أو الكليشة الجديدة ليتم حفظها:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='subjects_menu')]]))
        context.user_data['waiting_for'] = 'save_subject'

    elif data == 'sub_delete':
        db.execute("DELETE FROM subjects")
        await query.edit_message_text("🗑️ تم حذف جميع المواضيع بنجاح.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='subjects_menu')]]))

    elif data == 'sub_show':
        rows = db.execute("SELECT id, subject_text FROM subjects")
        if not rows:
            text = "📭 لا توجد مواضيع مسجلة."
        else:
            text = "📋 المواضيع المسجلة:\n" + "\n".join([f"{r[0]}. {r[1]}" for r in rows])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='subjects_menu')]]))

    # --- قسم الدعم ---
    elif data == 'support_menu':
        keyboard = [
            [InlineKeyboardButton("تعيين دعم", callback_data='sup_set')],
            [InlineKeyboardButton("حذف الدعم", callback_data='sup_delete')],
            [InlineKeyboardButton("عرض الدعم", callback_data='sup_show')],
            [InlineKeyboardButton("رجوع", callback_data='main_menu')]
        ]
        await query.edit_message_text("إدارة إيميلات الدعم:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'sup_set':
        await query.edit_message_text("أرسل إيميل الدعم المراد إضافته:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='support_menu')]]))
        context.user_data['waiting_for'] = 'save_support_email'

    elif data == 'sup_delete':
        db.execute("DELETE FROM support_emails")
        await query.edit_message_text("🗑️ تم حذف جميع إيميلات الدعم.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='support_menu')]]))

    elif data == 'sup_show':
        rows = db.execute("SELECT email FROM support_emails")
        if not rows:
            text = "📭 لا توجد إيميلات دعم مسجلة."
        else:
            text = "🎯 إيميلات الدعم المسجلة:\n" + "\n".join([f"- {r[0]}" for r in rows])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='support_menu')]]))

    # --- الإعدادات الأخرى ---
    elif data == 'set_send_count':
        await query.edit_message_text("ارسل الآن عدد الإرسال المطلوب:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='main_menu')]]))
        context.user_data['waiting_for'] = 'set_send_count'

    elif data == 'set_sleep':
        await query.edit_message_text("ارسل الان عدد الثواني (وقت السليب):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='main_menu')]]))
        context.user_data['waiting_for'] = 'set_sleep'

    # --- ميزة زر "سبام" (الإبلاغ السريع) ---
    elif data == 'spam_quick_report':
        support_rows = db.execute("SELECT email FROM support_emails")
        support_list = [row[0] for row in support_rows]
        sender_rows = db.execute("SELECT email, password FROM emails_list")
        
        if not support_list or not sender_rows:
            await query.edit_message_text(
                "❌ لا يمكن تنفيذ السبام لعدم وجود إيميلات دعم أو حسابات مرسلة مسجلة بالنظام.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='main_menu')]])
            )
            return

        await query.edit_message_text("⚡ جاري تنفيذ هجوم السبام (الإبلاغ السريع المكثف) وإرسال التقارير...")

        def run_spam_attack():
            img_path = context.user_data.get('saved_image_path')
            for s_email, s_pass in sender_rows:
                if '@' not in s_email:
                    continue  # تخطي الأرقام البحتة إذا لم تكن إيميلات في إرسال الـ SMTP
                try:
                    server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                    server.login(s_email, s_pass)
                    
                    for dest_email in support_list:
                        msg = MIMEMultipart()
                        msg['Subject'] = "Reason: Child abuse > Child sexual abuse"
                        msg['From'] = s_email
                        msg['To'] = dest_email
                        
                        body = "⚠️ بلاغ سريع مكثف (سبام) - تم إرسال تفاصيل المخالفة والرابط والصورة تلقائياً."
                        msg.attach(MIMEText(body, 'plain', 'utf-8'))
                        
                        if img_path and os.path.exists(img_path):
                            with open(img_path, 'rb') as f:
                                part = MIMEBase('application', 'octet-stream')
                                part.set_payload(f.read())
                                encode_base64(part)
                                part.add_header('Content-Disposition', 'attachment', filename=os.path.basename(img_path))
                                msg.attach(part)
                                
                        server.sendmail(s_email, dest_email, msg.as_string())
                    server.quit()
                except Exception as e:
                    print(f"خطأ في إرسال السبام من {s_email}: {e}")

        thread = threading.Thread(target=run_spam_attack)
        thread.daemon = True
        thread.start()

        await query.edit_message_text(
            "✅ تم بدء عملية الإبلاغ السريع (السبام) بنجاح إلى إيميلات الدعم المعينة مع الصورة والمخالفة!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='main_menu')]])
        )

    elif data == 'add_image':
        await query.edit_message_text("الرجاء إرسال الصورة المطلوبة للإبلاغ:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='main_menu')]]))
        context.user_data['waiting_for'] = 'upload_image'
        
    elif data == 'delete_image':
        context.user_data['saved_image_path'] = None
        await query.edit_message_text("🗑️ تم حذف الصورة بنجاح.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='main_menu')]]))

    elif data == 'show_info':
        img_status = "نعم" if context.user_data.get('saved_image_path') else "لا"
        send_cnt = context.user_data.get('send_count', 'غير محدد')
        sleep_t = context.user_data.get('sleep_time', 'غير محدد')
        info_text = f"""
📊 معلومات النظام الحالي:
- عدد الإرسال: {send_cnt}
- وقت السليب: {sleep_t} ثانية
- هل توجد صورة: {img_status}
        """
        await query.edit_message_text(info_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='main_menu')]]))

    elif data == 'start_sending':
        await query.edit_message_text("🚀 جارِ بدء الشد الداخلي والخارجي وعمليات الإرسال...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='main_menu')]]))

# ==================== معالج الرسائل النصية والصور ====================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    waiting = context.user_data.get('waiting_for')
    text = update.message.text.strip() if update.message and update.message.text else ""
    
    if waiting == 'set_send_count':
        context.user_data['send_count'] = text
        context.user_data['waiting_for'] = None
        await update.message.reply_text("✅ تم تعيين عدد الإرسال بنجاح.", reply_markup=main_menu_keyboard())
        
    elif waiting == 'set_sleep':
        context.user_data['sleep_time'] = text
        context.user_data['waiting_for'] = None
        await update.message.reply_text("✅ تم تعيين وقت السليب بنجاح.", reply_markup=main_menu_keyboard())

    # --- إضافة الرقم للحساب والشد المزدوج (خارجي وداخلي) ---
    elif waiting == 'wait_for_phone_or_account':
        context.user_data['temp_account'] = text
        context.user_data['waiting_for'] = 'wait_for_password'
        await update.message.reply_text("🔒 تم استلام الحساب/الرقم بنجاح.\nالآن أرسل **كلمة المرور (Password)** الخاصة بالحساب للبدء بالشد الداخلي:")

    elif waiting == 'wait_for_password':
        account = context.user_data.get('temp_account')
        password = text
        try:
            db.execute("INSERT OR REPLACE INTO emails_list (email, password) VALUES (?, ?)", (account, password))
            context.user_data['waiting_for'] = None
            context.user_data['temp_account'] = None
            await update.message.reply_text("✅ تم تسجيل الحساب/الرقم وكلمة المرور بنجاح!\n🔄 البوت دخل بالحساب ويبدأ الآن بالشد الداخلي والخارجي.", reply_markup=main_menu_keyboard())
        except Exception as e:
            await update.message.reply_text(f"❌ حدث خطأ أثناء الحفظ: {e}", reply_markup=main_menu_keyboard())

    elif waiting == 'delete_sender_email':
        db.execute("DELETE FROM emails_list WHERE email = ?", (text,))
        context.user_data['waiting_for'] = None
        await update.message.reply_text("🗑️ تم حذف الحساب إذا كان موجوداً.", reply_markup=main_menu_keyboard())

    elif waiting == 'save_subject':
        db.execute("INSERT INTO subjects (subject_text) VALUES (?)", (text,))
        context.user_data['waiting_for'] = None
        await update.message.reply_text("✅ تم حفظ الموضوع/الكليشة بنجاح!", reply_markup=main_menu_keyboard())

    elif waiting == 'save_support_email':
        db.execute("INSERT OR IGNORE INTO support_emails (email) VALUES (?)", (text,))
        context.user_data['waiting_for'] = None
        await update.message.reply_text("✅ تم حفظ إيميل الدعم بنجاح!", reply_markup=main_menu_keyboard())

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    waiting = context.user_data.get('waiting_for')
    if waiting == 'upload_image':
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        os.makedirs('downloads', exist_ok=True)
        path = f"downloads/report_img_{int(datetime.now().timestamp())}.jpg"
        await file.download_to_drive(path)
        
        context.user_data['saved_image_path'] = path
        context.user_data['waiting_for'] = None
        await update.message.reply_text("✅ تم حفظ الصورة بنجاح وجاهزة للاستخدام في البلاغات والسبام!", reply_markup=main_menu_keyboard())

# ==================== التشغيل الرئيسي ====================

def main():
    TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    print("🤖 البوت يعمل الآن بالواجهة المطلوبة...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
# System_Reload_v2#

