import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_NAME = os.getenv('DATABASE_NAME', 'reports.db')
DEFAULT_SENDER_EMAIL = os.getenv('DEFAULT_SENDER_EMAIL', '')
DEFAULT_SENDER_PASSWORD = os.getenv('DEFAULT_SENDER_PASSWORD', '')
INITIAL_ADMINS = [int(aid.strip()) for aid in os.getenv('INITIAL_ADMINS', '').split(',') if aid.strip()]
