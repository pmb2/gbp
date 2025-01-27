from datetime import datetime, timedelta
from django.conf import settings
from ..models import Business, Task
from ..utils.email_service import EmailService


class AutomationManager:
    def __init__(self, business):
        self.business = business
        self.email_service = EmailService()
        self.preferences = business.get_email_preferences()

    def handle_task(self, task_type, content):
        """Handle task based on automation settings"""
        automation_level = self._get_automation_level(task_type)

        if automation_level == 'manual':
            self._create_notification(task_type, content)
        elif automation_level == 'approval':
            self._request_approval(task_type, content)
        elif automation_level == 'auto':
            self._execute_task(task_type, content)

    def _get_automation_level(self, task_type):
        """Get automation level for task type"""
        if task_type == 'post':
            return self.business.posts_automation
        elif task_type == 'review':
            return self.business.reviews_automation
        elif task_type == 'qa':
            return self.business.qa_automation
        elif task_type == 'account_status':
            return 'auto'  # Assume account status checks are always automatic
        return 'manual'  # Default to manual

    def _create_notification(self, task_type, content):
        """Create manual task notification"""
        self.email_service.send_task_notification(
            self.business,
            task_type,
            content
        )

    def _request_approval(self, task_type, content):
        """Create approval request"""
        task = Task.objects.create(
            business=self.business,
            type=task_type,
            content=content,
            status='pending',
            auto_approve_at=datetime.now() + timedelta(
                hours=self.preferences.get('auto_approve_hours', 24)
            )
        )

        self.email_service.send_content_approval(
            self.business,
            task_type,
            content,
            task.id
        )

    def _execute_task(self, task_type, content):
        """Execute automated task with RAG context"""
        from ..utils.rag_utils import get_relevant_context
        
        # Get relevant knowledge base context
        rag_context = get_relevant_context(
            query=content,
            business_id=self.business.business_id,
            min_similarity=0.6
        )
        
        # Create task with RAG-enhanced content
        task = Task.objects.create(
            business=self.business,
            type=task_type,
            content={
                'original': content,
                'rag_context': rag_context,
                'generated': self._generate_task_content(task_type, content, rag_context)
            },
            status='completed',
            executed_at=datetime.now()
        )

        if task_type == 'post':
            self._create_post(content)
        elif task_type == 'review':
            self._respond_to_review(content)
        elif task_type == 'qa':
            self._answer_question(content)
        elif task_type == 'account_status':
            self._check_account_status()

        self._send_execution_report(task)

    def _send_execution_report(self, task):
        """Send report of automated action"""
        self.email_service.send_automation_report(
            self.business,
            task.type,
            task.content,
            task.executed_at
        )

    def check_compliance(self):
        """Check business profile compliance"""
        issues = []

        # Check profile completeness
        completion = self.business.calculate_profile_completion()
        if completion < 100:
            issues.append("Profile information incomplete")

        # Check post frequency
        last_post = self.business.last_post_date
        if last_post and (datetime.now() - last_post).days > 7:
            issues.append("No posts in the last 7 days")

        # Check review responses
        if self.business.has_unresponded_reviews():
            issues.append("Unresponded reviews pending")

        # Check Q&A responses
        if self.business.has_unanswered_questions():
            issues.append("Unanswered Q&A pending")

        if issues:
            self.email_service.send_compliance_alert(
                self.business,
                issues
            )

    def monitor_reviews(self):
        """Monitor and respond to reviews"""
        new_reviews = self.business.get_new_reviews()
        for review in new_reviews:
            self._execute_task('review', review)

    def monitor_questions(self):
        """Monitor and answer new Q&A"""
        new_questions = self.business.get_new_questions()
        for question in new_questions:
            self._execute_task('qa', question)

    def _check_account_status(self):
        """Check account status and alert if necessary"""
        status = self.business.get_account_status()
        if status != 'active':
            self.email_service.send_compliance_alert(
                self.business,
                [f"Account status: {status}"]
            )

    def generate_weekly_report(self):
        """Generate and send weekly performance report"""
        report_data = {
            'profile_completion': self.business.calculate_profile_completion(),
            'posts_stats': self._get_posts_stats(),
            'reviews_stats': self._get_reviews_stats(),
            'qa_stats': self._get_qa_stats(),
            'compliance_score': self.business.compliance_score
        }

        self.email_service.send_weekly_report(
            self.business,
            report_data
        )
