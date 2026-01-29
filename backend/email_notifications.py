"""
Email notification system for Tesserae V6
Sends notifications to administrators when users submit text requests or feedback
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from backend.logging_config import get_logger

logger = get_logger('email')

def get_notification_emails():
    """Get notification email addresses from database settings"""
    try:
        from backend.app import get_db_cursor
        with get_db_cursor(commit=False) as cur:
            cur.execute("SELECT value FROM settings WHERE key = 'notification_emails'")
            result = cur.fetchone()
            if result and result[0]:
                emails = [e.strip() for e in result[0].split(',') if e.strip()]
                return emails
    except Exception as e:
        logger.error(f"Failed to get notification emails: {e}")
    return []

def send_notification(subject, body, notification_type='general'):
    """
    Send email notification to configured administrators.
    Uses SMTP if configured, otherwise logs the notification.
    """
    emails = get_notification_emails()
    if not emails:
        logger.info(f"No notification emails configured - skipping {notification_type} notification")
        return False
    
    smtp_host = os.environ.get('SMTP_HOST', '')
    smtp_port = int(os.environ.get('SMTP_PORT', '587'))
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_password = os.environ.get('SMTP_PASSWORD', '')
    from_email = os.environ.get('SMTP_FROM', smtp_user or 'noreply@tesserae.app')
    
    if not smtp_host or not smtp_user:
        logger.info(f"SMTP not configured - notification logged instead: {subject}")
        logger.info(f"Would send to: {', '.join(emails)}")
        logger.info(f"Body: {body[:200]}...")
        return True
    
    try:
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = ', '.join(emails)
        msg['Subject'] = f"[Tesserae] {subject}"
        
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, emails, msg.as_string())
        
        logger.info(f"Notification sent to {len(emails)} recipients: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email notification: {e}")
        return False

def notify_text_request(request_data):
    """Send notification about a new text request"""
    subject = f"New Text Request: {request_data.get('author', 'Unknown')} - {request_data.get('work', 'Unknown')}"
    body = f"""A new text request has been submitted to Tesserae.

Submitter: {request_data.get('name', 'Anonymous')}
Email: {request_data.get('email', 'Not provided')}

Requested Text:
- Author: {request_data.get('author', 'Unknown')}
- Work: {request_data.get('work', 'Unknown')}
- Language: {request_data.get('language', 'la')}

Notes:
{request_data.get('notes', 'None')}

Please log in to the Admin Panel to review this request.
"""
    return send_notification(subject, body, 'text_request')

def notify_feedback(feedback_data):
    """Send notification about new user feedback"""
    feedback_type = feedback_data.get('type', 'suggestion').title()
    subject = f"New {feedback_type} Submitted"
    body = f"""New feedback has been submitted to Tesserae.

Submitter: {feedback_data.get('name', 'Anonymous')}
Email: {feedback_data.get('email', 'Not provided')}
Type: {feedback_type}

Message:
{feedback_data.get('message', 'No message')}

Please log in to the Admin Panel to review this feedback.
"""
    return send_notification(subject, body, 'feedback')
