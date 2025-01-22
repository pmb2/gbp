from django.db import migrations, models
from django.core.validators import RegexValidator

class Migration(migrations.Migration):
    dependencies = [
        ('gbp_django', '0002_enable_pgvector'),
    ]

    operations = [
        migrations.CreateModel(
            name='AutomationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('business_id', models.CharField(max_length=255, validators=[RegexValidator(regex='^[a-zA-Z0-9_-]+$')])),
                ('action_type', models.CharField(choices=[('FILE_UPLOAD', 'File Upload'), ('AUTO_RESPONSE', 'Automated Response'), ('SCHEDULED_TASK', 'Scheduled Task'), ('SYSTEM_ALERT', 'System Alert')], default='FILE_UPLOAD', max_length=50)),
                ('details', models.JSONField()),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('RUNNING', 'Running'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed')], default='PENDING', max_length=50)),
                ('user_id', models.CharField(max_length=255, validators=[RegexValidator(regex='^[a-zA-Z0-9_-]+$')])),
                ('error_message', models.TextField(blank=True, null=True)),
                ('retries', models.IntegerField(default=0)),
                ('executed_at', models.DateTimeField(blank=True, null=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'indexes': [
                    models.Index(fields=['business_id', '-created_at'], name='gbp_django__busines_f0e75a_idx'),
                    models.Index(fields=['status', 'action_type'], name='gbp_django__status_0675f2_idx'),
                ],
            },
        ),
    ]
