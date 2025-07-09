import argparse
import re

import pandas as pd
from django.core.management.base import BaseCommand

from va_explorer.va_data_management.models import ODKFormChoice


class Command(BaseCommand):
    """Load the pregnancy outcome ODK XLSForm definition."""

    help = "Load pregnancy outcome form definition"

    def add_arguments(self, parser):
        parser.add_argument("definition_file", type=argparse.FileType("rb"))

    def handle(self, *args, **options):
        form_name = "pregnancy_outcome"
        definition_file = options["definition_file"]

        survey = pd.read_excel(definition_file, sheet_name="survey")
        choices = pd.read_excel(definition_file, sheet_name="choices")

        label_col = None
        for col in choices.columns:
            if str(col).lower().startswith("label"):
                label_col = col
                break
        if not label_col:
            self.stderr.write("Could not find label column in choices sheet")
            return

        created = 0
        for _, srow in survey.iterrows():
            qtype = str(srow.get("type", ""))
            match = re.match(r"select_(?:one|multiple)\s+(.+)", qtype)
            if not match:
                continue
            list_name = match.group(1)
            field = srow.get("name")
            if not field:
                continue
            sub = choices[choices["list_name"] == list_name]
            for _, crow in sub.iterrows():
                ODKFormChoice.objects.update_or_create(
                    form_name=form_name,
                    field_name=field,
                    value=str(crow["name"]),
                    defaults={"label": str(crow[label_col])},
                )
                created += 1
        self.stdout.write(f"Loaded {created} choices for form {form_name}")
