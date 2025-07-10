import argparse
from collections import defaultdict

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from va_explorer.va_data_management.models import (
    ODKFormChoice,
    PregnancyOutcome,
)
from va_explorer.va_data_management.utils.loading import normalize_dataframe_columns


class Command(BaseCommand):
    """Load a pregnancy outcome CSV using the previously loaded ODK definition."""

    help = "Load pregnancy outcome CSV data"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=argparse.FileType("r"))

    def handle(self, *args, **options):
        form_name = "pregnancy_outcome"
        csv_file = options["csv_file"]

        if not ODKFormChoice.objects.filter(form_name=form_name).exists():
            raise CommandError(
                "Definition for form 'pregnancy_outcome' has not been loaded"
            )

        df = pd.read_csv(csv_file)
        df = normalize_dataframe_columns(df, PregnancyOutcome)

        lookup = defaultdict(dict)
        for choice in ODKFormChoice.objects.filter(form_name=form_name):
            lookup[choice.field_name][choice.value] = choice.label

        for field, mapping in lookup.items():
            if field in df.columns:
                df[field] = df[field].map(lambda v, _m=mapping: _m.get(str(v), v))

        objects = [PregnancyOutcome(**row) for row in df.to_dict(orient="records")]
        PregnancyOutcome.objects.bulk_create(objects)

        self.stdout.write(f"Imported {len(objects)} records for pregnancy_outcome")
