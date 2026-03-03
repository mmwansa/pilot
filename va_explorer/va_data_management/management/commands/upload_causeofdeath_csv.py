import csv
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from va_explorer.va_data_management.models import CauseOfDeath, VerbalAutopsy


def _parse_datetime_or_none(value):
    raw = (value or "").strip()
    if not raw:
        return None

    dt = parse_datetime(raw)
    if dt is None:
        if raw.endswith("Z"):
            dt = parse_datetime(raw.replace("Z", "+00:00"))
    if dt is None:
        return None

    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


class Command(BaseCommand):
    help = (
        "Upload cause, algorithm, settings, created, updated, and verbalautopsy_id "
        "to va_data_management_causeofdeath from CSV."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_path",
            type=str,
            help="Input CSV file path (absolute or relative).",
        )
        parser.add_argument(
            "--clear-existing",
            action="store_true",
            help="Delete all existing CauseOfDeath rows before upload.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        _ = args
        csv_path = Path(options["csv_path"]).expanduser()
        if not csv_path.is_absolute():
            csv_path = Path.cwd() / csv_path
        if not csv_path.exists():
            raise CommandError(f"CSV file not found: {csv_path}")
        if not csv_path.is_file():
            raise CommandError(f"CSV path is not a file: {csv_path}")

        if options["clear_existing"]:
            deleted, _ = CauseOfDeath.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f"Deleted {deleted} existing CauseOfDeath rows.")
            )

        valid_va_ids = set(VerbalAutopsy.objects.values_list("id", flat=True))
        created_count = 0
        skipped_count = 0
        timestamp_updates = 0

        with csv_path.open("r", newline="", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            headers = set(reader.fieldnames or [])

            # Accept both correct and requested misspelled header.
            algorithm_column = "algorithm" if "algorithm" in headers else "algrorithm"
            required = {"cause", "settings", "created", "updated", "verbalautopsy_id"}
            if algorithm_column == "algorithm":
                required.add("algorithm")
            else:
                required.add("algrorithm")

            if not required.issubset(headers):
                raise CommandError(f"CSV must contain columns: {', '.join(sorted(required))}")

            for row in reader:
                cause = (row.get("cause") or "").strip()
                algorithm = (row.get(algorithm_column) or "").strip()
                settings_raw = (row.get("settings") or "").strip()
                verbalautopsy_id_raw = (row.get("verbalautopsy_id") or "").strip()

                if not cause or not verbalautopsy_id_raw.isdigit():
                    skipped_count += 1
                    continue

                verbalautopsy_id = int(verbalautopsy_id_raw)
                if verbalautopsy_id not in valid_va_ids:
                    skipped_count += 1
                    continue

                try:
                    settings = json.loads(settings_raw) if settings_raw else {}
                except json.JSONDecodeError:
                    skipped_count += 1
                    continue

                created_dt = _parse_datetime_or_none(row.get("created"))
                updated_dt = _parse_datetime_or_none(row.get("updated"))

                cod = CauseOfDeath.objects.create(
                    cause=cause,
                    algorithm=algorithm,
                    settings=settings,
                    verbalautopsy_id=verbalautopsy_id,
                )
                created_count += 1

                if created_dt is not None or updated_dt is not None:
                    CauseOfDeath.objects.filter(pk=cod.pk).update(
                        created=created_dt or cod.created,
                        updated=updated_dt or cod.updated,
                    )
                    timestamp_updates += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Upload complete. "
                f"Created={created_count}, TimestampUpdated={timestamp_updates}, Skipped={skipped_count}"
            )
        )
