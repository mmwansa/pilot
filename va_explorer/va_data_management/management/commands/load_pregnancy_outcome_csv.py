import argparse
import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from va_explorer.va_data_management.models import (
    ODKFormChoice,
    PregnancyOutcome,
    SRSClusterLocation,
)
from va_explorer.va_data_management.utils.loading import (
    normalize_dataframe_columns,
    normalize_string,
    load_odk_csv_to_model,
)


class Command(BaseCommand):
    help = (
        "Load pregnancy outcome CSV data. Adds 'cluster' column to match "
        "EA name (CSV) to SRSClusterLocation.name and inserts SRSClusterLocation.code "
        "into the 'cluster' column before saving."
    )

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=argparse.FileType("r"))
        parser.add_argument(
            "--log_missing_ea",
            type=str,
            default="missing_ea_name_mappings.csv",
            help="CSV file to log unmatched EA names"
        )

    def handle(self, *args, **options):
        form_name = "pregnancy_outcome"
        csv_file = options["csv_file"]
        missing_log = options["log_missing_ea"]

        norm_form_name = normalize_string(form_name)
        odk_choices = ODKFormChoice.objects.filter(form_name=norm_form_name)
        if not odk_choices.exists():
            raise CommandError("ODK form definition for 'pregnancy_outcome' not loaded.")

        df = pd.read_csv(csv_file)
        df = normalize_dataframe_columns(df, PregnancyOutcome)

        # Map EA → SRSClusterLocation.name → code
        ea_to_code_map = {
            loc.name.strip(): loc.code
            for loc in SRSClusterLocation.objects.exclude(name__isnull=True).exclude(code__isnull=True)
        }

        # Create 'cluster' column in the dataframe
        df["cluster"] = df["ea"].astype(str).str.strip().map(ea_to_code_map)

        # Log rows where EA didn't match
        missing_ea_df = df[df["cluster"].isnull()]
        if not missing_ea_df.empty:
            missing_ea_df[["key", "ea"]].drop_duplicates().to_csv(missing_log, index=False)
            self.stdout.write(
                self.style.WARNING(
                    f"{len(missing_ea_df)} records had unmatched EA values. Logged to {missing_log}"
                )
            )

        odk_map_columns = [
            'province', 'district', 'constituency', 'ward', 'ea', 'supervisor', 'enumerator', 'consent',
            'PO_07', 'PO_09', 'PO_11', 'PO_11A', 'PO_15', 'PO_21', 'PO_22', 'PO_26', 'PO_28', 'PO_30',
            'PO_31', 'informant', 'PO_34', 'PO_35', 'PO_37', 'PO_42', 'PO_43', 'PO_44', 'PO_45',
            'PO_46', 'PO_47B', 'PO_48', 'PO_49C', 'PO_49E', 'PO_50'
        ]

        objects = load_odk_csv_to_model(
            df=df,
            model=PregnancyOutcome,
            odk_choices_queryset=odk_choices,
            odk_map_columns=odk_map_columns,
            verbose=True
        )

        PregnancyOutcome.objects.bulk_create(objects)
        self.stdout.write(self.style.SUCCESS(f"Successfully imported {len(objects)} pregnancy outcome records."))
