from django.db import migrations
from pgvector.django import VectorExtension

class Migration(migrations.Migration):
    dependencies = [
        ('gbp_django', '0003_alter_emailaddress_create_unique_verified_email'),
    ]

    operations = [
        VectorExtension()
    ]
