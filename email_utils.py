from flask import render_template
from flask_mail import Message
from . import mail
from .models import Notification
from datetime import datetime

def send_email(app, notification):
    try:
        with app.app_context():
            msg = Message(
                subject=notification.subject,
                recipients=[notification.recipient],
                html=render_template('notification.html', message=notification.message),
                body=render_template('notification.txt', message=notification.message),
            )
            mail.send(msg)
            notification.status = "sent"
            notification.sent_at = datetime.utcnow()
    except Exception as e:
        notification.status = "failed"
        print(f"Failed to send email: {e}")
