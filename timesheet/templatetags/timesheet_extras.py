from django import template

register = template.Library()


@register.filter
def sum_duration(entries):
    """Sum duration hours from queryset/list of entries"""
    return round(sum(e.duration_hours for e in entries), 1)


@register.filter
def status_badge_class(status):
    """Return Bootstrap badge class for a given status"""
    status_map = {
        "DRAFT": "secondary",
        "SUBMITTED": "info",
        "APPROVED": "success",
        "REJECTED": "danger",
        "PENDING": "warning",
    }
    return status_map.get(status, "secondary")
