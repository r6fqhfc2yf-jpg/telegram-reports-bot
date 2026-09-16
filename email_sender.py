import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import DEFAULT_SENDER_EMAIL, DEFAULT_SENDER_PASSWORD

def send_report_email(recipient_email, subject, description, image_path=None):
    if not DEFAULT_SENDER_EMAIL or not DEFAULT_SENDER_PASSWORD:
        print('⚠ بيانات الإيميل غير محددة')
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = DEFAULT_SENDER_EMAIL
        msg['To'] = recipient_email
        msg['Subject'] = f'إبلاغ جديد: {subject}'
        
        body = f'''
        تم استقبال إبلاغك بنجاح!
        
        الموضوع: {subject}
        الوصف: {description}
        
        شكراً لك على الإبلاغ.
        '''
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(DEFAULT_SENDER_EMAIL, DEFAULT_SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f'✅ تم إرسال الإيميل إلى {recipient_email}')
        return True
    except Exception as e:
        print(f'❌ خطأ في إرسال الإيميل: {e}')
        return False
