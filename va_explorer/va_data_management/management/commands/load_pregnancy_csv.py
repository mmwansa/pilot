import argparse
import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from va_explorer.va_data_management.models import ODKFormChoice, Pregnancy

from va_explorer.va_data_management.utils.loading import (
    normalize_dataframe_columns, normalize_string, load_odk_csv_to_model
)


class Command(BaseCommand):
    """Load a pregnancy CSV using the previously loaded ODK definition."""

    help = "Load pregnancy CSV data"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=argparse.FileType("r"))

    def handle(self, *args, **options):
        form_name = "pregnancy"
        csv_file = options["csv_file"]

        norm_form_name = normalize_string(form_name)

        if not ODKFormChoice.objects.filter(form_name=norm_form_name).exists():
            raise CommandError("Definition for form 'pregnancy' has not been loaded")

        df = pd.read_csv(csv_file)
        df = normalize_dataframe_columns(df, Pregnancy)

        odk_map_columns = [
            'province','district','constituency','ward','ea','enumerator','consent',
            'PE_03','PE_08','PE_09','PE_10','PE_11','PE_12','PE_12A',
            'PE_13','PE_14','PE_15','PE_16','PE_17','PE_18','PE_23','PE_24',
        ]
        odk_map_columns = [c.strip() for c in odk_map_columns]

        objects = load_odk_csv_to_model(
            df=df,
            model=Pregnancy,
            odk_choices_queryset=ODKFormChoice.objects.filter(form_name=norm_form_name),
            odk_map_columns=odk_map_columns,
            verbose=True  # Set to False to reduce output
        )

        Pregnancy.objects.bulk_create(objects)
        self.stdout.write(f"Imported {len(objects)} records for pregnancy")