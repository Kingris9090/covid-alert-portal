# Generated by Django 3.1.7 on 2021-02-26 01:36

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    replaces = [('register', '0004_location_short_code'), ('register', '0004_emailconfirmation')]

    dependencies = [
        ('register', '0003_auto_20210204_1508'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailConfirmation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('email', models.EmailField(max_length=255, verbose_name='email')),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddField(
            model_name='location',
            name='short_code',
            field=models.CharField(max_length=8, null=True, unique=True, verbose_name='Short code'),
        ),
    ]
