import argparse
import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from va_explorer.va_data_management.models import ODKFormChoice, Pregnancy
from va_explorer.va_data_management.utils.loading import normalize_dataframe_columns, normalize_string, normalize_value


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
            'province','district','constituency','ward','ea',
            'PE_03','PE_08','PE_09','PE_10','PE_11',
            'PE_12','PE_12A','PE_13','PE_14','PE_15',
            'PE_16','PE_17','PE_18','PE_23','PE_24',
        ]
        odk_map_columns = [c.strip() for c in odk_map_columns]

        # Build odk_map (all normalized but case preserved)
        all_choices = ODKFormChoice.objects.filter(form_name=norm_form_name)
        odk_map = {}
        for choice in all_choices:
            field_name = normalize_string(choice.field_name)
            value = normalize_value(choice.value)
            if field_name not in odk_map:
                odk_map[field_name] = {}
            odk_map[field_name][value] = choice.label

        def lookup_label(col, v):
            """Map value to label with normalization and robust handling."""
            v_norm = normalize_value(v)
            if v_norm in odk_map.get(col, {}):
                return odk_map[col][v_norm]
            # Fallback
            return v if pd.isnull(v) or str(v).lower() == "nan" else v_norm

        # Perform label replacement
        for col in odk_map_columns:
            if col in df.columns and col in odk_map:
                print(f"Mapping csv column '{col}' with odk_map keys {list(odk_map[col].keys())}")
                print("BEFORE:", df[col].unique())
                df[col] = df[col].map(lambda v, c=col: lookup_label(c, v))
                print("AFTER:", df[col].unique())
            elif col not in df.columns:
                print(f"Column '{col}' not in DataFrame")
            elif col not in odk_map:
                print(f"Column '{col}' not in odk_map") 

        # Remove duplicate columns after renaming
        df = df.loc[:, ~df.columns.duplicated()]

        # Only keep columns that are model fields
        model_fields = {f.name for f in Pregnancy._meta.get_fields()}
        df = df[[col for col in df.columns if col in model_fields]]

        # Identify integer fields in the model
        int_fields = [
            f.name for f in Pregnancy._meta.get_fields()
            if getattr(f, "get_internal_type", lambda: None)() in [
                "IntegerField",
                "BigIntegerField",
                "SmallIntegerField",
                "PositiveIntegerField",
                "PositiveSmallIntegerField",
            ]
        ]

        def nan_to_none_for_intfields(row, int_fields):
            return {
                k: (None if (k in int_fields and pd.isnull(v)) else v)
                for k, v in row.items()
            }

        objects = [
            Pregnancy(**nan_to_none_for_intfields(row, int_fields))
            for row in df.to_dict(orient="records")
        ]
        Pregnancy.objects.bulk_create(objects)

        self.stdout.write(f"Imported {len(objects)} records for pregnancy")
