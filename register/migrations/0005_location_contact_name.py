# Generated by Django 3.1.7 on 2021-03-01 16:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('register', '0004_location_short_code_squashed_0006_merge_20210226_0132'),
    ]

    operations = [
        migrations.AddField(
            model_name='location',
            name='contact_name',
            field=models.CharField(max_length=200, null=True, verbose_name='Contact name'),
        ),
    ]
