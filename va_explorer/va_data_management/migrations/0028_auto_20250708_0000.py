from django.db import migrations, models
import uuid

class Migration(migrations.Migration):

    dependencies = [
        ('va_data_management', '0027_death_historicaldeath'),
    ]

    operations = [
        migrations.AlterField(
            model_name='household',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name='household',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='pregnancy',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name='pregnancy',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='pregnancyoutcome',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name='pregnancyoutcome',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='death',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name='death',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='householdmember',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
