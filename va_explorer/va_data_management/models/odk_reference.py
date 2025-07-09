from django.db import models


class ODKFormChoice(models.Model):
    form_name = models.CharField(max_length=100)
    field_name = models.CharField(max_length=100)
    value = models.TextField()
    label = models.TextField()

    class Meta:
        unique_together = ("form_name", "field_name", "value")

    def __str__(self):
        return f"{self.form_name}:{self.field_name} {self.value}->{self.label}"
