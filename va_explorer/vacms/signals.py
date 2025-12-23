from django.db.models.signals import post_save
from django.dispatch import receiver

from va_explorer.vacms.cmsmodels.events import Event
from va_explorer.vacms.notifications import remove_va_schedule_message


@receiver(post_save, sender=Event, dispatch_uid="vacms_event_status_cleanup")
def handle_event_status_save(sender, instance, **kwargs):
    """
    Ensure mailbox notifications are removed when a VA interview is not pending.
    """
    if instance.va_interview_status in (
        Event.VAInterviewStatus.COMPLETED,
        Event.VAInterviewStatus.NOT_DONE,
    ):
        remove_va_schedule_message(instance)
