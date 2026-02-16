import calendar
from collections import Counter
from datetime import date, datetime, time, timedelta

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from va_explorer.va_data_management.models import Death, Household, Pregnancy, PregnancyOutcome

WINDOW_COLUMNS = ("24", "1 week", "1 month", "Overall")


def _fix_tz_offset(text):
    if len(text) >= 5 and (text[-5] in "+-") and text[-4:].isdigit():
        return text[:-5] + text[-5:-2] + ":" + text[-2:]
    return text


def _parse_submission_datetime(raw_value):
    if isinstance(raw_value, datetime):
        dt = raw_value
    elif isinstance(raw_value, date):
        dt = datetime.combine(raw_value, time.min)
    else:
        raw = str(raw_value or "").strip()
        if not raw:
            return None

        normalized = _fix_tz_offset(raw.replace("Z", "+00:00"))
        candidates = [normalized]
        if "T" in normalized:
            candidates.append(_fix_tz_offset(normalized.replace("T", " ")))

        dt = None
        for candidate in candidates:
            dt = parse_datetime(candidate)
            if dt:
                break

        if dt is None:
            parsed_date = parse_date(normalized)
            if parsed_date is not None:
                dt = datetime.combine(parsed_date, time.min)

        if dt is None:
            return None

    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return timezone.localtime(dt)


def _sub_calendar_months(dt, months):
    year = dt.year
    month = dt.month - months
    while month <= 0:
        month += 12
        year -= 1

    # Clamp day for short months.
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _month_sequence_12(now_local):
    start = _sub_calendar_months(now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0), 11)
    months = []
    current = start
    for _ in range(12):
        months.append(current)
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    return months


def _empty_metric_trend(month_labels):
    return {
        "table": {"recorded": {label: 0 for label in WINDOW_COLUMNS}},
        "graphs": {"recorded": {"x": month_labels, "y": [0.0] * len(month_labels)}},
    }


def build_trend_for_queryset(queryset, key_field="key"):
    now_local = timezone.localtime(timezone.now())
    since_day = now_local - timedelta(days=1)
    since_week = now_local - timedelta(days=7)
    since_month = _sub_calendar_months(now_local, 1)

    months = _month_sequence_12(now_local)
    month_keys = [month.strftime("%Y-%m") for month in months]
    month_labels = [month.strftime("%b") for month in months]
    output = _empty_metric_trend(month_labels)

    rows = (
        queryset.exclude(**{f"{key_field}__isnull": True})
        .exclude(**{key_field: ""})
        .values(key_field, "submissiondate")
    )

    latest_by_key = {}
    for row in rows:
        row_key = row.get(key_field)
        timestamp = _parse_submission_datetime(row.get("submissiondate"))
        if not row_key or timestamp is None:
            continue
        existing = latest_by_key.get(row_key)
        if existing is None or timestamp > existing:
            latest_by_key[row_key] = timestamp

    if not latest_by_key:
        return output

    timestamps = list(latest_by_key.values())
    output["table"]["recorded"]["Overall"] = len(timestamps)
    output["table"]["recorded"]["24"] = sum(1 for ts in timestamps if ts >= since_day)
    output["table"]["recorded"]["1 week"] = sum(1 for ts in timestamps if ts >= since_week)
    output["table"]["recorded"]["1 month"] = sum(1 for ts in timestamps if ts >= since_month)

    month_counter = Counter(ts.strftime("%Y-%m") for ts in timestamps)
    output["graphs"]["recorded"]["y"] = [float(month_counter.get(key, 0)) for key in month_keys]
    return output


def get_model_trends_data():
    return {
        "households": build_trend_for_queryset(Household.objects.all()),
        "pregnancies": build_trend_for_queryset(Pregnancy.objects.all()),
        "pregnancy_outcomes": build_trend_for_queryset(PregnancyOutcome.objects.all()),
        "deaths": build_trend_for_queryset(Death.objects.all()),
    }
