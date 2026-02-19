from django.db import migrations


def _has_value(value):
    normalized = ("" if value is None else str(value)).strip().lower()
    return normalized not in {"", "nan", "none", "null"}


def _normalized_community_va(record):
    hospital = getattr(record, "hospital", None)
    ward = getattr(record, "ward", None)
    # Use area as fallback where ward is not available/meaningful.
    if not _has_value(ward):
        ward = getattr(record, "area", None)
    community_va = getattr(record, "community_va", None)

    if _has_value(hospital):
        return "no"
    if _has_value(ward):
        return "yes"

    normalized = ("" if community_va is None else str(community_va)).strip().lower()
    if normalized in {"no", "n", "false", "0"}:
        return "no"
    return "yes"


def _backfill_model(model):
    field_names = {f.name for f in model._meta.get_fields()}
    if "community_va" not in field_names:
        return

    select_fields = ["community_va"]
    if "hospital" in field_names:
        select_fields.append("hospital")
    if "ward" in field_names:
        select_fields.append("ward")
    if "area" in field_names:
        select_fields.append("area")

    to_update = []
    for record in model.objects.only(*select_fields).iterator(chunk_size=1000):
        normalized = _normalized_community_va(record)
        if (record.community_va or "") != normalized:
            record.community_va = normalized
            to_update.append(record)
            if len(to_update) >= 1000:
                model.objects.bulk_update(to_update, ["community_va"], batch_size=1000)
                to_update = []
    if to_update:
        model.objects.bulk_update(to_update, ["community_va"], batch_size=1000)


def forwards(apps, schema_editor):
    _ = schema_editor  # unused
    VerbalAutopsy = apps.get_model("va_data_management", "VerbalAutopsy")
    HistoricalVerbalAutopsy = apps.get_model(
        "va_data_management", "HistoricalVerbalAutopsy"
    )
    _backfill_model(VerbalAutopsy)
    _backfill_model(HistoricalVerbalAutopsy)


class Migration(migrations.Migration):
    dependencies = [
        (
            "va_data_management",
            "0021_historicalverbalautopsy_community_va_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
