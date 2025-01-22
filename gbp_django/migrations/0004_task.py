from django.db import migrations, models
import django.utils.timezone
from datetime import time

class Migration(migrations.Migration):
    dependencies = [
        ('gbp_django', '0003_automationlog'),
    ]

    operations = [
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('task_type', models.CharField(choices=[('POST', 'Social Post'), ('PHOTO', 'Photo Upload'), ('REVIEW', 'Review Monitoring'), ('QA', 'Q&A Check'), ('COMPLIANCE', 'Compliance Check')], default='POST', max_length=20)),
                ('frequency', models.CharField(choices=[('DAILY', 'Daily'), ('WEEKLY', 'Weekly'), ('MONTHLY', 'Monthly'), ('CUSTOM', 'Custom')], default='WEEKLY', max_length=20)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('RUNNING', 'Running'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed'), ('PAUSED', 'Paused')], default='PENDING', max_length=20)),
                ('next_run', models.DateTimeField(default=django.utils.timezone.now)),
                ('scheduled_time', models.TimeField(default=time(9, 0))),
                ('scheduled_date', models.DateField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('parameters', models.JSONField(default=dict)),
                ('last_run', models.DateTimeField(blank=True, null=True)),
                ('retry_count', models.IntegerField(default=0)),
            ],
        ),
    ]
