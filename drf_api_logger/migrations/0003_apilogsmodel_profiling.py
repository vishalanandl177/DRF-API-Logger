from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('drf_api_logger', '0002_auto_20211221_2155'),
    ]

    operations = [
        migrations.AddField(
            model_name='apilogsmodel',
            name='profiling_data',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='apilogsmodel',
            name='sql_query_count',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
