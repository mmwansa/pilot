from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("va_data_management", "0030_merge_20250709_0208"),
    ]

    operations = [
        migrations.CreateModel(
            name="ODKFormChoice",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("form_name", models.CharField(max_length=100)),
                ("field_name", models.CharField(max_length=100)),
                ("value", models.TextField()),
                ("label", models.TextField()),
            ],
            options={
                "unique_together": {("form_name", "field_name", "value")},
            },
        ),
    ]

