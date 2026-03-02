# app.py - COMPLETE DEOBIZ MANAGER WITH ALL FIXES
# Production-ready version with POS, notifications, mobile fixes, and enhanced security

import os
import secrets
import json
import csv
from datetime import datetime, timedelta
from functools import wraps
import io
import base64
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify, send_file, make_response, Response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from supabase import create_client, Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
import qrcode
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from PIL import Image
from config import Config

# ==========================================
# FLASK APP INITIALIZATION
# ==========================================

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=Config.SESSION_LIFETIME_HOURS)
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH
app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER

# Create upload folder
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs('static', exist_ok=True)

# Initialize Supabase
supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

# ==========================================
# DECORATORS
# ==========================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

# ==========================================
# HELPER FUNCTIONS - ACTIVITY LOGGING
# ==========================================

def log_activity(activity_type, description, metadata=None):
    """Enhanced activity logging for security and audit"""
    try:
        ip_address = request.remote_addr
        user_id = session.get('user_id')
        
        supabase.table('activity_log').insert({
            'user_id': user_id,
            'activity_type': activity_type,
            'description': description,
            'ip_address': ip_address,
            'metadata': json.dumps(metadata) if metadata else None,
            'created_at': datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print(f"Failed to log activity: {e}")

# ==========================================
# HELPER FUNCTIONS - LOGO (FIXED)
# ==========================================

def get_logo_path():
    """Get the path to the user's logo - FIXED VERSION"""
    logo_path = os.path.join(Config.UPLOAD_FOLDER, 'logo.png')
    if os.path.exists(logo_path):
        return logo_path
    return None  # Don't create default

def get_logo_base64():
    """Get logo as base64 for email embedding"""
    logo_path = get_logo_path()
    if logo_path and os.path.exists(logo_path):
        with open(logo_path, 'rb') as f:
            return base64.b64encode(f.read()).decode()
    return None

def generate_pwa_icons():
    """Generate PWA icons from uploaded logo - FIXED VERSION"""
    logo_path = get_logo_path()
    if not logo_path:
        return False
    
    try:
        logo = Image.open(logo_path)
        
        # Ensure RGB mode
        if logo.mode in ('RGBA', 'LA', 'P'):
            # Create white background
            background = Image.new('RGB', logo.size, (255, 255, 255))
            if logo.mode == 'RGBA' or logo.mode == 'LA':
                background.paste(logo, mask=logo.split()[-1])  # Use alpha channel as mask
            else:
                background.paste(logo)
            logo = background
        
        # Generate 192x192
        icon_192 = logo.resize((192, 192), Image.Resampling.LANCZOS)
        icon_192.save('static/icon-192.png')
        
        # Generate 512x512
        icon_512 = logo.resize((512, 512), Image.Resampling.LANCZOS)
        icon_512.save('static/icon-512.png')
        
        # Generate favicon
        favicon = logo.resize((32, 32), Image.Resampling.LANCZOS)
        favicon.save('static/favicon.ico', format='ICO')
        
        return True
    except Exception as e:
        print(f"Error generating icons: {e}")
        return False

# ==========================================
# HELPER FUNCTIONS - EMAIL WITH LOGO (FIXED)
# ==========================================

def send_email_with_logo(to_email, subject, html_content, attachment=None, filename=None):
    """Send email with embedded logo - FIXED VERSION"""
    try:
        msg = MIMEMultipart('related')
        msg['From'] = f"{Config.COMPANY_NAME} <{Config.EMAIL_SENDER}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg_alternative = MIMEMultipart('alternative')
        msg.attach(msg_alternative)
        
        # Attach HTML
        html_part = MIMEText(html_content, 'html')
        msg_alternative.attach(html_part)
        
        # Attach logo as embedded image - FIXED
        logo_path = get_logo_path()
        if logo_path and os.path.exists(logo_path):
            with open(logo_path, 'rb') as f:
                logo_img = MIMEImage(f.read())
                logo_img.add_header('Content-ID', '<logo>')
                logo_img.add_header('Content-Disposition', 'inline', filename='logo.png')
                msg.attach(logo_img)
        
        # Attach PDF if provided
        if attachment and filename:
            pdf_part = MIMEApplication(attachment, _subtype='pdf')
            pdf_part.add_header('Content-Disposition', 'attachment', filename=filename)
            msg.attach(pdf_part)
        
        server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT)
        server.starttls()
        server.login(Config.EMAIL_SENDER, Config.EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def get_email_template(doc_type, data):
    """Professional email template with embedded logo"""
    logo_tag = '<img src="cid:logo" alt="Logo" class="logo">' if get_logo_path() else '<div class="logo" style="background: linear-gradient(135deg, #0EA5E9, #0284C7); color: white; font-size: 36px; font-weight: 700; display: flex; align-items: center; justify-content: center;">D</div>'
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                line-height: 1.6; 
                color: #2d3748; 
                margin: 0; 
                padding: 0;
                background-color: #f7fafc;
            }}
            .email-container {{
                max-width: 600px;
                margin: 0 auto;
                background: white;
            }}
            .header {{ 
                background: linear-gradient(135deg, {Config.PRIMARY_COLOR} 0%, {Config.ACCENT_COLOR} 100%);
                color: white; 
                padding: 40px 30px;
                text-align: center;
            }}
            .logo {{
                width: 80px;
                height: 80px;
                margin: 0 auto 20px;
                background: white;
                border-radius: 50%;
                padding: 10px;
            }}
            .header h1 {{
                margin: 0 0 10px 0;
                font-size: 28px;
                font-weight: 700;
            }}
            .tagline {{
                margin: 0;
                font-size: 14px;
                opacity: 0.95;
                font-style: italic;
            }}
            .content {{ 
                padding: 40px 30px;
                background: white;
            }}
            .content h2 {{
                color: {Config.PRIMARY_COLOR};
                margin: 0 0 20px 0;
                font-size: 22px;
            }}
            .summary {{ 
                background: #f7fafc;
                padding: 25px;
                border-radius: 12px;
                margin: 25px 0;
                border-left: 4px solid {Config.PRIMARY_COLOR};
            }}
            .summary h3 {{
                color: {Config.PRIMARY_COLOR};
                margin: 0 0 15px 0;
                font-size: 16px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .summary-item {{
                display: flex;
                justify-content: space-between;
                padding: 8px 0;
                border-bottom: 1px solid #e2e8f0;
            }}
            .summary-item:last-child {{
                border-bottom: none;
            }}
            .summary-label {{
                color: #718096;
                font-size: 14px;
            }}
            .summary-value {{
                color: #2d3748;
                font-weight: 600;
                font-size: 14px;
            }}
            .cta {{ 
                text-align: center; 
                margin: 35px 0;
            }}
            .button {{ 
                background: {Config.PRIMARY_COLOR};
                color: white; 
                padding: 15px 40px;
                text-decoration: none; 
                border-radius: 8px;
                display: inline-block;
                font-weight: 600;
                font-size: 15px;
                box-shadow: 0 4px 12px rgba(14, 165, 233, 0.3);
            }}
            .footer {{ 
                background: #2d3748;
                color: white;
                padding: 35px 30px;
                text-align: center;
            }}
            .signature {{
                margin: 20px 0;
            }}
            .signature-logo {{
                width: 60px;
                height: 60px;
                margin: 0 auto 15px;
                background: white;
                border-radius: 50%;
                padding: 8px;
            }}
            .signature h4 {{
                margin: 0 0 5px 0;
                font-size: 16px;
                color: white;
            }}
            .signature p {{
                margin: 3px 0;
                font-size: 13px;
                opacity: 0.9;
            }}
            .footer-links {{
                margin-top: 20px;
                padding-top: 20px;
                border-top: 1px solid rgba(255,255,255,0.2);
            }}
            .footer-links a {{
                color: white;
                text-decoration: none;
                margin: 0 10px;
                font-size: 13px;
            }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="header">
                {logo_tag}
                <h1>{Config.COMPANY_NAME}</h1>
                <p class="tagline">{Config.COMPANY_TAGLINE}</p>
            </div>
            
            <div class="content">
                <h2>{doc_type} Ready</h2>
                <p>Dear <strong>{data.get('client_name', 'Valued Client')}</strong>,</p>
                <p>Your {doc_type.lower()} from <strong>{Config.COMPANY_NAME}</strong> is ready. Please find it attached to this email.</p>
                
                <div class="summary">
                    <h3>Document Summary</h3>
                    <div class="summary-item">
                        <span class="summary-label">Document Number</span>
                        <span class="summary-value">{data.get('number', 'N/A')}</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-label">Date</span>
                        <span class="summary-value">{data.get('date', datetime.now().strftime('%d %B %Y'))}</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-label">Amount</span>
                        <span class="summary-value">{Config.COMPANY_CURRENCY} {data.get('total', 0):,.0f}</span>
                    </div>
                </div>
                
                <div class="cta">
                    <a href="https://{Config.COMPANY_WEBSITE}" class="button">Visit Our Website</a>
                </div>
                
                <p style="color: #718096; font-size: 14px; margin-top: 30px;">If you have any questions or concerns, please don't hesitate to reach out to us.</p>
            </div>
            
            <div class="footer">
                <div class="signature">
                    {logo_tag.replace('class="logo"', 'class="signature-logo"')}
                    <h4>{Config.FOUNDER_NAME}</h4>
                    <p>{Config.FOUNDER_TITLE}</p>
                    <p style="margin-top: 15px;">
                        <strong>{Config.COMPANY_NAME}</strong><br/>
                        {Config.COMPANY_LOCATION}<br/>
                        {Config.COMPANY_EMAIL}<br/>
                        {Config.COMPANY_WEBSITE}
                    </p>
                </div>
                
                <div class="footer-links">
                    <p style="font-size: 12px; opacity: 0.8; margin-bottom: 10px;">{Config.COMPANY_TAGLINE}</p>
                    <p style="font-size: 11px; opacity: 0.7;">&copy; {datetime.now().year} {Config.COMPANY_NAME}. All rights reserved.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

def get_otp_email_template(otp):
    """OTP email with logo"""
    logo_tag = '<img src="cid:logo" alt="Logo" class="logo">' if get_logo_path() else '<div class="logo" style="background: linear-gradient(135deg, #0EA5E9, #0284C7); color: white; font-size: 36px; font-weight: 700; display: flex; align-items: center; justify-content: center;">D</div>'
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; margin: 0; padding: 0; background: #f7fafc; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; }}
            .header {{ background: linear-gradient(135deg, {Config.PRIMARY_COLOR}, {Config.ACCENT_COLOR}); color: white; padding: 40px; text-align: center; }}
            .logo {{ width: 80px; height: 80px; margin: 0 auto 20px; background: white; border-radius: 50%; padding: 10px; }}
            .content {{ padding: 40px; text-align: center; }}
            .otp-box {{ background: #f7fafc; padding: 30px; border-radius: 12px; margin: 30px 0; border: 2px dashed {Config.PRIMARY_COLOR}; }}
            .otp {{ font-size: 42px; font-weight: 700; color: {Config.PRIMARY_COLOR}; letter-spacing: 15px; }}
            .footer {{ background: #2d3748; color: white; padding: 25px; text-align: center; font-size: 13px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                {logo_tag}
                <h1 style="margin: 0 0 10px 0;">{Config.COMPANY_NAME}</h1>
                <p style="margin: 0; font-style: italic; opacity: 0.95;">{Config.COMPANY_TAGLINE}</p>
            </div>
            <div class="content">
                <h2 style="color: {Config.PRIMARY_COLOR}; margin: 0 0 20px 0;">Your Login Verification Code</h2>
                <p style="color: #718096; font-size: 15px;">Enter this code to complete your login:</p>
                <div class="otp-box">
                    <div class="otp">{otp}</div>
                </div>
                <p style="color: #718096; font-size: 14px;">This code will expire in <strong>{Config.OTP_EXPIRY_MINUTES} minutes</strong>.</p>
                <p style="color: #e53e3e; font-size: 13px; margin-top: 30px;">⚠️ If you didn't request this code, please ignore this email.</p>
            </div>
            <div class="footer">
                {logo_tag.replace('width: 80px; height: 80px;', 'width: 50px; height: 50px;').replace('padding: 10px;', 'padding: 5px; margin-bottom: 15px;')}
                <p style="margin: 5px 0;"><strong>{Config.COMPANY_NAME}</strong></p>
                <p style="margin: 5px 0; opacity: 0.9;">{Config.COMPANY_LOCATION}</p>
                <p style="margin: 5px 0; opacity: 0.9;">{Config.COMPANY_EMAIL}</p>
            </div>
        </div>
    </body>
    </html>
    """

# ==========================================
# HELPER FUNCTIONS - SECURITY
# ==========================================

def generate_otp():
    return ''.join([str(secrets.randbelow(10)) for _ in range(6)])

def check_ip_blocked(ip_address):
    try:
        window_start = datetime.utcnow() - timedelta(hours=Config.LOGIN_ATTEMPT_WINDOW_HOURS)
        result = supabase.table('login_attempts').select('*').eq('ip_address', ip_address).eq('success', False).gte('timestamp', window_start.isoformat()).execute()
        return len(result.data) >= Config.MAX_LOGIN_ATTEMPTS
    except:
        return False

def log_login_attempt(username, ip_address, user_agent, success):
    try:
        supabase.table('login_attempts').insert({
            'username': username,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'success': success,
            'timestamp': datetime.utcnow().isoformat()
        }).execute()
        
        if not success:
            result = supabase.table('login_attempts').select('*').eq('ip_address', ip_address).eq('success', False).execute()
            if len(result.data) >= Config.MAX_LOGIN_ATTEMPTS:
                alert_html = f"<p><strong>Security Alert:</strong> Multiple failed login attempts detected.</p><p>IP Address: {ip_address}</p><p>Username: {username}</p>"
                send_email_with_logo(Config.COMPANY_EMAIL, 'Security Alert: Failed Login Attempts', alert_html, None, None)
                
                # Log security event
                log_activity('security_alert', f'Multiple failed login attempts from {ip_address}', {
                    'ip_address': ip_address,
                    'username': username,
                    'attempt_count': len(result.data)
                })
    except Exception as e:
        print(f"Error logging attempt: {e}")

# ==========================================
# HELPER FUNCTIONS - PDF WITH LOGO (FIXED)
# ==========================================

def create_qr_code(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer

def generate_pdf_kyambogo_style(doc_type, data):
    """Generate PDF with Kyambogo University style - FIXED LOGO"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=15*mm, bottomMargin=15*mm, leftMargin=20*mm, rightMargin=20*mm)
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles - smaller fonts
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading1'],
        fontSize=10,
        textColor=colors.HexColor('#2d3748'),
        spaceAfter=2,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=colors.HexColor(Config.PRIMARY_COLOR),
        spaceAfter=8,
        spaceBefore=8,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    small_text = ParagraphStyle(
        'SmallText',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#4a5568'),
        alignment=TA_CENTER
    )
    
    body_text = ParagraphStyle(
        'BodyText',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#2d3748'),
        spaceAfter=4
    )
    
    # Header with logo (FIXED)
    logo_path = get_logo_path()
    if logo_path and os.path.exists(logo_path):
        try:
            logo = RLImage(logo_path, width=50, height=50)
            logo.hAlign = 'CENTER'
            story.append(logo)
            story.append(Spacer(1, 8))
        except Exception as e:
            print(f"Error adding logo to PDF: {e}")
    
    # Company details
    story.append(Paragraph(f"<b>{Config.COMPANY_NAME}</b>", header_style))
    story.append(Paragraph(Config.COMPANY_TAGLINE, small_text))
    story.append(Paragraph(f"{Config.COMPANY_LOCATION} • {Config.COMPANY_EMAIL} • {Config.COMPANY_WEBSITE}", small_text))
    
    # Decorative line
    story.append(Spacer(1, 8))
    line_table = Table([['']], colWidths=[doc.width])
    line_table.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, 0), 2, colors.HexColor(Config.PRIMARY_COLOR)),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.HexColor(Config.ACCENT_COLOR)),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 8))
    
    # Document title with colored background
    title_table = Table([[Paragraph(f"<b>{doc_type.upper()}</b>", title_style)]], colWidths=[doc.width])
    title_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e6f7ff')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor(Config.PRIMARY_COLOR)),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(title_table)
    story.append(Spacer(1, 10))
    
    # Document info table
    info_data = [
        [Paragraph(f"<b>Document No:</b>", body_text), Paragraph(data.get('number', 'N/A'), body_text), 
         Paragraph(f"<b>Date:</b>", body_text), Paragraph(data.get('date', datetime.utcnow().strftime('%d/%m/%Y'))[:10], body_text)]
    ]
    
    if 'client_name' in data:
        info_data.append([Paragraph(f"<b>Client:</b>", body_text), Paragraph(data['client_name'], body_text), '', ''])
    
    info_table = Table(info_data, colWidths=[doc.width*0.25, doc.width*0.25, doc.width*0.25, doc.width*0.25])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f7fafc')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 12))
    
    # Items table (if applicable)
    if 'items' in data and data['items']:
        table_data = [
            [Paragraph('<b>Description</b>', body_text), 
             Paragraph('<b>Qty</b>', body_text), 
             Paragraph('<b>Rate</b>', body_text), 
             Paragraph('<b>Amount</b>', body_text)]
        ]
        
        for item in data['items']:
            table_data.append([
                Paragraph(item.get('description', ''), body_text),
                Paragraph(str(item.get('quantity', 1)), body_text),
                Paragraph(f"{Config.COMPANY_CURRENCY} {item.get('rate', 0):,.0f}", body_text),
                Paragraph(f"{Config.COMPANY_CURRENCY} {item.get('amount', 0):,.0f}", body_text)
            ])
        
        items_table = Table(table_data, colWidths=[doc.width*0.46, doc.width*0.18, doc.width*0.18, doc.width*0.18])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(Config.PRIMARY_COLOR)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 10))
        
        # Totals table
        totals_data = []
        if 'subtotal' in data:
            totals_data.append(['', '', Paragraph('<b>Subtotal:</b>', body_text), Paragraph(f"{Config.COMPANY_CURRENCY} {data['subtotal']:,.0f}", body_text)])
        if 'tax' in data and data['tax'] > 0:
            totals_data.append(['', '', Paragraph('<b>Tax:</b>', body_text), Paragraph(f"{Config.COMPANY_CURRENCY} {data['tax']:,.0f}", body_text)])
        if 'discount' in data and data['discount'] > 0:
            totals_data.append(['', '', Paragraph('<b>Discount:</b>', body_text), Paragraph(f"- {Config.COMPANY_CURRENCY} {data['discount']:,.0f}", body_text)])
        if 'total' in data:
            totals_data.append(['', '', Paragraph('<b>TOTAL:</b>', title_style), Paragraph(f"<b>{Config.COMPANY_CURRENCY} {data['total']:,.0f}</b>", title_style)])
        
        totals_table = Table(totals_data, colWidths=[doc.width*0.46, doc.width*0.18, doc.width*0.18, doc.width*0.18])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LINEABOVE', (2, -1), (-1, -1), 2, colors.HexColor(Config.PRIMARY_COLOR)),
            ('BACKGROUND', (2, -1), (-1, -1), colors.HexColor('#e6f7ff')),
        ]))
        story.append(totals_table)
    
    elif 'amount' in data:
        # For receipts - simple amount display
        amount_data = [[
            Paragraph('<b>Amount Paid:</b>', title_style),
            Paragraph(f"<b>{Config.COMPANY_CURRENCY} {data['amount']:,.0f}</b>", title_style)
        ]]
        if 'payment_method' in data:
            amount_data.append([
                Paragraph('<b>Payment Method:</b>', body_text),
                Paragraph(data['payment_method'], body_text)
            ])
        if 'description' in data:
            amount_data.append([
                Paragraph('<b>For:</b>', body_text),
                Paragraph(data['description'], body_text)
            ])
        
        amount_table = Table(amount_data, colWidths=[doc.width*0.5, doc.width*0.5])
        amount_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e6f7ff')),
            ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor(Config.PRIMARY_COLOR)),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        story.append(amount_table)
    
    story.append(Spacer(1, 20))
    
    # QR Code centered
    qr_data = f"{doc_type}:{data.get('number', 'N/A')}:{datetime.utcnow().isoformat()}"
    qr_buffer = create_qr_code(qr_data)
    qr_img = RLImage(qr_buffer, width=60, height=60)
    qr_img.hAlign = 'CENTER'
    story.append(qr_img)
    story.append(Spacer(1, 8))
    story.append(Paragraph("Scan for verification", small_text))
    
    story.append(Spacer(1, 15))
    
    # Footer
    footer_table = Table([
        [Paragraph("This is a computer-generated document. No signature required.", small_text)],
        [Paragraph(f"<b>{Config.COMPANY_NAME}</b> • {Config.COMPANY_TAGLINE}", small_text)],
        [Paragraph(f"{Config.COMPANY_LOCATION} • {Config.COMPANY_EMAIL} • {Config.COMPANY_WEBSITE}", small_text)]
    ], colWidths=[doc.width])
    footer_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f7fafc')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LINEABOVE', (0, 0), (-1, 0), 1, colors.HexColor(Config.PRIMARY_COLOR)),
    ]))
    story.append(footer_table)
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ==========================================
# HELPER FUNCTIONS - PRICING CALCULATOR
# ==========================================

def calculate_smart_price(project_type, estimated_hours, complexity, urgency, revisions):
    """Smart pricing engine to help avoid undercharging"""
    base_rates = {
        'Web Development': 50000,
        'Mobile App': 75000,
        'UI/UX Design': 40000,
        'Branding': 60000,
        'SEO/Marketing': 45000,
        'Content Creation': 35000,
        'Consulting': 80000,
        'Other': 50000
    }
    
    complexity_multipliers = {
        'Simple': 1.0,
        'Medium': 1.5,
        'Complex': 2.0,
        'Very Complex': 2.5
    }
    
    urgency_multipliers = {
        'Standard': 1.0,
        'Rush (1 week)': 1.3,
        'Urgent (3 days)': 1.5,
        'Emergency (24hrs)': 2.0
    }
    
    revision_cost = max(0, (revisions - 2)) * 20000
    
    base_rate = base_rates.get(project_type, 50000)
    complexity_multiplier = complexity_multipliers.get(complexity, 1.0)
    urgency_multiplier = urgency_multipliers.get(urgency, 1.0)
    
    base_price = base_rate * estimated_hours * complexity_multiplier * urgency_multiplier
    total_price = base_price + revision_cost
    
    min_price = total_price * 0.85
    max_price = total_price * 1.15
    
    return {
        'suggested_price': round(total_price, -3),
        'min_price': round(min_price, -3),
        'max_price': round(max_price, -3),
        'breakdown': {
            'base_rate_per_hour': base_rate,
            'total_hours': estimated_hours,
            'complexity_multiplier': complexity_multiplier,
            'urgency_multiplier': urgency_multiplier,
            'revision_cost': revision_cost,
            'base_before_revisions': round(base_price, -3)
        }
    }

# ==========================================
# HELPER FUNCTIONS - ANALYTICS
# ==========================================

def get_dashboard_analytics():
    """Get comprehensive dashboard analytics"""
    try:
        invoices = supabase.table('invoices').select('*').execute()
        expenses = supabase.table('expenses').select('*').execute()
        clients = supabase.table('clients').select('*').execute()
        
        today = datetime.utcnow().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        last_month_start = (month_start - timedelta(days=1)).replace(day=1)
        
        # Revenue calculations
        today_revenue = sum([inv['total'] for inv in invoices.data if inv['status'] == 'paid' and datetime.fromisoformat(inv['date'].replace('Z', '+00:00')).date() == today])
        week_revenue = sum([inv['total'] for inv in invoices.data if inv['status'] == 'paid' and datetime.fromisoformat(inv['date'].replace('Z', '+00:00')).date() >= week_start])
        month_revenue = sum([inv['total'] for inv in invoices.data if inv['status'] == 'paid' and datetime.fromisoformat(inv['date'].replace('Z', '+00:00')).date() >= month_start])
        last_month_revenue = sum([inv['total'] for inv in invoices.data if inv['status'] == 'paid' and last_month_start <= datetime.fromisoformat(inv['date'].replace('Z', '+00:00')).date() < month_start])
        
        # Expense calculations
        month_expenses = sum([exp['amount'] for exp in expenses.data if datetime.fromisoformat(exp['date'].replace('Z', '+00:00')).date() >= month_start])
        total_expenses = sum([exp['amount'] for exp in expenses.data])
        
        # Profit calculations
        net_profit = month_revenue - month_expenses
        profit_margin = (net_profit / month_revenue * 100) if month_revenue > 0 else 0
        
        # Growth calculations
        revenue_growth = ((month_revenue - last_month_revenue) / last_month_revenue * 100) if last_month_revenue > 0 else 0
        
        # Outstanding invoices
        outstanding = sum([inv['total'] for inv in invoices.data if inv['status'] == 'pending'])
        
        # Top clients
        client_revenue = {}
        for inv in invoices.data:
            if inv['status'] == 'paid':
                client_id = inv.get('client_id')
                if client_id:
                    client_revenue[client_id] = client_revenue.get(client_id, 0) + inv['total']
        
        top_clients = sorted(client_revenue.items(), key=lambda x: x[1], reverse=True)[:5]
        top_clients_data = []
        for client_id, revenue in top_clients:
            client = next((c for c in clients.data if c['id'] == client_id), None)
            if client:
                top_clients_data.append({'name': client['name'], 'revenue': revenue})
        
        # Revenue by month (last 6 months)
        monthly_revenue = []
        for i in range(6):
            month_date = today.replace(day=1) - timedelta(days=30*i)
            month_start_date = month_date.replace(day=1)
            next_month = (month_start_date + timedelta(days=32)).replace(day=1)
            
            month_rev = sum([inv['total'] for inv in invoices.data if inv['status'] == 'paid' and month_start_date <= datetime.fromisoformat(inv['date'].replace('Z', '+00:00')).date() < next_month])
            monthly_revenue.insert(0, {
                'month': month_start_date.strftime('%b %Y'),
                'revenue': month_rev
            })
        
        # Expense by category
        expense_by_category = {}
        for exp in expenses.data:
            category = exp['category']
            expense_by_category[category] = expense_by_category.get(category, 0) + exp['amount']
        
        # Business health score
        health_score = min(100, max(0, 50 + profit_margin))
        
        return {
            'today_revenue': today_revenue,
            'week_revenue': week_revenue,
            'month_revenue': month_revenue,
            'total_expenses': total_expenses,
            'month_expenses': month_expenses,
            'net_profit': net_profit,
            'profit_margin': profit_margin,
            'revenue_growth': revenue_growth,
            'outstanding': outstanding,
            'health_score': health_score,
            'total_clients': len(clients.data),
            'top_clients': top_clients_data,
            'monthly_revenue': monthly_revenue,
            'expense_by_category': expense_by_category
        }
    except Exception as e:
        print(f"Analytics error: {e}")
        return None

# ==========================================
# HELPER FUNCTIONS - CEO REPORT
# ==========================================

def generate_ceo_report():
    try:
        analytics = get_dashboard_analytics()
        if not analytics:
            return
        
        today = datetime.utcnow().date()
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', sans-serif; margin: 0; padding: 0; background: #f7fafc; }}
                .container {{ max-width: 700px; margin: 0 auto; background: white; }}
                .header {{ background: linear-gradient(135deg, {Config.PRIMARY_COLOR}, {Config.ACCENT_COLOR}); color: white; padding: 40px; text-align: center; }}
                .logo {{ width: 80px; height: 80px; margin: 0 auto 20px; background: white; border-radius: 50%; padding: 10px; }}
                .content {{ padding: 40px; }}
                .metric {{ background: #f7fafc; padding: 20px; margin: 15px 0; border-radius: 12px; border-left: 4px solid {Config.PRIMARY_COLOR}; }}
                .insights {{ background: #fff3cd; padding: 25px; border-radius: 12px; margin: 25px 0; }}
                .footer {{ background: #2d3748; color: white; padding: 30px; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    {'<img src="cid:logo" alt="Logo" class="logo">' if get_logo_path() else '<div class="logo" style="font-size: 36px;">D</div>'}
                    <h1 style="margin: 0 0 10px 0;">Daily CEO Report</h1>
                    <p style="margin: 0; opacity: 0.95;">{Config.COMPANY_NAME} • {today.strftime('%d %B %Y')}</p>
                </div>
                <div class="content">
                    <h2 style="color: {Config.PRIMARY_COLOR}; margin-bottom: 25px;">Today's Performance</h2>
                    
                    <div class="metric">
                        <h3 style="margin: 0 0 10px 0; color: {Config.PRIMARY_COLOR};">Revenue: {Config.COMPANY_CURRENCY} {analytics['today_revenue']:,.0f}</h3>
                    </div>
                    
                    <div class="metric">
                        <h3 style="margin: 0 0 10px 0; color: {Config.PRIMARY_COLOR};">Monthly Revenue: {Config.COMPANY_CURRENCY} {analytics['month_revenue']:,.0f}</h3>
                        <p style="margin: 0; color: #718096;">Growth: {analytics['revenue_growth']:.1f}%</p>
                    </div>
                    
                    <div class="metric">
                        <h3 style="margin: 0 0 10px 0; color: {Config.PRIMARY_COLOR};">Expenses: {Config.COMPANY_CURRENCY} {analytics['month_expenses']:,.0f}</h3>
                    </div>
                    
                    <div class="metric">
                        <h3 style="margin: 0 0 10px 0; color: {Config.PRIMARY_COLOR};">Net Profit: {Config.COMPANY_CURRENCY} {analytics['net_profit']:,.0f}</h3>
                        <p style="margin: 0; color: #718096;">Margin: {analytics['profit_margin']:.1f}%</p>
                    </div>
                    
                    <div class="metric">
                        <h3 style="margin: 0 0 10px 0; color: {Config.PRIMARY_COLOR};">Outstanding: {Config.COMPANY_CURRENCY} {analytics['outstanding']:,.0f}</h3>
                    </div>
                    
                    <div class="metric">
                        <h3 style="margin: 0 0 10px 0; color: {Config.PRIMARY_COLOR};">Business Health Score: {analytics['health_score']:.0f}/100</h3>
                    </div>
                    
                    <div class="insights">
                        <h3 style="color: #856404; margin: 0 0 15px 0;">📊 AI Insights & Recommendations</h3>
                        <ul style="margin: 0; padding-left: 20px; color: #856404;">
                            <li style="margin: 8px 0;"><strong>Maintain:</strong> {'Strong profit margins' if analytics['profit_margin'] > 20 else 'Focus on cost control'}</li>
                            <li style="margin: 8px 0;"><strong>Improve:</strong> {'Follow up on outstanding invoices' if analytics['outstanding'] > 0 else 'Excellent payment collection'}</li>
                            <li style="margin: 8px 0;"><strong>Action:</strong> {'Consider increasing capacity' if analytics['month_revenue'] > analytics['month_expenses'] * 3 else 'Focus on revenue generation'}</li>
                            <li style="margin: 8px 0;"><strong>Growth:</strong> {'Excellent growth momentum' if analytics['revenue_growth'] > 10 else 'Focus on client acquisition'}</li>
                        </ul>
                    </div>
                </div>
                <div class="footer">
                    {'<img src="cid:logo" alt="Logo" style="width: 60px; height: 60px; background: white; border-radius: 50%; padding: 8px; margin-bottom: 15px;">' if get_logo_path() else ''}
                    <p style="margin: 5px 0;"><strong>{Config.COMPANY_NAME}</strong></p>
                    <p style="margin: 5px 0; opacity: 0.9; font-style: italic;">{Config.COMPANY_TAGLINE}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        send_email_with_logo(Config.COMPANY_EMAIL, f'Daily CEO Report - {today.strftime("%d %B %Y")}', html_content, None, None)
        
        # Log activity
        log_activity('ceo_report_sent', f'Daily CEO report sent for {today}')
        
    except Exception as e:
        print(f"Error generating CEO report: {e}")

# ==========================================
# HELPER FUNCTIONS - PAYMENT REMINDERS
# ==========================================

def send_payment_reminders():
    """Send payment reminders for overdue invoices"""
    try:
        today = datetime.utcnow().date()
        overdue_date = today - timedelta(days=7)
        
        invoices = supabase.table('invoices').select('*').eq('status', 'pending').execute()
        
        for invoice in invoices.data:
            inv_date = datetime.fromisoformat(invoice['date'].replace('Z', '+00:00')).date()
            days_overdue = (today - inv_date).days
            
            # Send reminders at 7, 14, 21 days
            if days_overdue in [7, 14, 21]:
                client = supabase.table('clients').select('*').eq('id', invoice['client_id']).execute().data[0]
                
                html = f"""
                <!DOCTYPE html>
                <html>
                <body style="font-family: Arial, sans-serif;">
                    <h2 style="color: {Config.PRIMARY_COLOR};">Payment Reminder</h2>
                    <p>Dear {client['name']},</p>
                    <p>This is a friendly reminder that Invoice <strong>{invoice['number']}</strong> for <strong>{Config.COMPANY_CURRENCY} {invoice['total']:,.0f}</strong> is now <strong>{days_overdue} days overdue</strong>.</p>
                    <p><strong>Original Date:</strong> {inv_date.strftime('%d %B %Y')}</p>
                    <p>Please settle this at your earliest convenience.</p>
                    <p>Best regards,<br>{Config.COMPANY_NAME}</p>
                </body>
                </html>
                """
                
                send_email_with_logo(client['email'], f'Reminder: Invoice {invoice["number"]} - {days_overdue} days overdue', html)
                
                # Log activity
                log_activity('payment_reminder_sent', f'Payment reminder sent for invoice {invoice["number"]}', {
                    'invoice_id': invoice['id'],
                    'client_id': client['id'],
                    'days_overdue': days_overdue
                })
    except Exception as e:
        print(f"Error sending payment reminders: {e}")

# ==========================================
# DATABASE INITIALIZATION
# ==========================================

def init_db():
    tables = [
        'users', 'clients', 'services', 'quotations', 
        'invoices', 'receipts', 'expenses', 
        'login_attempts', 'otps', 'settings', 'activity_log', 'pos_sales'
    ]
    
    for table in tables:
        try:
            supabase.table(table).select('*').limit(1).execute()
        except Exception as e:
            print(f"Table {table} check: {e}")

# ==========================================
# SCHEDULER
# ==========================================

scheduler = BackgroundScheduler()

# CEO Report (daily at 6 PM UTC = 9 PM Uganda)
if Config.CEO_REPORT_ENABLED:
    scheduler.add_job(
        func=generate_ceo_report, 
        trigger="cron", 
        hour=Config.CEO_REPORT_HOUR, 
        minute=Config.CEO_REPORT_MINUTE, 
        timezone=pytz.UTC
    )

# Payment Reminders (daily at 9 AM UTC = 12 PM Uganda)
scheduler.add_job(
    func=send_payment_reminders,
    trigger="cron",
    hour=9,
    minute=0,
    timezone=pytz.UTC
)

scheduler.start()

# Initialize
init_db()

# ==========================================
# ROUTES - FILE UPLOAD (FIXED)
# ==========================================

@app.route('/upload-logo', methods=['POST'])
@login_required
def upload_logo():
    """Upload company logo - FIXED VERSION"""
    try:
        if 'logo' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['logo']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Use PNG, JPG, or JPEG'}), 400
        
        # Save original logo
        logo_path = os.path.join(Config.UPLOAD_FOLDER, 'logo.png')
        img = Image.open(file)
        
        # Convert to RGB if needed (preserve quality)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA' or img.mode == 'LA':
                background.paste(img, mask=img.split()[-1])
            else:
                background.paste(img)
            img = background
        
        # Save as PNG
        img.save(logo_path, 'PNG', quality=95)
        
        # Generate PWA icons
        success = generate_pwa_icons()
        
        # Log activity
        log_activity('logo_uploaded', 'Company logo uploaded', {'filename': file.filename})
        
        return jsonify({
            'success': True, 
            'message': 'Logo uploaded successfully! Refresh page to see changes.',
            'icons_generated': success
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==========================================
# ROUTES - AUTH
# ==========================================

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    try:
        users = supabase.table('users').select('*').execute()
        if len(users.data) > 0:
            return redirect(url_for('login'))
    except:
        pass
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        hashed = generate_password_hash(password)
        
        try:
            supabase.table('users').insert({
                'username': username,
                'password': hashed,
                'email': Config.COMPANY_EMAIL,
                'created_at': datetime.utcnow().isoformat()
            }).execute()
            
            log_activity('user_created', f'Admin user {username} created')
            
            return redirect(url_for('login'))
        except Exception as e:
            return f"Setup error: {e}"
    
    return render_template_string(SETUP_TEMPLATE)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')
        
        if check_ip_blocked(ip_address):
            return render_template_string(LOGIN_TEMPLATE, error='Too many failed attempts. Please try again later.')
        
        try:
            user = supabase.table('users').select('*').eq('username', username).execute()
            
            if len(user.data) > 0 and check_password_hash(user.data[0]['password'], password):
                otp = generate_otp()
                expires_at = datetime.utcnow() + timedelta(minutes=Config.OTP_EXPIRY_MINUTES)
                
                supabase.table('otps').insert({
                    'user_id': user.data[0]['id'],
                    'otp': otp,
                    'expires_at': expires_at.isoformat(),
                    'used': False
                }).execute()
                
                html = get_otp_email_template(otp)
                send_email_with_logo(Config.COMPANY_EMAIL, f'Your Login Code for {Config.COMPANY_NAME}', html, None, None)
                
                session['temp_user_id'] = user.data[0]['id']
                log_login_attempt(username, ip_address, user_agent, True)
                
                log_activity('login_initiated', f'Login initiated for {username}', {'ip': ip_address})
                
                return redirect(url_for('verify_otp'))
            else:
                log_login_attempt(username, ip_address, user_agent, False)
                return render_template_string(LOGIN_TEMPLATE, error='Invalid credentials')
        except Exception as e:
            return render_template_string(LOGIN_TEMPLATE, error=f'Login error: {e}')
    
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if 'temp_user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        otp = request.form.get('otp')
        
        try:
            result = supabase.table('otps').select('*').eq('user_id', session['temp_user_id']).eq('otp', otp).eq('used', False).execute()
            
            if len(result.data) > 0:
                otp_data = result.data[0]
                expires_at = datetime.fromisoformat(otp_data['expires_at'].replace('Z', '+00:00'))
                
                if datetime.utcnow().replace(tzinfo=pytz.UTC) < expires_at.replace(tzinfo=pytz.UTC):
                    supabase.table('otps').update({'used': True}).eq('id', otp_data['id']).execute()
                    session['user_id'] = session['temp_user_id']
                    session.pop('temp_user_id', None)
                    session.permanent = True
                    
                    log_activity('login_success', f'User logged in successfully', {'user_id': session['user_id']})
                    
                    return redirect(url_for('dashboard'))
                else:
                    return render_template_string(OTP_TEMPLATE, error='OTP expired. Please login again.')
            else:
                alert_html = f"<p><strong>Failed OTP attempt</strong> for user ID: {session['temp_user_id']}</p>"
                send_email_with_logo(Config.COMPANY_EMAIL, 'Failed OTP Verification Attempt', alert_html, None, None)
                
                log_activity('otp_failed', 'Failed OTP verification attempt', {'user_id': session['temp_user_id']})
                
                return render_template_string(OTP_TEMPLATE, error='Invalid OTP')
        except Exception as e:
            return render_template_string(OTP_TEMPLATE, error=f'Verification error: {e}')
    
    return render_template_string(OTP_TEMPLATE)

@app.route('/logout')
def logout():
    log_activity('logout', 'User logged out')
    session.clear()
    return redirect(url_for('login'))

# ==========================================
# ROUTES - DASHBOARD
# ==========================================

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        analytics = get_dashboard_analytics()
        if not analytics:
            return "Error loading dashboard"
        
        return render_template_string(DASHBOARD_TEMPLATE, **analytics)
    except Exception as e:
        return f"Dashboard error: {e}"

@app.route('/api/dashboard-data')
@login_required
def dashboard_data():
    """API endpoint for dashboard analytics"""
    analytics = get_dashboard_analytics()
    return jsonify(analytics)

# ==========================================
# ROUTES - CLIENTS
# ==========================================

@app.route('/clients')
@login_required
def clients():
    try:
        result = supabase.table('clients').select('*').order('created_at', desc=True).execute()
        return render_template_string(CLIENTS_TEMPLATE, clients=result.data)
    except Exception as e:
        return f"Error: {e}"

@app.route('/clients/add', methods=['POST'])
@login_required
def add_client():
    try:
        data = {
            'name': request.form.get('name'),
            'email': request.form.get('email'),
            'phone': request.form.get('phone'),
            'company': request.form.get('company'),
            'label': request.form.get('label', 'New'),
            'created_at': datetime.utcnow().isoformat()
        }
        result = supabase.table('clients').insert(data).execute()
        
        log_activity('client_added', f'Added client: {data["name"]}', {'client_id': result.data[0]['id']})
        
        return redirect(url_for('clients'))
    except Exception as e:
        return f"Error: {e}"

@app.route('/clients/edit/<int:client_id>', methods=['POST'])
@login_required
def edit_client(client_id):
    try:
        data = {
            'name': request.form.get('name'),
            'email': request.form.get('email'),
            'phone': request.form.get('phone'),
            'company': request.form.get('company'),
            'label': request.form.get('label')
        }
        supabase.table('clients').update(data).eq('id', client_id).execute()
        
        log_activity('client_edited', f'Edited client: {data["name"]}', {'client_id': client_id})
        
        return redirect(url_for('clients'))
    except Exception as e:
        return
    
    # Continuing app.py from where we left off...

        return f"Error: {e}"

@app.route('/clients/delete/<int:client_id>')
@login_required
def delete_client(client_id):
    try:
        # Get client name before deleting
        client = supabase.table('clients').select('*').eq('id', client_id).execute().data[0]
        
        supabase.table('clients').delete().eq('id', client_id).execute()
        
        log_activity('client_deleted', f'Deleted client: {client["name"]}', {'client_id': client_id})
        
        return redirect(url_for('clients'))
    except Exception as e:
        return f"Error: {e}"

@app.route('/api/clients/search')
@login_required
def search_clients():
    """Search clients by name or email - AJAX endpoint"""
    query = request.args.get('q', '').lower()
    
    try:
        clients = supabase.table('clients').select('*').execute()
        
        results = [
            c for c in clients.data 
            if query in c['name'].lower() or query in c['email'].lower()
        ]
        
        return jsonify(results[:10])  # Limit to 10 results
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==========================================
# ROUTES - PRICING CALCULATOR
# ==========================================

@app.route('/pricing-calculator')
@login_required
def pricing_calculator():
    return render_template_string(PRICING_CALCULATOR_TEMPLATE)

@app.route('/api/calculate-price', methods=['POST'])
@login_required
def api_calculate_price():
    try:
        data = request.json
        result = calculate_smart_price(
            data['project_type'],
            float(data['estimated_hours']),
            data['complexity'],
            data['urgency'],
            int(data['revisions'])
        )
        
        log_activity('price_calculated', 'Price calculated using calculator', {
            'project_type': data['project_type'],
            'suggested_price': result['suggested_price']
        })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ==========================================
# ROUTES - QUOTATIONS
# ==========================================

@app.route('/quotations')
@login_required
def quotations():
    try:
        result = supabase.table('quotations').select('*').order('created_at', desc=True).execute()
        clients_result = supabase.table('clients').select('*').execute()
        return render_template_string(QUOTATIONS_TEMPLATE, quotations=result.data, clients=clients_result.data)
    except Exception as e:
        return f"Error: {e}"

@app.route('/quotations/add', methods=['POST'])
@login_required
def add_quotation():
    try:
        result = supabase.table('quotations').select('*').execute()
        quot_number = f"QT{len(result.data) + 1:05d}"
        
        items = json.loads(request.form.get('items', '[]'))
        subtotal = sum([item['amount'] for item in items])
        tax = float(request.form.get('tax', 0))
        discount = float(request.form.get('discount', 0))
        total = subtotal + tax - discount
        
        data = {
            'number': quot_number,
            'client_id': int(request.form.get('client_id')),
            'date': datetime.utcnow().isoformat(),
            'validity_date': request.form.get('validity_date'),
            'items': json.dumps(items),
            'subtotal': subtotal,
            'tax': tax,
            'discount': discount,
            'total': total,
            'status': 'pending'
        }
        
        quot_result = supabase.table('quotations').insert(data).execute()
        
        log_activity('quotation_created', f'Created quotation {quot_number}', {
            'quotation_id': quot_result.data[0]['id'],
            'client_id': data['client_id'],
            'total': total
        })
        
        return redirect(url_for('quotations'))
    except Exception as e:
        return f"Error: {e}"

@app.route('/quotations/convert/<int:quot_id>')
@login_required
def convert_quotation_to_invoice(quot_id):
    try:
        quot = supabase.table('quotations').select('*').eq('id', quot_id).execute().data[0]
        
        inv_result = supabase.table('invoices').select('*').execute()
        inv_number = f"INV{len(inv_result.data) + 1:05d}"
        
        invoice_data = {
            'number': inv_number,
            'client_id': quot['client_id'],
            'date': datetime.utcnow().isoformat(),
            'items': quot['items'],
            'subtotal': quot['subtotal'],
            'tax': quot['tax'],
            'discount': quot['discount'],
            'total': quot['total'],
            'status': 'pending',
            'quotation_id': quot_id
        }
        
        inv = supabase.table('invoices').insert(invoice_data).execute()
        supabase.table('quotations').update({'status': 'converted'}).eq('id', quot_id).execute()
        
        log_activity('quotation_converted', f'Converted quotation {quot["number"]} to invoice {inv_number}', {
            'quotation_id': quot_id,
            'invoice_id': inv.data[0]['id']
        })
        
        return redirect(url_for('invoices'))
    except Exception as e:
        return f"Error: {e}"

@app.route('/quotations/pdf/<int:quot_id>')
@login_required
def quotation_pdf(quot_id):
    try:
        quot = supabase.table('quotations').select('*').eq('id', quot_id).execute().data[0]
        client = supabase.table('clients').select('*').eq('id', quot['client_id']).execute().data[0]
        
        pdf_data = {
            'number': quot['number'],
            'client_name': client['name'],
            'date': quot['date'][:10],
            'items': json.loads(quot['items']),
            'subtotal': quot['subtotal'],
            'tax': quot['tax'],
            'discount': quot['discount'],
            'total': quot['total']
        }
        
        pdf = generate_pdf_kyambogo_style('Quotation', pdf_data)
        
        log_activity('quotation_pdf_downloaded', f'Downloaded PDF for quotation {quot["number"]}', {
            'quotation_id': quot_id
        })
        
        return send_file(
            io.BytesIO(pdf),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'Quotation_{quot["number"]}.pdf'
        )
    except Exception as e:
        return f"Error: {e}"

@app.route('/quotations/email/<int:quot_id>')
@login_required
def email_quotation(quot_id):
    try:
        quot = supabase.table('quotations').select('*').eq('id', quot_id).execute().data[0]
        client = supabase.table('clients').select('*').eq('id', quot['client_id']).execute().data[0]
        
        pdf_data = {
            'number': quot['number'],
            'client_name': client['name'],
            'date': quot['date'][:10],
            'items': json.loads(quot['items']),
            'subtotal': quot['subtotal'],
            'tax': quot['tax'],
            'discount': quot['discount'],
            'total': quot['total']
        }
        
        pdf = generate_pdf_kyambogo_style('Quotation', pdf_data)
        html = get_email_template('Quotation', pdf_data)
        
        send_email_with_logo(client['email'], f'Quotation {quot["number"]} from {Config.COMPANY_NAME}', html, pdf, f'Quotation_{quot["number"]}.pdf')
        
        log_activity('quotation_emailed', f'Emailed quotation {quot["number"]} to {client["email"]}', {
            'quotation_id': quot_id,
            'client_email': client['email']
        })
        
        return redirect(url_for('quotations'))
    except Exception as e:
        return f"Error: {e}"

# ==========================================
# ROUTES - INVOICES
# ==========================================

@app.route('/invoices')
@login_required
def invoices():
    try:
        result = supabase.table('invoices').select('*').order('created_at', desc=True).execute()
        clients_result = supabase.table('clients').select('*').execute()
        return render_template_string(INVOICES_TEMPLATE, invoices=result.data, clients=clients_result.data)
    except Exception as e:
        return f"Error: {e}"

@app.route('/invoices/add', methods=['POST'])
@login_required
def add_invoice():
    try:
        result = supabase.table('invoices').select('*').execute()
        inv_number = f"INV{len(result.data) + 1:05d}"
        
        items = json.loads(request.form.get('items', '[]'))
        subtotal = sum([item['amount'] for item in items])
        tax = float(request.form.get('tax', 0))
        discount = float(request.form.get('discount', 0))
        total = subtotal + tax - discount
        
        data = {
            'number': inv_number,
            'client_id': int(request.form.get('client_id')),
            'date': datetime.utcnow().isoformat(),
            'items': json.dumps(items),
            'subtotal': subtotal,
            'tax': tax,
            'discount': discount,
            'total': total,
            'status': 'pending'
        }
        
        inv = supabase.table('invoices').insert(data).execute()
        
        log_activity('invoice_created', f'Created invoice {inv_number}', {
            'invoice_id': inv.data[0]['id'],
            'client_id': data['client_id'],
            'total': total
        })
        
        return redirect(url_for('invoices'))
    except Exception as e:
        return f"Error: {e}"

@app.route('/invoices/mark-paid/<int:inv_id>')
@login_required
def mark_invoice_paid(inv_id):
    try:
        payment_method = request.args.get('method', 'Bank Transfer')
        
        supabase.table('invoices').update({
            'status': 'paid', 
            'paid_date': datetime.utcnow().isoformat()
        }).eq('id', inv_id).execute()
        
        invoice = supabase.table('invoices').select('*').eq('id', inv_id).execute().data[0]
        result = supabase.table('receipts').select('*').execute()
        rec_number = f"REC{len(result.data) + 1:05d}"
        
        client = supabase.table('clients').select('*').eq('id', invoice['client_id']).execute().data[0]
        
        receipt_data = {
            'number': rec_number,
            'invoice_id': inv_id,
            'client_id': invoice['client_id'],
            'pos_sale': False,
            'date': datetime.utcnow().isoformat(),
            'amount': invoice['total'],
            'payment_method': payment_method,
            'description': f'Payment for Invoice {invoice["number"]}'
        }
        
        rec = supabase.table('receipts').insert(receipt_data).execute()
        
        # Auto-send receipt email
        pdf_data = {
            'number': rec_number,
            'client_name': client['name'],
            'date': receipt_data['date'][:10],
            'amount': receipt_data['amount'],
            'payment_method': payment_method,
            'description': receipt_data['description']
        }
        pdf = generate_pdf_kyambogo_style('Receipt', pdf_data)
        html = get_email_template('Receipt', pdf_data)
        send_email_with_logo(client['email'], f'Receipt {rec_number} from {Config.COMPANY_NAME}', html, pdf, f'Receipt_{rec_number}.pdf')
        
        log_activity('invoice_paid', f'Marked invoice {invoice["number"]} as paid, receipt {rec_number} generated', {
            'invoice_id': inv_id,
            'receipt_id': rec.data[0]['id'],
            'amount': invoice['total']
        })
        
        return redirect(url_for('invoices'))
    except Exception as e:
        return f"Error: {e}"

@app.route('/invoices/pdf/<int:inv_id>')
@login_required
def invoice_pdf(inv_id):
    try:
        invoice = supabase.table('invoices').select('*').eq('id', inv_id).execute().data[0]
        client = supabase.table('clients').select('*').eq('id', invoice['client_id']).execute().data[0]
        
        pdf_data = {
            'number': invoice['number'],
            'client_name': client['name'],
            'date': invoice['date'][:10],
            'items': json.loads(invoice['items']),
            'subtotal': invoice['subtotal'],
            'tax': invoice['tax'],
            'discount': invoice['discount'],
            'total': invoice['total']
        }
        
        pdf = generate_pdf_kyambogo_style('Invoice', pdf_data)
        
        log_activity('invoice_pdf_downloaded', f'Downloaded PDF for invoice {invoice["number"]}', {
            'invoice_id': inv_id
        })
        
        return send_file(
            io.BytesIO(pdf),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'Invoice_{invoice["number"]}.pdf'
        )
    except Exception as e:
        return f"Error: {e}"

@app.route('/invoices/email/<int:inv_id>')
@login_required
def email_invoice(inv_id):
    try:
        invoice = supabase.table('invoices').select('*').eq('id', inv_id).execute().data[0]
        client = supabase.table('clients').select('*').eq('id', invoice['client_id']).execute().data[0]
        
        pdf_data = {
            'number': invoice['number'],
            'client_name': client['name'],
            'date': invoice['date'][:10],
            'items': json.loads(invoice['items']),
            'subtotal': invoice['subtotal'],
            'tax': invoice['tax'],
            'discount': invoice['discount'],
            'total': invoice['total']
        }
        
        pdf = generate_pdf_kyambogo_style('Invoice', pdf_data)
        html = get_email_template('Invoice', pdf_data)
        
        send_email_with_logo(client['email'], f'Invoice {invoice["number"]} from {Config.COMPANY_NAME}', html, pdf, f'Invoice_{invoice["number"]}.pdf')
        
        log_activity('invoice_emailed', f'Emailed invoice {invoice["number"]} to {client["email"]}', {
            'invoice_id': inv_id,
            'client_email': client['email']
        })
        
        return redirect(url_for('invoices'))
    except Exception as e:
        return f"Error: {e}"

@app.route('/invoices/whatsapp/<int:inv_id>')
@login_required
def whatsapp_invoice(inv_id):
    try:
        invoice = supabase.table('invoices').select('*').eq('id', inv_id).execute().data[0]
        client = supabase.table('clients').select('*').eq('id', invoice['client_id']).execute().data[0]
        
        message = f"Hello {client['name']}, your invoice {invoice['number']} for {Config.COMPANY_CURRENCY} {invoice['total']:,.0f} is ready. Please check your email for details."
        phone = client['phone'].replace('+', '').replace(' ', '')
        
        whatsapp_url = f"https://wa.me/{phone}?text={message}"
        
        log_activity('invoice_whatsapp_shared', f'Shared invoice {invoice["number"]} via WhatsApp', {
            'invoice_id': inv_id,
            'client_phone': phone
        })
        
        return redirect(whatsapp_url)
    except Exception as e:
        return f"Error: {e}"

# ==========================================
# ROUTES - RECEIPTS
# ==========================================

@app.route('/receipts')
@login_required
def receipts():
    try:
        result = supabase.table('receipts').select('*').order('created_at', desc=True).execute()
        return render_template_string(RECEIPTS_TEMPLATE, receipts=result.data)
    except Exception as e:
        return f"Error: {e}"

@app.route('/receipts/pdf/<int:rec_id>')
@login_required
def receipt_pdf(rec_id):
    try:
        receipt = supabase.table('receipts').select('*').eq('id', rec_id).execute().data[0]
        client = supabase.table('clients').select('*').eq('id', receipt['client_id']).execute().data[0]
        
        pdf_data = {
            'number': receipt['number'],
            'client_name': client['name'],
            'date': receipt['date'][:10],
            'amount': receipt['amount'],
            'payment_method': receipt['payment_method'],
            'description': receipt.get('description', '')
        }
        
        pdf = generate_pdf_kyambogo_style('Receipt', pdf_data)
        
        log_activity('receipt_pdf_downloaded', f'Downloaded PDF for receipt {receipt["number"]}', {
            'receipt_id': rec_id
        })
        
        return send_file(
            io.BytesIO(pdf),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'Receipt_{receipt["number"]}.pdf'
        )
    except Exception as e:
        return f"Error: {e}"

# ==========================================
# ROUTES - POS (NEW FEATURE!)
# ==========================================

@app.route('/pos')
@login_required
def pos():
    """Point of Sale interface for quick sales"""
    try:
        clients = supabase.table('clients').select('*').execute()
        return render_template_string(POS_TEMPLATE, clients=clients.data)
    except Exception as e:
        return f"Error: {e}"

@app.route('/pos/sale', methods=['POST'])
@login_required
def create_pos_sale():
    """Create quick POS sale with instant receipt"""
    try:
        # Get form data
        client_name = request.form.get('client_name')
        client_email = request.form.get('client_email')
        service_description = request.form.get('service_description')
        amount = float(request.form.get('amount'))
        payment_method = request.form.get('payment_method', 'Cash')
        
        # Get or create client
        client_result = supabase.table('clients').select('*').eq('email', client_email).execute()
        
        if len(client_result.data) > 0:
            client_id = client_result.data[0]['id']
        else:
            # Create new client
            new_client = supabase.table('clients').insert({
                'name': client_name,
                'email': client_email,
                'phone': '',
                'company': '',
                'label': 'New',
                'created_at': datetime.utcnow().isoformat()
            }).execute()
            client_id = new_client.data[0]['id']
        
        # Generate receipt number
        receipts = supabase.table('receipts').select('*').execute()
        rec_number = f"REC{len(receipts.data) + 1:05d}"
        
        # Create receipt
        receipt_data = {
            'number': rec_number,
            'invoice_id': None,
            'client_id': client_id,
            'pos_sale': True,
            'date': datetime.utcnow().isoformat(),
            'amount': amount,
            'payment_method': payment_method,
            'description': service_description
        }
        
        receipt = supabase.table('receipts').insert(receipt_data).execute()
        
        # Create POS sale record
        pos_data = {
            'receipt_id': receipt.data[0]['id'],
            'client_name': client_name,
            'client_email': client_email,
            'service_description': service_description,
            'amount': amount,
            'payment_method': payment_method,
            'created_at': datetime.utcnow().isoformat()
        }
        
        supabase.table('pos_sales').insert(pos_data).execute()
        
        # Generate and email receipt
        pdf_data = {
            'number': rec_number,
            'client_name': client_name,
            'date': receipt_data['date'][:10],
            'amount': amount,
            'payment_method': payment_method,
            'description': service_description
        }
        
        pdf = generate_pdf_kyambogo_style('Receipt', pdf_data)
        html = get_email_template('Receipt', pdf_data)
        
        email_sent = send_email_with_logo(
            client_email, 
            f'Receipt {rec_number} from {Config.COMPANY_NAME}', 
            html, 
            pdf, 
            f'Receipt_{rec_number}.pdf'
        )
        
        log_activity('pos_sale_created', f'POS sale created: {rec_number} - {Config.COMPANY_CURRENCY} {amount:,.0f}', {
            'receipt_id': receipt.data[0]['id'],
            'client_name': client_name,
            'amount': amount
        })
        
        return jsonify({
            'success': True,
            'receipt_number': rec_number,
            'email_sent': email_sent,
            'message': f'Receipt {rec_number} created and emailed to {client_email}'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==========================================
# ROUTES - EXPENSES
# ==========================================

@app.route('/expenses')
@login_required
def expenses():
    try:
        result = supabase.table('expenses').select('*').order('date', desc=True).execute()
        
        total = sum([exp['amount'] for exp in result.data])
        by_category = {}
        for exp in result.data:
            cat = exp['category']
            by_category[cat] = by_category.get(cat, 0) + exp['amount']
        
        return render_template_string(EXPENSES_TEMPLATE, expenses=result.data, total=total, by_category=by_category)
    except Exception as e:
        return f"Error: {e}"

@app.route('/expenses/add', methods=['POST'])
@login_required
def add_expense():
    try:
        data = {
            'category': request.form.get('category'),
            'description': request.form.get('description'),
            'amount': float(request.form.get('amount')),
            'date': datetime.utcnow().isoformat()
        }
        exp = supabase.table('expenses').insert(data).execute()
        
        log_activity('expense_added', f'Added expense: {data["description"]} - {Config.COMPANY_CURRENCY} {data["amount"]:,.0f}', {
            'expense_id': exp.data[0]['id'],
            'category': data['category'],
            'amount': data['amount']
        })
        
        return redirect(url_for('expenses'))
    except Exception as e:
        return f"Error: {e}"

@app.route('/expenses/delete/<int:exp_id>')
@login_required
def delete_expense(exp_id):
    """Delete expense - NEW"""
    try:
        expense = supabase.table('expenses').select('*').eq('id', exp_id).execute().data[0]
        supabase.table('expenses').delete().eq('id', exp_id).execute()
        
        log_activity('expense_deleted', f'Deleted expense: {expense["description"]}', {
            'expense_id': exp_id,
            'amount': expense['amount']
        })
        
        return redirect(url_for('expenses'))
    except Exception as e:
        return f"Error: {e}"

# ==========================================
# ROUTES - REPORTS
# ==========================================

@app.route('/reports')
@login_required
def reports():
    return render_template_string(REPORTS_TEMPLATE)

@app.route('/reports/generate', methods=['POST'])
@login_required
def generate_report():
    try:
        report_type = request.form.get('report_type')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        if report_type == 'revenue':
            invoices = supabase.table('invoices').select('*').execute()
            data = [inv for inv in invoices.data if inv['status'] == 'paid' and start_date <= inv['date'][:10] <= end_date]
        elif report_type == 'expenses':
            expenses = supabase.table('expenses').select('*').execute()
            data = [exp for exp in expenses.data if start_date <= exp['date'][:10] <= end_date]
        elif report_type == 'clients':
            data = supabase.table('clients').select('*').execute().data
        else:
            return "Invalid report type"
        
        output = io.StringIO()
        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        
        log_activity('report_generated', f'Generated {report_type} report for {start_date} to {end_date}', {
            'report_type': report_type,
            'start_date': start_date,
            'end_date': end_date
        })
        
        response = Response(output.getvalue(), mimetype='text/csv')
        response.headers['Content-Disposition'] = f'attachment; filename={report_type}_report_{datetime.utcnow().strftime("%Y%m%d")}.csv'
        return response
        
    except Exception as e:
        return f"Error: {e}"

# ==========================================
# ROUTES - SECURITY
# ==========================================

@app.route('/security')
@login_required
def security():
    try:
        attempts = supabase.table('login_attempts').select('*').order('timestamp', desc=True).limit(50).execute()
        return render_template_string(SECURITY_TEMPLATE, attempts=attempts.data)
    except Exception as e:
        return f"Error: {e}"

@app.route('/security/activity')
@login_required
def security_activity():
    """Activity log - NEW ENHANCED SECURITY FEATURE"""
    try:
        # Get filter parameters
        activity_type = request.args.get('type', 'all')
        limit = int(request.args.get('limit', 100))
        
        if activity_type == 'all':
            activities = supabase.table('activity_log').select('*').order('created_at', desc=True).limit(limit).execute()
        else:
            activities = supabase.table('activity_log').select('*').eq('activity_type', activity_type).order('created_at', desc=True).limit(limit).execute()
        
        return render_template_string(ACTIVITY_LOG_TEMPLATE, activities=activities.data)
    except Exception as e:
        return f"Error: {e}"

# ==========================================
# ROUTES - SETTINGS
# ==========================================

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        try:
            settings_result = supabase.table('settings').select('*').limit(1).execute()
            
            settings_data = {
                'email_sender': request.form.get('email_sender'),
                'company_name': request.form.get('company_name'),
                'company_tagline': request.form.get('company_tagline'),
                'company_website': request.form.get('company_website'),
                'company_location': request.form.get('company_location'),
                'primary_color': request.form.get('primary_color'),
                'accent_color': request.form.get('accent_color'),
                'secondary_color': request.form.get('secondary_color'),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            if len(settings_result.data) > 0:
                supabase.table('settings').update(settings_data).eq('id', settings_result.data[0]['id']).execute()
            else:
                supabase.table('settings').insert(settings_data).execute()
            
            log_activity('settings_updated', 'Company settings updated', settings_data)
            
            return redirect(url_for('settings'))
        except Exception as e:
            return f"Error: {e}"
    
    try:
        settings_result = supabase.table('settings').select('*').limit(1).execute()
        settings_data = settings_result.data[0] if len(settings_result.data) > 0 else {}
        return render_template_string(SETTINGS_TEMPLATE, settings=settings_data)
    except:
        return render_template_string(SETTINGS_TEMPLATE, settings={})

# ==========================================
# ROUTES - PWA
# ==========================================

@app.route('/manifest.json')
def manifest():
    return jsonify({
        'name': Config.PWA_NAME,
        'short_name': Config.PWA_SHORT_NAME,
        'description': f'{Config.COMPANY_NAME} - {Config.COMPANY_TAGLINE}',
        'start_url': '/',
        'display': 'standalone',
        'background_color': '#ffffff',
        'theme_color': Config.PRIMARY_COLOR,
        'icons': [
            {
                'src': '/static/icon-192.png',
                'sizes': '192x192',
                'type': 'image/png',
                'purpose': 'any maskable'
            },
            {
                'src': '/static/icon-512.png',
                'sizes': '512x512',
                'type': 'image/png',
                'purpose': 'any maskable'
            }
        ]
    })

@app.route('/sw.js')
def service_worker():
    return render_template_string(SERVICE_WORKER, mimetype='application/javascript')

@app.route('/favicon.ico')
def favicon():
    return send_file('static/favicon.ico', mimetype='image/x-icon')

# ==========================================
# HTML TEMPLATES - COMPLETE WITH ALL FIXES
# ==========================================

BASE_STYLE = f"""
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    
    :root {{
        --primary: {Config.PRIMARY_COLOR};
        --accent: {Config.ACCENT_COLOR};
        --secondary: {Config.SECONDARY_COLOR};
        --sidebar-bg: linear-gradient(180deg, {Config.PRIMARY_COLOR} 0%, {Config.ACCENT_COLOR} 100%);
        --text-dark: #1a202c;
        --text-light: #718096;
    }}
    
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        background: #f7fafc;
        color: var(--text-dark);
        font-size: 14px;
    }}
    
    /* Mobile Sidebar - Blue gradient */
    .mobile-nav {{
        position: fixed;
        top: 0;
        left: -100%;
        width: 280px;
        height: 100vh;
        background: var(--sidebar-bg);
        transition: left 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        z-index: 1000;
        overflow-y: auto;
        box-shadow: 4px 0 20px rgba(0,0,0,0.2);
    }}
    
    .mobile-nav.active {{
        left: 0;
    }}
    
    .mobile-overlay {{
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100vh;
        background: rgba(0,0,0,0.6);
        z-index: 999;
        display: none;
        backdrop-filter: blur(2px);
    }}
    
    .mobile-overlay.active {{
        display: block;
    }}
    
    .nav-header {{
        padding: 25px 20px;
        background: rgba(255,255,255,0.1);
        backdrop-filter: blur(10px);
        color: white;
        text-align: center;
        border-bottom: 1px solid rgba(255,255,255,0.2);
    }}
    
    .nav-logo {{
        width: 60px;
        height: 60px;
        margin: 0 auto 12px;
        background: white;
        border-radius: 50%;
        padding: 6px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }}
    
    .nav-logo img {{
        width: 100%;
        height: 100%;
        object-fit: contain;
        border-radius: 50%;
    }}
    
    .nav-header h2 {{
        font-size: 16px;
        margin-bottom: 4px;
        font-weight: 700;
    }}
    
    .nav-header p {{
        font-size: 11px;
        opacity: 0.9;
        font-style: italic;
    }}
    
    .nav-links {{
        padding: 10px 0;
    }}
    
    .nav-links a {{
        display: flex;
        align-items: center;
        padding: 12px 20px;
        color: white;
        text-decoration: none;
        transition: all 0.2s;
        font-size: 13px;
        font-weight: 500;
        border-left: 4px solid transparent;
    }}
    
    .nav-links a:hover, .nav-links a.active {{
        background: rgba(255,255,255,0.15);
        border-left-color: white;
    }}
    
    .nav-links a span {{
        margin-right: 10px;
        font-size: 16px;
        width: 20px;
        text-align: center;
    }}
    
    /* Top Bar */
    .top-bar {{
        position: sticky;
        top: 0;
        background: white;
        padding: 12px 16px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        z-index: 100;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        min-height: 56px;
    }}
    
    .hamburger {{
        display: flex;
        flex-direction: column;
        gap: 4px;
        cursor: pointer;
        padding: 6px;
        background: var(--primary);
        border-radius: 6px;
    }}
    
    .hamburger span {{
        width: 22px;
        height: 2px;
        background: white;
        border-radius: 2px;
        transition: 0.3s;
    }}
    
    .hamburger.active span:nth-child(1) {{
        transform: rotate(45deg) translate(5px, 5px);
    }}
    
    .hamburger.active span:nth-child(2) {{
        opacity: 0;
    }}
    
    .hamburger.active span:nth-child(3) {{
        transform: rotate(-45deg) translate(5px, -5px);
    }}
    
    .page-title {{
        font-size: 16px;
        font-weight: 600;
        color: var(--text-dark);
    }}
    
    /* Main Content */
    .main-content {{
        padding: 16px;
        max-width: 1400px;
        margin: 0 auto;
        background: #f7fafc;
        min-height: calc(100vh - 56px);
        padding-bottom: 80px; /* Space for bottom nav on mobile */
    }}
    
    /* Cards */
    .card {{
        background: white;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border: 1px solid #e5e7eb;
    }}
    
    .metric-card {{
        text-align: center;
        padding: 20px 16px;
        background: linear-gradient(135deg, #ffffff 0%, #f7fafc 100%);
    }}
    
    .metric-icon {{
        width: 44px;
        height: 44px;
        margin: 0 auto 12px;
        background: var(--sidebar-bg);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 20px;
        box-shadow: 0 4px 12px rgba(14, 165, 233, 0.3);
    }}
    
    .metric-value {{
        font-size: 24px;
        font-weight: 700;
        color: var(--primary);
        margin: 8px 0;
    }}
    
    .metric-label {{
        color: var(--text-light);
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 500;
    }}
    
    .metric-change {{
        font-size: 11px;
        margin-top: 6px;
        padding: 3px 8px;
        border-radius: 12px;
        display: inline-block;
        font-weight: 600;
    }}
    
    .metric-change.positive {{
        background: #d4edda;
        color: #155724;
    }}
    
    .metric-change.negative {{
        background: #f8d7da;
        color: #721c24;
    }}
    
    /* Grid Layout */
    .grid {{
        display: grid;
        gap: 16px;
    }}
    
    .grid-2 {{ grid-template-columns: repeat(2, 1fr); }}
    .grid-3 {{ grid-template-columns: repeat(3, 1fr); }}
    .grid-4 {{ grid-template-columns: repeat(4, 1fr); }}
    
    @media (max-width: 768px) {{
        .grid-2, .grid-3, .grid-4 {{ grid-template-columns: 1fr; }}
        .grid-2.keep-mobile {{ grid-template-columns: repeat(2, 1fr); }}
    }}
    
    /* Buttons */
    .btn {{
        padding: 10px 20px;
        border: none;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        text-decoration: none;
        justify-content: center;
        min-height: 40px;
    }}
    
    .btn-primary {{
        background: var(--sidebar-bg);
        color: white;
        box-shadow: 0 2px 8px rgba(14, 165, 233, 0.3);
    }}
    
    .btn-primary:hover {{
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(14, 165, 233, 0.4);
    }}
    
    .btn-secondary {{
        background: white;
        color: var(--primary);
        border: 2px solid var(--primary);
    }}
    
    .btn-secondary:hover {{
        background: var(--primary);
        color: white;
    }}
    
    .btn-success {{
        background: linear-gradient(135deg, #10b981, #059669);
        color: white;
    }}
    
    .btn-danger {{
        background: linear-gradient(135deg, #ef4444, #dc2626);
        color: white;
    }}
    
    .btn-sm {{
        padding: 6px 12px;
        font-size: 12px;
        min-height: 32px;
    }}
    
    .btn:disabled {{
        opacity: 0.5;
        cursor: not-allowed;
    }}
    
    /* Forms */
    .form-group {{
        margin-bottom: 16px;
    }}
    
    .form-label {{
        display: block;
        margin-bottom: 6px;
        color: var(--text-dark);
        font-weight: 500;
        font-size: 13px;
    }}
    
    .form-control {{
        width: 100%;
        padding: 10px 12px;
        border: 2px solid #e5e7eb;
        border-radius: 8px;
        font-size: 14px;
        background: white;
        transition: all 0.2s;
        min-height: 40px;
    }}
    
    .form-control:focus {{
        outline: none;
        border-color: var(--primary);
        box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.1);
    }}
    
    /* Modal */
    .modal {{
        display: none;
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.6);
        z-index: 2000;
        align-items: center;
        justify-content: center;
        padding: 16px;
        backdrop-filter: blur(3px);
        overflow-y: auto;
    }}
    
    .modal.active {{
        display: flex;
    }}
    
    .modal-content {{
        background: white;
        border-radius: 16px;
        max-width: 600px;
        width: 100%;
        max-height: 90vh;
        overflow-y: auto;
        padding: 24px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        animation: modalSlideUp 0.3s ease;
        margin: auto;
    }}
    
    @keyframes modalSlideUp {{
        from {{
            opacity: 0;
            transform: translateY(50px);
        }}
        to {{
            opacity: 1;
            transform: translateY(0);
        }}
    }}
    
    .modal-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
    }}
    
    .modal-title {{
        font-size: 20px;
        font-weight: 700;
        color: var(--primary);
    }}
    
    .modal-close {{
        background: none;
        border: none;
        font-size: 28px;
        cursor: pointer;
        color: var(--text-light);
        padding: 0;
        width: 30px;
        height: 30px;
        line-height: 1;
    }}
    
    /* Table */
    .table-container {{
        overflow-x: auto;
        border-radius: 10px;
        background: white;
        border: 1px solid #e5e7eb;
        -webkit-overflow-scrolling: touch;
    }}
    
    table {{
        width: 100%;
        border-collapse: collapse;
        min-width: 600px;
    }}
    
    th, td {{
        padding: 12px;
        text-align: left;
        border-bottom: 1px solid #e5e7eb;
        font-size: 13px;
        white-space: nowrap;
    }}
    
    th {{
        background: var(--sidebar-bg);
        color: white;
        font-weight: 600;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}
    
    tr:hover {{
        background: #f7fafc;
    }}
    
    tr:last-child td {{
        border-bottom: none;
    }}
    
    /* Badge */
    .badge {{
        display: inline-block;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.3px;
    }}
    
    .badge-success {{ background: #d4edda; color: #155724; }}
    .badge-warning {{ background: #fff3cd; color: #856404; }}
    .badge-danger {{ background: #f8d7da; color: #721c24; }}
    .badge-info {{ background: #d1ecf1; color: #0c5460; }}
    .badge-primary {{ background: #cce5ff; color: #004085; }}
    
    /* Toast Notifications - NEW */
    .toast {{
        position: fixed;
        top: 70px;
        right: 20px;
        background: white;
        padding: 14px 18px;
        border-radius: 10px;
        box-shadow: 0 6px 20px rgba(0,0,0,0.15);
        display: flex;
        align-items: center;
        gap: 10px;
        z-index: 9999;
        min-width: 280px;
        animation: slideInRight 0.3s ease;
        border-left: 4px solid var(--primary);
    }}
    
    .toast.toast-success {{ border-left-color: #10b981; }}
    .toast.toast-error {{ border-left-color: #ef4444; }}
    
    .toast-icon {{
        font-size: 20px;
    }}
    
    .toast-message {{
        flex: 1;
        font-size: 13px;
        font-weight: 500;
    }}
    
    .toast-hide {{
        animation: slideOutRight 0.3s ease forwards;
    }}
    
    @keyframes slideInRight {{
        from {{
            transform: translateX(400px);
            opacity: 0;
        }}
        to {{
            transform: translateX(0);
            opacity: 1;
        }}
    }}
    
    @keyframes slideOutRight {{
        to {{
            transform: translateX(400px);
            opacity: 0;
        }}
    }}
    
    /* Loading Spinner */
    .spinner {{
        border: 2px solid rgba(14, 165, 233, 0.1);
        border-top: 2px solid var(--primary);
        border-radius: 50%;
        width: 16px;
        height: 16px;
        animation: spin 0.8s linear infinite;
        display: inline-block;
        vertical-align: middle;
    }}
    
    @keyframes spin {{
        0% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(360deg); }}
    }}
    
    .btn-spinner {{
        display: none;
        align-items: center;
        gap: 8px;
    }}
    
    /* Bottom Navigation - Mobile Only */
    .bottom-nav {{
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: white;
        display: none;
        justify-content: space-around;
        padding: 8px 0;
        box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
        z-index: 100;
    }}
    
    .bottom-nav a {{
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        color: var(--text-light);
        text-decoration: none;
        font-size: 10px;
        padding: 6px 12px;
        min-width: 60px;
    }}
    
    .bottom-nav a i {{
        font-size: 20px;
    }}
    
    .bottom-nav a.active {{
        color: var(--primary);
    }}
    
    @media (max-width: 1023px) {{
        .bottom-nav {{ display: flex; }}
    }}
    
    /* PWA Install Prompt */
    .install-prompt {{
        position: fixed;
        bottom: 80px;
        left: 16px;
        right: 16px;
        background: white;
        padding: 16px;
        border-radius: 12px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.15);
        z-index: 3000;
        animation: slideInBottom 0.3s ease;
    }}
    
    .install-prompt-content {{
        display: flex;
        align-items: center;
        gap: 12px;
    }}
    
    .install-prompt img {{
        width: 40px;
        height: 40px;
        border-radius: 8px;
    }}
    
    .install-prompt > div {{
        flex: 1;
    }}
    
    .install-prompt strong {{
        display: block;
        font-size: 14px;
        margin-bottom: 2px;
    }}
    
    .install-prompt p {{
        font-size: 12px;
        color: var(--text-light);
        margin: 0;
    }}
    
    .btn-close {{
        background: none;
        border: none;
        font-size: 24px;
        cursor: pointer;
        color: var(--text-light);
        padding: 0;
        width: 24px;
        height: 24px;
    }}
    
    @keyframes slideInBottom {{
        from {{
            transform: translateY(100px);
            opacity: 0;
        }}
        to {{
            transform: translateY(0);
            opacity: 1;
        }}
    }}
    
    /* Chart Container */
    .chart-container {{
        position: relative;
        height: 280px;
        margin: 16px 0;
    }}
    
    /* Health Score */
    .health-score {{
        text-align: center;
        padding: 32px 20px;
        background: var(--sidebar-bg);
        border-radius: 16px;
        color: white;
        position: relative;
        overflow: hidden;
        box-shadow: 0 8px 24px rgba(14, 165, 233, 0.3);
    }}
    
    .health-score::before {{
        content: '';
        position: absolute;
        top: -50%;
        right: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
    }}
    
    .health-score-value {{
        font-size: 56px;
        font-weight: 700;
        margin: 16px 0;
        position: relative;
        z-index: 1;
    }}
    
    .health-score-label {{
        font-size: 14px;
        opacity: 0.95;
        position: relative;
        z-index: 1;
    }}
    
    /* Autocomplete */
    .autocomplete-results {{
        position: absolute;
        z-index: 1000;
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        max-height: 200px;
        overflow-y: auto;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        margin-top: 4px;
        width: 100%;
    }}
    
    .autocomplete-item {{
        padding: 10px 12px;
        cursor: pointer;
        border-bottom: 1px solid #f3f4f6;
    }}
    
    .autocomplete-item:hover {{
        background: #f7fafc;
    }}
    
    .autocomplete-item:last-child {{
        border-bottom: none;
    }}
    
    .autocomplete-item strong {{
        display: block;
        font-size: 13px;
        margin-bottom: 2px;
    }}
    
    .autocomplete-item small {{
        font-size: 11px;
        color: var(--text-light);
    }}
    
    /* Responsive */
    @media (min-width: 1024px) {{
        .mobile-nav {{
            position: fixed;
            left: 0;
            width: 260px;
            border-radius: 0;
        }}
        
        .hamburger {{
            display: none;
        }}
        
        .main-content {{
            margin-left: 260px;
        }}
        
        .top-bar {{
            margin-left: 260px;
        }}
        
        .bottom-nav {{
            display: none;
        }}
    }}
    
    /* Utilities */
    .text-center {{ text-align: center; }}
    .text-right {{ text-align: right; }}
    .mt-20 {{ margin-top: 20px; }}
    .mb-20 {{ margin-bottom: 20px; }}
    .flex {{ display: flex; }}
    .flex-between {{ display: flex; justify-content: space-between; align-items: center; }}
    .gap-10 {{ gap: 10px; }}
    
    /* Hide on mobile */
    @media (max-width: 768px) {{
        .hide-mobile {{ display: none !important; }}
    }}
</style>
"""

# Due to length, I'll continue with the critical templates in the next message...
# For now, let me provide the POS template and other new templates

POS_TEMPLATE = BASE_STYLE + '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>POS - Quick Sale - DeoBiz Manager</title>
    <link rel="icon" href="/favicon.ico" type="image/x-icon">
</head>
<body>
    <div class="mobile-nav" id="mobileNav">
        <div class="nav-header">
            <div class="nav-logo">
                <img src="/static/icon-192.png" alt="Logo">
            </div>
            <h2>DeoBiz Manager</h2>
            <p>Visualising Your Vision</p>
        </div>
        <div class="nav-links">
            <a href="/dashboard"><span>📊</span> Dashboard</a>
            <a href="/pos" class="active"><span>💵</span> POS - Quick Sale</a>
            <a href="/clients"><span>👥</span> Clients</a>
            <a href="/quotations"><span>📝</span> Quotations</a>
            <a href="/invoices"><span>🧾</span> Invoices</a>
            <a href="/receipts"><span>📄</span> Receipts</a>
            <a href="/expenses"><span>💰</span> Expenses</a>
            <a href="/pricing-calculator"><span>🧮</span> Pricing Calculator</a>
            <a href="/reports"><span>📈</span> Reports</a>
            <a href="/security"><span>🔒</span> Security</a>
            <a href="/settings"><span>⚙️</span> Settings</a>
            <a href="/logout"><span>🚪</span> Logout</a>
        </div>
    </div>
    
    <div class="mobile-overlay" id="mobileOverlay" onclick="toggleNav()"></div>
    
    <div class="top-bar">
        <div class="hamburger" id="hamburger" onclick="toggleNav()">
            <span></span>
            <span></span>
            <span></span>
        </div>
        <div class="page-title">💵 POS - Quick Sale</div>
        <div style="width: 40px;"></div>
    </div>
    
    <div class="main-content">
        <div class="card">
            <h2 style="color: var(--primary); margin-bottom: 8px;">🚀 Quick Sale</h2>
            <p style="color: var(--text-light); margin-bottom: 24px; font-size: 13px;">Generate instant receipt and auto-email to client</p>
            
            <form id="posForm">
                <div class="form-group" style="position: relative;">
                    <label class="form-label">Customer Name</label>
                    <input type="text" id="clientSearch" class="form-control" placeholder="Type to search..." autocomplete="off" required>
                    <div id="clientResults" class="autocomplete-results" style="display: none;"></div>
                    <input type="hidden" id="selectedClientEmail">
                </div>
                
                <div class="form-group">
                    <label class="form-label">Customer Email</label>
                    <input type="email" id="clientEmail" class="form-control" placeholder="client@email.com" required>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Service / Product Description</label>
                    <textarea id="serviceDescription" class="form-control" rows="3" placeholder="E.g., Website development, Logo design..." required></textarea>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Amount (UGX)</label>
                    <input type="number" id="amount" class="form-control" placeholder="0" min="0" step="1000" required>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Payment Method</label>
                    <select id="paymentMethod" class="form-control">
                        <option value="Cash">Cash</option>
                        <option value="Bank Transfer">Bank Transfer</option>
                        <option value="Mobile Money">Mobile Money</option>
                        <option value="Card">Card</option>
                        <option value="Cheque">Cheque</option>
                    </select>
                </div>
                
                <button type="submit" class="btn btn-primary" style="width: 100%;" id="submitBtn">
                    <span class="btn-text">💳 Generate Receipt & Email</span>
                    <span class="btn-spinner">
                        <span class="spinner"></span> Processing...
                    </span>
                </button>
            </form>
        </div>
        
        <div class="card" style="background: #fff3cd; border-color: #ffc107;">
            <strong style="color: #856404;">💡 Quick Tips:</strong>
            <ul style="margin: 8px 0 0 16px; padding: 0; color: #856404; font-size: 13px; line-height: 1.8;">
                <li>Type customer name to search existing clients</li>
                <li>Receipt auto-generates with unique number</li>
                <li>PDF auto-emails to customer instantly</li>
                <li>Perfect for walk-in sales!</li>
            </ul>
        </div>
    </div>
    
    <!-- Bottom Navigation -->
    <nav class="bottom-nav">
        <a href="/dashboard"><i>📊</i><span>Home</span></a>
        <a href="/pos" class="active"><i>💵</i><span>POS</span></a>
        <a href="/invoices"><i>🧾</i><span>Invoices</span></a>
        <a href="/clients"><i>👥</i><span>Clients</span></a>
    </nav>
    
    <script>
        function toggleNav() {
            document.getElementById('mobileNav').classList.toggle('active');
            document.getElementById('mobileOverlay').classList.toggle('active');
            document.getElementById('hamburger').classList.toggle('active');
        }
        
        // Toast notification function
        function showToast(message, type = 'success') {
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.innerHTML = `
                <span class="toast-icon">${type === 'success' ? '✅' : '❌'}</span>
                <span class="toast-message">${message}</span>
            `;
            document.body.appendChild(toast);
            
            setTimeout(() => {
                toast.classList.add('toast-hide');
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }


                
        // Client autocomplete search
        let searchTimeout;
        document.getElementById('clientSearch').addEventListener('input', function(e) {
            clearTimeout(searchTimeout);
            const query = e.target.value;
            
            if (query.length < 2) {
                document.getElementById('clientResults').style.display = 'none';
                return;
            }
            
            searchTimeout = setTimeout(async () => {
                try {
                    const response = await fetch(`/api/clients/search?q=${encodeURIComponent(query)}`);
                    const clients = await response.json();
                    
                    const resultsDiv = document.getElementById('clientResults');
                    
                    if (clients.length > 0) {
                        resultsDiv.innerHTML = clients.map(c => `
                            <div class="autocomplete-item" onclick="selectClient('${c.name.replace(/'/g, "\\'")}', '${c.email}')">
                                <strong>${c.name}</strong>
                                <small>${c.email}</small>
                            </div>
                        `).join('');
                        resultsDiv.style.display = 'block';
                    } else {
                        resultsDiv.style.display = 'none';
                    }
                } catch (error) {
                    console.error('Search error:', error);
                }
            }, 300);
        });
        
        function selectClient(name, email) {
            document.getElementById('clientSearch').value = name;
            document.getElementById('clientEmail').value = email;
            document.getElementById('selectedClientEmail').value = email;
            document.getElementById('clientResults').style.display = 'none';
        }
        
        // Close autocomplete when clicking outside
        document.addEventListener('click', function(e) {
            if (!e.target.closest('#clientSearch')) {
                document.getElementById('clientResults').style.display = 'none';
            }
        });
        
        // Form submission
        document.getElementById('posForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const submitBtn = document.getElementById('submitBtn');
            submitBtn.disabled = true;
            submitBtn.querySelector('.btn-text').style.display = 'none';
            submitBtn.querySelector('.btn-spinner').style.display = 'inline-flex';
            
            const formData = new FormData();
            formData.append('client_name', document.getElementById('clientSearch').value);
            formData.append('client_email', document.getElementById('clientEmail').value);
            formData.append('service_description', document.getElementById('serviceDescription').value);
            formData.append('amount', document.getElementById('amount').value);
            formData.append('payment_method', document.getElementById('paymentMethod').value);
            
            try {
                const response = await fetch('/pos/sale', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showToast(`✅ ${result.message}`, 'success');
                    
                    // Reset form
                    document.getElementById('posForm').reset();
                    
                    // Redirect to receipts after 2 seconds
                    setTimeout(() => {
                        window.location.href = '/receipts';
                    }, 2000);
                } else {
                    showToast(`❌ Error: ${result.error}`, 'error');
                }
            } catch (error) {
                showToast('❌ Failed to create sale. Please try again.', 'error');
                console.error('Error:', error);
            } finally {
                submitBtn.disabled = false;
                submitBtn.querySelector('.btn-text').style.display = 'inline';
                submitBtn.querySelector('.btn-spinner').style.display = 'none';
            }
        });
    </script>
</body>
</html>
'''

# Add these templates to app.py after the DASHBOARD_TEMPLATE

# ==========================================
# CLIENTS TEMPLATE - COMPLETE WITH MOBILE FIXES
# ==========================================

CLIENTS_TEMPLATE = BASE_STYLE + '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Clients - DeoBiz Manager</title>
    <link rel="icon" href="/favicon.ico" type="image/x-icon">
</head>
<body>
    <div class="mobile-nav" id="mobileNav">
        <div class="nav-header">
            <div class="nav-logo">
                <img src="/static/icon-192.png" alt="Logo">
            </div>
            <h2>DeoBiz Manager</h2>
            <p>Visualising Your Vision</p>
        </div>
        <div class="nav-links">
            <a href="/dashboard"><span>📊</span> Dashboard</a>
            <a href="/pos"><span>💵</span> POS - Quick Sale</a>
            <a href="/clients" class="active"><span>👥</span> Clients</a>
            <a href="/quotations"><span>📝</span> Quotations</a>
            <a href="/invoices"><span>🧾</span> Invoices</a>
            <a href="/receipts"><span>📄</span> Receipts</a>
            <a href="/expenses"><span>💰</span> Expenses</a>
            <a href="/pricing-calculator"><span>🧮</span> Pricing Calculator</a>
            <a href="/reports"><span>📈</span> Reports</a>
            <a href="/security"><span>🔒</span> Security</a>
            <a href="/settings"><span>⚙️</span> Settings</a>
            <a href="/logout"><span>🚪</span> Logout</a>
        </div>
    </div>
    
    <div class="mobile-overlay" id="mobileOverlay" onclick="toggleNav()"></div>
    
    <div class="top-bar">
        <div class="hamburger" id="hamburger" onclick="toggleNav()">
            <span></span>
            <span></span>
            <span></span>
        </div>
        <div class="page-title">👥 Clients</div>
        <button class="btn btn-primary btn-sm" onclick="openModal()">+ Add</button>
    </div>
    
    <div class="main-content">
        <div class="card">
            <div style="margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center;">
                <h3 style="color: var(--primary); font-size: 16px; margin: 0;">📋 Client List ({{ clients|length }})</h3>
            </div>
            
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th class="hide-mobile">Email</th>
                            <th class="hide-mobile">Phone</th>
                            <th>Label</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for client in clients %}
                        <tr>
                            <td>
                                <strong>{{ client.name }}</strong>
                                <div class="hide-desktop" style="font-size: 11px; color: var(--text-light); margin-top: 2px;">
                                    {{ client.email }}<br>{{ client.phone }}
                                </div>
                            </td>
                            <td class="hide-mobile">{{ client.email }}</td>
                            <td class="hide-mobile">{{ client.phone }}</td>
                            <td><span class="badge badge-{{ 'success' if client.label == 'High Value' else 'info' if client.label == 'Repeat' else 'warning' }}">{{ client.label }}</span></td>
                            <td style="white-space: nowrap;">
                                <button class="btn btn-secondary btn-sm" onclick="editClient({{ client.id }}, '{{ client.name.replace("'", "\\'") }}', '{{ client.email }}', '{{ client.phone }}', '{{ client.company }}', '{{ client.label }}')">✏️</button>
                                <a href="/clients/delete/{{ client.id }}" class="btn btn-danger btn-sm" onclick="return confirm('Delete {{ client.name }}?')">🗑️</a>
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="5" style="text-align: center; padding: 40px; color: var(--text-light);">
                                No clients yet. Click "+ Add" to create your first client.
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    
    <!-- Bottom Navigation -->
    <nav class="bottom-nav">
        <a href="/dashboard"><i>📊</i><span>Home</span></a>
        <a href="/pos"><i>💵</i><span>POS</span></a>
        <a href="/invoices"><i>🧾</i><span>Invoices</span></a>
        <a href="/clients" class="active"><i>👥</i><span>Clients</span></a>
    </nav>
    
    <!-- Add Modal -->
    <div class="modal" id="addModal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 class="modal-title">Add New Client</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <form method="POST" action="/clients/add" id="addForm">
                <div class="form-group">
                    <label class="form-label">Full Name *</label>
                    <input type="text" name="name" class="form-control" required autofocus>
                </div>
                <div class="form-group">
                    <label class="form-label">Email Address *</label>
                    <input type="email" name="email" class="form-control" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Phone Number *</label>
                    <input type="tel" name="phone" class="form-control" placeholder="+256..." required>
                </div>
                <div class="form-group">
                    <label class="form-label">Company (Optional)</label>
                    <input type="text" name="company" class="form-control">
                </div>
                <div class="form-group">
                    <label class="form-label">Client Label</label>
                    <select name="label" class="form-control">
                        <option value="New">New</option>
                        <option value="Repeat">Repeat</option>
                        <option value="High Value">High Value</option>
                    </select>
                </div>
                <div class="flex gap-10">
                    <button type="submit" class="btn btn-primary" style="flex: 1;">💾 Save Client</button>
                    <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                </div>
            </form>
        </div>
    </div>
    
    <!-- Edit Modal -->
    <div class="modal" id="editModal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 class="modal-title">Edit Client</h3>
                <button class="modal-close" onclick="closeEditModal()">&times;</button>
            </div>
            <form method="POST" id="editForm">
                <div class="form-group">
                    <label class="form-label">Full Name *</label>
                    <input type="text" name="name" id="editName" class="form-control" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Email Address *</label>
                    <input type="email" name="email" id="editEmail" class="form-control" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Phone Number *</label>
                    <input type="tel" name="phone" id="editPhone" class="form-control" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Company (Optional)</label>
                    <input type="text" name="company" id="editCompany" class="form-control">
                </div>
                <div class="form-group">
                    <label class="form-label">Client Label</label>
                    <select name="label" id="editLabel" class="form-control">
                        <option value="New">New</option>
                        <option value="Repeat">Repeat</option>
                        <option value="High Value">High Value</option>
                    </select>
                </div>
                <div class="flex gap-10">
                    <button type="submit" class="btn btn-primary" style="flex: 1;">💾 Update Client</button>
                    <button type="button" class="btn btn-secondary" onclick="closeEditModal()">Cancel</button>
                </div>
            </form>
        </div>
    </div>
    
    <script>
        function toggleNav() {
            document.getElementById('mobileNav').classList.toggle('active');
            document.getElementById('mobileOverlay').classList.toggle('active');
            document.getElementById('hamburger').classList.toggle('active');
        }
        
        function showToast(message, type = 'success') {
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.innerHTML = `
                <span class="toast-icon">${type === 'success' ? '✅' : '❌'}</span>
                <span class="toast-message">${message}</span>
            `;
            document.body.appendChild(toast);
            setTimeout(() => {
                toast.classList.add('toast-hide');
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
        
        function openModal() {
            document.getElementById('addModal').classList.add('active');
        }
        
        function closeModal() {
            document.getElementById('addModal').classList.remove('active');
        }
        
        function editClient(id, name, email, phone, company, label) {
            document.getElementById('editForm').action = '/clients/edit/' + id;
            document.getElementById('editName').value = name;
            document.getElementById('editEmail').value = email;
            document.getElementById('editPhone').value = phone;
            document.getElementById('editCompany').value = company;
            document.getElementById('editLabel').value = label;
            document.getElementById('editModal').classList.add('active');
        }
        
        function closeEditModal() {
            document.getElementById('editModal').classList.remove('active');
        }
        
        // Show success toast if client added
        if (window.location.search.includes('success')) {
            showToast('✅ Client saved successfully!');
            window.history.replaceState({}, document.title, window.location.pathname);
        }
    </script>
</body>
</html>
'''

# ==========================================
# PRICING CALCULATOR TEMPLATE - COMPLETE
# ==========================================

PRICING_CALCULATOR_TEMPLATE = BASE_STYLE + '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Pricing Calculator - DeoBiz Manager</title>
    <link rel="icon" href="/favicon.ico" type="image/x-icon">
</head>
<body>
    <div class="mobile-nav" id="mobileNav">
        <div class="nav-header">
            <div class="nav-logo">
                <img src="/static/icon-192.png" alt="Logo">
            </div>
            <h2>DeoBiz Manager</h2>
            <p>Visualising Your Vision</p>
        </div>
        <div class="nav-links">
            <a href="/dashboard"><span>📊</span> Dashboard</a>
            <a href="/pos"><span>💵</span> POS - Quick Sale</a>
            <a href="/clients"><span>👥</span> Clients</a>
            <a href="/quotations"><span>📝</span> Quotations</a>
            <a href="/invoices"><span>🧾</span> Invoices</a>
            <a href="/receipts"><span>📄</span> Receipts</a>
            <a href="/expenses"><span>💰</span> Expenses</a>
            <a href="/pricing-calculator" class="active"><span>🧮</span> Pricing Calculator</a>
            <a href="/reports"><span>📈</span> Reports</a>
            <a href="/security"><span>🔒</span> Security</a>
            <a href="/settings"><span>⚙️</span> Settings</a>
            <a href="/logout"><span>🚪</span> Logout</a>
        </div>
    </div>
    
    <div class="mobile-overlay" id="mobileOverlay" onclick="toggleNav()"></div>
    
    <div class="top-bar">
        <div class="hamburger" id="hamburger" onclick="toggleNav()">
            <span></span>
            <span></span>
            <span></span>
        </div>
        <div class="page-title">🧮 Pricing Calculator</div>
        <div style="width: 40px;"></div>
    </div>
    
    <div class="main-content">
        <div class="card">
            <h2 style="color: var(--primary); margin-bottom: 8px; font-size: 18px;">💡 Smart Pricing Calculator</h2>
            <p style="color: var(--text-light); margin-bottom: 24px; font-size: 13px;">Get AI-powered pricing recommendations to avoid undercharging</p>
            
            <form id="pricingForm">
                <div class="form-group">
                    <label class="form-label">Project Type</label>
                    <select id="projectType" class="form-control" required>
                        <option value="Web Development">Web Development</option>
                        <option value="Mobile App">Mobile App</option>
                        <option value="UI/UX Design">UI/UX Design</option>
                        <option value="Branding">Branding</option>
                        <option value="SEO/Marketing">SEO/Marketing</option>
                        <option value="Content Creation">Content Creation</option>
                        <option value="Consulting">Consulting</option>
                        <option value="Other">Other</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Estimated Hours</label>
                    <input type="number" id="estimatedHours" class="form-control" min="1" step="0.5" placeholder="E.g., 20" required>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Complexity Level</label>
                    <select id="complexity" class="form-control" required>
                        <option value="Simple">Simple (Basic project)</option>
                        <option value="Medium">Medium (Standard project)</option>
                        <option value="Complex">Complex (Advanced features)</option>
                        <option value="Very Complex">Very Complex (Enterprise level)</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Urgency / Timeline</label>
                    <select id="urgency" class="form-control" required>
                        <option value="Standard">Standard (2+ weeks)</option>
                        <option value="Rush (1 week)">Rush (1 week)</option>
                        <option value="Urgent (3 days)">Urgent (3 days)</option>
                        <option value="Emergency (24hrs)">Emergency (24 hours)</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Number of Revisions Included</label>
                    <input type="number" id="revisions" class="form-control" min="0" value="2" required>
                    <small style="color: var(--text-light); font-size: 11px; margin-top: 4px; display: block;">First 2 revisions are free, additional revisions add UGX 20,000 each</small>
                </div>
                
                <button type="submit" class="btn btn-primary" style="width: 100%;">🎯 Calculate Recommended Price</button>
            </form>
        </div>
        
        <div id="resultCard" class="card" style="display: none;">
            <h3 style="color: var(--primary); margin-bottom: 20px; font-size: 18px;">💰 Recommended Pricing</h3>
            
            <div style="background: linear-gradient(135deg, var(--primary), var(--accent)); color: white; padding: 28px; border-radius: 14px; text-align: center; margin-bottom: 20px; box-shadow: 0 8px 20px rgba(14, 165, 233, 0.3);">
                <div style="font-size: 12px; opacity: 0.9; margin-bottom: 8px; letter-spacing: 1px;">SUGGESTED PRICE</div>
                <div style="font-size: 40px; font-weight: 700; margin-bottom: 4px;" id="suggestedPrice">0</div>
                <div style="font-size: 12px; opacity: 0.9;">UGX</div>
            </div>
            
            <div class="grid grid-2">
                <div style="background: rgba(14, 165, 233, 0.1); padding: 18px; border-radius: 10px; text-align: center;">
                    <div style="color: var(--text-light); font-size: 11px; margin-bottom: 6px; text-transform: uppercase;">Minimum</div>
                    <div style="font-size: 20px; font-weight: 600; color: var(--primary);" id="minPrice">0</div>
                </div>
                <div style="background: rgba(14, 165, 233, 0.1); padding: 18px; border-radius: 10px; text-align: center;">
                    <div style="color: var(--text-light); font-size: 11px; margin-bottom: 6px; text-transform: uppercase;">Maximum</div>
                    <div style="font-size: 20px; font-weight: 600; color: var(--primary);" id="maxPrice">0</div>
                </div>
            </div>
            
            <div style="margin-top: 28px;">
                <h4 style="color: var(--primary); margin-bottom: 14px; font-size: 15px;">📊 Price Breakdown</h4>
                <table style="width: 100%; font-size: 13px;">
                    <tr>
                        <td style="padding: 8px 0; color: var(--text-light);">Base Rate per Hour</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: 600;" id="baseRate">0</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: var(--text-light);">Total Hours</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: 600;" id="totalHours">0</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: var(--text-light);">Complexity Multiplier</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: 600;" id="complexityMult">0x</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: var(--text-light);">Urgency Multiplier</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: 600;" id="urgencyMult">0x</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: var(--text-light);">Revision Cost</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: 600;" id="revisionCost">0</td>
                    </tr>
                    <tr style="border-top: 2px solid var(--primary);">
                        <td style="padding: 10px 0; font-weight: 700; font-size: 14px;">Base Price</td>
                        <td style="padding: 10px 0; text-align: right; font-weight: 700; color: var(--primary); font-size: 14px;" id="baseBeforeRevisions">0</td>
                    </tr>
                </table>
            </div>
            
            <div style="margin-top: 28px; padding: 18px; background: #fff3cd; border-radius: 10px; border-left: 4px solid #ffc107;">
                <strong style="color: #856404; font-size: 13px;">💡 Pro Tip:</strong>
                <p style="color: #856404; margin-top: 8px; line-height: 1.6; font-size: 12px;">
                    This is a recommended range based on industry standards. Consider your experience level, client budget, and project scope when finalizing the price. Don't forget to account for meetings, revisions, and project management time!
                </p>
            </div>
        </div>
    </div>
    
    <nav class="bottom-nav">
        <a href="/dashboard"><i>📊</i><span>Home</span></a>
        <a href="/pos"><i>💵</i><span>POS</span></a>
        <a href="/invoices"><i>🧾</i><span>Invoices</span></a>
        <a href="/clients"><i>👥</i><span>Clients</span></a>
    </nav>
    
    <script>
        function toggleNav() {
            document.getElementById('mobileNav').classList.toggle('active');
            document.getElementById('mobileOverlay').classList.toggle('active');
            document.getElementById('hamburger').classList.toggle('active');
        }
        
        function showToast(message, type = 'success') {
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.innerHTML = `
                <span class="toast-icon">${type === 'success' ? '✅' : '❌'}</span>
                <span class="toast-message">${message}</span>
            `;
            document.body.appendChild(toast);
            setTimeout(() => {
                toast.classList.add('toast-hide');
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
        
        document.getElementById('pricingForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const data = {
                project_type: document.getElementById('projectType').value,
                estimated_hours: parseFloat(document.getElementById('estimatedHours').value),
                complexity: document.getElementById('complexity').value,
                urgency: document.getElementById('urgency').value,
                revisions: parseInt(document.getElementById('revisions').value)
            };
            
            try {
                const response = await fetch('/api/calculate-price', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                
                document.getElementById('suggestedPrice').textContent = result.suggested_price.toLocaleString();
                document.getElementById('minPrice').textContent = 'UGX ' + result.min_price.toLocaleString();
                document.getElementById('maxPrice').textContent = 'UGX ' + result.max_price.toLocaleString();
                
                document.getElementById('baseRate').textContent = 'UGX ' + result.breakdown.base_rate_per_hour.toLocaleString();
                document.getElementById('totalHours').textContent = result.breakdown.total_hours;
                document.getElementById('complexityMult').textContent = result.breakdown.complexity_multiplier + 'x';
                document.getElementById('urgencyMult').textContent = result.breakdown.urgency_multiplier + 'x';
                document.getElementById('revisionCost').textContent = 'UGX ' + result.breakdown.revision_cost.toLocaleString();
                document.getElementById('baseBeforeRevisions').textContent = 'UGX ' + result.breakdown.base_before_revisions.toLocaleString();
                
                document.getElementById('resultCard').style.display = 'block';
                document.getElementById('resultCard').scrollIntoView({ behavior: 'smooth' });
                
                showToast('✅ Price calculated successfully!');
            } catch (error) {
                showToast('❌ Error calculating price: ' + error.message, 'error');
            }
        });
    </script>
</body>
</html>
'''

# Continue with QUOTATIONS, INVOICES, RECEIPTS, EXPENSES, REPORTS, SECURITY, SETTINGS templates...
# Due to length, I'll provide them in smaller chunks

QUOTATIONS_TEMPLATE = BASE_STYLE + '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Quotations - DeoBiz Manager</title>
    <link rel="icon" href="/favicon.ico" type="image/x-icon">
</head>
<body>
    <div class="mobile-nav" id="mobileNav">
        <div class="nav-header">
            <div class="nav-logo">
                <img src="/static/icon-192.png" alt="Logo">
            </div>
            <h2>DeoBiz Manager</h2>
            <p>Visualising Your Vision</p>
        </div>
        <div class="nav-links">
            <a href="/dashboard"><span>📊</span> Dashboard</a>
            <a href="/pos"><span>💵</span> POS - Quick Sale</a>
            <a href="/clients"><span>👥</span> Clients</a>
            <a href="/quotations" class="active"><span>📝</span> Quotations</a>
            <a href="/invoices"><span>🧾</span> Invoices</a>
            <a href="/receipts"><span>📄</span> Receipts</a>
            <a href="/expenses"><span>💰</span> Expenses</a>
            <a href="/pricing-calculator"><span>🧮</span> Pricing Calculator</a>
            <a href="/reports"><span>📈</span> Reports</a>
            <a href="/security"><span>🔒</span> Security</a>
            <a href="/settings"><span>⚙️</span> Settings</a>
            <a href="/logout"><span>🚪</span> Logout</a>
        </div>
    </div>
    
    <div class="mobile-overlay" id="mobileOverlay" onclick="toggleNav()"></div>
    
    <div class="top-bar">
        <div class="hamburger" id="hamburger" onclick="toggleNav()">
            <span></span>
            <span></span>
            <span></span>
        </div>
        <div class="page-title">📝 Quotations</div>
        <button class="btn btn-primary btn-sm" onclick="openModal()">+ New</button>
    </div>
    
    <div class="main-content">
        <div class="card">
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Number</th>
                            <th class="hide-mobile">Client</th>
                            <th class="hide-mobile">Date</th>
                            <th>Amount</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for quot in quotations %}
                        <tr>
                            <td><strong>{{ quot.number }}</strong></td>
                            <td class="hide-mobile">Client #{{ quot.client_id }}</td>
                            <td class="hide-mobile">{{ quot.date[:10] }}</td>
                            <td><strong>{{ "{:,.0f}".format(quot.total) }}</strong></td>
                            <td><span class="badge badge-{{ 'success' if quot.status == 'converted' else 'warning' }}">{{ quot.status }}</span></td>
                            <td style="white-space: nowrap;">
                                {% if quot.status != 'converted' %}
                                <a href="/quotations/convert/{{ quot.id }}" class="btn btn-success btn-sm" onclick="return confirm('Convert to invoice?')">→📄</a>
                                {% endif %}
                                <a href="/quotations/pdf/{{ quot.id }}" class="btn btn-secondary btn-sm">📥</a>
                                <a href="/quotations/email/{{ quot.id }}" class="btn btn-primary btn-sm" onclick="showToast('Sending email...'); return true;">📧</a>
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="6" style="text-align: center; padding: 40px; color: var(--text-light);">
                                No quotations yet. Click "+ New" to create your first quotation.
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    
    <nav class="bottom-nav">
        <a href="/dashboard"><i>📊</i><span>Home</span></a>
        <a href="/pos"><i>💵</i><span>POS</span></a>
        <a href="/invoices"><i>🧾</i><span>Invoices</span></a>
        <a href="/clients"><i>👥</i><span>Clients</span></a>
    </nav>
    
    <!-- Add Modal -->
    <div class="modal" id="addModal">
        <div class="modal-content" style="max-width: 700px;">
            <div class="modal-header">
                <h3 class="modal-title">Create Quotation</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <form method="POST" action="/quotations/add" onsubmit="return prepareSubmit()">
                <div class="form-group">
                    <label class="form-label">Client *</label>
                    <select name="client_id" class="form-control" required>
                        <option value="">-- Select Client --</option>
                        {% for client in clients %}
                        <option value="{{ client.id }}">{{ client.name }} ({{ client.email }})</option>
                        {% endfor %}
                    </select>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Valid Until</label>
                    <input type="date" name="validity_date" class="form-control" required>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Line Items</label>
                    <div id="items">
                        <div class="item-row" style="display: grid; grid-template-columns: 2fr 1fr 1fr 1fr auto; gap: 8px; margin-bottom: 8px; align-items: center;">
                            <input type="text" placeholder="Description" class="form-control item-desc" required style="min-height: 38px;">
                            <input type="number" placeholder="Qty" class="form-control item-qty" value="1" min="1" required style="min-height: 38px;">
                            <input type="number" placeholder="Rate" class="form-control item-rate" min="0" required style="min-height: 38px;">
                            <input type="number" placeholder="Amount" class="form-control item-amount" readonly style="min-height: 38px; background: #f3f4f6;">
                            <button type="button" onclick="removeItem(this)" class="btn btn-danger btn-sm">×</button>
                        </div>
                    </div>
                    <button type="button" onclick="addItem()" class="btn btn-secondary btn-sm">+ Add Item</button>
                </div>
                
                <div class="grid grid-2">
                    <div class="form-group">
                        <label class="form-label">Tax (UGX)</label>
                        <input type="number" name="tax" class="form-control" value="0" min="0" step="100">
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Discount (UGX)</label>
                        <input type="number" name="discount" class="form-control" value="0" min="0" step="100">
                    </div>
                </div>
                
                <input type="hidden" name="items" id="items-data">
                
                <div class="flex gap-10">
                    <button type="submit" class="btn btn-primary" style="flex: 1;">💾 Create Quotation</button>
                    <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                </div>
            </form>
        </div>
    </div>
    
    <script>
        function toggleNav() {
            document.getElementById('mobileNav').classList.toggle('active');
            document.getElementById('mobileOverlay').classList.toggle('active');
            document.getElementById('hamburger').classList.toggle('active');
        }
        
        function showToast(message, type = 'success') {
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.innerHTML = `
                <span class="toast-icon">${type === 'success' ? '✅' : '❌'}</span>
                <span class="toast-message">${message}</span>
            `;
            document.body.appendChild(toast);
            setTimeout(() => {
                toast.classList.add('toast-hide');
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
        
        function openModal() {
            document.getElementById('addModal').classList.add('active');
        }
        
        function closeModal() {
            document.getElementById('addModal').classList.remove('active');
        }
        
        function addItem() {
            const container = document.getElementById('items');
            const div = document.createElement('div');
            div.className = 'item-row';
            div.style.cssText = 'display: grid; grid-template-columns: 2fr 1fr 1fr 1fr auto; gap: 8px; margin-bottom: 8px; align-items: center;';
            div.innerHTML = `
                <input type="text" placeholder="Description" class="form-control item-desc" required style="min-height: 38px;">
                <input type="number" placeholder="Qty" class="form-control item-qty" value="1" min="1" required style="min-height: 38px;">
                <input type="number" placeholder="Rate" class="form-control item-rate" min="0" required style="min-height: 38px;">
                <input type="number" placeholder="Amount" class="form-control item-amount" readonly style="min-height: 38px; background: #f3f4f6;">
                <button type="button" onclick="removeItem(this)" class="btn btn-danger btn-sm">×</button>
            `;
            container.appendChild(div);
            attachCalculators();
        }
        
        function removeItem(btn) {
            if (document.querySelectorAll('.item-row').length > 1) {
                btn.parentElement.remove();
            } else {
                showToast('❌ At least one item is required', 'error');
            }
        }
        
        function attachCalculators() {
            document.querySelectorAll('.item-qty, .item-rate').forEach(input => {
                input.removeEventListener('input', calculateItem);
                input.addEventListener('input', calculateItem);
            });
        }
        
        function calculateItem(e) {
            const row = e.target.closest('.item-row');
            const qty = parseFloat(row.querySelector('.item-qty').value) || 0;
            const rate = parseFloat(row.querySelector('.item-rate').value) || 0;
            row.querySelector('.item-amount').value = (qty * rate).toFixed(0);
        }
        
        function prepareSubmit() {
            const items = [];
            document.querySelectorAll('.item-row').forEach(row => {
                const desc = row.querySelector('.item-desc').value;
                const qty = parseFloat(row.querySelector('.item-qty').value);
                const rate = parseFloat(row.querySelector('.item-rate').value);
                const amount = parseFloat(row.querySelector('.item-amount').value);
                
                if (desc && qty && rate) {
                    items.push({
                        description: desc,
                        quantity: qty,
                        rate: rate,
                        amount: amount
                    });
                }
            });
            
            if (items.length === 0) {
                showToast('❌ Please add at least one item', 'error');
                return false;
            }
            
            document.getElementById('items-data').value = JSON.stringify(items);
            return true;
        }
        
        attachCalculators();
    </script>
</body>
</html>
'''

# Let me continue with INVOICES, RECEIPTS, EXPENSES, REPORTS, SECURITY, and SETTINGS in the next part...
# Continue adding these templates to app.py

# ==========================================
# INVOICES TEMPLATE - COMPLETE
# ==========================================

INVOICES_TEMPLATE = BASE_STYLE + '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Invoices - DeoBiz Manager</title>
    <link rel="icon" href="/favicon.ico" type="image/x-icon">
</head>
<body>
    <div class="mobile-nav" id="mobileNav">
        <div class="nav-header">
            <div class="nav-logo">
                <img src="/static/icon-192.png" alt="Logo">
            </div>
            <h2>DeoBiz Manager</h2>
            <p>Visualising Your Vision</p>
        </div>
        <div class="nav-links">
            <a href="/dashboard"><span>📊</span> Dashboard</a>
            <a href="/pos"><span>💵</span> POS - Quick Sale</a>
            <a href="/clients"><span>👥</span> Clients</a>
            <a href="/quotations"><span>📝</span> Quotations</a>
            <a href="/invoices" class="active"><span>🧾</span> Invoices</a>
            <a href="/receipts"><span>📄</span> Receipts</a>
            <a href="/expenses"><span>💰</span> Expenses</a>
            <a href="/pricing-calculator"><span>🧮</span> Pricing Calculator</a>
            <a href="/reports"><span>📈</span> Reports</a>
            <a href="/security"><span>🔒</span> Security</a>
            <a href="/settings"><span>⚙️</span> Settings</a>
            <a href="/logout"><span>🚪</span> Logout</a>
        </div>
    </div>
    
    <div class="mobile-overlay" id="mobileOverlay" onclick="toggleNav()"></div>
    
    <div class="top-bar">
        <div class="hamburger" id="hamburger" onclick="toggleNav()">
            <span></span>
            <span></span>
            <span></span>
        </div>
        <div class="page-title">🧾 Invoices</div>
        <button class="btn btn-primary btn-sm" onclick="openModal()">+ New</button>
    </div>
    
    <div class="main-content">
        <div class="card">
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Number</th>
                            <th class="hide-mobile">Client</th>
                            <th class="hide-mobile">Date</th>
                            <th>Amount</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for inv in invoices %}
                        <tr>
                            <td>
                                <strong>{{ inv.number }}</strong>
                                <div class="hide-desktop" style="font-size: 11px; color: var(--text-light); margin-top: 2px;">
                                    {{ inv.date[:10] }}
                                </div>
                            </td>
                            <td class="hide-mobile">Client #{{ inv.client_id }}</td>
                            <td class="hide-mobile">{{ inv.date[:10] }}</td>
                            <td><strong>{{ "{:,.0f}".format(inv.total) }}</strong></td>
                            <td><span class="badge badge-{{ 'success' if inv.status == 'paid' else 'warning' }}">{{ inv.status }}</span></td>
                            <td style="white-space: nowrap;">
                                {% if inv.status == 'pending' %}
                                <button class="btn btn-success btn-sm" onclick="markPaid({{ inv.id }})">✓</button>
                                {% endif %}
                                <a href="/invoices/pdf/{{ inv.id }}" class="btn btn-secondary btn-sm">📥</a>
                                <a href="/invoices/email/{{ inv.id }}" class="btn btn-primary btn-sm" onclick="showToast('Sending...'); return true;">📧</a>
                                <a href="/invoices/whatsapp/{{ inv.id }}" class="btn btn-success btn-sm">💬</a>
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="6" style="text-align: center; padding: 40px; color: var(--text-light);">
                                No invoices yet. Click "+ New" to create your first invoice.
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    
    <nav class="bottom-nav">
        <a href="/dashboard"><i>📊</i><span>Home</span></a>
        <a href="/pos"><i>💵</i><span>POS</span></a>
        <a href="/invoices" class="active"><i>🧾</i><span>Invoices</span></a>
        <a href="/clients"><i>👥</i><span>Clients</span></a>
    </nav>
    
    <!-- Mark Paid Modal -->
    <div class="modal" id="paidModal">
        <div class="modal-content" style="max-width: 400px;">
            <div class="modal-header">
                <h3 class="modal-title">Mark as Paid</h3>
                <button class="modal-close" onclick="closePaidModal()">&times;</button>
            </div>
            <form id="paidForm">
                <div class="form-group">
                    <label class="form-label">Payment Method</label>
                    <select id="paymentMethod" class="form-control">
                        <option value="Bank Transfer">Bank Transfer</option>
                        <option value="Mobile Money">Mobile Money</option>
                        <option value="Cash">Cash</option>
                        <option value="Card">Card</option>
                        <option value="Cheque">Cheque</option>
                    </select>
                </div>
                <div class="flex gap-10">
                    <button type="submit" class="btn btn-success" style="flex: 1;">✓ Mark Paid & Generate Receipt</button>
                    <button type="button" class="btn btn-secondary" onclick="closePaidModal()">Cancel</button>
                </div>
            </form>
        </div>
    </div>
    
    <!-- Add Modal -->
    <div class="modal" id="addModal">
        <div class="modal-content" style="max-width: 700px;">
            <div class="modal-header">
                <h3 class="modal-title">Create Invoice</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <form method="POST" action="/invoices/add" onsubmit="return prepareSubmit()">
                <div class="form-group">
                    <label class="form-label">Client *</label>
                    <select name="client_id" class="form-control" required>
                        <option value="">-- Select Client --</option>
                        {% for client in clients %}
                        <option value="{{ client.id }}">{{ client.name }} ({{ client.email }})</option>
                        {% endfor %}
                    </select>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Line Items</label>
                    <div id="items">
                        <div class="item-row" style="display: grid; grid-template-columns: 2fr 1fr 1fr 1fr auto; gap: 8px; margin-bottom: 8px; align-items: center;">
                            <input type="text" placeholder="Description" class="form-control item-desc" required style="min-height: 38px;">
                            <input type="number" placeholder="Qty" class="form-control item-qty" value="1" min="1" required style="min-height: 38px;">
                            <input type="number" placeholder="Rate" class="form-control item-rate" min="0" required style="min-height: 38px;">
                            <input type="number" placeholder="Amount" class="form-control item-amount" readonly style="min-height: 38px; background: #f3f4f6;">
                            <button type="button" onclick="removeItem(this)" class="btn btn-danger btn-sm">×</button>
                        </div>
                    </div>
                    <button type="button" onclick="addItem()" class="btn btn-secondary btn-sm">+ Add Item</button>
                </div>
                
                <div class="grid grid-2">
                    <div class="form-group">
                        <label class="form-label">Tax (UGX)</label>
                        <input type="number" name="tax" class="form-control" value="0" min="0" step="100">
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Discount (UGX)</label>
                        <input type="number" name="discount" class="form-control" value="0" min="0" step="100">
                    </div>
                </div>
                
                <input type="hidden" name="items" id="items-data">
                
                <div class="flex gap-10">
                    <button type="submit" class="btn btn-primary" style="flex: 1;">💾 Create Invoice</button>
                    <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                </div>
            </form>
        </div>
    </div>
    
    <script>
        let currentInvoiceId = null;
        
        function toggleNav() {
            document.getElementById('mobileNav').classList.toggle('active');
            document.getElementById('mobileOverlay').classList.toggle('active');
            document.getElementById('hamburger').classList.toggle('active');
        }
        
        function showToast(message, type = 'success') {
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.innerHTML = `
                <span class="toast-icon">${type === 'success' ? '✅' : '❌'}</span>
                <span class="toast-message">${message}</span>
            `;
            document.body.appendChild(toast);
            setTimeout(() => {
                toast.classList.add('toast-hide');
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
        
        function openModal() {
            document.getElementById('addModal').classList.add('active');
        }
        
        function closeModal() {
            document.getElementById('addModal').classList.remove('active');
        }
        
        function markPaid(invoiceId) {
            currentInvoiceId = invoiceId;
            document.getElementById('paidModal').classList.add('active');
        }
        
        function closePaidModal() {
            document.getElementById('paidModal').classList.remove('active');
            currentInvoiceId = null;
        }
        
        document.getElementById('paidForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const method = document.getElementById('paymentMethod').value;
            window.location.href = `/invoices/mark-paid/${currentInvoiceId}?method=${encodeURIComponent(method)}`;
        });
        
        function addItem() {
            const container = document.getElementById('items');
            const div = document.createElement('div');
            div.className = 'item-row';
            div.style.cssText = 'display: grid; grid-template-columns: 2fr 1fr 1fr 1fr auto; gap: 8px; margin-bottom: 8px; align-items: center;';
            div.innerHTML = `
                <input type="text" placeholder="Description" class="form-control item-desc" required style="min-height: 38px;">
                <input type="number" placeholder="Qty" class="form-control item-qty" value="1" min="1" required style="min-height: 38px;">
                <input type="number" placeholder="Rate" class="form-control item-rate" min="0" required style="min-height: 38px;">
                <input type="number" placeholder="Amount" class="form-control item-amount" readonly style="min-height: 38px; background: #f3f4f6;">
                <button type="button" onclick="removeItem(this)" class="btn btn-danger btn-sm">×</button>
            `;
            container.appendChild(div);
            attachCalculators();
        }
        
        function removeItem(btn) {
            if (document.querySelectorAll('.item-row').length > 1) {
                btn.parentElement.remove();
            } else {
                showToast('❌ At least one item is required', 'error');
            }
        }
        
        function attachCalculators() {
            document.querySelectorAll('.item-qty, .item-rate').forEach(input => {
                input.removeEventListener('input', calculateItem);
                input.addEventListener('input', calculateItem);
            });
        }
        
        function calculateItem(e) {
            const row = e.target.closest('.item-row');
            const qty = parseFloat(row.querySelector('.item-qty').value) || 0;
            const rate = parseFloat(row.querySelector('.item-rate').value) || 0;
            row.querySelector('.item-amount').value = (qty * rate).toFixed(0);
        }
        
        function prepareSubmit() {
            const items = [];
            document.querySelectorAll('.item-row').forEach(row => {
                const desc = row.querySelector('.item-desc').value;
                const qty = parseFloat(row.querySelector('.item-qty').value);
                const rate = parseFloat(row.querySelector('.item-rate').value);
                const amount = parseFloat(row.querySelector('.item-amount').value);
                
                if (desc && qty && rate) {
                    items.push({
                        description: desc,
                        quantity: qty,
                        rate: rate,
                        amount: amount
                    });
                }
            });
            
            if (items.length === 0) {
                showToast('❌ Please add at least one item', 'error');
                return false;
            }
            
            document.getElementById('items-data').value = JSON.stringify(items);
            return true;
        }
        
        attachCalculators();
    </script>
</body>
</html>
'''

# ==========================================
# RECEIPTS TEMPLATE - COMPLETE
# ==========================================

RECEIPTS_TEMPLATE = BASE_STYLE + '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Receipts - DeoBiz Manager</title>
    <link rel="icon" href="/favicon.ico" type="image/x-icon">
</head>
<body>
    <div class="mobile-nav" id="mobileNav">
        <div class="nav-header">
            <div class="nav-logo">
                <img src="/static/icon-192.png" alt="Logo">
            </div>
            <h2>DeoBiz Manager</h2>
            <p>Visualising Your Vision</p>
        </div>
        <div class="nav-links">
            <a href="/dashboard"><span>📊</span> Dashboard</a>
            <a href="/pos"><span>💵</span> POS - Quick Sale</a>
            <a href="/clients"><span>👥</span> Clients</a>
            <a href="/quotations"><span>📝</span> Quotations</a>
            <a href="/invoices"><span>🧾</span> Invoices</a>
            <a href="/receipts" class="active"><span>📄</span> Receipts</a>
            <a href="/expenses"><span>💰</span> Expenses</a>
            <a href="/pricing-calculator"><span>🧮</span> Pricing Calculator</a>
            <a href="/reports"><span>📈</span> Reports</a>
            <a href="/security"><span>🔒</span> Security</a>
            <a href="/settings"><span>⚙️</span> Settings</a>
            <a href="/logout"><span>🚪</span> Logout</a>
        </div>
    </div>
    
    <div class="mobile-overlay" id="mobileOverlay" onclick="toggleNav()"></div>
    
    <div class="top-bar">
        <div class="hamburger" id="hamburger" onclick="toggleNav()">
            <span></span>
            <span></span>
            <span></span>
        </div>
        <div class="page-title">📄 Receipts</div>
        <a href="/pos" class="btn btn-primary btn-sm">+ POS Sale</a>
    </div>
    
    <div class="main-content">
        <div class="card">
            <h3 style="color: var(--primary); font-size: 16px; margin-bottom: 16px;">📋 All Receipts ({{ receipts|length }})</h3>
            
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Number</th>
                            <th class="hide-mobile">Invoice/POS</th>
                            <th class="hide-mobile">Date</th>
                            <th>Amount</th>
                            <th class="hide-mobile">Method</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for rec in receipts %}
                        <tr>
                            <td>
                                <strong>{{ rec.number }}</strong>
                                <div class="hide-desktop" style="font-size: 11px; color: var(--text-light); margin-top: 2px;">
                                    {{ rec.date[:10] }} • {{ rec.payment_method }}
                                </div>
                            </td>
                            <td class="hide-mobile">
                                {% if rec.pos_sale %}
                                <span class="badge badge-success">POS Sale</span>
                                {% else %}
                                <span class="badge badge-info">INV #{{ rec.invoice_id }}</span>
                                {% endif %}
                            </td>
                            <td class="hide-mobile">{{ rec.date[:10] }}</td>
                            <td><strong>{{ "{:,.0f}".format(rec.amount) }}</strong></td>
                            <td class="hide-mobile"><span class="badge badge-primary">{{ rec.payment_method }}</span></td>
                            <td>
                                <a href="/receipts/pdf/{{ rec.id }}" class="btn btn-primary btn-sm">📥 Download</a>
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="6" style="text-align: center; padding: 40px; color: var(--text-light);">
                                No receipts yet. Mark an invoice as paid or make a POS sale to generate receipts.
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="card" style="background: #e6f7ff; border-color: var(--primary);">
            <strong style="color: var(--primary); font-size: 13px;">ℹ️ About Receipts</strong>
            <p style="color: var(--text-dark); margin-top: 8px; font-size: 12px; line-height: 1.6;">
                Receipts are automatically generated when:<br>
                • You mark an invoice as paid<br>
                • You complete a POS sale<br><br>
                All receipts are auto-emailed to clients with PDF attachment.
            </p>
        </div>
    </div>
    
    <nav class="bottom-nav">
        <a href="/dashboard"><i>📊</i><span>Home</span></a>
        <a href="/pos"><i>💵</i><span>POS</span></a>
        <a href="/invoices"><i>🧾</i><span>Invoices</span></a>
        <a href="/clients"><i>👥</i><span>Clients</span></a>
    </nav>
    
    <script>
        function toggleNav() {
            document.getElementById('mobileNav').classList.toggle('active');
            document.getElementById('mobileOverlay').classList.toggle('active');
            document.getElementById('hamburger').classList.toggle('active');
        }
    </script>
</body>
</html>
'''

# ==========================================
# EXPENSES TEMPLATE - COMPLETE
# ==========================================

EXPENSES_TEMPLATE = BASE_STYLE + '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Expenses - DeoBiz Manager</title>
    <link rel="icon" href="/favicon.ico" type="image/x-icon">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
</head>
<body>
    <div class="mobile-nav" id="mobileNav">
        <div class="nav-header">
            <div class="nav-logo">
                <img src="/static/icon-192.png" alt="Logo">
            </div>
            <h2>DeoBiz Manager</h2>
            <p>Visualising Your Vision</p>
        </div>
        <div class="nav-links">
            <a href="/dashboard"><span>📊</span> Dashboard</a>
            <a href="/pos"><span>💵</span> POS - Quick Sale</a>
            <a href="/clients"><span>👥</span> Clients</a>
            <a href="/quotations"><span>📝</span> Quotations</a>
            <a href="/invoices"><span>🧾</span> Invoices</a>
            <a href="/receipts"><span>📄</span> Receipts</a>
            <a href="/expenses" class="active"><span>💰</span> Expenses</a>
            <a href="/pricing-calculator"><span>🧮</span> Pricing Calculator</a>
            <a href="/reports"><span>📈</span> Reports</a>
            <a href="/security"><span>🔒</span> Security</a>
            <a href="/settings"><span>⚙️</span> Settings</a>
            <a href="/logout"><span>🚪</span> Logout</a>
        </div>
    </div>
    
    <div class="mobile-overlay" id="mobileOverlay" onclick="toggleNav()"></div>
    
    <div class="top-bar">
        <div class="hamburger" id="hamburger" onclick="toggleNav()">
            <span></span>
            <span></span>
            <span></span>
        </div>
        <div class="page-title">💰 Expenses</div>
        <button class="btn btn-primary btn-sm" onclick="openModal()">+ Add</button>
    </div>
    
    <div class="main-content">
        <!-- Total Expense Card -->
        <div class="card" style="background: linear-gradient(135deg, var(--accent), var(--secondary)); color: white; text-align: center; padding: 28px; box-shadow: 0 8px 20px rgba(6, 182, 212, 0.3);">
            <div style="font-size: 12px; opacity: 0.9; margin-bottom: 8px; letter-spacing: 1px;">TOTAL EXPENSES</div>
            <div style="font-size: 36px; font-weight: 700; margin-bottom: 4px;">UGX {{ "{:,.0f}".format(total) }}</div>
            <div style="font-size: 12px; opacity: 0.9;">All-time business expenses</div>
        </div>
        
        <!-- Expense by Category Chart -->
        {% if by_category %}
        <div class="card">
            <h3 style="color: var(--primary); margin-bottom: 16px; font-size: 16px;">📊 Expenses by Category</h3>
            <div class="chart-container">
                <canvas id="expenseChart"></canvas>
            </div>
        </div>
        {% endif %}
        
        <!-- Expense List -->
        <div class="card">
            <h3 style="color: var(--primary); margin-bottom: 16px; font-size: 16px;">📋 Expense History ({{ expenses|length }})</h3>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Category</th>
                            <th class="hide-mobile">Description</th>
                            <th>Amount</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for exp in expenses %}
                        <tr>
                            <td>{{ exp.date[:10] }}</td>
                            <td><span class="badge badge-info">{{ exp.category }}</span></td>
                            <td class="hide-mobile">{{ exp.description }}</td>
                            <td><strong>{{ "{:,.0f}".format(exp.amount) }}</strong></td>
                            <td>
                                <a href="/expenses/delete/{{ exp.id }}" class="btn btn-danger btn-sm" onclick="return confirm('Delete this expense?')">🗑️</a>
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="5" style="text-align: center; padding: 40px; color: var(--text-light);">
                                No expenses yet. Click "+ Add" to track your first expense.
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    
    <nav class="bottom-nav">
        <a href="/dashboard"><i>📊</i><span>Home</span></a>
        <a href="/pos"><i>💵</i><span>POS</span></a>
        <a href="/invoices"><i>🧾</i><span>Invoices</span></a>
        <a href="/clients"><i>👥</i><span>Clients</span></a>
    </nav>
    
    <!-- Add Modal -->
    <div class="modal" id="addModal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 class="modal-title">Add Expense</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <form method="POST" action="/expenses/add">
                <div class="form-group">
                    <label class="form-label">Category *</label>
                    <select name="category" class="form-control" required>
                        <option value="Office Supplies">Office Supplies</option>
                        <option value="Software">Software & Subscriptions</option>
                        <option value="Marketing">Marketing & Advertising</option>
                        <option value="Utilities">Utilities (Internet, Power)</option>
                        <option value="Travel">Travel & Transport</option>
                        <option value="Equipment">Equipment & Hardware</option>
                        <option value="Salaries">Salaries & Wages</option>
                        <option value="Other">Other</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Description *</label>
                    <input type="text" name="description" class="form-control" placeholder="E.g., Adobe Creative Cloud subscription" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Amount (UGX) *</label>
                    <input type="number" name="amount" class="form-control" placeholder="0" min="0" step="100" required>
                </div>
                <div class="flex gap-10">
                    <button type="submit" class="btn btn-primary" style="flex: 1;">💾 Save Expense</button>
                    <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                </div>
            </form>
        </div>
    </div>
    
    <script>
        function toggleNav() {
            document.getElementById('mobileNav').classList.toggle('active');
            document.getElementById('mobileOverlay').classList.toggle('active');
            document.getElementById('hamburger').classList.toggle('active');
        }
        
        function showToast(message, type = 'success') {
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.innerHTML = `
                <span class="toast-icon">${type === 'success' ? '✅' : '❌'}</span>
                <span class="toast-message">${message}</span>
            `;
            document.body.appendChild(toast);
            setTimeout(() => {
                toast.classList.add('toast-hide');
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
        
        function openModal() {
            document.getElementById('addModal').classList.add('active');
        }
        
        function closeModal() {
            document.getElementById('addModal').classList.remove('active');
        }
        
        {% if by_category %}
        // Expense Chart
        const ctx = document.getElementById('expenseChart').getContext('2d');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: {{ by_category.keys()|list|tojson }},
                datasets: [{
                    label: 'Expenses (UGX)',
                    data: {{ by_category.values()|list|tojson }},
                    backgroundColor: 'rgba(14, 165, 233, 0.7)',
                    borderColor: 'rgba(14, 165, 233, 1)',
                    borderWidth: 2,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return 'UGX ' + context.parsed.y.toLocaleString();
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return 'UGX ' + (value/1000) + 'k';
                            }
                        }
                    }
                }
            }
        });
        {% endif %}
    </script>
</body>
</html>
'''

# ==========================================
# REPORTS TEMPLATE - COMPLETE
# ==========================================

REPORTS_TEMPLATE = BASE_STYLE + '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Reports - DeoBiz Manager</title>
    <link rel="icon" href="/favicon.ico" type="image/x-icon">
</head>
<body>
    <div class="mobile-nav" id="mobileNav">
        <div class="nav-header">
            <div class="nav-logo">
                <img src="/static/icon-192.png" alt="Logo">
            </div>
            <h2>DeoBiz Manager</h2>
            <p>Visualising Your Vision</p>
        </div>
        <div class="nav-links">
            <a href="/dashboard"><span>📊</span> Dashboard</a>
            <a href="/pos"><span>💵</span> POS - Quick Sale</a>
            <a href="/clients"><span>👥</span> Clients</a>
            <a href="/quotations"><span>📝</span> Quotations</a>
            <a href="/invoices"><span>🧾</span> Invoices</a>
            <a href="/receipts"><span>📄</span> Receipts</a>
            <a href="/expenses"><span>💰</span> Expenses</a>
            <a href="/pricing-calculator"><span>🧮</span> Pricing Calculator</a>
            <a href="/reports" class="active"><span>📈</span> Reports</a>
            <a href="/security"><span>🔒</span> Security</a>
            <a href="/settings"><span>⚙️</span> Settings</a>
            <a href="/logout"><span>🚪</span> Logout</a>
        </div>
    </div>
    
    <div class="mobile-overlay" id="mobileOverlay" onclick="toggleNav()"></div>
    
    <div class="top-bar">
        <div class="hamburger" id="hamburger" onclick="toggleNav()">
            <span></span>
            <span></span>
            <span></span>
        </div>
        <div class="page-title">📈 Reports</div>
        <div style="width: 40px;"></div>
    </div>
    
    <div class="main-content">
        <div class="card">
            <h2 style="color: var(--primary); margin-bottom: 8px; font-size: 18px;">📊 Generate Custom Report</h2>
            <p style="color: var(--text-light); margin-bottom: 24px; font-size: 13px;">Export your data as CSV for analysis in Excel or Google Sheets</p>
            
            <form method="POST" action="/reports/generate">
                <div class="form-group">
                    <label class="form-label">Report Type *</label>
                    <select name="report_type" class="form-control" required>
                        <option value="revenue">💰 Revenue Report (Paid Invoices)</option>
                        <option value="expenses">💸 Expense Report</option>
                        <option value="clients">👥 Client List</option>
                        <option value="profit">📊 Profit & Loss</option>
                    </select>
                </div>
                
                <div class="grid grid-2">
                    <div class="form-group">
                        <label class="form-label">Start Date *</label>
                        <input type="date" name="start_date" class="form-control" required>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">End Date *</label>
                        <input type="date" name="end_date" class="form-control" required>
                    </div>
                </div>
                
                <button type="submit" class="btn btn-primary" style="width: 100%;">📥 Generate & Download CSV</button>
            </form>
        </div>
        
        <div class="card">
            <h3 style="color: var(--primary); margin-bottom: 16px; font-size: 16px;">⚡ Quick Reports</h3>
            <p style="color: var(--text-light); margin-bottom: 16px; font-size: 13px;">Generate common reports with one click</p>
            
            <div class="grid grid-2">
                <button class="btn btn-secondary" onclick="downloadReport('revenue')" style="justify-content: center;">
                    💰 This Month Revenue
                </button>
                <button class="btn btn-secondary" onclick="downloadReport('expenses')" style="justify-content: center;">
                    💸 This Month Expenses
                </button>
                <button class="btn btn-secondary" onclick="downloadReport('clients')" style="justify-content: center;">
                    👥 All Clients
                </button>
                <button class="btn btn-secondary" onclick="downloadReport('profit')" style="justify-content: center;">
                    📊 Profit/Loss
                </button>
            </div>
        </div>
        
        <div class="card" style="background: #fff3cd; border-color: #ffc107;">
            <strong style="color: #856404; font-size: 13px;">💡 Pro Tips</strong>
            <ul style="margin: 8px 0 0 16px; padding: 0; color: #856404; font-size: 12px; line-height: 1.8;">
                <li>CSV files can be opened in Excel, Google Sheets, or Numbers</li>
                <li>Use revenue reports for tax calculations</li>
                <li>Export client list for email marketing campaigns</li>
                <li>Profit/Loss reports help track business health</li>
            </ul>
        </div>
    </div>
    
    <nav class="bottom-nav">
        <a href="/dashboard"><i>📊</i><span>Home</span></a>
        <a href="/pos"><i>💵</i><span>POS</span></a>
        <a href="/invoices"><i>🧾</i><span>Invoices</span></a>
        <a href="/clients"><i>👥</i><span>Clients</span></a>
    </nav>
    
    <script>
        function toggleNav() {
            document.getElementById('mobileNav').classList.toggle('active');
            document.getElementById('mobileOverlay').classList.toggle('active');
            document.getElementById('hamburger').classList.toggle('active');
        }
        
        function showToast(message, type = 'success') {
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.innerHTML = `
                <span class="toast-icon">${type === 'success' ? '✅' : '❌'}</span>
                <span class="toast-message">${message}</span>
            `;
            document.body.appendChild(toast);
            setTimeout(() => {
                toast.classList.add('toast-hide');
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
        
        function downloadReport(type) {
            const today = new Date();
            const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
            const startDate = firstDay.toISOString().split('T')[0];
            const endDate = today.toISOString().split('T')[0];
            
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = '/reports/generate';
            
            const typeInput = document.createElement('input');
            typeInput.type = 'hidden';
            typeInput.name = 'report_type';
            typeInput.value = type;
            form.appendChild(typeInput);
            
            const startInput = document.createElement('input');
            startInput.type = 'hidden';
            startInput.name = 'start_date';
            startInput.value = startDate;
            form.appendChild(startInput);
            
            const endInput = document.createElement('input');
            endInput.type = 'hidden';
            endInput.name = 'end_date';
            endInput.value = endDate;
            form.appendChild(endInput);
            
            document.body.appendChild(form);
            showToast('📥 Generating report...');
            form.submit();
            document.body.removeChild(form);
        }
    </script>
</body>
</html>
'''

# ==========================================
# SECURITY TEMPLATE - COMPLETE
# ==========================================

SECURITY_TEMPLATE = BASE_STYLE + '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Security - DeoBiz Manager</title>
    <link rel="icon" href="/favicon.ico" type="image/x-icon">
</head>
<body>
    <div class="mobile-nav" id="mobileNav">
        <div class="nav-header">
            <div class="nav-logo">
                <img src="/static/icon-192.png" alt="Logo">
            </div>
            <h2>DeoBiz Manager</h2>
            <p>Visualising Your Vision</p>
        </div>
        <div class="nav-links">
            <a href="/dashboard"><span>📊</span> Dashboard</a>
            <a href="/pos"><span>💵</span> POS - Quick Sale</a>
            <a href="/clients"><span>👥</span> Clients</a>
            <a href="/quotations"><span>📝</span> Quotations</a>
            <a href="/invoices"><span>🧾</span> Invoices</a>
            <a href="/receipts"><span>📄</span> Receipts</a>
            <a href="/expenses"><span>💰</span> Expenses</a>
            <a href="/pricing-calculator"><span>🧮</span> Pricing Calculator</a>
            <a href="/reports"><span>📈</span> Reports</a>
            <a href="/security" class="active"><span>🔒</span> Security</a>
            <a href="/settings"><span>⚙️</span> Settings</a>
            <a href="/logout"><span>🚪</span> Logout</a>
        </div>
    </div>
    
    <div class="mobile-overlay" id="mobileOverlay" onclick="toggleNav()"></div>
    
    <div class="top-bar">
        <div class="hamburger" id="hamburger" onclick="toggleNav()">
            <span></span>
            <span></span>
            <span></span>
        </div>
        <div class="page-title">🔒 Security Dashboard</div>
        <a href="/security/activity" class="btn btn-secondary btn-sm">📋 Activity Log</a>
    </div>
    
    <div class="main-content">
        <div class="card" style="background: linear-gradient(135deg, #10b981, #059669); color: white; box-shadow: 0 8px 20px rgba(16, 185, 129, 0.3);">
            <h3 style="margin-bottom: 14px; font-size: 16px;">🛡️ Security Features Active</h3>
            <ul style="list-style: none; padding: 0; margin: 0;">
                <li style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.2); font-size: 13px;">✓ Two-Factor Authentication (2FA via Email)</li>
                <li style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.2); font-size: 13px;">✓ IP Blocking after 5 failed attempts</li>
                <li style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.2); font-size: 13px;">✓ Email alerts for suspicious activity</li>
                <li style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.2); font-size: 13px;">✓ Password hashing & encryption</li>
                <li style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.2); font-size: 13px;">✓ Session timeout protection (24 hours)</li>
                <li style="padding: 10px 0; font-size: 13px;">✓ Comprehensive activity logging</li>
            </ul>
        </div>
        
        <div class="card">
            <h2 style="color: var(--primary); margin-bottom: 8px; font-size: 18px;">🔐 Login Activity Log</h2>
            <p style="color: var(--text-light); margin-bottom: 20px; font-size: 13px;">Monitor all login attempts and security events (Last 50)</p>
            
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Username</th>
                            <th class="hide-mobile">IP Address</th>
                            <th>Timestamp</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for attempt in attempts %}
                        <tr>
                            <td><strong>{{ attempt.username }}</strong></td>
                            <td class="hide-mobile">{{ attempt.ip_address }}</td>
                            <td style="white-space: nowrap;">{{ attempt.timestamp[:19].replace('T', ' ') }}</td>
                            <td>
                                {% if attempt.success %}
                                <span class="badge badge-success">✓ Success</span>
                                {% else %}
                                <span class="badge badge-danger">✗ Failed</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="4" style="text-align: center; padding: 40px; color: var(--text-light);">
                                No login attempts recorded yet.
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="card" style="background: #e6f7ff; border-color: var(--primary);">
            <strong style="color: var(--primary); font-size: 13px;">ℹ️ Security Best Practices</strong>
            <ul style="margin: 8px 0 0 16px; padding: 0; color: var(--text-dark); font-size: 12px; line-height: 1.8;">
                <li>Never share your login credentials</li>
                <li>Use a strong, unique password</li>
                <li>Review security logs regularly</li>
                <li>Enable notifications for failed login attempts</li>
                <li>Access the system only from trusted devices</li>
            </ul>
        </div>
    </div>
    
    <nav class="bottom-nav">
        <a href="/dashboard"><i>📊</i><span>Home</span></a>
        <a href="/pos"><i>💵</i><span>POS</span></a>
        <a href="/invoices"><i>🧾</i><span>Invoices</span></a>
        <a href="/clients"><i>👥</i><span>Clients</span></a>
    </nav>
    
    <script>
        function toggleNav() {
            document.getElementById('mobileNav').classList.toggle('active');
            document.getElementById('mobileOverlay').classList.toggle('active');
            document.getElementById('hamburger').classList.toggle('active');
        }
    </script>
</body>
</html>
'''

# ==========================================
# SETTINGS TEMPLATE - COMPLETE WITH LOGO UPLOAD
# ==========================================

SETTINGS_TEMPLATE = BASE_STYLE + '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Settings - DeoBiz Manager</title>
    <link rel="icon" href="/favicon.ico" type="image/x-icon">
</head>
<body>
    <div class="mobile-nav" id="mobileNav">
        <div class="nav-header">
            <div class="nav-logo">
                <img src="/static/icon-192.png" alt="Logo">
            </div>
            <h2>DeoBiz Manager</h2>
            <p>Visualising Your Vision</p>
        </div>
        <div class="nav-links">
            <a href="/dashboard"><span>📊</span> Dashboard</a>
            <a href="/pos"><span>💵</span> POS - Quick Sale</a>
            <a href="/clients"><span>👥</span> Clients</a>
            <a href="/quotations"><span>📝</span> Quotations</a>
            <a href="/invoices"><span>🧾</span> Invoices</a>
            <a href="/receipts"><span>📄</span> Receipts</a>
            <a href="/expenses"><span>💰</span> Expenses</a>
            <a href="/pricing-calculator"><span>🧮</span> Pricing Calculator</a>
            <a href="/reports"><span>📈</span> Reports</a>
            <a href="/security"><span>🔒</span> Security</a>
            <a href="/settings" class="active"><span>⚙️</span> Settings</a>
            <a href="/logout"><span>🚪</span> Logout</a>
        </div>
    </div>
    
    <div class="mobile-overlay" id="mobileOverlay" onclick="toggleNav()"></div>
    
    <div class="top-bar">
        <div class="hamburger" id="hamburger" onclick="toggleNav()">
            <span></span>
            <span></span>
            <span></span>
        </div>
        <div class="page-title">⚙️ Settings</div>
        <div style="width: 40px;"></div>
    </div>
    
    <div class="main-content">
        <!-- Logo Upload Section -->
        <div class="card">
            <h2 style="color: var(--primary); margin-bottom: 8px; font-size: 18px;">🖼️ Upload Company Logo</h2>
            <p style="color: var(--text-light); margin-bottom: 20px; font-size: 13px;">Upload your logo to use it in PDFs, emails, and as app icon</p>
            
            <form id="logoForm" enctype="multipart/form-data">
                <div class="form-group">
                    <label class="form-label">Choose Logo Image (PNG recommended)</label>
                    <input type="file" id="logoInput" name="logo" accept="image/png,image/jpeg,image/jpg" class="form-control" style="padding: 8px;">
                    <small style="color: var(--text-light); font-size: 11px; margin-top: 6px; display: block;">
                        • Recommended size: 512x512 pixels<br>
                        • Format: PNG with transparent background<br>
                        • Will be used for: PWA icons, PDFs, emails, favicon
                    </small>
                </div>
                <button type="submit" class="btn btn-primary" id="uploadBtn">
                    <span class="btn-text">📤 Upload Logo</span>
                    <span class="btn-spinner">
                        <span class="spinner"></span> Uploading...
                    </span>
                </button>
            </form>
            
            <div style="margin-top: 20px; padding: 16px; background: #e6f7ff; border-radius: 10px; border-left: 4px solid var(--primary);">
                <strong style="color: var(--primary); font-size: 13px;">Current Logo Preview:</strong>
                <div style="margin-top: 12px; text-align: center;">
                    <img src="/static/icon-192.png" style="width: 100px; height: 100px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2 style="color: var(--primary); margin-bottom: 8px; font-size: 18px;">⚙️ Company Settings</h2>
            <p style="color: var(--text-light); margin-bottom: 24px; font-size: 13px;">Manage your business information and branding</p>
            
            <form method="POST">
                <h3 style="color: var(--primary); margin-bottom: 14px; font-size: 16px;">📧 Email Configuration</h3>
                <div class="form-group">
                    <label class="form-label">Email Sender</label>
                    <input type="email" name="email_sender" class="form-control" value="{{ settings.get('email_sender', 'deoug45@gmail.com') }}">
                </div>
                
                <hr style="margin: 28px 0; border: none; border-top: 1px solid #e5e7eb;">
                
                <h3 style="color: var(--primary); margin-bottom: 14px; font-size: 16px;">🏢 Company Information</h3>
                <div class="form-group">
                    <label class="form-label">Company Name</label>
                    <input type="text" name="company_name" class="form-control" value="{{ settings.get('company_name', 'Deo Digital Solutions') }}">
                </div>
                
                <div class="form-group">
                    <label class="form-label">Company Tagline</label>
                    <input type="text" name="company_tagline" class="form-control" value="{{ settings.get('company_tagline', 'Visualising Your Vision') }}">
                </div>
                
                <div class="form-group">
                    <label class="form-label">Website</label>
                    <input type="text" name="company_website" class="form-control" value="{{ settings.get('company_website', 'www.deodigitalsolutions.com') }}">
                </div>
                
                <div class="form-group">
                    <label class="form-label">Location</label>
                    <input type="text" name="company_location" class="form-control" value="{{ settings.get('company_location', 'Kampala, Uganda') }}">
                </div>
                
                <hr style="margin: 28px 0; border: none; border-top: 1px solid #e5e7eb;">
                
                <h3 style="color: var(--primary); margin-bottom: 14px; font-size: 16px;">🎨 Brand Colors (3 Color Scheme)</h3>
                <div class="grid grid-3">
                    <div class="form-group">
                        <label class="form-label">Primary Color (Sky Blue)</label>
                        <input type="color" name="primary_color" class="form-control" value="{{ settings.get('primary_color', '#0EA5E9') }}" style="height: 54px;">
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Accent Color (Blue)</label>
                        <input type="color" name="accent_color" class="form-control" value="{{ settings.get('accent_color', '#0284C7') }}" style="height: 54px;">
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Secondary Color (Cyan)</label>
                        <input type="color" name="secondary_color" class="form-control" value="{{ settings.get('secondary_color', '#06B6D4') }}" style="height: 54px;">
                    </div>
                </div>
                
                <button type="submit" class="btn btn-primary" style="width: 100%;">💾 Save Settings</button>
            </form>
        </div>
        
        <div class="card" style="background: #fff3cd; border-color: #ffc107;">
            <strong style="color: #856404; font-size: 13px;">ℹ️ Important Note</strong>
            <ul style="margin: 8px 0 0 16px; padding: 0; color: #856404; font-size: 12px; line-height: 1.8;">
                <li>Changes to settings will apply immediately to all documents and emails</li>
                <li>Logo changes require page refresh to see updates</li>
                <li>Make sure to test your changes before sending to clients</li>
                <li>Keep your logo file in uploads folder as "logo.png"</li>
            </ul>
        </div>
    </div>
    
    <nav class="bottom-nav">
        <a href="/dashboard"><i>📊</i><span>Home</span></a>
        <a href="/pos"><i>💵</i><span>POS</span></a>
        <a href="/invoices"><i>🧾</i><span>Invoices</span></a>
        <a href="/clients"><i>👥</i><span>Clients</span></a>
    </nav>
    
    <script>
        function toggleNav() {
            document.getElementById('mobileNav').classList.toggle('active');
            document.getElementById('mobileOverlay').classList.toggle('active');
            document.getElementById('hamburger').classList.toggle('active');
        }
        
        function showToast(message, type = 'success') {
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.innerHTML = `
                <span class="toast-icon">${type === 'success' ? '✅' : '❌'}</span>
                <span class="toast-message">${message}</span>
            `;
            document.body.appendChild(toast);
            setTimeout(() => {
                toast.classList.add('toast-hide');
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
        
        // Handle logo upload
        document.getElementById('logoForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formData = new FormData();
            const logoFile = document.getElementById('logoInput').files[0];
            
            if (!logoFile) {
                showToast('❌ Please select a logo file', 'error');
                return;
            }
            
            // Check file size (max 5MB)
            if (logoFile.size > 5 * 1024 * 1024) {
                showToast('❌ File too large. Maximum size is 5MB', 'error');
                return;
            }
            
            formData.append('logo', logoFile);
            
            const btn = document.getElementById('uploadBtn');
            btn.disabled = true;
            btn.querySelector('.btn-text').style.display = 'none';
            btn.querySelector('.btn-spinner').style.display = 'inline-flex';
            
            try {
                const response = await fetch('/upload-logo', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showToast('✅ ' + result.message);
                    
                    // Reload page after 2 seconds to show new logo
                    setTimeout(() => {
                        window.location.reload();
                    }, 2000);
                } else {
                    showToast('❌ Error: ' + result.error, 'error');
                }
            } catch (error) {
                showToast('❌ Upload failed: ' + error.message, 'error');
            } finally {
                btn.disabled = false;
                btn.querySelector('.btn-text').style.display = 'inline';
                btn.querySelector('.btn-spinner').style.display = 'none';
            }
        });
    </script>
</body>
</html>
'''

# Add this at the very end of app.py, just before the if __name__ == "__main__" block

ACTIVITY_LOG_TEMPLATE = BASE_STYLE + '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Activity Log - DeoBiz Manager</title>
    <link rel="icon" href="/favicon.ico" type="image/x-icon">
</head>
<body>
    <div class="mobile-nav" id="mobileNav">
        <div class="nav-header">
            <div class="nav-logo">
                <img src="/static/icon-192.png" alt="Logo">
            </div>
            <h2>DeoBiz Manager</h2>
            <p>Visualising Your Vision</p>
        </div>
        <div class="nav-links">
            <a href="/dashboard"><span>📊</span> Dashboard</a>
            <a href="/pos"><span>💵</span> POS - Quick Sale</a>
            <a href="/clients"><span>👥</span> Clients</a>
            <a href="/quotations"><span>📝</span> Quotations</a>
            <a href="/invoices"><span>🧾</span> Invoices</a>
            <a href="/receipts"><span>📄</span> Receipts</a>
            <a href="/expenses"><span>💰</span> Expenses</a>
            <a href="/pricing-calculator"><span>🧮</span> Pricing Calculator</a>
            <a href="/reports"><span>📈</span> Reports</a>
            <a href="/security" class="active"><span>🔒</span> Security</a>
            <a href="/settings"><span>⚙️</span> Settings</a>
            <a href="/logout"><span>🚪</span> Logout</a>
        </div>
    </div>
    
    <div class="mobile-overlay" id="mobileOverlay" onclick="toggleNav()"></div>
    
    <div class="top-bar">
        <div class="hamburger" id="hamburger" onclick="toggleNav()">
            <span></span>
            <span></span>
            <span></span>
        </div>
        <div class="page-title">📋 Activity Log</div>
        <a href="/security" class="btn btn-secondary btn-sm">← Back</a>
    </div>
    
    <div class="main-content">
        <div class="card">
            <h2 style="color: var(--primary); margin-bottom: 8px;">📋 Comprehensive Activity Log</h2>
            <p style="color: var(--text-light); margin-bottom: 20px; font-size: 13px;">Track all system activities and user actions</p>
            
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Activity</th>
                            <th>Description</th>
                            <th class="hide-mobile">IP Address</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for activity in activities %}
                        <tr>
                            <td style="white-space: nowrap;">{{ activity.created_at[:19].replace('T', ' ') }}</td>
                            <td>
                                <span class="badge badge-info">{{ activity.activity_type.replace('_', ' ').title() }}</span>
                            </td>
                            <td>{{ activity.description }}</td>
                            <td class="hide-mobile">{{ activity.ip_address or 'N/A' }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    
    <nav class="bottom-nav">
        <a href="/dashboard"><i>📊</i><span>Home</span></a>
        <a href="/pos"><i>💵</i><span>POS</span></a>
        <a href="/invoices"><i>🧾</i><span>Invoices</span></a>
        <a href="/clients"><i>👥</i><span>Clients</span></a>
    </nav>
    
    <script>
        function toggleNav() {
            document.getElementById('mobileNav').classList.toggle('active');
            document.getElementById('mobileOverlay').classList.toggle('active');
            document.getElementById('hamburger').classList.toggle('active');
        }
    </script>
</body>
</html>
'''

# Now let me provide the COMPLETE remaining templates with ALL fixes

SETUP_TEMPLATE = BASE_STYLE + '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Setup - DeoBiz Manager</title>
    <link rel="icon" href="/favicon.ico" type="image/x-icon">
</head>
<body style="background: linear-gradient(135deg, var(--primary) 0%, var(--accent) 50%, var(--secondary) 100%);">
    <div style="min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px;">
        <div style="background: white; max-width: 400px; width: 100%; padding: 32px; border-radius: 16px; box-shadow: 0 20px 60px rgba(0,0,0,0.3);">
            <div style="text-align: center; margin-bottom: 28px;">
                <div style="width: 70px; height: 70px; margin: 0 auto 16px; background: var(--sidebar-bg); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-size: 32px; font-weight: 700; box-shadow: 0 8px 20px rgba(14, 165, 233, 0.3);">D</div>
                <h1 style="color: var(--primary); font-size: 22px; margin-bottom: 8px;">DeoBiz Manager</h1>
                <p style="color: var(--text-light); font-style: italic; font-size: 13px;">Visualising Your Vision</p>
            </div>
            <form method="POST">
                <div class="form-group">
                    <label class="form-label">Admin Username</label>
                    <input type="text" name="username" class="form-control" required autofocus>
                </div>
                <div class="form-group">
                    <label class="form-label">Admin Password</label>
                    <input type="password" name="password" class="form-control" required>
                </div>
                <button type="submit" class="btn btn-primary" style="width: 100%;">🚀 Complete Setup</button>
            </form>
        </div>
    </div>
</body>
</html>
'''

LOGIN_TEMPLATE = BASE_STYLE + '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Login - DeoBiz Manager</title>
    <link rel="icon" href="/favicon.ico" type="image/x-icon">
    <link rel="manifest" href="/manifest.json">
</head>
<body style="background: linear-gradient(135deg, var(--primary) 0%, var(--accent) 50%, var(--secondary) 100%);">
    <div style="min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px;">
        <div style="background: white; max-width: 400px; width: 100%; padding: 32px; border-radius: 16px; box-shadow: 0 20px 60px rgba(0,0,0,0.3);">
            <div style="text-align: center; margin-bottom: 28px;">
                <img src="/static/icon-192.png" style="width: 70px; height: 70px; margin: 0 auto 16px; border-radius: 50%; box-shadow: 0 8px 20px rgba(14, 165, 233, 0.3);">
                <h1 style="color: var(--primary); font-size: 22px; margin-bottom: 8px;">Welcome Back</h1>
                <p style="color: var(--text-light); font-style: italic; font-size: 13px;">Visualising Your Vision</p>
            </div>
            {% if error %}
            <div style="background: #fee; color: #c33; padding: 12px; border-radius: 8px; margin-bottom: 16px; text-align: center; font-size: 13px; border-left: 4px solid #dc3545;">{{ error }}</div>
            {% endif %}
            <form method="POST" id="loginForm">
                <div class="form-group">
                    <label class="form-label">Username</label>
                    <input type="text" name="username" class="form-control" required autofocus>
                </div>
                <div class="form-group">
                    <label class="form-label">Password</label>
                    <input type="password" name="password" class="form-control" required>
                </div>
                <button type="submit" class="btn btn-primary" style="width: 100%;" id="loginBtn">
                    <span class="btn-text">🔐 Login with 2FA</span>
                    <span class="btn-spinner">
                        <span class="spinner"></span> Logging in...
                    </span>
                </button>
            </form>
        </div>
    </div>
    
    <script>
        // Show loading state on login
        document.getElementById('loginForm').addEventListener('submit', function() {
            const btn = document.getElementById('loginBtn');
            btn.disabled = true;
            btn.querySelector('.btn-text').style.display = 'none';
            btn.querySelector('.btn-spinner').style.display = 'inline-flex';
        });
        
        // Register service worker
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js');
        }
    </script>
</body>
</html>
'''

OTP_TEMPLATE = BASE_STYLE + '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Verify OTP - DeoBiz Manager</title>
    <link rel="icon" href="/favicon.ico" type="image/x-icon">
</head>
<body style="background: linear-gradient(135deg, var(--primary) 0%, var(--accent) 50%, var(--secondary) 100%);">
    <div style="min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px;">
        <div style="background: white; max-width: 400px; width: 100%; padding: 32px; border-radius: 16px; box-shadow: 0 20px 60px rgba(0,0,0,0.3);">
            <div style="text-align: center; margin-bottom: 28px;">
                <div style="width: 70px; height: 70px; margin: 0 auto 16px; background: var(--sidebar-bg); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-size: 32px; box-shadow: 0 8px 20px rgba(14, 165, 233, 0.3);">🔒</div>
                <h1 style="color: var(--primary); font-size: 22px; margin-bottom: 8px;">Verify OTP</h1>
                <p style="color: var(--text-light); font-size: 13px;">Check your email for the verification code</p>
            </div>
            {% if error %}
            <div style="background: #fee; color: #c33; padding: 12px; border-radius: 8px; margin-bottom: 16px; text-align: center; font-size: 13px; border-left: 4px solid #dc3545;">{{ error }}</div>
            {% endif %}
            <form method="POST" id="otpForm">
                <div class="form-group">
                    <label class="form-label">Enter 6-Digit OTP</label>
                    <input type="text" name="otp" class="form-control" maxlength="6" pattern="[0-9]{6}" style="text-align: center; letter-spacing: 12px; font-size: 24px; font-weight: 700; padding: 14px;" required autofocus>
                    <small style="color: var(--text-light); font-size: 12px; margin-top: 6px; display: block; text-align: center;">Code expires in 10 minutes</small>
                </div>
                <button type="submit" class="btn btn-primary" style="width: 100%;" id="verifyBtn">
                    <span class="btn-text">✓ Verify & Login</span>
                    <span class="btn-spinner">
                        <span class="spinner"></span> Verifying...
                    </span>
                </button>
            </form>
        </div>
    </div>
    
    <script>
        // Auto-focus on OTP input
        document.querySelector('input[name="otp"]').focus();
        
        // Show loading state
        document.getElementById('otpForm').addEventListener('submit', function() {
            const btn = document.getElementById('verifyBtn');
            btn.disabled = true;
            btn.querySelector('.btn-text').style.display = 'none';
            btn.querySelector('.btn-spinner').style.display = 'inline-flex';
        });
        
        // Auto-submit when 6 digits entered
        document.querySelector('input[name="otp"]').addEventListener('input', function(e) {
            if (e.target.value.length === 6) {
                document.getElementById('otpForm').submit();
            }
        });
    </script>
</body>
</html>
'''

# Continue with the remaining LARGE templates (Dashboard, Clients, etc.)
# Due to character limits, I'll provide the most critical ones

DASHBOARD_TEMPLATE = BASE_STYLE + '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Dashboard - DeoBiz Manager</title>
    <link rel="icon" href="/favicon.ico" type="image/x-icon">
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#0EA5E9">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
</head>
<body>
    <!-- Mobile Navigation -->
    <div class="mobile-nav" id="mobileNav">
        <div class="nav-header">
            <div class="nav-logo">
                <img src="/static/icon-192.png" alt="Logo">
            </div>
            <h2>DeoBiz Manager</h2>
            <p>Visualising Your Vision</p>
        </div>
        <div class="nav-links">
            <a href="/dashboard" class="active"><span>📊</span> Dashboard</a>
            <a href="/pos"><span>💵</span> POS - Quick Sale</a>
            <a href="/clients"><span>👥</span> Clients</a>
            <a href="/quotations"><span>📝</span> Quotations</a>
            <a href="/invoices"><span>🧾</span> Invoices</a>
            <a href="/receipts"><span>📄</span> Receipts</a>
            <a href="/expenses"><span>💰</span> Expenses</a>
            <a href="/pricing-calculator"><span>🧮</span> Pricing Calculator</a>
            <a href="/reports"><span>📈</span> Reports</a>
            <a href="/security"><span>🔒</span> Security</a>
            <a href="/settings"><span>⚙️</span> Settings</a>
            <a href="/logout"><span>🚪</span> Logout</a>
        </div>
    </div>
    
    <div class="mobile-overlay" id="mobileOverlay" onclick="toggleNav()"></div>
    
    <!-- Top Bar -->
    <div class="top-bar">
        <div class="hamburger" id="hamburger" onclick="toggleNav()">
            <span></span>
            <span></span>
            <span></span>
        </div>
        <div class="page-title">📊 Dashboard</div>
        <div style="width: 40px;"></div>
    </div>
    
    <!-- Main Content -->
    <div class="main-content">
        <!-- Health Score -->
        <div class="health-score">
            <div class="health-score-label">Business Health Score</div>
            <div class="health-score-value">{{ "%.0f"|format(health_score) }}</div>
            <div style="font-size: 13px; opacity: 0.9;">Out of 100</div>
        </div>
        
        <!-- Metrics Grid -->
        <div class="grid grid-2 keep-mobile">
            <div class="card metric-card">
                <div class="metric-icon">💵</div>
                <div class="metric-label">Today's Revenue</div>
                <div class="metric-value">{{ "{:,.0f}".format(today_revenue) }}</div>
                <div class="metric-change positive">+{{ "%.1f"|format(revenue_growth) }}%</div>
            </div>
            
            <div class="card metric-card">
                <div class="metric-icon">📅</div>
                <div class="metric-label">Weekly Revenue</div>
                <div class="metric-value">{{ "{:,.0f}".format(week_revenue) }}</div>
            </div>
            
            <div class="card metric-card">
                <div class="metric-icon">📆</div>
                <div class="metric-label">Monthly Revenue</div>
                <div class="metric-value">{{ "{:,.0f}".format(month_revenue) }}</div>
            </div>
            
            <div class="card metric-card">
                <div class="metric-icon">💸</div>
                <div class="metric-label">Total Expenses</div>
                <div class="metric-value">{{ "{:,.0f}".format(total_expenses) }}</div>
            </div>
            
            <div class="card metric-card">
                <div class="metric-icon">💰</div>
                <div class="metric-label">Net Profit</div>
                <div class="metric-value">{{ "{:,.0f}".format(net_profit) }}</div>
                <div class="metric-change {{ 'positive' if profit_margin > 0 else 'negative' }}">{{ "%.1f"|format(profit_margin) }}%</div>
            </div>
            
            <div class="card metric-card">
                <div class="metric-icon">📋</div>
                <div class="metric-label">Outstanding</div>
                <div class="metric-value">{{ "{:,.0f}".format(outstanding) }}</div>
            </div>
        </div>
        
        <!-- Revenue Chart -->
        <div class="card">
            <h3 style="margin-bottom: 16px; color: var(--primary); font-size: 16px;">📈 Revenue Trend (Last 6 Months)</h3>
            <div class="chart-container">
                <canvas id="revenueChart"></canvas>
            </div>
        </div>
        
        <!-- Top Clients -->
        {% if top_clients %}
        <div class="card">
            <h3 style="margin-bottom: 16px; color: var(--primary); font-size: 16px;">⭐ Top Clients</h3>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Client</th>
                            <th>Revenue</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for client in top_clients %}
                        <tr>
                            <td><strong>{{ client.name }}</strong></td>
                            <td>UGX {{ "{:,.0f}".format(client.revenue) }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        {% endif %}
        
        <!-- Expense Breakdown -->
        <div class="card">
            <h3 style="margin-bottom: 16px; color: var(--primary); font-size: 16px;">💸 Expense Breakdown</h3>
            <div class="chart-container">
                <canvas id="expenseChart"></canvas>
            </div>
        </div>
    </div>
    
    <!-- Bottom Navigation -->
    <nav class="bottom-nav">
        <a href="/dashboard" class="active"><i>📊</i><span>Home</span></a>
        <a href="/pos"><i>💵</i><span>POS</span></a>
        <a href="/invoices"><i>🧾</i><span>Invoices</span></a>
        <a href="/clients"><i>👥</i><span>Clients</span></a>
    </nav>
    
    <script>
        // Toggle Navigation
        function toggleNav() {
            document.getElementById('mobileNav').classList.toggle('active');
            document.getElementById('mobileOverlay').classList.toggle('active');
            document.getElementById('hamburger').classList.toggle('active');
        }
        
        // Toast notification function
        function showToast(message, type = 'success') {
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.innerHTML = `
                <span class="toast-icon">${type === 'success' ? '✅' : '❌'}</span>
                <span class="toast-message">${message}</span>
            `;
            document.body.appendChild(toast);
            
            setTimeout(() => {
                toast.classList.add('toast-hide');
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
        
        // Register Service Worker
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js').then(() => {
                console.log('Service Worker registered');
            });
        }
        
        // PWA Install Prompt
        let deferredPrompt;
        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            deferredPrompt = e;
            
            // Show custom install button
            const installPrompt = document.createElement('div');
            installPrompt.className = 'install-prompt';
            installPrompt.innerHTML = `
                <div class="install-prompt-content">
                    <img src="/static/icon-192.png" width="40">
                    <div style="flex: 1;">
                        <strong>Install DeoBiz Manager</strong>
                        <p>Quick access from your home screen</p>
                    </div>
                    <button class="btn btn-primary btn-sm" onclick="installApp()">Install</button>
                    <button class="btn-close" onclick="closeInstallPrompt()">×</button>
                </div>
            `;
            document.body.appendChild(installPrompt);
        });
        
        function installApp() {
            if (deferredPrompt) {
                deferredPrompt.prompt();
                deferredPrompt.userChoice.then((choiceResult) => {
                    if (choiceResult.outcome === 'accepted') {
                        showToast('App installed successfully! ✅');
                    }
                    deferredPrompt = null;
                    closeInstallPrompt();
                });
            }
        }
        
        function closeInstallPrompt() {
            const prompt = document.querySelector('.install-prompt');
            if (prompt) prompt.remove();
        }
        
        // Request notification permission
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
        
        // Show success toast on login
        if (window.location.search.includes('login=success')) {
            showToast('✅ Login successful! Welcome back.');
            window.history.replaceState({}, document.title, window.location.pathname);
        }
        
        // Revenue Chart
        const revenueCtx = document.getElementById('revenueChart').getContext('2d');
        new Chart(revenueCtx, {
            type: 'line',
            data: {
                labels: {{ monthly_revenue|map(attribute='month')|list|tojson }},
                datasets: [{
                    label: 'Revenue (UGX)',
                    data: {{ monthly_revenue|map(attribute='revenue')|list|tojson }},
                    borderColor: 'rgb(14, 165, 233)',
                    backgroundColor: 'rgba(14, 165, 233, 0.1)',
                    tension: 0.4,
                    fill: true,
                    borderWidth: 2,
                    pointRadius: 4,
                    pointBackgroundColor: 'rgb(14, 165, 233)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return 'UGX ' + context.parsed.y.toLocaleString();
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return 'UGX ' + (value/1000) + 'k';
                            }
                        }
                    }
                }
            }
        });
        
        // Expense Chart
        const expenseCtx = document.getElementById('expenseChart').getContext('2d');
        new Chart(expenseCtx, {
            type: 'doughnut',
            data: {
                labels: {{ expense_by_category.keys()|list|tojson }},
                datasets: [{
                    data: {{ expense_by_category.values()|list|tojson }},
                    backgroundColor: [
                        'rgba(14, 165, 233, 0.8)',
                        'rgba(2, 132, 199, 0.8)',
                        'rgba(6, 182, 212, 0.8)',
                        'rgba(16, 185, 129, 0.8)',
                        'rgba(245, 158, 11, 0.8)',
                        'rgba(239, 68, 68, 0.8)',
                        'rgba(168, 85, 247, 0.8)',
                        'rgba(236, 72, 153, 0.8)'
                    ],
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 12,
                            font: { size: 11 }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.label + ': UGX ' + context.parsed.toLocaleString();
                            }
                        }
                    }
                }
            }
        });
    </script>
</body>
</html>
'''

# Due to space, I'll provide the SERVICE_WORKER and finish with the main execution

SERVICE_WORKER = '''
const CACHE_NAME = 'deobiz-v3';
const urlsToCache = [
  '/',
  '/dashboard',
  '/pos',
  '/clients',
  '/quotations',
  '/invoices',
  '/expenses',
  '/manifest.json',
  '/static/icon-192.png',
  '/static/icon-512.png',
  '/static/favicon.ico'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
  self.skipWaiting();
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
      .catch(() => caches.match('/dashboard'))
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  return self.clients.claim();
});

// Push notification support
self.addEventListener('push', event => {
  const data = event.data.json();
  const options = {
    body: data.body,
    icon: '/static/icon-192.png',
    badge: '/static/icon-192.png',
    vibrate: [200, 100, 200],
    data: { url: data.url || '/dashboard' }
  };
  
  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow(event.notification.data.url)
  );
});
'''

# ==========================================
# MAIN EXECUTION
# ==========================================

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 80))
    app.run(host="0.0.0.0", port=port, debug=False)
