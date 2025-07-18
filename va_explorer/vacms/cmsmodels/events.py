from django.db import models
from django.urls import reverse

from va_explorer.vacms.cmsmodels.cms import Staff
from va_explorer.va_data_management.models import (
    Death,
    Pregnancy,
    PregnancyOutcome,
    Household,
    VerbalAutopsy,
)


class Event(models.Model):

    class EventType(models.IntegerChoices):  # okay
        NO_EVENT = 0, "No Event"
        PREGNANCY = 1, "Pregnancy"
        PREGNANCY_OUTCOME = 2, "Pregnancy Outcome"
        DEATH = 3, "Death"

    class EventStatus(models.IntegerChoices):
        NEW_EVENT = 0, "New Event"
        DATA_COLLECTION_SCHEDULED = 1, "Data Collection Scheduled"
        DATA_COLLECTION_COMPLETED = 2, "Data Collection Completed"
        DATA_COLLECTION_ON_HOLD = 3, "Data Collection On Hold"
        VA_INTERVIEW_SCHEDULED = 4, "VA Interview Scheduled"
        VA_INTERVIEW_COMPLETED = 5, "VA Interview Completed"
        VA_INTERVIEW_ON_HOLD = 6, "VA Interview On Hold"

    data_collection_staff = models.ForeignKey(
        Staff,
        related_name="data_collection_events",  # Changed from "staff"
        null=True,
        on_delete=models.RESTRICT,
        help_text="Foreign key to the Staff.",
    )

    va_interview_staff = models.ForeignKey(
        Staff,
        related_name="va_interview_events",  # Changed from "staff"
        null=True,
        on_delete=models.RESTRICT,
        help_text="Foreign key to the Staff.",
    )

    death = models.ForeignKey(
        Death,
        related_name="events",  # Changed from "death"
        null=True,
        blank=False,
        on_delete=models.RESTRICT,
        help_text="Foreign key to the Death.",
    )

    va = models.ForeignKey(
        VerbalAutopsy,
        related_name="events",  # Changed from "va"
        null=True,
        blank=False,
        on_delete=models.RESTRICT,
        help_text="Foreign key to the verbal autopsy.",
    )

    pregnancy = models.ForeignKey(
        Pregnancy,
        related_name="events",  # Changed from "pregnancy"
        null=True,
        blank=False,
        on_delete=models.RESTRICT,
        help_text="Foreign key to the Pregnancy.",
    )

    pregnancy_outcome = models.ForeignKey(
        PregnancyOutcome,
        related_name="events",  # Changed from "pregnancy_outcome"
        null=True,
        blank=False,
        on_delete=models.RESTRICT,
        help_text="Foreign key to the Pregnancy Outcome.",
    )

    household = models.ForeignKey(
        Household,
        related_name="events",  # Changed from "household"
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        help_text="Foreign key to the Household.",
    )

    # odk properties
    deviceid = models.CharField("Device ID", max_length=255, blank=True, null=True)
    instanceid = models.CharField("Instance ID", max_length=255, blank=True, null=True)
    today = models.CharField("Date Recorded", max_length=255, blank=True, null=True)
    start = models.CharField("Form Start Time", max_length=255, blank=True, null=True)
    province = models.CharField(
        "[Select province]", max_length=255, blank=True, null=True
    )
    district = models.CharField(
        "[Select district]", max_length=255, blank=True, null=True
    )
    constituency = models.CharField(
        "[Select Constituency]", max_length=255, blank=True, null=True
    )
    ward = models.CharField("[Select Ward]", max_length=255, blank=True, null=True)
    ea = models.CharField(
        "[Select Enumeration Area]", max_length=255, blank=True, null=True
    )
    supervisor = models.CharField(
        "Select the name of your supervisor", max_length=255, blank=True, null=True
    )
    enumerator = models.CharField(
        "Select your name", max_length=255, blank=True, null=True
    )

    event_type_code = models.TextField(
        "[Select type of event]", max_length=255, blank=True, null=True
    )

    event_type = models.IntegerField(
        choices=EventType.choices,
        null=True,
    )

    event_status = models.IntegerField(choices=EventStatus.choices, null=True)

    data_collect_proposed_date = models.DateField("Data Collection Proposed Date", blank=True, null=True)
    data_collect_scheduled_date = models.DateField("Data Collection Scheduled Date",blank=False, null=True)
    data_collect_complete_date = models.DateField("Data Collection Complete Date",blank=False, null=True)
    data_collect_contact_name = models.CharField("Data Collection Contact Name",max_length=255, blank=True, null=True)
    data_collect_contact_tel = models.CharField("Data Collection Contact Phone",max_length=255, blank=True, null=True)
    data_collect_comments = models.TextField("Data Collection Comments",max_length=255, blank=True, null=True)

    interview_proposed_date = models.DateField("VA Interview Proposed Date",blank=True, null=True,)
    interview_scheduled_date = models.DateField("VA Interview Scheduled Date",blank=False, null=True)
    interview_complete_date = models.DateField("VA Interview Complete Date",blank=False, null=True)
    interview_contact_name = models.CharField("VA Interview Contact Name",max_length=255, blank=True, null=True)
    interview_contact_tel = models.CharField("VA Interview Contact Phone",max_length=255, blank=True, null=True)
    interview_comments = models.TextField("VA Interview Comments",max_length=255, blank=True, null=True)

    respondent_name = models.CharField("Respondent Name", max_length=255, blank=True, null=True)
    respondent_phone = models.CharField("Respondent Phone",max_length=255, blank=True, null=True)

    submission_date = models.DateField(blank=True, null=True)
    completion_date = models.DateField(blank=True, null=True)

    comment = models.CharField(max_length=255, blank=True, null=True)

    form_version = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = True
        db_table = "cms_events"

    def __str__(self):
        return f"Event: {self.id} - {self.EventType(self.event_type).label}"

    def get_absolute_url(self):  # new
        # return reverse('cms-baby-list', args=[str(self.id)])
        return reverse("cms-event-list", None)