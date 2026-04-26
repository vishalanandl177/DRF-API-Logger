from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('drf_api_logger', '0003_apilogsmodel_profiling'),
    ]

    operations = [
        migrations.AddField(
            model_name='apilogsmodel',
            name='error_type',
            field=models.CharField(blank=True, db_index=True, default=None, max_length=256, null=True),
        ),
    ]
