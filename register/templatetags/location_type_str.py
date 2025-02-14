from django import template
from django.utils.translation import gettext_lazy as _
from ..forms import (
    type_place,
    type_event,
    type_event_or_place,
    location_category_type_map,
)

register = template.Library()


@register.simple_tag
def location_type_str(location_category, prefix, *args, **kwargs):
    """
    Returns whole string based on type of location, event or place
    """
    if location_category:
        if prefix == "address":
            if location_category_type_map[location_category] == type_place:
                return _("Address of place")
            elif location_category_type_map[location_category] == type_event:
                return _("Address of event")
            elif location_category_type_map[location_category] == type_event_or_place:
                return _("Address of place or event")
        elif prefix == "name":
            if location_category_type_map[location_category] == type_place:
                return _("Name of place")
            elif location_category_type_map[location_category] == type_event:
                return _("Name of event")
            elif location_category_type_map[location_category] == type_event_or_place:
                return _("Name of place or event")
        raise ValueError(
            "Location category or prefix not valid for template tag filter."
        )
