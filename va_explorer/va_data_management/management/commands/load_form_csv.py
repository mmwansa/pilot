import argparse
from collections import defaultdict

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from va_explorer.va_data_management.models import (
    Death,
    Household,
    HouseholdMember,
    ODKFormChoice,
    Pregnancy,
    PregnancyOutcome,
)

FORM_MODEL_MAP = {
    "household": Household,
    "household_member": HouseholdMember,
    "pregnancy": Pregnancy,
    "pregnancy_outcome": PregnancyOutcome,
    "death": Death,
}


class Command(BaseCommand):
    help = "Load CSV data for a form using ODK definition reference"

    def add_arguments(self, parser):
        parser.add_argument("form_name", choices=FORM_MODEL_MAP.keys())
        parser.add_argument("csv_file", type=argparse.FileType("r"))

    def handle(self, *args, **options):
        form_name = options["form_name"]
        csv_file = options["csv_file"]

        if not ODKFormChoice.objects.filter(form_name=form_name).exists():
            raise CommandError(f"Definition for form '{form_name}' has not been loaded")

        df = pd.read_csv(csv_file)

        # Build mapping of field -> value -> label
        lookup = defaultdict(dict)
        for choice in ODKFormChoice.objects.filter(form_name=form_name):
            lookup[choice.field_name][choice.value] = choice.label

        for field, mapping in lookup.items():
            if field in df.columns:
                df[field] = df[field].map(lambda v, _map=mapping: _map.get(str(v), v))

        model = FORM_MODEL_MAP[form_name]
        objects = [model(**row) for row in df.to_dict(orient="records")]
        model.objects.bulk_create(objects)

        self.stdout.write(f"Imported {len(objects)} records for {form_name}")
