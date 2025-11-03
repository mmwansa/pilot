from django.conf import settings

from ..va_data_management.models import (
    VerbalAutopsy,
    questions_to_autodetect_duplicates,
)


def settings_context(_request):
    return {"settings": settings}


def auto_detect_duplicates(_request):
    return {"AUTO_DETECT_DUPLICATES": len(questions_to_autodetect_duplicates()) > 0}


def duplicates_count(_request):
    return {"DUPLICATES_COUNT": VerbalAutopsy.objects.filter(duplicate=True).count()}


def mailbox(request):
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        return {"MAILBOX_UNREAD_COUNT": user.mailbox_unread_count}
    return {"MAILBOX_UNREAD_COUNT": 0}
