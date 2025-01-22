from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
from datetime import datetime
import logging

# Configure logger for detailed logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class EmailService:
    @staticmethod
    def send_email(template_name, subject, recipient_list, context, fail_silently=False):
        """
        Helper function to send emails with detailed logging.
        Sends both HTML and plain text versions.
        """
        logger.debug(f"Preparing to send email: {subject} to {recipient_list}")
        try:
            # Render the HTML content
            logger.debug(f"Rendering email template: emails/{template_name}.html with context: {context}")
            html_content = render_to_string(f'emails/{template_name}.html', context)
            text_content = strip_tags(html_content)

            # Create email message
            logger.debug(f"Creating email message for recipients: {recipient_list}")
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=recipient_list
            )
            msg.attach_alternative(html_content, "text/html")

            # Send email
            logger.info(f"Sending email with subject: '{subject}' to {recipient_list}")
            msg.send()
            logger.info(f"Email sent successfully: {subject} to {recipient_list}")
        except Exception as e:
            logger.error(f"Error while sending email to {recipient_list} with subject: {subject} - {e}")
            if not fail_silently:
                raise
        finally:
            logger.debug(f"Finished processing email for subject: {subject}")

    @staticmethod
    def send_welcome_email(user):
        """
        Send welcome email to newly registered users.
        """
        logger.info(f"Initiating welcome email process for user: {user.email}")
        subject = 'Welcome to GBP Automation Pro!'
        context = {
            'user_name': user.name or "Valued User",
            'current_year': datetime.now().year,
        }
        EmailService.send_email('welcome_email', subject, [user.email], context)

    @staticmethod
    def send_verification_email(business):
        """
        Send email verification for businesses.
        """
        logger.info(f"Initiating email verification process for business: {business.business_name}")
        subject = 'Verify Your Business Email - GBP Automation Pro'
        context = {
            'business_name': business.business_name,
            'verification_url': f"{settings.SITE_URL}/verify-email/{business.email_verification_token}/",
            'current_year': datetime.now().year,
        }
        EmailService.send_email('verify_business_email', subject, [business.business_email], context)

    @staticmethod
    def send_weekly_report(business, report_data):
        """
        Send weekly performance reports.
        """
        logger.info(f"Initiating weekly report email for business: {business.business_name}")
        subject = f'Weekly Performance Report - {business.business_name}'
        context = {
            'business_name': business.business_name,
            'report_data': report_data,
            'dashboard_url': f"{settings.SITE_URL}/dashboard/",
            'current_year': datetime.now().year,
        }
        EmailService.send_email('weekly_report', subject, [business.user.email], context)

    @staticmethod
    def send_task_notification(business, task_type, content):
        """
        Send notification for manual tasks that require user action.
        """
        logger.info(f"Initiating task notification email for task: {task_type} in business: {business.business_name}")
        subject = f'Action Required: {task_type.title()} Update - {business.business_name}'
        context = {
            'business_name': business.business_name,
            'task_type': task_type,
            'content': content,
            'action_url': f"{settings.SITE_URL}/dashboard/",
            'current_year': datetime.now().year,
        }
        EmailService.send_email('task_notification', subject, [business.user.email], context)

    @staticmethod
    def send_automation_report(business, task_type, content, executed_at):
        """
        Send report of automated tasks that have been completed.
        """
        logger.info(f"Initiating automation report email for task: {task_type} in business: {business.business_name}")
        subject = f'Automation Update: {task_type.title()} Completed - {business.business_name}'
        context = {
            'business_name': business.business_name,
            'task_type': task_type,
            'content': content,
            'executed_at': executed_at,
            'automation_settings': {
                'posts': business.posts_automation,
                'reviews': business.reviews_automation,
                'qa': business.qa_automation,
            },
            'dashboard_url': f"{settings.SITE_URL}/dashboard/",
            'current_year': datetime.now().year,
        }
        EmailService.send_email('automation_report', subject, [business.user.email], context)

    @staticmethod
    def send_compliance_alert(business, issues):
        """
        Send compliance alerts for flagged issues.
        """
        logger.info(f"Initiating compliance alert email for business: {business.business_name}")
        subject = f'Compliance Alert - {business.business_name}'
        context = {
            'business_name': business.business_name,
            'issues': issues,
            'dashboard_url': f"{settings.SITE_URL}/dashboard/",
            'current_year': datetime.now().year,
        }
        EmailService.send_email('compliance_alert', subject, [business.user.email], context)

    @staticmethod
    def forward_feedback(user_email, feedback_type, message):
        """
        Forward user feedback to the support team with enhanced formatting.
        """
        logger.info(f"Initiating feedback forwarding process from user: {user_email}")
        subject = f'New {feedback_type.title()} Feedback Received'
        context = {
            'user_email': user_email,
            'feedback_type': feedback_type.title(),
            'message': message,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'system_info': 'GBP Automation Pro v2.4.1'
        }
        try:
            EmailService.send_email(
                'forward_feedback', 
                subject,
                [settings.FEEDBACK_EMAIL],
                context
            )
            logger.info(f"Successfully forwarded feedback from {user_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to forward feedback: {str(e)}")
            return False
