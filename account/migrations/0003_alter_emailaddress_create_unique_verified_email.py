from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('account', '0002_email_max_length'),
    ]

    operations = [
        # Handle existing constraint without creating duplicate
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterUniqueTogether(
                    name='emailaddress',
                    unique_together={('user', 'email')},
                ),
            ]
        ),
    ]
