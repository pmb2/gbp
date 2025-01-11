from celery import shared_task
from ..models import Business
from .automation_manager import AutomationManager
from django_celery_beat.models import PeriodicTask, IntervalSchedule

# Create schedule
schedule, _ = IntervalSchedule.objects.get_or_create(
    every=1,
    period=IntervalSchedule.DAYS,  # Adjust as needed
)

# Create periodic task
PeriodicTask.objects.get_or_create(
    interval=schedule,
    name='Automate All Business Tasks',
    task='gbp_django.tasks.automate_all_business_tasks',
)


@shared_task
def automate_all_business_tasks():
    """Automates tasks for all businesses."""
    businesses = Business.objects.all()
    for business in businesses:
        manager = AutomationManager(business)
        manager.monitor_reviews()
        manager.monitor_questions()
        manager.check_compliance()
        manager.generate_weekly_report()
