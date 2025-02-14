# Generated by Django 3.1.3 on 2020-11-13 16:37

from django.db import migrations
import phonenumber_field.modelfields


class Migration(migrations.Migration):

    dependencies = [
        ("profiles", "0016_update_description_name_phone_number"),
    ]

    operations = [
        migrations.AlterField(
            model_name="healthcareuser",
            name="phone_number",
            field=phonenumber_field.modelfields.PhoneNumberField(
                blank=True,
                help_text="You must enter a new code each time you log in. We’ll text the code to your mobile phone number.",
                max_length=128,
                region=None,
            ),
        ),
    ]
