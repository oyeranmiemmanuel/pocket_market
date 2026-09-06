from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import Notification


@login_required(login_url="accounts:login")
def notification_list(request):
    """
    Full notification history for the logged-in user, newest first.
    Visiting this page marks everything currently unread as read - the
    simplest possible "seen" model for an MVP with no per-item read/unread
    toggle in the UI yet.
    """
    notifications = Notification.objects.filter(user=request.user)
    notifications.filter(is_read=False).update(is_read=True)

    return render(request, "notifications/list.html", {"notifications": notifications})


@login_required(login_url="accounts:login")
def notification_redirect(request, pk):
    """
    Clicking a notification (e.g. from the nav dropdown) marks it read
    and sends the user to wherever it points, or back to the list if it
    has no target url.
    """
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=["is_read"])

    return redirect(notification.url or "notifications:list")
