from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vacms", "0003_alter_event_data_collection_staff_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="va_interview_status",
            field=models.CharField(
                choices=[
                    ("scheduled", "Scheduled"),
                    ("completed", "Successfully Completed"),
                    ("not_done", "Not Done"),
                    ("postponed", "Postponed"),
                ],
                default="scheduled",
                max_length=20,
                verbose_name="VA Interview Status",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="va_not_done_reason",
            field=models.CharField(
                blank=True,
                choices=[
                    ("relocated", "Household relocated"),
                    ("dod_outside_period", "Date of death outside target period"),
                    ("non_resident", "Deceased not resident of EA"),
                    ("other", "Other"),
                ],
                max_length=32,
                null=True,
                verbose_name="Reason not done",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="va_not_done_other",
            field=models.CharField(
                blank=True,
                max_length=255,
                null=True,
                verbose_name="Not done - other comment",
            ),
        ),
    ]
