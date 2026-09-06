from .models import Notification


def unread_notifications(request):
    """
    Makes `unread_notification_count` and `recent_notifications` available
    in every template - used by core/base.html's nav bell, so individual
    views don't each need to remember to pass this in.

    Requires adding this to TEMPLATES[0]["OPTIONS"]["context_processors"]
    in settings.py:

        "apps.notifications.context_processors.unread_nsotifications"
    """
    if not request.user.is_authenticated:
        return {}

    qs = Notification.objects.filter(user=request.user)
    return {
        "unread_notification_count": qs.filter(is_read=False).count(),
        "recent_notifications": qs[:5],
    }
