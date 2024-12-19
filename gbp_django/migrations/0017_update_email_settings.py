from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('gbp_django', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='business',
            name='email_settings',
            field=models.TextField(blank=True, default='{}', help_text='Email notification preferences'),
        ),
        migrations.RunPython(
            code=lambda apps, schema_editor: apps.get_model('gbp_django', 'Business').objects.update(
                email_settings='{"enabled":true,"compliance_alerts":true,"content_approval":true,"weekly_summary":true,"verification_reminders":true}'
            ),
            reverse_code=lambda apps, schema_editor: apps.get_model('gbp_django', 'Business').objects.update(
                email_settings='{}'
            )
        ),
    ]
