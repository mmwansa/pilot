import re
from collections import defaultdict
from datetime import timedelta
from io import BytesIO

import pandas as pd
from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured

from config.celery_app import app
from config.settings.base import env
from va_explorer.va_data_management.management.commands.import_from_kobo import (
    BATCH_SIZE,
)
from va_explorer.va_data_management.management.commands.load_form_csv import (
    FORM_MODEL_MAP,
)
from va_explorer.va_data_management.models import ODKFormChoice
from va_explorer.va_data_management.utils import coding, kobo, odk
from va_explorer.va_data_management.utils.loading import load_records_from_dataframe
from va_explorer.va_data_management.utils.odk import (
    pyodk_download_definition,
    pyodk_download_table,
)


def _iter_odk_sync_schedules():
    """Yield Celery schedules based on the configured ODK sync options."""
    schedules = []

    interval_raw = env("ODK_SYNC_INTERVAL_MINUTES", default=None)
    if interval_raw not in (None, ""):
        try:
            interval = int(interval_raw)
        except (TypeError, ValueError) as exc:
            raise ImproperlyConfigured(
                "ODK_SYNC_INTERVAL_MINUTES must be an integer number of minutes."
            ) from exc
        if interval <= 0:
            raise ImproperlyConfigured(
                "ODK_SYNC_INTERVAL_MINUTES must be a positive integer."
            )
        schedules.append(timedelta(minutes=interval))

    cron_entries = env.list("ODK_SYNC_CRONTAB", default=["0 0 * * *"])
    for expr in cron_entries:
        expression = expr.strip()
        if not expression:
            continue
        parts = expression.split()
        if len(parts) != 5:
            raise ImproperlyConfigured(
                "Each ODK_SYNC_CRONTAB entry must have five fields: minute, "
                "hour, day_of_month, month_of_year, and day_of_week."
            )
        minute, hour, day_of_month, month_of_year, day_of_week = parts
        schedules.append(
            crontab(
                minute=minute,
                hour=hour,
                day_of_month=day_of_month,
                month_of_year=month_of_year,
                day_of_week=day_of_week,
            )
        )

    if not schedules:
        schedules.append(crontab(hour=0, minute=0))

    return schedules


def load_definition_from_bytes(form_name: str, content: bytes) -> int:
    """Parse an XLSForm definition and populate ODKFormChoice."""
    survey = pd.read_excel(BytesIO(content), sheet_name="survey")
    choices = pd.read_excel(BytesIO(content), sheet_name="choices")
    label_col = None
    for col in choices.columns:
        if str(col).lower().startswith("label"):
            label_col = col
            break
    if label_col is None:
        return 0
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
    return created


def import_dataframe_records(form_name: str, df: pd.DataFrame) -> int:
    """Map values using ODKFormChoice and save model records."""
    lookup = defaultdict(dict)
    for choice in ODKFormChoice.objects.filter(form_name=form_name):
        lookup[choice.field_name][choice.value] = choice.label
    for field, mapping in lookup.items():
        if field in df.columns:
            df[field] = df[field].map(lambda v, _m=mapping: _m.get(str(v), v))
    model = FORM_MODEL_MAP[form_name]
    objects = [model(**row) for row in df.to_dict(orient="records")]
    model.objects.bulk_create(objects)
    return len(objects)


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    # Import from Kobo daily at 00:00
    sender.add_periodic_task(
        crontab(hour=0, minute=0), import_from_kobo.s(), name="Import from Kobo daily"
    )

    # Run Coding Algorithms daily at 00:30
    sender.add_periodic_task(
        crontab(hour=0, minute=30),
        run_coding_algorithms.s(),
        name="Run Coding Algorithms daily",
    )

    # Import forms and data from ODK according to the configured schedule(s)
    for index, schedule in enumerate(_iter_odk_sync_schedules(), start=1):
        name = "Import ODK forms" if index == 1 else f"Import ODK forms #{index}"
        sender.add_periodic_task(schedule, import_odk_forms.s(), name=name)


# Result of tasks need to be json serializable so return dicts.
@app.task()
def run_coding_algorithms():
    results = coding.run_coding_algorithms()
    return {
        "num_coded": len(results["causes"]),
        "num_total": len(results["verbal_autopsies"]),
        "num_issues": len(results["issues"]),
    }


@app.task()
def import_from_odk():
    options = {
        "email": env("ODK_EMAIL"),
        "password": env("ODK_PASSWORD"),
        "project_id": env("ODK_PROJECT_ID"),
        "form_id": env("ODK_FORM_ID"),
    }
    data = odk.download_responses(
        options["email"],
        options["password"],
        project_id=options["project_id"],
        form_id=options["form_id"],
    )
    results = load_records_from_dataframe(data)
    return {
        "num_created": len(results["created"]),
        "num_ignored": len(results["ignored"]),
        "num_outdated": len(results["outdated"]),
    }


@app.task()
def import_from_kobo():
    options = {
        "token": env("KOBO_API_TOKEN"),
        "asset_id": env("KOBO_ASSET_ID"),
    }
    data, next_page = kobo.download_responses(
        options["token"], options["asset_id"], BATCH_SIZE, None
    )
    results = load_records_from_dataframe(data)

    num_created = len(results["created"])
    num_ignored = len(results["ignored"])
    num_outdated = len(results["outdated"])
    num_corrected = len(results["corrected"])
    num_invalid = len(results["removed"])

    # Process all available pages of kobo data since it is provided via pagination
    while next_page is not None:
        data, next_page = kobo.download_responses(
            options["token"], options["asset_id"], BATCH_SIZE, next_page
        )
        results = load_records_from_dataframe(data)
        num_created = num_created + len(results["created"])
        num_ignored = num_ignored + len(results["ignored"])
        num_outdated = num_outdated + len(results["outdated"])
        num_corrected = num_corrected + len(results["corrected"])
        num_invalid = num_invalid + len(results["removed"])

    return {
        "num_ignored": num_ignored,
        "num_outdated": num_outdated,
        "num_created": num_created,
        "num_corrected": num_corrected,
        "num_removed": num_invalid,
    }


def _sync_odk_forms():
    """Download ODK form definitions and data using pyODK."""
    forms = {
        "household": env("ODK_HOUSEHOLD_FORM_ID", default=""),
        "pregnancy": env("ODK_PREGNANCY_FORM_ID", default=""),
        "pregnancy_outcome": env("ODK_PREGNANCY_OUTCOME_FORM_ID", default=""),
        "death": env("ODK_DEATH_FORM_ID", default=""),
    }
    results = {}
    for name, form_id in forms.items():
        if not form_id:
            continue
        definition = pyodk_download_definition(form_id)
        if definition:
            load_definition_from_bytes(name, definition)
        df = pyodk_download_table(form_id)
        if not df.empty:
            num = import_dataframe_records(name, df)
            results[name] = num
    return results


@app.task()
def import_odk_forms():
    """Celery task wrapper around the pyODK synchronization pipeline."""
    return _sync_odk_forms()


def sync_odk_forms():
    """Expose the pyODK sync pipeline for synchronous callers."""
    return _sync_odk_forms()
