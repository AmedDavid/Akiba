from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()


@register.filter
def money(value, decimals=2):
    """
    Format a number with thousand separators and fixed decimals.
    Usage: {{ amount|money }} or {{ amount|money:0 }}
    """
    try:
        q = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return value
    try:
        decimals_int = int(decimals)
    except (TypeError, ValueError):
        decimals_int = 2
    format_str = f"{{:,.{decimals_int}f}}"
    return format_str.format(q)

