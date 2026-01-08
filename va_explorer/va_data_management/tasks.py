import logging

from celery.schedules import crontab

from config.celery_app import app
from config.settings.base import env
from django.conf import settings
from va_explorer.va_data_management.management.commands.import_from_kobo import (
    BATCH_SIZE,
)
from va_explorer.va_data_management.odk.service import ODKPullService
from va_explorer.va_data_management.utils import coding, kobo, odk
from va_explorer.va_data_management.utils.loading import load_records_from_dataframe

logger = logging.getLogger(__name__)


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

    # Import forms and data from ODK daily at 01:00
    interval = max(env.int("ODK_PULL_INTERVAL_MINUTES", default=30), 1)
    sender.add_periodic_task(
        crontab(minute=f"*/{interval}"),
        pull_odk_scheduled.s(),
        name="Pull ODK submissions",
    )


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
    """Legacy entrypoint maintained for compatibility; delegates to pull_odk_scheduled."""
    return pull_odk_scheduled()


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


@app.task()
def import_odk_forms():
    """Legacy alias to keep historical schedule names working."""
    return pull_odk_scheduled()


def _odk_form_configs():
    configs = getattr(settings, "ODK_PULL_FORMS", [])
    normalized = []
    for cfg in configs:
        form_id = cfg.get("form_id")
        if not form_id:
            continue
        normalized.append(
            {
                "form_id": form_id,
                "form_name": cfg.get("form_name"),
                "project_id": cfg.get("project_id")
                or getattr(settings, "ODK_DEFAULT_PROJECT_ID", None),
                "enabled": cfg.get("enabled", True),
                "frequency_minutes": cfg.get("frequency_minutes"),
            }
        )
    return normalized


@app.task()
def pull_odk_scheduled():
    service = ODKPullService(
        default_project_id=getattr(settings, "ODK_DEFAULT_PROJECT_ID", None)
    )
    configs = _odk_form_configs()
    summary = service.pull_forms(configs)
    logger.info("ODK scheduled pull complete", extra={"summary": summary})
    return summary
