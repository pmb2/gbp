from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('gbp_django', '0016_auto_20231218_2028'),
    ]

    operations = [
        migrations.AlterField(
            model_name='business',
            name='email_settings',
            field=models.JSONField(blank=True, default=dict, help_text='Email notification preferences'),
        ),
        migrations.RunPython(
            code=lambda apps, schema_editor: apps.get_model('gbp_django', 'Business').objects.update(
                email_settings={
                    'enabled': True,
                    'compliance_alerts': True,
                    'content_approval': True,
                    'weekly_summary': True,
                    'verification_reminders': True
                }
            ),
            reverse_code=lambda apps, schema_editor: apps.get_model('gbp_django', 'Business').objects.update(
                email_settings={}
            )
        ),
    ]
