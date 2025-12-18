from django.urls import reverse

from va_explorer.users.models import UserMessage

from .constants import VA_SCHEDULE_MESSAGE_SUBJECT


def ensure_va_schedule_message(event, request):
    """Create one mailbox notification per scheduled VA event."""
    if not (event and event.va_interview_staff_id):
        return

    existing = UserMessage.objects.filter(
        user_id=event.va_interview_staff_id,
        metadata__event_id=event.pk,
        subject=VA_SCHEDULE_MESSAGE_SUBJECT,
    )
    if existing.exists():
        return

    scheduled_date = event.interview_scheduled_date
    scheduled_date_str = (
        scheduled_date.strftime("%Y-%m-%d")
        if hasattr(scheduled_date, "strftime")
        else str(scheduled_date) if scheduled_date else ""
    )
    death_record = event.death
    deceased_name = getattr(death_record, "DE_03", None) or f"Death {event.pk}"
    event_detail_url = request.build_absolute_uri(
        reverse("cms-event-detail", kwargs={"pk": event.pk})
    )

    UserMessage.objects.create(
        user=event.va_interview_staff,
        subject=VA_SCHEDULE_MESSAGE_SUBJECT,
        body=(
            "A new verbal autopsy for "
            f"{deceased_name} has been scheduled on {scheduled_date_str}.\n"
            f"View the details: {event_detail_url}"
        ),
        metadata={
            "event_id": event.pk,
            "death_id": getattr(death_record, "pk", None),
            "scheduled_date": scheduled_date_str,
        },
    )


def remove_va_schedule_message(event):
    """Delete the scheduled-VA mailbox notification for the given event."""
    if not (event and event.va_interview_staff_id):
        return

    UserMessage.objects.filter(
        user_id=event.va_interview_staff_id,
        metadata__event_id=event.pk,
        subject=VA_SCHEDULE_MESSAGE_SUBJECT,
    ).delete()
