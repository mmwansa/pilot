from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('va_data_management', '0027_death_historicaldeath'),
    ]

    operations = [
        migrations.RunSQL(
            "ALTER TABLE va_data_management_household DROP CONSTRAINT IF EXISTS va_data_management_household_pkey CASCADE;"
        ),
        migrations.RunSQL(
            "ALTER TABLE va_data_management_household ADD COLUMN id SERIAL PRIMARY KEY;"
        ),
        migrations.RunSQL(
            "ALTER TABLE va_data_management_household ADD CONSTRAINT household_uuid_key UNIQUE (uuid);"
        ),

        migrations.RunSQL(
            "ALTER TABLE va_data_management_pregnancy DROP CONSTRAINT IF EXISTS va_data_management_pregnancy_pkey CASCADE;"
        ),
        migrations.RunSQL(
            "ALTER TABLE va_data_management_pregnancy ADD COLUMN id SERIAL PRIMARY KEY;"
        ),
        migrations.RunSQL(
            "ALTER TABLE va_data_management_pregnancy ADD CONSTRAINT pregnancy_uuid_key UNIQUE (uuid);"
        ),

        migrations.RunSQL(
            "ALTER TABLE va_data_management_pregnancyoutcome DROP CONSTRAINT IF EXISTS va_data_management_pregnancyoutcome_pkey CASCADE;"
        ),
        migrations.RunSQL(
            "ALTER TABLE va_data_management_pregnancyoutcome ADD COLUMN id SERIAL PRIMARY KEY;"
        ),
        migrations.RunSQL(
            "ALTER TABLE va_data_management_pregnancyoutcome ADD CONSTRAINT pregnancyoutcome_uuid_key UNIQUE (uuid);"
        ),

        migrations.RunSQL(
            "ALTER TABLE va_data_management_death DROP CONSTRAINT IF EXISTS va_data_management_death_pkey CASCADE;"
        ),
        migrations.RunSQL(
            "ALTER TABLE va_data_management_death ADD COLUMN id SERIAL PRIMARY KEY;"
        ),
        migrations.RunSQL(
            "ALTER TABLE va_data_management_death ADD CONSTRAINT death_uuid_key UNIQUE (uuid);"
        ),

        migrations.RunSQL(
            "ALTER TABLE va_data_management_householdmember ADD COLUMN uuid UUID DEFAULT gen_random_uuid();"
        ),
        migrations.RunSQL(
            "ALTER TABLE va_data_management_householdmember ADD CONSTRAINT householdmember_household_id_fkey FOREIGN KEY (household_id) REFERENCES va_data_management_household(id);"
        ),
        migrations.RunSQL(
            "ALTER TABLE va_data_management_pregnancyoutcome ADD CONSTRAINT pregnancyoutcome_pregnancy_id_fkey FOREIGN KEY (pregnancy_id) REFERENCES va_data_management_pregnancy(id);"
        ),
    ]
