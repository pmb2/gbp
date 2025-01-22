from django.db import migrations
from pgvector.django import VectorExtension

class Migration(migrations.Migration):
    dependencies = [
        ('gbp_django', '0004_automate_log_and_tasks'),
    ]

    operations = [
        VectorExtension()
    ]
