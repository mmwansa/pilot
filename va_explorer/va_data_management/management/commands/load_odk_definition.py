import argparse
import re
import os
import pandas as pd
from django.core.management.base import BaseCommand
from va_explorer.va_data_management.models import ODKFormChoice
from va_explorer.va_data_management.utils.loading import normalize_string, normalize_value

FORM_ID_MAP = {
    "E_HOUSEHOLD": "household",
    "E_PREGNANCY": "pregnancy",
    "E_PREGNANCY_OUTCOME": "pregnancy-outcome",
    "E_DEATH": "death",
}

class Command(BaseCommand):
    """Load an ODK XLSForm definition using form ID from settings."""

    help = "Load ODK form definition with normalization (case preserved)"

    def add_arguments(self, parser):
        parser.add_argument(
            "definition_file",
            type=str,
            help="Path to XLSForm definition file"
        )

    def handle(self, *args, **options):
        definition_file_path = options["definition_file"]

        # Check that the file exists before opening
        if not os.path.isfile(definition_file_path):
            # Try to extract form name for error message
            try:
                xl = pd.ExcelFile(definition_file_path)
                settings = xl.parse(sheet_name="settings")
                form_id = None
                for col in settings.columns:
                    if str(col).strip().lower() == "form_id":
                        form_id = settings.iloc[0][col]
                        break
                form_id_str = str(form_id).strip().upper() if form_id else "UNKNOWN"
                form_name = FORM_ID_MAP.get(form_id_str, form_id_str)
            except Exception:
                form_name = "UNKNOWN"
            self.stderr.write(f"Error: The file for the form '{definition_file_path}' cannot be found.")
            return

        # Now proceed to open the file
        try:
            settings = pd.read_excel(definition_file_path, sheet_name="settings")
            form_id = None
            for col in settings.columns:
                if str(col).strip().lower() == "form_id":
                    form_id = settings.iloc[0][col]
                    break
            if not form_id:
                self.stderr.write("Could not find 'form_id' in settings sheet.")
                return
            form_id_str = str(form_id).strip().upper()
            form_name = FORM_ID_MAP.get(form_id_str)
            if not form_name:
                self.stderr.write(f"Form ID '{form_id_str}' is not recognized or mapped.")
                return
        except Exception as ex:
            self.stderr.write(f"Error reading form_id from settings sheet: {ex}")
            return

        norm_form_name = normalize_string(form_name)
        if ODKFormChoice.objects.filter(form_name=norm_form_name).exists():
            self.stderr.write(
                f"Error: The form '{form_name}' has already been loaded into ODKChoices. "
                "If you wish to reload, you must first delete existing choices for this form."
            )
            return

        try:
            survey = pd.read_excel(definition_file_path, sheet_name="survey")
            choices = pd.read_excel(definition_file_path, sheet_name="choices")
        except Exception as ex:
            self.stderr.write(f"Error reading 'survey' or 'choices' sheets: {ex}")
            return

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
            norm_field = normalize_string(field)
            sub = choices[choices["list_name"] == list_name]
            for _, crow in sub.iterrows():
                raw_value = crow["name"]
                raw_label = crow[label_col]
                norm_value = normalize_value(raw_value)
                norm_label = str(raw_label).strip()
                ODKFormChoice.objects.update_or_create(
                    form_name=norm_form_name,
                    field_name=norm_field,
                    value=norm_value,
                    defaults={"label": norm_label},
                )
                created += 1
        self.stdout.write(f"Loaded {created} choices for form {form_name} (normalized, case preserved)")
