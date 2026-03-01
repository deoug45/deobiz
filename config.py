# config.py

from dotenv import load_dotenv
import os
import secrets

# Load .env variables
load_dotenv()

class Config:
    """Application Configuration - All settings centralized"""
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))

   # Flask Settings
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    SESSION_LIFETIME_HOURS = int(os.environ.get('SESSION_LIFETIME_HOURS', 2))
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Database Settings (Supabase)
    SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
    
    # Email Settings
    SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    EMAIL_SENDER = os.environ.get('EMAIL_SENDER', 'deoug45@gmail.com')
    EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')
    COMPANY_EMAIL = os.environ.get('COMPANY_EMAIL', 'deoug45@gmail.com')
    
    # Company Branding
    COMPANY_NAME = os.environ.get('COMPANY_NAME', 'Deo Digital Solutions')
    COMPANY_TAGLINE = os.environ.get('COMPANY_TAGLINE', 'Visualising Your Vision')
    COMPANY_WEBSITE = os.environ.get('COMPANY_WEBSITE', 'www.deodigitalsolutions.com')
    COMPANY_LOCATION = os.environ.get('COMPANY_LOCATION', 'Kampala, Uganda')
    COMPANY_CURRENCY = os.environ.get('COMPANY_CURRENCY', 'UGX')
    FOUNDER_NAME = os.environ.get('FOUNDER_NAME', 'Ayebare Deogratious')
    FOUNDER_TITLE = os.environ.get('FOUNDER_TITLE', 'Founder & Lead Developer')
    
    # Colors - Three Color Scheme
    PRIMARY_COLOR = os.environ.get('PRIMARY_COLOR', '#0EA5E9')      # Sky Blue
    ACCENT_COLOR = os.environ.get('ACCENT_COLOR', '#0284C7')        # Blue
    SECONDARY_COLOR = os.environ.get('SECONDARY_COLOR', '#06B6D4')  # Cyan
    
    # Security Settings
    MAX_LOGIN_ATTEMPTS = int(os.environ.get('MAX_LOGIN_ATTEMPTS', 5))
    LOGIN_ATTEMPT_WINDOW_HOURS = int(os.environ.get('LOGIN_ATTEMPT_WINDOW_HOURS', 1))
    OTP_EXPIRY_MINUTES = int(os.environ.get('OTP_EXPIRY_MINUTES', 10))
    OTP_LENGTH = int(os.environ.get('OTP_LENGTH', 6))
    
    # CEO Report Settings
    CEO_REPORT_ENABLED = os.environ.get('CEO_REPORT_ENABLED', 'True').lower() == 'true'
    CEO_REPORT_HOUR = int(os.environ.get('CEO_REPORT_HOUR', 21))
    CEO_REPORT_MINUTE = int(os.environ.get('CEO_REPORT_MINUTE', 0))
    TIMEZONE = os.environ.get('TIMEZONE', 'Africa/Kampala')
    
    # PWA Settings
    PWA_NAME = os.environ.get('PWA_NAME', 'DeoBiz Manager')
    PWA_SHORT_NAME = os.environ.get('PWA_SHORT_NAME', 'DeoBiz')
    
    # File Upload Settings
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx', 'xls', 'xlsx'}
    
    # PDF Settings
    PDF_PAGE_SIZE = 'A4'
    PDF_FONT_NAME = os.environ.get('PDF_FONT_NAME', 'Helvetica')
    PDF_FONT_SIZE = int(os.environ.get('PDF_FONT_SIZE', 12))
    
    # Business Logic Settings
    DEFAULT_TAX_RATE = float(os.environ.get('DEFAULT_TAX_RATE', 0))
    DEFAULT_DISCOUNT_RATE = float(os.environ.get('DEFAULT_DISCOUNT_RATE', 0))
    QUOTATION_VALIDITY_DAYS = int(os.environ.get('QUOTATION_VALIDITY_DAYS', 30))
    INVOICE_DUE_DAYS = int(os.environ.get('INVOICE_DUE_DAYS', 30))