import argparse
import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from va_explorer.va_data_management.models import ODKFormChoice, PregnancyOutcome
from va_explorer.va_data_management.utils.loading import (
    normalize_dataframe_columns, normalize_string, load_odk_csv_to_model
)


class Command(BaseCommand):
    """Load a pregnancy outcome CSV using the previously loaded ODK definition."""

    help = "Load pregnancy outcome CSV data"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=argparse.FileType("r"))

    def handle(self, *args, **options):
        form_name = "pregnancy_outcome"
        csv_file = options["csv_file"]

        norm_form_name = normalize_string(form_name)

        if not ODKFormChoice.objects.filter(form_name=norm_form_name).exists():
            raise CommandError("Definition for form 'pregnancy-outcome' has not been loaded")

        df = pd.read_csv(csv_file)
        df = normalize_dataframe_columns(df, PregnancyOutcome)

        odk_map_columns = [
            'province','district','constituency','ward','ea','supervisor','enumerator','consent',
            'PO_07','PO_09','PO_11','PO_11A','PO_15','PO_21','PO_22','PO_26','PO_28','PO_30',
            'PO_31','informant','PO_34','PO_35','PO_37','PO_42','PO_43','PO_44','PO_45',
            'PO_46','PO_47B','PO_48','PO_49C', 'PO_49E','PO_50'
        ]
        odk_map_columns = [c.strip() for c in odk_map_columns]

        objects = load_odk_csv_to_model(
            df=df,
            model=PregnancyOutcome,
            odk_choices_queryset=ODKFormChoice.objects.filter(form_name=norm_form_name),
            odk_map_columns=odk_map_columns,
            verbose=True  # Set to False to reduce output
        )
        PregnancyOutcome.objects.bulk_create(objects)
        self.stdout.write(f"Imported {len(objects)} records for pregnancy outcome")