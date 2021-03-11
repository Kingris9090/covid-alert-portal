from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.conf import settings
from portal.widgets import CDSSelectWidget, CDSRadioWidget
from portal.forms import HealthcareBaseForm
from datetime import datetime
import pytz


hours = [
    (str(hour), datetime.strftime(datetime(2020, 1, 1, hour), "%H:%S"))
    for hour in range(24)
]
class DateForm(HealthcareBaseForm):
    def __init__(self, num_dates=1, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.num_dates = num_dates

        # Generate the desired number of date fields
        for i in range(num_dates):
            self.fields[f"day_{i}"] = forms.IntegerField(
                label=_("Day"), min_value=1, max_value=31, widget=forms.TextInput
            )
            self.fields[f"month_{i}"] = forms.IntegerField(
                label=_("Month"),
                min_value=1,
                max_value=12,
                widget=forms.TextInput,
            )
            self.fields[f"year_{i}"] = forms.IntegerField(
                label=_("Year"),
                min_value=2021,
                max_value=datetime.now().year,
                initial=2021,
                widget=forms.TextInput,
            )
            self.fields[f"start_hour_{i}"] = forms.ChoiceField(
                label=_("From"),
                choices=hours,
                # widget=CDSSelectWidget,
            )
            self.fields[f"end_hour_{i}"] = forms.ChoiceField(
                label=_("To"),
                choices=hours,
                # widget=CDSSelectWidget,
            )
        # Add the fieldset to the meta class
        # Idea adapted from: https://schinckel.net/2013/06/14/django-fieldsets/
        meta = getattr(self, "Meta", None)
        meta.fieldsets = tuple(
            (f"date_{i}", {"fields": (f"day_{i}", f"month_{i}", f"year_{i}", f"start_hour_{i}", f"end_hour_{i}")})
            for i in range(num_dates)
        )

    class Meta:
        fieldsets = ()

    def clean(self):
        # Validate each date provided to ensure that it is in fact a correct date
        cleaned_data = super().clean()
        is_valid = True
        error_msg = _("Invalid date specified.")
        for i in range(self.num_dates):
            try:
                tz = pytz.timezone(settings.TIME_ZONE or "UTC")
                cleaned_data[f"start_date_{i}"] = datetime(
                    year=cleaned_data.get(f"year_{i}", -1),
                    month=cleaned_data.get(f"month_{i}", -1),
                    day=cleaned_data.get(f"day_{i}", -1),
                    hour=int(cleaned_data.get(f"start_hour_{i}", -1)),
                ).replace(tzinfo=tz)
                cleaned_data[f"end_date_{i}"] = datetime(
                    year=cleaned_data.get(f"year_{i}", -1),
                    month=cleaned_data.get(f"month_{i}", -1),
                    day=cleaned_data.get(f"day_{i}", -1),
                    hour=int(cleaned_data.get(f"end_hour_{i}", -1)),
                ).replace(tzinfo=tz)
            except ValueError:
                is_valid = False
                meta = getattr(self, "Meta", None)
                meta.fieldsets[i][1]["error"] = error_msg

        if not is_valid:
            raise ValidationError(error_msg)

    def add_duplicate_error(self, index):
        error_msg = _(
            "Someone already notified people who were there at this date and time."
        )
        meta = getattr(self, "Meta", None)
        meta.fieldsets[index][1]["error"] = error_msg
        self.add_error(None, error_msg)  # Add a non-field error to flag this state


class SeverityForm(HealthcareBaseForm):
    alert_level = forms.ChoiceField(
        label="",
        choices=[
            ("1", _("Somebody sneezed...")),
            ("2", _("Sirens and lights flashing everywhere!")),
            ("3", _("Zombie apocalypse!!!!")),
        ],
        widget=CDSRadioWidget(attrs={"class": "multichoice-radio"}),
    )
