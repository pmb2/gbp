from django.core.management.base import BaseCommand
from gbp_django.tasks.tasks import automate_all_business_tasks


class Command(BaseCommand):
    help = 'Trigger automation tasks for all businesses.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting automation tasks for all businesses...")

        # Trigger Celery task for all business automation
        result = automate_all_business_tasks.delay()

        # Log task ID and success
        self.stdout.write(f"Task ID: {result.id}")
        self.stdout.write(self.style.SUCCESS('Automation tasks successfully triggered.'))
