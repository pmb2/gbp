from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('account', '0002_email_max_length'),
    ]

    operations = [
        # No-op migration to skip duplicate constraint
        migrations.RunPython(
            lambda apps, schema_editor: None,
            lambda apps, schema_editor: None
        )
    ]
