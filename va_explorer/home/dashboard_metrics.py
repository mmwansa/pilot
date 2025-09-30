from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Iterable, Optional, Sequence

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from va_explorer.va_data_management.models import (
    Death,
    Household,
    HouseholdMember,
    Pregnancy,
    PregnancyOutcome,
    VerbalAutopsy,
)


def _fix_tz_offset(s: str) -> str:
    """
    Normalize timezone suffixes like +0000 -> +00:00 so Django can parse them.
    """
    if len(s) >= 5 and (s[-5] in "+-") and s[-4:].isdigit():
        return s[:-5] + s[-5:-2] + ":" + s[-2:]
    return s


def _parse_submission_timestamp(value: object) -> Optional[datetime]:
    """Return a timezone-aware ``datetime`` for heterogeneous timestamp inputs."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, time.min)
    else:
        if value is None:
            return None
        raw = str(value).strip()
        if not raw:
            return None

        # Common normalizations from ODK/Kobo/CSV exports
        normalised = raw.replace("Z", "+00:00")
        normalised = _fix_tz_offset(normalised)

        candidates = [normalised]
        # Also try a space instead of T
        if "T" in normalised:
            candidates.append(_fix_tz_offset(normalised.replace("T", " ")))
        # If there are fractional seconds, try a variant without them (keep TZ)
        if "." in normalised:
            prefix, _, suffix = normalised.partition(".")
            if suffix:
                tz_sep = "+" if "+" in suffix else ("-" if "-" in suffix else "")
                if tz_sep:
                    tz_index = suffix.find(tz_sep)
                    candidates.append(prefix + _fix_tz_offset(suffix[tz_index:]))
                else:
                    candidates.append(prefix)

        dt = None
        for candidate in candidates:
            dt = parse_datetime(candidate)
            if dt:
                break

        if dt is None:
            parsed_date = parse_date(normalised)
            if parsed_date is not None:
                dt = datetime.combine(parsed_date, time.min)

        if dt is None:
            return None

    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _first_valid_timestamp(obj: object, fields: Sequence[str]) -> Optional[datetime]:
    for field in fields:
        value = getattr(obj, field, None)
        timestamp = _parse_submission_timestamp(value)
        if timestamp is not None:
            return timestamp
    return None


def _normalise_queryset(qs, key_field: str):
    return qs.exclude(**{f"{key_field}__isnull": True}).exclude(**{key_field: ""})


def _count_recent_records(
    qs, *, key_field: Optional[str], date_fields: Iterable[str]
) -> tuple[int, int]:
    """
    Return (total, count_in_last_24h) for a queryset.

    If key_field is provided, we will distinct on non-empty values of that field.
    Otherwise we use the queryset as-is (assumed already deduplicated).
    """
    if key_field:
        filtered = _normalise_queryset(qs, key_field)
        total = filtered.values_list(key_field, flat=True).distinct().count()
    else:
        filtered = qs
        total = filtered.count()

    since = timezone.now() - timedelta(days=1)
    recent_keys: set = set()
    only_fields = list(date_fields)
    if key_field:
        only_fields.append(key_field)

    for record in filtered.only(*only_fields):
        timestamp = _first_valid_timestamp(record, date_fields)
        if timestamp and timestamp >= since:
            identifier = getattr(record, key_field) if key_field else record.pk
            recent_keys.add(identifier)

    return total, len(recent_keys)


def _safe_int(value: object) -> int:
    if value in (None, ""):
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    text = str(value).strip().replace(",", "")
    if not text:
        return 0
    try:
        return int(float(text))
    except (TypeError, ValueError):
        digits = "".join(ch for ch in text if (ch.isdigit() or ch == "-"))
        try:
            return int(digits)
        except (TypeError, ValueError):
            return 0


def get_homepage_metrics() -> dict[str, int]:
    # -------------------------
    # Households / clusters
    # -------------------------
    households = _normalise_queryset(Household.objects.all(), "key")

    # Total Number of EAs ever visited: count distinct, non-empty Household.ea values
    total_eas = (
        households.exclude(ea__isnull=True)
        .exclude(ea="")
        .values_list("ea", flat=True)
        .distinct()
        .count()
    )

    # Total Number of people counted: count rows in HouseholdMember (counting IDs)
    total_people = HouseholdMember.objects.count()

    # -------------------------
    # Pregnancies (use submissiondate/start/today)
    # -------------------------
    total_pregnancies, today_pregnancies = _count_recent_records(
        Pregnancy.objects.all(),
        key_field="key",
        date_fields=("submissiondate", "start", "today"),
    )

    # -------------------------
    # Pregnancy Outcomes (use submissiondate/start/today)
    # -------------------------
    total_preg_outcomes, today_preg_outcomes = _count_recent_records(
        PregnancyOutcome.objects.all(),
        key_field="key",
        date_fields=("submissiondate", "start", "today"),
    )

    # -------------------------
    # Deaths (use submissiondate/start/today)
    # -------------------------
    total_deaths, today_deaths = _count_recent_records(
        Death.objects.all(),
        key_field="key",
        date_fields=("submissiondate", "start", "today"),
    )

    # -------------------------
    # Verbal Autopsies (canonical, non-deleted; use submissiondate/Id10012/created)
    # -------------------------
    vas_canonical = VerbalAutopsy.objects.filter(deleted_at__isnull=True, duplicate=False)
    total_vas, today_vas = _count_recent_records(
        vas_canonical,
        key_field="instanceid",
        date_fields=("submissiondate", "Id10012", "created"),
    )

    return {
        "total_eas": total_eas,
        "total_people": total_people,
        "total_pregnancies": total_pregnancies,
        "today_pregnancies": today_pregnancies,
        "total_preg_outcomes": total_preg_outcomes,
        "today_preg_outcomes": today_preg_outcomes,
        "total_deaths": total_deaths,
        "today_deaths": today_deaths,
        "total_vas": total_vas,
        "today_vas": today_vas,
    }
