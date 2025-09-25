import argparse
import os
import re
import pandas as pd
from django.core.management.base import BaseCommand
from va_explorer.va_data_management.models import ODKFormChoice
from va_explorer.va_data_management.utils.loading import normalize_string, normalize_value

FORM_ID_MAP = {
    "BASELINE_CENSUS": "household",
    "E_PREGNANCY": "pregnancy",
    "E_PREGNANCY_OUTCOME": "pregnancy-outcome",
    "E_DEATH": "death",
}


class Command(BaseCommand):
    """Load an ODK XLSForm definition using form ID from settings (robust, debuggable)."""

    help = "Load ODK form definition with normalization (case preserved). Supports --verbose, --dry-run, --only, --force."

    # ---------------------------
    # CLI
    # ---------------------------
    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument(
            "definition_file",
            type=str,
            help="Path to XLSForm definition file (.xlsx)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print detailed debug output.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and report without writing to the database.",
        )
        parser.add_argument(
            "--only",
            type=str,
            help="Only import choices for this survey field name (e.g., HH_33).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete existing choices for this form before loading.",
        )

    # ---------------------------
    # Helpers
    # ---------------------------
    @staticmethod
    def _canon_header(s: str) -> str:
        return str(s or "").strip().lower().replace(" ", "_")

    def _find_column(self, df: pd.DataFrame, target: str):
        """Find a column by canonicalized name (e.g., 'list_name' matches 'list name')."""
        target = self._canon_header(target)
        for col in df.columns:
            if self._canon_header(col) == target:
                return col
        return None

    # ---------------------------
    # Main
    # ---------------------------
    def handle(self, *args, **options):
        definition_file_path = options["definition_file"]
        verbose = options.get("verbose", False)
        dry_run = options.get("dry_run", False)
        only_field = options.get("only")
        force = options.get("force", False)

        # --- Existence check ---
        if not os.path.isfile(definition_file_path):
            self.stderr.write(f"Error: File not found: {definition_file_path}")
            return

        # --- Read settings to derive form_name via FORM_ID_MAP ---
        try:
            settings = pd.read_excel(
                definition_file_path,
                sheet_name="settings",
                dtype=str,
                engine="openpyxl",
                keep_default_na=False,
            )
        except Exception as ex:
            self.stderr.write(f"Error reading 'settings' sheet: {ex}")
            return

        form_id_col = None
        for col in settings.columns:
            if self._canon_header(col) == "form_id":
                form_id_col = col
                break

        if not form_id_col:
            self.stderr.write("Could not find 'form_id' column in 'settings' sheet.")
            return

        form_id = (settings.iloc[0][form_id_col] or "").strip()
        if not form_id:
            self.stderr.write("Empty 'form_id' in 'settings' sheet.")
            return

        form_id_str = form_id.upper()
        form_name = FORM_ID_MAP.get(form_id_str)
        if not form_name:
            self.stderr.write(f"Form ID '{form_id_str}' is not recognized or mapped.")
            return

        norm_form_name = normalize_string(form_name)

        # --- Handle existing rows (force or bail) ---
        if force:
            deleted = ODKFormChoice.objects.filter(form_name=norm_form_name).delete()
            self.stdout.write(f"[INFO] --force: deleted existing rows for form '{form_name}': {deleted}")
        elif ODKFormChoice.objects.filter(form_name=norm_form_name).exists():
            self.stderr.write(
                f"Error: The form '{form_name}' has already been loaded into ODKChoices. "
                f"Use --force to reload."
            )
            return

        # --- Read survey & choices ---
        try:
            survey = pd.read_excel(
                definition_file_path,
                sheet_name="survey",
                dtype=str,
                engine="openpyxl",
                keep_default_na=False,
            )
            choices = pd.read_excel(
                definition_file_path,
                sheet_name="choices",
                dtype=str,
                engine="openpyxl",
                keep_default_na=False,
            )
        except Exception as ex:
            self.stderr.write(f"Error reading 'survey' or 'choices' sheets: {ex}")
            return

        # --- Detect label column (label or label::<lang>) ---
        label_col = next((c for c in choices.columns if str(c).lower().startswith("label")), None)
        if not label_col:
            self.stderr.write("Could not find a 'label' column in choices sheet (e.g., 'label' or 'label::English').")
            return

        # --- Detect list_name column robustly ---
        list_name_col = self._find_column(choices, "list_name")
        if not list_name_col:
            self.stderr.write(
                f"Could not find 'list_name' column in choices sheet. Got columns: {list(choices.columns)}"
            )
            return

        # Precompute normalized list_name on choices
        choices["_list_name_norm"] = choices[list_name_col].apply(lambda x: normalize_string(x))

        created = 0
        missing_lists = []  # list of tuples (field_name, list_name_raw)

        # --- Iterate survey rows, parse select_* and match list names robustly ---
        for _, srow in survey.iterrows():
            qtype = str(srow.get("type", "") or "").strip()
            # Match: select_one ..., select_multiple ..., with optional _from_file
            m = re.match(r"select_(?:one|multiple)(?:_from_file)?\s+(.+)", qtype, flags=re.IGNORECASE)
            if not m:
                continue

            # Take only first token after select_* (ignore 'or_other' and other suffixes)
            list_name_raw = m.group(1).strip().split()[0]

            field = (srow.get("name") or "").strip()
            if not field:
                continue

            if only_field and field != only_field:
                continue

            norm_field = normalize_string(field)
            norm_list = normalize_string(list_name_raw)

            sub = choices[choices["_list_name_norm"] == norm_list]

            if verbose:
                self.stdout.write(
                    f"[DEBUG] field='{field}' norm_field='{norm_field}' "
                    f"list_name_raw='{list_name_raw}' norm_list='{norm_list}' "
                    f"matches={len(sub)}"
                )

            if sub.empty:
                missing_lists.append((field, list_name_raw))
                continue

            # Upsert rows (or dry-run)
            for _, crow in sub.iterrows():
                raw_value = crow.get("name")
                if raw_value in (None, ""):
                    continue
                raw_label = crow.get(label_col, "")
                norm_value = normalize_value(raw_value)
                norm_label = str(raw_label).strip() if raw_label is not None else ""

                if dry_run:
                    if verbose:
                        self.stdout.write(
                            f"[DRY-RUN] would upsert: form='{norm_form_name}', field='{norm_field}', "
                            f"value='{norm_value}', label='{norm_label}'"
                        )
                    created += 1
                else:
                    ODKFormChoice.objects.update_or_create(
                        form_name=norm_form_name,
                        field_name=norm_field,
                        value=norm_value,
                        defaults={"label": norm_label},
                    )
                    created += 1

        # --- Diagnostics for missing lists ---
        if missing_lists:
            self.stderr.write("[WARN] Some select questions had no matching choices list:")
            unique_lists = sorted({ln for _, ln in missing_lists})
            self.stderr.write(
                "       Missing list_names (normalized): " + ", ".join(normalize_string(x) for x in unique_lists)
            )
            for field, ln in missing_lists:
                self.stderr.write(f"       field '{field}' expected list '{ln}'")

        self.stdout.write(f"Loaded {created} choices for form '{form_name}' (normalized, case preserved){' [DRY-RUN]' if dry_run else ''}")
