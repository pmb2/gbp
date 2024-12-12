from django.db import migrations
from django.db.models import Value
from django.contrib.postgres.fields.jsonb import KeyTextTransform

def update_email_settings(apps, schema_editor):
    Business = apps.get_model('gbp_django', 'Business')
    db_alias = schema_editor.connection.alias
    
    # First update any string 'Enabled' values to proper JSON
    Business.objects.using(db_alias).filter(
        email_settings='Enabled'
    ).update(
        email_settings={
            'enabled': True,
            'compliance_alerts': True,
            'content_approval': True,
            'weekly_summary': True,
            'verification_reminders': True
        }
    )
    
    # Then handle any null or invalid values
    Business.objects.using(db_alias).filter(
        email_settings__isnull=True
    ).update(
        email_settings={}
    )

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
