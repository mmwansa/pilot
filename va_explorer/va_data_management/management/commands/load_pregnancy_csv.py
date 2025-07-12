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

        # Read the CSV file into a DataFrame
        df = pd.read_csv(csv_file)
        df.columns = df.columns.str.strip()  # strip whitespace from headers

        # List of columns to apply value -> label replacement
        odk_map_columns = [
            'province', 'district', 'constituency', 'ward', 'ea', 'PE-03', 'PE-08', 'PE-09', 'PE-10', 'PE-11',
            'PE-12', 'PE-12A', 'PE-13', 'PE-14', 'PE-15', 'PE-16', 'PE-17', 'PE-18', 'PE-23', 'PE-24'
        ]
        odk_map_columns = [c.strip() for c in odk_map_columns]

        # Build odk_map from ODKFormChoice, making sure field_names are stripped
        all_choices = ODKFormChoice.objects.filter(form_name=form_name)
        odk_map = {}
        for choice in all_choices:
            field_name = choice.field_name.strip()
            if field_name not in odk_map:
                odk_map[field_name] = {}
            odk_map[field_name][str(choice.value)] = choice.label

        # --- Robust value-to-label function ---
        def lookup_label(col, v):
            """
            Convert a code value in the DataFrame (may be float, int, string, nan) to odk_map label.
            Handles zero-padded, integer, float, and string codes.
            """
            if pd.isnull(v) or str(v).lower() == 'nan':
                return v  # Keep as NaN/None
            v_str = str(v).strip()
            # Try exact match
            if v_str in odk_map[col]:
                return odk_map[col][v_str]
            # Try zero-padded string if numeric
            if v_str.isdigit():
                padded = v_str.zfill(2)
                if padded in odk_map[col]:
                    return odk_map[col][padded]
            # Try int-from-float (e.g., '1.0' -> '01')
            try:
                as_int = int(float(v_str))
                as_int_str = str(as_int).zfill(2)
                if as_int_str in odk_map[col]:
                    return odk_map[col][as_int_str]
            except Exception:
                pass
            # Fallback: return as-is
            return v

        # --- Perform label replacement ---
        for col in odk_map_columns:
            if col in df.columns and col in odk_map:
                print(f"Mapping csv column '{col}' with odk_map keys {list(odk_map[col].keys())}")
                print("BEFORE:", df[col].unique())
                df[col] = df[col].map(lambda v: lookup_label(col, v))
                print("AFTER:", df[col].unique())
            elif col not in df.columns:
                print(f"Column '{col}' not in DataFrame")
            elif col not in odk_map:
                print(f"Column '{col}' not in odk_map")

        # Rename and filter DataFrame columns to align with model fields.
        df = normalize_dataframe_columns(df, Pregnancy)

        # Remove duplicate columns after renaming
        df = df.loc[:, ~df.columns.duplicated()]

        # Only keep columns that are model fields
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
