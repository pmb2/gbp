from django.db import migrations

def convert_business_ids(apps, schema_editor):
    Business = apps.get_model('gbp_django', 'Business')
    # Generate new sequential business_ids
    for index, business in enumerate(Business.objects.all().order_by('id')):
        business.business_id = index + 1  # Start from 1
        business.save()

class Migration(migrations.Migration):
    dependencies = [
        ('gbp_django', '0022_remove_business_id_business_google_business_id_and_more'),
    ]

    operations = [
        migrations.RunPython(convert_business_ids),
    ]
