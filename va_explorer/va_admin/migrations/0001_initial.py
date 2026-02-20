from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AdminPanelAlert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.CharField(choices=[("interaction", "Interaction"), ("security", "Security"), ("system", "System")], db_index=True, max_length=32)),
                ("severity", models.PositiveSmallIntegerField(choices=[(1, "Low"), (2, "Medium"), (3, "High"), (4, "Critical")], db_index=True, default=2)),
                ("title", models.CharField(max_length=255)),
                ("summary", models.CharField(blank=True, max_length=512)),
                ("details", models.TextField(blank=True)),
                ("context", models.JSONField(blank=True, default=dict)),
                ("path", models.CharField(blank=True, max_length=512)),
                ("ip_address", models.CharField(blank=True, max_length=64)),
                ("user_agent", models.CharField(blank=True, max_length=512)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="admin_panel_alerts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at", "-severity"),
            },
        ),
    ]
