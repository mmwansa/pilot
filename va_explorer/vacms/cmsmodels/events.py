from django.db import models
from django.urls import reverse

from va_explorer.vacms.cmsmodels.cms import Staff
from va_explorer.va_data_management.models import Death, Pregnancy, PregnancyOutcome, Household

class Event(models.Model):
    
    class EventType(models.IntegerChoices):  # okay
        NO_EVENT = 0, "No Event"
        PREGNANCY = 1, "Pregnancy"
        PREGNANCY_OUTCOME = 2, "Pregnancy Outcome"
        DEATH = 3, "Death"
    
    class EventStatus(models.IntegerChoices):
        NEW_EVENT = 0, "New Event"
        INTERVIEW_SCHEDULED = 1, "Interview Scheduled"
        INTERVIEW_COMPLETED = 2, "Interview Completed"
        INTERVIEW_ON_HOLD = 3, "Interview On Hold"
    
    interview_staff = models.ForeignKey(
        Staff,
        related_name='staff',
        null=True,
        on_delete=models.RESTRICT,
        help_text='Foreign key to the Staff.'
    )
    
    death = models.ForeignKey(
        Death,
        related_name='death',
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        help_text='Foreign key to the Death.'
    )
    
    pregnancy = models.ForeignKey(
        Pregnancy,
        related_name='pregnancy',
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        help_text='Foreign key to the Pregnancy.'
    )
    
    pregnancy_outcome = models.ForeignKey(
        PregnancyOutcome,
        related_name='pregnancy_outcome',
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        help_text='Foreign key to the Pregnancy Outcome.'
    )
    
    household = models.ForeignKey(
        Household,
        related_name='household',
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        help_text='Foreign key to the Household.'
    )
    
    #odk properties
    deviceid = models.CharField("Device ID", blank=True, null=True)
    instanceid = models.CharField("Instance ID", blank=True, null=True)
    today = models.CharField("Date Recorded", blank=True, null=True)
    start = models.CharField("Form Start Time", blank=True, null=True)
    province = models.CharField("[Select province]", blank=True, null=True)
    district = models.CharField("[Select district]", blank=True, null=True)
    constituency = models.CharField("[Select Constituency]", blank=True, null=True)
    ward = models.CharField("[Select Ward]", blank=True, null=True)
    ea = models.CharField("[Select Enumeration Area]", blank=True, null=True)
    supervisor = models.CharField("Select the name of your supervisor", blank=True, null=True)
    enumerator = models.CharField("Select your name", blank=True, null=True)
    
    event_type_code = models.TextField("[Select type of event]", blank=True, null=True)
    
    event_type = models.IntegerField(
        choices=EventType.choices,
        null=True,
    )
    
    event_status = models.IntegerField(choices=EventStatus.choices, null=True)
    
    interview_proposed_date = models.DateField(blank=True, null=True)
    interview_scheduled_date = models.DateField(blank=True, null=True)
    interview_contact_name = models.CharField(max_length=255, blank=True, null=True)
    interview_contact_tel = models.CharField(max_length=255, blank=True, null=True)
    
    respondent_name = models.CharField(max_length=255, blank=True, null=True)
    respondent_phone = models.CharField(max_length=255, blank=True, null=True)
    
    submission_date = models.DateField(blank=True, null=True)
    completion_date = models.DateField(blank=True, null=True)
    
    comment = models.CharField(max_length=255, blank=True, null=True)
    
    form_version = models.CharField(max_length=255, blank=True, null=True)
    
    class Meta:
        managed = True
        db_table = "cms_events"

    def __str__(self):
        return f"Event: {self.id} - {self.EventType(self.event_type).label}"
    
    def get_absolute_url(self): # new
        #return reverse('cms-baby-list', args=[str(self.id)])
        return reverse('cms-event-list', None)

