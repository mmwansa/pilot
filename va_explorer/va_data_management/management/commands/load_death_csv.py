import argparse
import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from va_explorer.va_data_management.models import ODKFormChoice, Death
from va_explorer.va_data_management.utils.loading import (
    normalize_dataframe_columns, normalize_string, load_odk_csv_to_model
)

class Command(BaseCommand):
    """Load a death CSV using the previously loaded ODK definition."""

    help = "Load death CSV data"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=argparse.FileType("r"))

    def handle(self, *args, **options):
        form_name = "death"
        csv_file = options["csv_file"]

        norm_form_name = normalize_string(form_name)

        if not ODKFormChoice.objects.filter(form_name=norm_form_name).exists():
            raise CommandError("Definition for form 'death' has not been loaded")

        df = pd.read_csv(csv_file)
        df = normalize_dataframe_columns(df, Death)

        odk_map_columns = [
            'province','district','constituency','ward','ea','supervisor','enumerator','consent',
            'DE_05','DE_07','DE_09','DE_11','DE_13','DE_16','DE_17',
            'DE_18','DE_21','DE_24','DE_30','DE_31'
        ]
        odk_map_columns = [c.strip() for c in odk_map_columns]

        objects = load_odk_csv_to_model(
            df=df,
            model=Death,
            odk_choices_queryset=ODKFormChoice.objects.filter(form_name=norm_form_name),
            odk_map_columns=odk_map_columns,
            verbose=True  # Set to False to reduce output
        )
        Death.objects.bulk_create(objects)
        self.stdout.write(f"Imported {len(objects)} records for death")
