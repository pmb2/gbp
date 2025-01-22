from django.db import migrations
from pgvector.django import VectorExtension

class Migration(migrations.Migration):
    dependencies = [
        ('gbp_django', '0001_initial'),
    ]

    operations = [
        VectorExtension()
    ]
