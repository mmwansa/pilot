from django.db import models
from simple_history.models import HistoricalRecords


class Death(models.Model):

    deviceid = models.TextField("Device ID", blank=True)
    today = models.TextField("Date Recorded", blank=True)
    start = models.TextField("Form Start Time", blank=True)

    province = models.TextField("Province", blank=True)
    district = models.TextField("District", blank=True)
    constituency = models.TextField("Constituency", blank=True)
    ward = models.TextField("Ward", blank=True)
    rural_urban = models.TextField("Rural/Urban", blank=True)
    ea = models.TextField("Enumeration Area (EA)", blank=True)

    # Personnel
    enumerator = models.TextField("Enumerator", blank=True)
    supervisor = models.TextField("Supervisor", blank=True)
    consent = models.TextField("Did respondent give consent?", blank=True)

    code_input = models.TextField("Survey Building Number (SBN)", blank=True)
    death_occurred = models.TextField("Did death occur?", blank=True)
    description = models.TextField("Description of Death", blank=True)

    respondent = models.TextField("Respondent's Name", blank=True)
    result_other = models.TextField("Other result (Specify)", blank=True)

    deceased_name = models.TextField("Name of Deceased", blank=True)
    date_of_death = models.TextField("Date of Death", blank=True)
    age_at_death = models.TextField("Age at Death", blank=True)
    sex_of_deceased = models.TextField("Sex of Deceased", blank=True)
    cause_of_death = models.TextField("Cause of Death", blank=True)
    death_certificate_issued = models.TextField("Death Certificate Issued", blank=True)

    gps_coordinates = models.TextField("GPS Coordinates for Death Location", blank=True)

    submit_time = models.TextField("Submission Time", blank=True)
    end = models.TextField("Form End Time", blank=True)

    history = HistoricalRecords()

    def __str__(self):
        return f"{self.deceased_name} - {self.date_of_death}"
