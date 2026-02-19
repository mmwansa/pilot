import csv
import itertools
import os
from operator import itemgetter
from pathlib import Path

from django.db.models import (
    Case,
    CharField,
    Count,
    DateField,
    F,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Cast, Substr, TruncMonth

from va_explorer.va_data_management.models import (
    Location,
    SRSClusterLocation,
    questions_to_autodetect_duplicates,
)
from va_explorer.va_data_management.utils.loading import get_va_summary_stats


def load_cod_groupings(cause_of_death: str):
    INTERVA_GROUPCODE = os.environ.get("INTERVA_GROUPCODE") == "True"
    if INTERVA_GROUPCODE:
        filename = "cod_groupings_interva_groupcode_true.csv"
    else:
        filename = "cod_groupings_interva_groupcode_false.csv"
    path = Path(__file__).parent.parent / "data" / filename

    with open(path) as csvfile:
        filereader = csv.DictReader(csvfile)
        remove = ["algorithm", "cod"]
        headers = [header for header in filereader.fieldnames if header not in remove]

        data = []
        for row in filereader:
            data.append(row)

        cods = sorted([row.get("cod") for row in data] + headers)

    filter_causes = []
    if cause_of_death:
        for row in data:
            if row.get("cod") == cause_of_death:
                filter_causes.append(row.get("cod"))
                break

            for key, value in row.items():
                if cause_of_death == key and value == "1":
                    filter_causes.append(row.get("cod"))

    return {"dropdown_options": cods, "filter_causes": filter_causes}


def _compact_spaces(value):
    return " ".join(str(value or "").strip().split())


def _strip_geo_suffix(value, level):
    text = _compact_spaces(value)
    if not text:
        return ""

    suffixes = {
        "Province": ("province",),
        "District": ("district",),
        "Constituency": ("constituency",),
        "Ward": ("ward",),
        "EA": ("ea", "enumeration area"),
    }.get(level, ())

    lowered = text.lower()
    for suffix in suffixes:
        token = f" {suffix}"
        if lowered.endswith(token):
            return _compact_spaces(text[: -len(token)])
    return text


def _region_name_variants(name, level):
    base = _strip_geo_suffix(name, level)
    if not base:
        return set()

    variants = {base}
    if level == "Province":
        variants.add(f"{base} Province")
    elif level == "District":
        variants.add(f"{base} District")
    elif level == "Constituency":
        variants.add(f"{base} Constituency")
    elif level == "Ward":
        variants.add(f"{base} Ward")
    elif level == "EA":
        variants.add(f"{base} EA")
        variants.add(f"{base} Enumeration Area")
    return {_compact_spaces(v) for v in variants if _compact_spaces(v)}


def _parse_region_of_interest(region_of_interest):
    text = _compact_spaces(region_of_interest)
    if not text:
        return "", None

    lowered = text.lower()
    if lowered in {"zambia", "zambia country", "country zambia"}:
        return "Zambia", "Zambia"

    for level in ("EA", "Ward", "Constituency", "District", "Province"):
        token = f" {level.lower()}"
        if lowered.endswith(token):
            return text[: -len(token)].strip(), level
    return text, None


def _serialize_geo_counts(counts, key_name):
    return [{key_name: name, "count": count} for name, count in sorted(counts.items())]


def _build_srs_code_maps():
    level_map = {
        "Province": "province",
        "District": "district",
        "Constituency": "constituency",
        "Ward": "ward",
        "EA": "ea",
    }
    maps = {level: {} for level in level_map}
    qs = SRSClusterLocation.objects.filter(location_type__isnull=False).values(
        "location_type", "code", "name"
    )
    for row in qs.iterator():
        loc_type = (row.get("location_type") or "").strip().lower()
        level = next((lvl for lvl, typ in level_map.items() if typ == loc_type), None)
        if not level:
            continue
        code = _compact_spaces(row.get("code"))
        name = _compact_spaces(row.get("name"))
        if code and name:
            maps[level][code.lower()] = name
    return maps


def _resolve_geo_name(value, level, code_maps):
    text = _strip_geo_suffix(value, level)
    if not text:
        return ""
    mapped = code_maps.get(level, {}).get(text.lower())
    return _strip_geo_suffix(mapped or text, level)


# ============ VA Data =================
def load_va_data(
    user, cause_of_death, start_date, end_date, region_of_interest, age, sex
):
    user_vas = user.verbal_autopsies(date_cutoff=start_date, end_date=end_date)

    # get stats on last update and last va interview date
    update_stats = get_va_summary_stats(user_vas)
    if len(questions_to_autodetect_duplicates()) > 0:
        update_stats["duplicates"] = user_vas.filter(duplicate=True).count()

    user_vas_filtered = user_vas.exclude(Id10023__in=["dk", "DK"]).annotate(
        province_name_from_location=Subquery(
            Location.objects.values("name").filter(
                Q(path=Substr(OuterRef("location__path"), 1, 8)), Q(depth=2)
            )[:1]
        ),
        district_name_from_location=Subquery(
            Location.objects.values("name").filter(
                Q(path=Substr(OuterRef("location__path"), 1, 12)),
                Q(depth=3),
            )[:1]
        ),
    )

    # apply cause of death filtering if sent in with request
    if cause_of_death:
        causes = load_cod_groupings(cause_of_death=cause_of_death)["filter_causes"]
        user_vas_filtered = user_vas_filtered.filter(causes__cause__in=causes)

    # apply geographic filtering if sent in with request
    if region_of_interest:
        region_name, region_level = _parse_region_of_interest(region_of_interest)
        if region_level and region_level != "Zambia":
            variants = _region_name_variants(region_name, region_level)
            query = Q()
            if region_level == "Province":
                for name in variants:
                    query |= Q(province__iexact=name) | Q(
                        province_name_from_location__iexact=name
                    )
            elif region_level == "District":
                for name in variants:
                    query |= Q(district__iexact=name) | Q(
                        district_name_from_location__iexact=name
                    ) | Q(area__iexact=name)
            elif region_level == "Constituency":
                for name in variants:
                    query |= Q(constituency__iexact=name)
            elif region_level == "Ward":
                for name in variants:
                    query |= Q(ward__iexact=name) | Q(area__iexact=name)
            elif region_level == "EA":
                for name in variants:
                    query |= (
                        Q(ea__iexact=name)
                        | Q(cluster__name__iexact=name)
                        | Q(cluster__code__iexact=name)
                    )
            if query:
                user_vas_filtered = user_vas_filtered.filter(query)

    # apply filtering for age sent in request, cover is<X>, is<X>1, and is<X>2
    # from VA specification
    if age:
        if age == "adult":
            user_vas_filtered = user_vas_filtered.filter(
                Q(isAdult="1")
                | Q(isAdult="1.0")
                | Q(isAdult1="1")
                | Q(isAdult1="1.0")
                | Q(isAdult2="1")
                | Q(isAdult2="1.0")
            )
        if age == "child":
            user_vas_filtered = user_vas_filtered.filter(
                Q(isChild="1")
                | Q(isChild="1.0")
                | Q(isChild1="1")
                | Q(isChild1="1.0")
                | Q(isChild2="1")
                | Q(isChild2="1.0")
            )
        if age == "neonate":
            user_vas_filtered = user_vas_filtered.filter(
                Q(isNeonatal="1")
                | Q(isNeonatal="1")
                | Q(isNeonatal1="1")
                | Q(isNeonatal1="1")
                | Q(isNeonatal2="1")
                | Q(isNeonatal2="1")
            )

    # apply filtering for sex sent in request
    if sex:
        user_vas_filtered = user_vas_filtered.filter(Id10019=sex)

    uncoded_vas = user_vas.filter(causes__cause__isnull=True).count()

    demographics = (
        user_vas_filtered.filter(causes__isnull=False)
        .values(
            gender=F("Id10019"),
            age_group_named=Case(
                When(isNeonatal="1", then=Value("neonate")),
                When(isNeonatal="1.0", then=Value("neonate")),
                When(isNeonatal1="1", then=Value("neonate")),
                When(isNeonatal1="1.0", then=Value("neonate")),
                When(isNeonatal2="1", then=Value("neonate")),
                When(isNeonatal2="1.0", then=Value("neonate")),
                When(isChild="1", then=Value("child")),
                When(isChild="1.0", then=Value("child")),
                When(isChild1="1", then=Value("child")),
                When(isChild1="1.0", then=Value("child")),
                When(isChild2="1", then=Value("child")),
                When(isChild2="1.0", then=Value("child")),
                When(isAdult="1", then=Value("adult")),
                When(isAdult="1.0", then=Value("adult")),
                When(isAdult1="1", then=Value("adult")),
                When(isAdult1="1.0", then=Value("adult")),
                When(isAdult2="1", then=Value("adult")),
                When(isAdult2="1.0", then=Value("adult")),
                default=Value("Unknown"),
                output_field=CharField(),
            ),
        )
        .annotate(count=Count("pk"))
        .order_by("age_group_named")
    )

    demographics = [
        {
            "age_group": key,
            **{item.get("gender"): item.get("count") for item in list(group)},
        }
        for key, group in itertools.groupby(demographics, itemgetter("age_group_named"))
    ]

    COD_sums = (
        user_vas_filtered.filter(causes__isnull=False)
        .select_related("causes")
        .values(cause=F("causes__cause"))
        .annotate(count=Count("pk"))
        .order_by("-count")
    )

    COD_trend = (
        user_vas_filtered.annotate(
            month=TruncMonth(Cast("Id10023", output_field=DateField()))
        )
        .filter(causes__isnull=False)
        .values("month")
        .annotate(count=Count("pk"))
        .order_by("month")
    )

    place_of_death = (
        user_vas_filtered.filter(causes__isnull=False)
        .values(place=F("Id10058"))
        .annotate(count=Count("pk"))
        .order_by("-count")
    )

    geographic_province_sums = (
        user_vas_filtered.filter(causes__isnull=False)
        .select_related("location")
        .values(province_name=F("province_name_from_location"))
        .annotate(count=Count("pk"))
    )

    geographic_district_sums = (
        user_vas_filtered.filter(causes__isnull=False)
        .select_related("location")
        .values(district_name=F("district_name_from_location"))
        .annotate(count=Count("pk"))
    )

    map_geo_rows = user_vas_filtered.values(
        "province",
        "district",
        "constituency",
        "ward",
        "ea",
        "area",
        "cluster__name",
        "cluster__code",
        "province_name_from_location",
        "district_name_from_location",
    )
    map_counts = {
        "Province": {},
        "District": {},
        "Constituency": {},
        "Ward": {},
        "EA": {},
    }
    geo_code_maps = _build_srs_code_maps()
    total_map_vas = 0
    for row in map_geo_rows.iterator():
        total_map_vas += 1

        province = _resolve_geo_name(
            row.get("province"), "Province", geo_code_maps
        ) or _resolve_geo_name(
            row.get("province_name_from_location"), "Province", geo_code_maps
        )
        district = _resolve_geo_name(
            row.get("district"), "District", geo_code_maps
        ) or _resolve_geo_name(
            row.get("district_name_from_location"), "District", geo_code_maps
        ) or _resolve_geo_name(
            row.get("area"), "District", geo_code_maps
        )
        constituency = _resolve_geo_name(
            row.get("constituency"), "Constituency", geo_code_maps
        )
        ward = _resolve_geo_name(
            row.get("ward") or row.get("area"), "Ward", geo_code_maps
        )
        ea = _resolve_geo_name(
            row.get("ea") or row.get("cluster__name") or row.get("cluster__code"),
            "EA",
            geo_code_maps,
        )

        if province:
            map_counts["Province"][province] = map_counts["Province"].get(province, 0) + 1
        if district:
            map_counts["District"][district] = map_counts["District"].get(district, 0) + 1
        if constituency:
            map_counts["Constituency"][constituency] = (
                map_counts["Constituency"].get(constituency, 0) + 1
            )
        if ward:
            map_counts["Ward"][ward] = map_counts["Ward"].get(ward, 0) + 1
        if ea:
            map_counts["EA"][ea] = map_counts["EA"].get(ea, 0) + 1

    data = {
        "COD_grouping": COD_sums,
        "COD_trend": COD_trend,
        "place_of_death": place_of_death,
        "demographics": demographics,
        "geographic_province_sums": geographic_province_sums,
        "geographic_district_sums": geographic_district_sums,
        "uncoded_vas": uncoded_vas,
        "update_stats": update_stats,
        "all_causes_list": load_cod_groupings(cause_of_death=cause_of_death)[
            "dropdown_options"
        ],
        "map_province_sums": _serialize_geo_counts(map_counts["Province"], "province_name"),
        "map_district_sums": _serialize_geo_counts(map_counts["District"], "district_name"),
        "map_constituency_sums": _serialize_geo_counts(
            map_counts["Constituency"], "constituency_name"
        ),
        "map_ward_sums": _serialize_geo_counts(map_counts["Ward"], "ward_name"),
        "map_ea_sums": _serialize_geo_counts(map_counts["EA"], "ea_name"),
        # Kept for frontend compatibility; now represents all filtered VAs for map display.
        "map_total_coded_vas": total_map_vas,
        "map_total_vas": total_map_vas,
    }

    return data
