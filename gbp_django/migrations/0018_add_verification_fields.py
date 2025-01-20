from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('gbp_django', '0017_update_email_settings'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='verification_status',
            field=models.CharField(
                choices=[
                    ('UNVERIFIED', 'Unverified'),
                    ('PENDING', 'Verification Pending'),
                    ('VERIFIED', 'Verified'),
                    ('SUSPENDED', 'Suspended'),
                ],
                default='UNVERIFIED',
                max_length=50
            ),
        ),
        migrations.AddField(
            model_name='business',
            name='verification_method',
            field=models.CharField(
                choices=[
                    ('NONE', 'None'),
                    ('EMAIL', 'Email'),
                    ('PHONE', 'Phone'),
                    ('POSTCARD', 'Postcard'),
                    ('OTHER', 'Other'),
                ],
                default='NONE',
                max_length=50
            ),
        ),
        migrations.AddField(
            model_name='business',
            name='last_verification_attempt',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
