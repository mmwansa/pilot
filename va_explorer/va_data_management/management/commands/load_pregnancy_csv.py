import argparse
import numpy as np
import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from va_explorer.va_data_management.models import ODKFormChoice, Pregnancy
from va_explorer.va_data_management.utils.loading import normalize_dataframe_columns

class Command(BaseCommand):
    """Load a pregnancy CSV using the previously loaded ODK definition."""

    help = "Load pregnancy CSV data"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=argparse.FileType("r"))

    def handle(self, *args, **options):
        form_name = "pregnancy"
        csv_file = options["csv_file"]

        if not ODKFormChoice.objects.filter(form_name=form_name).exists():
            raise CommandError("Definition for form 'pregnancy' has not been loaded")

        df = pd.read_csv(csv_file)

        # List of columns to apply value -> label replacement
        odk_map_columns = [
            "PE-02", "PE-03", "PE-05", "PE-06", "PE-07", "PE-07A", "PE-08", "PE-09", "PE-09A",
            "PE-10", "PE-10A", "PE-11", "PE-11_other", "PE-12", "PE-12A", "PE-12A_other", "PE-13",
            "PE-13_specify", "PE-14", "PE-14_specify", "PE-15", "PE-16", "PE-17", "PE-18", "PE-20",
            "PE-21", "PE-22", "PE-23", "PE-24", "PE-25-Latitude", "PE-25-Longitude", "PE-25-Altitude",
            "PE-25-Accuracy"
        ]

        # Get all ODKFormChoice entries for this form
        all_choices = ODKFormChoice.objects.filter(form_name=form_name)
        odk_map = {}
        for choice in all_choices:
            if choice.field_name not in odk_map:
                odk_map[choice.field_name] = {}
            odk_map[choice.field_name][str(choice.value)] = choice.label

        # Replace values in the DataFrame using the ODKFormChoice labels
        for col in odk_map_columns:
            if col in df.columns and col in odk_map:
                df[col] = df[col].astype(str).map(lambda v: odk_map[col].get(v, v))

        # Rename and filter DataFrame columns to align with model fields.
        df = normalize_dataframe_columns(df, Pregnancy)

        # Remove duplicate columns after renaming
        df = df.loc[:, ~df.columns.duplicated()]

        # Only keep columns that are model fields (just to be safe)
        model_fields = set([f.name for f in Pregnancy._meta.get_fields()])
        df = df[[col for col in df.columns if col in model_fields]]

        # Identify integer fields in the model
        int_fields = [
            f.name for f in Pregnancy._meta.get_fields()
            if getattr(f, 'get_internal_type', lambda: None)() in [
                'IntegerField', 'BigIntegerField', 'SmallIntegerField',
                'PositiveIntegerField', 'PositiveSmallIntegerField'
            ]
        ]

        # Helper to convert NaN to None for integer fields, per row
        def nan_to_none_for_intfields(row, int_fields):
            return {
                k: (None if (k in int_fields and pd.isnull(v)) else v)
                for k, v in row.items()
            }

        # Create objects with robust NaN-to-None for integer fields
        objects = [
            Pregnancy(**nan_to_none_for_intfields(row, int_fields))
            for row in df.to_dict(orient="records")
        ]
        Pregnancy.objects.bulk_create(objects)

        self.stdout.write(f"Imported {len(objects)} records for pregnancy")
