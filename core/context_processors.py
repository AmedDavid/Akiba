"""
Context processors for global template variables
"""
from .models import Notification


def notifications(request):
    """Add unread notification count to all templates"""
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
        return {'unread_count': unread_count}
    return {'unread_count': 0}

