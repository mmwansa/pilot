from django.db import models
from django.urls import reverse

class Staff(models.Model):
    
    class CmsStatusType(models.IntegerChoices):
        """
        Does not come from ODK. Used by the sy`stem/admins.
        """
        NORMAL = 1, 'Normal'
        DUPLICATE = 2, 'Duplicate'

    class StaffType(models.TextChoices):
        CSA = 'CSA', 'Community Surveillance Assistant'
        VA = 'VA', 'Verbal Autopsy Interviewer'

    code = models.CharField(max_length=12, blank=True, null=True, verbose_name='Staff Code')
    staff_type = models.CharField(max_length=12, choices=StaffType.choices, blank=False, null=False,
                                  verbose_name='Staff Type')
    full_name = models.CharField(max_length=100, blank=True, null=True, verbose_name='Staff Full Name')
    title = models.CharField(max_length=100, blank=True, null=True)
    mobile_per = models.CharField(max_length=9, blank=True, null=True)
    email = models.CharField(max_length=100, blank=True, null=True)
    cms_status = models.IntegerField(choices=CmsStatusType.choices, null=True)
    comment = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'vacms_staff'

    def __str__(self):
        return f"{self.code} - {self.full_name} ({self.id})"
    
    def get_absolute_url(self): # new
        #return reverse('cms-baby-list', args=[str(self.id)])
        return reverse('cms-staff-list', None)
