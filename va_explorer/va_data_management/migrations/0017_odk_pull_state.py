from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("va_data_management", "0016_rename_submission_date_historicalhousehold_submissiondate_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ODKPullLock",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("form_id", models.CharField(blank=True, max_length=255, null=True)),
                ("project_id", models.IntegerField(blank=True, null=True)),
                ("locked_at", models.DateTimeField(auto_now=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="ODKPullState",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("form_id", models.CharField(max_length=255)),
                ("project_id", models.IntegerField()),
                ("last_submission_at", models.DateTimeField(blank=True, null=True)),
                ("last_run_started_at", models.DateTimeField(blank=True, null=True)),
                ("last_run_finished_at", models.DateTimeField(blank=True, null=True)),
                ("last_run_status", models.CharField(blank=True, choices=[("SUCCESS", "Success"), ("FAILED", "Failed"), ("RUNNING", "Running")], max_length=20)),
                ("last_error", models.TextField(blank=True)),
                ("last_counts", models.JSONField(blank=True, default=dict)),
            ],
        ),
        migrations.AddIndex(
            model_name="odkpulllock",
            index=models.Index(fields=["form_id", "project_id"], name="va_data_ma_form_id_5e4e48_idx"),
        ),
        migrations.AddIndex(
            model_name="odkpullstate",
            index=models.Index(fields=["form_id", "project_id"], name="va_data_ma_form_id_3c076e_idx"),
        ),
        migrations.AlterUniqueTogether(
            name="odkpulllock",
            unique_together={("project_id", "form_id")},
        ),
        migrations.AlterUniqueTogether(
            name="odkpullstate",
            unique_together={("project_id", "form_id")},
        ),
    ]
