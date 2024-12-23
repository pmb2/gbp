from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
from datetime import datetime

class EmailService:
    @staticmethod
    def send_welcome_email(user):
        """Send welcome email when user registers"""
        subject = 'Welcome to GBP Automation Pro!'
        context = {
            'user_email': user.email,
            'current_year': datetime.now().year
        }
        
        html_content = render_to_string('emails/welcome_email.html', context)
        text_content = strip_tags(html_content)
        
        msg = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [user.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()

    @staticmethod
    def send_verification_email(business):
        """Send business email verification"""
        subject = 'Verify Your Business Email - GBP Automation Pro'
        context = {
            'business_name': business.business_name,
            'verification_url': f"{settings.SITE_URL}/api/business/verify-email/{business.email_verification_token}/",
            'current_year': datetime.now().year
        }
        
        html_content = render_to_string('emails/verify_business_email.html', context)
        text_content = strip_tags(html_content)
        
        msg = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [business.business_email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()

    @staticmethod
    def send_weekly_report(business, report_data):
        """Send weekly performance report"""
        subject = f'Weekly Performance Report - {business.business_name}'
        context = {
            'business_name': business.business_name,
            'report_data': report_data,
            'dashboard_url': f"{settings.SITE_URL}/dashboard/",
            'current_year': datetime.now().year
        }
        
        html_content = render_to_string('emails/weekly_report.html', context)
        text_content = strip_tags(html_content)
        
        msg = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [business.user.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()

    @staticmethod
    def send_task_notification(business, task_type, content):
        """Send notification for manual tasks"""
        subject = f'Action Required: {task_type.title()} Update - {business.business_name}'
        context = {
            'business_name': business.business_name,
            'task_type': task_type,
            'content': content,
            'action_url': f"{settings.SITE_URL}/dashboard/",
            'current_year': datetime.now().year
        }
        
        html_content = render_to_string('emails/task_notification.html', context)
        text_content = strip_tags(html_content)
        
        msg = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [business.user.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()

    @staticmethod
    def send_automation_report(business, task_type, content, executed_at):
        """Send report of automated actions"""
        subject = f'Automation Update: {task_type.title()} Completed - {business.business_name}'
        context = {
            'business_name': business.business_name,
            'task_type': task_type,
            'content': content,
            'executed_at': executed_at,
            'automation_settings': {
                'posts': business.posts_automation,
                'reviews': business.reviews_automation,
                'qa': business.qa_automation
            },
            'dashboard_url': f"{settings.SITE_URL}/dashboard/",
            'current_year': datetime.now().year
        }
        
        html_content = render_to_string('emails/automation_report.html', context)
        text_content = strip_tags(html_content)
        
        msg = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [business.user.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()

    @staticmethod
    def send_compliance_alert(business, issues):
        """Send compliance alert email"""
        subject = f'Compliance Alert - {business.business_name}'
        context = {
            'business_name': business.business_name,
            'issues': issues,
            'dashboard_url': f"{settings.SITE_URL}/dashboard/",
            'current_year': datetime.now().year
        }
        
        html_content = render_to_string('emails/compliance_alert.html', context)
        text_content = strip_tags(html_content)
        
        msg = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [business.user.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()

    @staticmethod
    def forward_feedback(user_email, feedback_type, message):
        """Forward user feedback to support"""
        subject = f'{settings.SUPPORT_EMAIL_SUBJECT_PREFIX} {feedback_type} from {user_email}'
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.FEEDBACK_EMAIL],
            fail_silently=False
        )
