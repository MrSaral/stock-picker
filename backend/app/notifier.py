import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Fetch SMTP settings from env (these will be gitignored)
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
TO_EMAIL = os.getenv("TO_EMAIL", "")

def send_email(subject: str, html_content: str) -> bool:
    """
    Sends an HTML email using standard SMTP.
    Returns True if successfully sent, False otherwise.
    """
    if not SMTP_USER or not SMTP_PASSWORD or not TO_EMAIL:
        logger.warning(
            "SMTP credentials or destination email not configured in .env. "
            "Skipping email sending, printing contents to logs."
        )
        print(f"--- MOCK EMAIL SEND ---")
        print(f"To: {TO_EMAIL or 'Not Configured'}")
        print(f"Subject: {subject}")
        print(f"Body: {html_content[:300]}...")
        print(f"-----------------------")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = TO_EMAIL

        part = MIMEText(html_content, "html")
        msg.attach(part)

        # Establish SMTP connection
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, TO_EMAIL, msg.as_string())
        server.quit()
        
        logger.info(f"Email notification successfully sent to {TO_EMAIL}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email notification: {e}")
        return False

def build_alerts_html(alerts: list) -> str:
    """
    Generate clean, styled HTML report for stock alerts.
    """
    alerts_rows = ""
    for alert in alerts:
        alerts_rows += f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #ddd; font-weight: bold;">{alert['ticker']}</td>
            <td style="padding: 10px; border-bottom: 1px solid #ddd;">{alert['name']}</td>
            <td style="padding: 10px; border-bottom: 1px solid #ddd; font-weight: bold;">${alert['current_price']:.2f}</td>
            <td style="padding: 10px; border-bottom: 1px solid #ddd; color: #6366f1;">{alert['reason']}</td>
        </tr>
        """
        
    return f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; border: 1px solid #eee; padding: 20px; border-radius: 8px; }}
            .header {{ background-color: #0b0f19; color: white; padding: 15px; text-align: center; border-radius: 6px 6px 0 0; }}
            .footer {{ font-size: 12px; color: #777; text-align: center; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>📈 Stock Picker & Monitor Alerts</h2>
            </div>
            <p>Hello,</p>
            <p>The following stock alert thresholds have been crossed or scheduled intervals reached:</p>
            <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                <thead>
                    <tr style="background-color: #f8f9fa; border-bottom: 2px solid #eee;">
                        <th style="padding: 10px; text-align: left;">Ticker</th>
                        <th style="padding: 10px; text-align: left;">Company</th>
                        <th style="padding: 10px; text-align: left;">Price</th>
                        <th style="padding: 10px; text-align: left;">Reason</th>
                    </tr>
                </thead>
                <tbody>
                    {alerts_rows}
                </tbody>
            </table>
            <p style="margin-top: 20px;">Check your dashboard for real-time tracking.</p>
            <div class="footer">
                <p>This is an automated notification from your personal Stock Picker project.</p>
            </div>
        </div>
    </body>
    </html>
    """
