from django.db import migrations

def update_email_settings(apps, schema_editor):
    Business = apps.get_model('gbp_django', 'Business')
    for business in Business.objects.all():
        if not isinstance(business.email_settings, dict):
            business.email_settings = {
                'enabled': True,
                'compliance_alerts': True,
                'content_approval': True,
                'weekly_summary': True,
                'verification_reminders': True
            }
            business.save()

class Migration(migrations.Migration):

    dependencies = [
        ('gbp_django', '0016_alter_business_email_settings'),
    ]

    operations = [
        migrations.RunPython(update_email_settings),
    ]
