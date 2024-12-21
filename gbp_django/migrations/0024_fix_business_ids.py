from django.db import migrations, models

def convert_business_ids(apps, schema_editor):
    Business = apps.get_model('gbp_django', 'Business')
    for business in Business.objects.all():
        # Generate a unique business_id if none exists
        if not business.business_id:
            business.business_id = f"BIZ_{business.id}"
        business.save()

class Migration(migrations.Migration):
    dependencies = [
        ('gbp_django', '0023_convert_business_ids'),
    ]

    operations = [
        migrations.AlterField(
            model_name='business',
            name='id',
            field=models.BigAutoField(primary_key=True),
        ),
        migrations.AlterField(
            model_name='business',
            name='business_id',
            field=models.CharField(max_length=255, unique=True),
        ),
        migrations.AlterField(
            model_name='business',
            name='google_business_id',
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
        migrations.RunPython(convert_business_ids),
    ]
