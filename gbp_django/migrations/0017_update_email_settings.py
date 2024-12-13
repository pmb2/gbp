from django.db import migrations
from django.db.models import Value

def update_email_settings(apps, schema_editor):
    Business = apps.get_model('gbp_django', 'Business')
    db_alias = schema_editor.connection.alias
    
    # Update all businesses to have proper JSON email settings
    default_settings = {
        'enabled': True,
        'compliance_alerts': True,
        'content_approval': True,
        'weekly_summary': True,
        'verification_reminders': True
    }
    
    # Update all businesses
    Business.objects.using(db_alias).all().update(email_settings=default_settings)

def reverse_email_settings(apps, schema_editor):
    Business = apps.get_model('gbp_django', 'Business')
    db_alias = schema_editor.connection.alias
    Business.objects.using(db_alias).update(email_settings={})

class Migration(migrations.Migration):

    dependencies = [
        ('gbp_django', '0016_alter_business_email_settings'),
    ]

    operations = [
        migrations.RunPython(update_email_settings, reverse_email_settings),
    ]
