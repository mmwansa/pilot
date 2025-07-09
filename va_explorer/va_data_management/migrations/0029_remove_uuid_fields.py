from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("va_data_management", "0028_auto_20250708_0000"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="household",
            name="uuid",
        ),
        migrations.RemoveField(
            model_name="householdmember",
            name="uuid",
        ),
        migrations.RemoveField(
            model_name="pregnancy",
            name="uuid",
        ),
        migrations.RemoveField(
            model_name="pregnancyoutcome",
            name="uuid",
        ),
        migrations.RemoveField(
            model_name="death",
            name="uuid",
        ),
        migrations.RemoveField(
            model_name="historicalhousehold",
            name="uuid",
        ),
        migrations.RemoveField(
            model_name="historicalpregnancy",
            name="uuid",
        ),
        migrations.RemoveField(
            model_name="historicalpregnancyoutcome",
            name="uuid",
        ),
        migrations.RemoveField(
            model_name="historicaldeath",
            name="uuid",
        ),
    ]
