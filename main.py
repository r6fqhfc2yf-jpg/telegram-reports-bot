import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import sqlite3
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.encoders import encode_base64
import json
from datetime import datetime
import threading

# ==================== إعداد السجلات (Logging) ====================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== قاعدة البيانات ====================

class Database:
    def __init__(self, db_name='reports.db'):
        self.db_name = db_name
        self.init_db()
    
    def init_db(self):
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # جدول الإعدادات
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            # جدول الأرقام المصرح بها
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS authorized_phones (
                    phone TEXT PRIMARY KEY,
                    added_date TEXT
                )
            ''')
            
            # جدول إيميلات الدعم
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS support_emails (
                    email TEXT PRIMARY KEY,
                    added_date TEXT
                )
            ''')
            
            # جدول المسؤولين
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY,
                    added_date TEXT
                )
            ''')
            
            # جدول الإبلاغات
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    phone TEXT,
                    reason TEXT,
                    subject TEXT,
                    description TEXT,
                    image_path TEXT,
                    email_contact TEXT,
                    sent_to_emails TEXT,
                    status TEXT,
                    created_at TEXT,
                    sent_at TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"خطأ في تهيئة قاعدة البيانات: {e}")
    
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

# ==================== إرسال الإيميلات ====================

class EmailSender:
    def __init__(self):
        self.sender_email = None
        self.sender_password = None
        self.load_config()
    
    def load_config(self):
        result = db.get_one("SELECT value FROM settings WHERE key = 'sender_email'")
        self.sender_email = result[0] if result else None
        
        result = db.get_one("SELECT value FROM settings WHERE key = 'sender_password'")
        self.sender_password = result[0] if result else None
    
    def send_report(self, to_emails, report_data):
        if not self.sender_email or not self.sender_password:
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"🔔 إبلاغ جديد - {report_data['reason']}"
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(to_emails)
            
            html_body = self.create_html_report(report_data)
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))
            
            # إضافة الصورة
            if report_data.get('image_path') and os.path.exists(report_data['image_path']):
                with open(report_data['image_path'], 'rb') as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                    encode_base64(part)
                    part.add_header('Content-Disposition', 'attachment', 
                                  filename=os.path.basename(report_data['image_path']))
                    msg.attach(part)
            
            server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
            server.login(self.sender_email, self.sender_password)
            server.send_message(msg)
            server.quit()
            
            return True
        except Exception as e:
            logger.error(f"❌ خطأ الإرسال: {e}")
            return False
    
    def create_html_report(self, data):
        return f"""
        <html dir="rtl">
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; }}
                .container {{ background: white; padding: 30px; border-radius: 15px; max-width: 700px; margin: auto; }}
                .header {{ color: #667eea; text-align: center; border-bottom: 3px solid #667eea; padding-bottom: 20px; }}
                .report-item {{ padding: 15px; background: #f8f9fa; margin: 15px 0; border-right: 4px solid #667eea; border-radius: 5px; }}
                .label {{ color: #667eea; font-weight: bold; }}
                .value {{ color: #333; margin-top: 5px; }}
                .footer {{ color: #999; font-size: 12px; text-align: center; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2 class="header">🔔 إبلاغ جديد من نظام المراقبة</h2>
                
                <div class="report-item">
                    <div class="label">🆔 رقم الإبلاغ:</div>
                    <div class="value">{data.get('report_id', 'N/A')}</div>
                </div>
                
                <div class="report-item">
                    <div class="label">👤 اسم المستخدم:</div>
                    <div class="value">{data.get('username', 'مجهول')}</div>
                </div>
                
                <div class="report-item">
                    <div class="label">📱 الرقم:</div>
                    <div class="value">{data.get('phone', 'N/A')}</div>
                </div>
                
                <div class="report-item">
                    <div class="label">⚠️ سبب الإبلاغ:</div>
                    <div class="value">{data.get('reason', 'N/A')}</div>
                </div>
                
                <div class="report-item">
                    <div class="label">📋 الموضوع:</div>
                    <div class="value">{data.get('subject', 'N/A')}</div>
                </div>
                
                <div class="report-item">
                    <div class="label">📝 الوصف:</div>
                    <div class="value">{data.get('description', 'N/A')}</div>
                </div>
                
                <div class="report-item">
                    <div class="label">📧 جهة الاتصال:</div>
                    <div class="value">{data.get('email_contact', 'N/A')}</div>
                </div>
                
                <div class="report-item">
                    <div class="label">⏰ التاريخ والوقت:</div>
                    <div class="value">{data.get('created_at', 'N/A')}</div>
                </div>
                
                <div class="footer">
                    <p>✅ تم الإرسال بنجاح من نظام الإبلاغات المتقدم</p>
                    <p>⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
            </div>
        </body>
        </html>
        """

email_sender = EmailSender()

# ==================== أسباب الإبلاغ ====================

REPORT_REASONS = {
    'harassment': '🚨 تحرش وإساءة معاملة',
    'fraud': '🎭 احتيال ونصب',
    'illegal': '⚖️ محتوى غير قانوني',
    'violence': '💥 عنف وتهديدات',
    'copyright': '©️ انتهاك حقوق ملكية',
    'spam': '📧 رسائل مزعجة',
    'other': '📌 أخرى'
}

# ==================== بوت تيليجرام ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin = db.get_one("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
    
    if is_admin:
        await admin_menu(update, context)
    else:
        await user_menu(update, context)

async def user_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📤 إرسال إبلاغ جديد", callback_data='new_report')],
        [InlineKeyboardButton("📱 تسجيل دخول", callback_data='login'),
         InlineKeyboardButton("👤 بيانات حسابي", callback_data='my_account')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(
            "🎯 **نظام الإبلاغات المتقدم**\n\nاستخدم الأزرار للبدء:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            "🎯 **نظام الإبلاغات المتقدم**\n\nاستخدم الأزرار للبدء:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    stats = db.execute("""
        SELECT COUNT(*), 
               SUM(CASE WHEN status='تم الإرسال' THEN 1 ELSE 0 END),
               SUM(CASE WHEN status='قيد المعالجة' THEN 1 ELSE 0 END)
        FROM reports
    """)[0]
    
    total = stats[0] or 0
    sent = stats[1] or 0
    pending = stats[2] or 0
    
    keyboard = [
        [InlineKeyboardButton("📧 إعدادات البريد", callback_data='email_config'),
         InlineKeyboardButton("📱 أرقام مصرح", callback_data='auth_phones')],
        [InlineKeyboardButton("👥 إيميلات الدعم", callback_data='support_emails'),
         InlineKeyboardButton("👮 المسؤولين", callback_data='admins_list')],
        [InlineKeyboardButton("📊 الإبلاغات", callback_data='view_reports'),
         InlineKeyboardButton("📈 الإحصائيات", callback_data='statistics')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    admin_text = f"""
🛡️ **لوحة التحكم الإدارية**
━━━━━━━━━━━━━━━━━━━━
📊 الإبلاغات الكلية: {total}
✅ تم الإرسال: {sent}
⏳ قيد المعالجة: {pending}
━━━━━━━━━━━━━━━━━━━━
    """
    
    await query.edit_message_text(admin_text, reply_markup=reply_markup, parse_mode='Markdown')

# ==================== معالج الأزرار ====================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'new_report':
        keyboard = [
            [InlineKeyboardButton(REPORT_REASONS[reason], callback_data=f'reason_{reason}')]
            for reason in REPORT_REASONS.keys()
        ]
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data='cancel')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("📱 **اختر سبب الإبلاغ:**", reply_markup=reply_markup)
    
    elif query.data.startswith('reason_'):
        reason = query.data.split('_', 1)[1]
        context.user_data['report_reason'] = reason
        
        await query.edit_message_text(
            "🖼️ **الخطوة 1/4**\n\nأرسل صورة الدليل/المخالفة:"
        )
        context.user_data['step'] = 1
        context.user_data['waiting_for'] = 'image'
    
    elif query.data == 'login':
        await query.edit_message_text("📱 **أدخل الرقم المصرح:**")
        context.user_data['waiting_for'] = 'login_phone'
    
    elif query.data == 'my_account':
        phone = context.user_data.get('phone', 'لم يتم تسجيل دخول')
        my_reports = db.execute(
            "SELECT COUNT(*) FROM reports WHERE phone = ?",
            (phone,)
        )[0][0] if phone != 'لم يتم تسجيل دخول' else 0
        
        await query.edit_message_text(
            f"👤 **معلوماتك:**\n📱 الرقم: `{phone}`\n📊 عدد الإبلاغات: `{my_reports}`",
            parse_mode='Markdown'
        )
    
    elif query.data == 'cancel':
        context.user_data.clear()
        await user_menu(update, context)
    
    elif query.data == 'email_config':
        await query.edit_message_text(
            "📧 **إعدادات البريد**\n\nأرسل بهذه الصيغة:\n`email:password`",
            parse_mode='Markdown'
        )
        context.user_data['waiting_for'] = 'email_config'
    
    elif query.data == 'auth_phones':
        phones = db.execute("SELECT phone FROM authorized_phones")
        phones_list = "\n".join([f"• {p[0]}" for p in phones]) if phones else "❌ لا توجد أرقام"
        await query.edit_message_text(f"📱 **الأرقام المصرح بها:**\n\n{phones_list}\n\nأرسل رقم جديد:")
        context.user_data['waiting_for'] = 'add_phone'
    
    elif query.data == 'support_emails':
        emails = db.execute("SELECT email FROM support_emails")
        emails_list = "\n".join([f"• {e[0]}" for e in emails]) if emails else "❌ لا توجد إيميلات"
        await query.edit_message_text(f"📧 **إيميلات الدعم:**\n\n{emails_list}\n\nأرسل إيميل جديد:")
        context.user_data['waiting_for'] = 'add_support_email'
    
    elif query.data == 'view_reports':
        reports = db.execute(
            "SELECT id, reason, subject, status, created_at FROM reports ORDER BY id DESC LIMIT 10"
        )
        reports_text = "📋 **الإبلاغات الأخيرة:**\n━━━━━━━━━━━━\n"
        if reports:
            for r in reports:
                reports_text += f"🆔 {r[0]} | {REPORT_REASONS.get(r[1], r[1])}\n📌 {r[2][:30]}...\n📊 {r[3]} | ⏰ {r[4][:10]}\n━━━━━━━━━━━━\n"
        else:
            reports_text += "❌ لا توجد إبلاغات"
        await query.edit_message_text(reports_text)

# ==================== معالج الرسائل ====================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if context.user_data.get('waiting_for') == 'login_phone':
        phone = text.strip()
        is_authorized = db.get_one("SELECT phone FROM authorized_phones WHERE phone = ?", (phone,))
        if is_authorized:
            context.user_data['phone'] = phone
            context.user_data['logged_in'] = True
            await update.message.reply_text(f"✅ **تم تسجيل الدخول بنجاح!**\n📱 الرقم: `{phone}`", parse_mode='Markdown')
            context.user_data['waiting_for'] = None
        else:
            await update.message.reply_text("❌ الرقم غير مصرح")
            
    elif context.user_data.get('step') == 2:
        context.user_data['report_subject'] = text
        await update.message.reply_text("📝 **الخطوة 3/4**\n\nاكتب وصف الإبلاغ بالتفصيل:")
        context.user_data['step'] = 3
        context.user_data['waiting_for'] = 'description'
        
    elif context.user_data.get('waiting_for') == 'description':
        context.user_data['report_description'] = text
        await update.message.reply_text("📧 **الخطوة 4/4**\n\nأرسل بريدك الإلكتروني:")
        context.user_data['step'] = 4
        context.user_data['waiting_for'] = 'email'
        
    elif context.user_data.get('waiting_for') == 'email':
        if '@' in text:
            phone = context.user_data.get('phone', 'لم يتم تسجيل')
            report_data = {
                'user_id': user_id,
                'phone': phone,
                'reason': context.user_data.get('report_reason'),
                'subject': context.user_data.get('report_subject'),
                'description': context.user_data.get('report_description'),
                'image_path': context.user_data.get('report_image_path'),
                'email_contact': text,
                'username': update.effective_user.username or update.effective_user.first_name,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            db.execute("""
                INSERT INTO reports 
                (user_id, phone, reason, subject, description, image_path, email_contact, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report_data['user_id'], report_data['phone'], report_data['reason'],
                report_data['subject'], report_data['description'], report_data['image_path'],
                report_data['email_contact'], 'قيد المعالجة', report_data['created_at']
            ))
            
            report_id = db.execute("SELECT last_insert_rowid() FROM reports")[0][0]
            report_data['report_id'] = report_id
            
            support_emails = db.execute("SELECT email FROM support_emails")
            to_emails = [e[0] for e in support_emails] if support_emails else []
            
            if to_emails:
                def send_emails():
                    if email_sender.send_report(to_emails, report_data):
                        db.execute("UPDATE reports SET status = ? WHERE id = ?", ('تم الإرسال', report_id))
                
                thread = threading.Thread(target=send_emails)
                thread.daemon = True
                thread.start()
            
            await update.message.reply_text(
                f"✅ **تم إرسال الإبلاغ بنجاح!**\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🆔 رقم الإبلاغ: `{report_id}`\n"
                f"📱 الرقم: `{phone}`\n"
                f"📧 الإيميل: `{text}`\n"
                f"⏰ الوقت: `{report_data['created_at']}`\n"
                f"📊 الحالة: `قيد الإرسال`\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"✨ تم الإرسال إلى {len(to_emails)} جهات دعم",
                parse_mode='Markdown'
            )
            context.user_data.clear()
        else:
            await update.message.reply_text("❌ بريد إلكتروني غير صحيح")
            
    elif context.user_data.get('waiting_for') == 'email_config':
        try:
            email, password = text.split(':')
            db.execute("DELETE FROM settings WHERE key = ?", ('sender_email',))
            db.execute("DELETE FROM settings WHERE key = ?", ('sender_password',))
            db.execute("INSERT INTO settings VALUES (?, ?)", ('sender_email', email))
            db.execute("INSERT INTO settings VALUES (?, ?)", ('sender_password', password))
            email_sender.load_config()
            await update.message.reply_text("✅ تم حفظ بيانات البريد!")
        except:
            await update.message.reply_text("❌ صيغة خاطئة. استخدم: email:password")
        context.user_data['waiting_for'] = None
        
    elif context.user_data.get('waiting_for') == 'add_phone':
        if text.isdigit():
            db.execute("INSERT OR IGNORE INTO authorized_phones VALUES (?, ?)", (text, datetime.now().isoformat()))
            await update.message.reply_text(f"✅ تم إضافة الرقم: {text}")
        else:
            await update.message.reply_text("❌ رقم غير صحيح")
        context.user_data['waiting_for'] = None
        
    elif context.user_data.get('waiting_for') == 'add_support_email':
        if '@' in text:
            db.execute("INSERT OR IGNORE INTO support_emails VALUES (?, ?)", (text, datetime.now().isoformat()))
            await update.message.reply_text(f"✅ تم إضافة الإيميل: {text}")
        else:
            await update.message.reply_text("❌ إيميل غير صحيح")
        context.user_data['waiting_for'] = None

# ==================== معالج الصور ====================

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_for') == 'image':
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        
        os.makedirs('reports', exist_ok=True)
        file_path = f"reports/report_{int(datetime.now().timestamp())}.jpg"
        await file.download_to_drive(file_path)
        
        context.user_data['report_image_path'] = file_path
        
        await update.message.reply_text("📋 **الخطوة 2/4**\n\nاكتب موضوع الإبلاغ:")
        context.user_data['step'] = 2
        context.user_data['waiting_for'] = 'subject'

# ==================== الدالة الرئيسية للتشغيل ====================

def main():
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        logger.error("خطأ: لم يتم تعيين BOT_TOKEN في متغيرات البيئة!")
        return

    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_menu))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    logger.info("🤖 البوت يعمل بنجاح...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
