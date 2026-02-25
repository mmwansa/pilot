from typing import Dict, Iterable, Optional, Set

from django.db.models import Q


def _collect_related_nodes(location) -> Iterable:
    """Yield the location, its descendants, and ancestors."""
    yield location
    for node in location.get_descendants():
        yield node
    for node in location.get_ancestors():
        yield node


def _allowed_location_names(user) -> Optional[Dict[str, Set[str]]]:
    if not user or not getattr(user, "is_authenticated", False):
        return None

    locations = getattr(user, "location_restrictions", None)
    if not locations:
        return None

    locations = locations.all()
    if not locations.exists():
        return None

    allowed: Dict[str, Set[str]] = {
        "province": set(),
        "district": set(),
        "constituency": set(),
        "ward": set(),
        "ea": set(),
    }

    for location in locations:
        for node in _collect_related_nodes(location):
            loc_type = (getattr(node, "location_type", "") or "").lower()
            name = getattr(node, "name", "")
            if loc_type in allowed and name:
                allowed[loc_type].add(name.strip())

    if not any(allowed.values()):
        return None

    return allowed


def restrict_queryset_to_user_locations(queryset, user, field_mapping=None):
    """
    Limit queryset rows to the geographic locations assigned to a user with
    location restrictions. If the user has no location assignments, the queryset
    is returned unchanged.
    """

    allowed = _allowed_location_names(user)
    if not allowed:
        return queryset

    default_mapping = {
        "province": "province",
        "district": "district",
        "constituency": "constituency",
        "ward": "ward",
        "ea": "ea",
    }
    mapping = field_mapping or default_mapping
    locations_qs = user.location_restrictions.all()
    has_non_province_assignments = locations_qs.exclude(
        location_type__iexact="province"
    ).exists()

    # Anchor by province when available to avoid cross-province leakage when
    # lower-level names overlap between provinces.
    combined_q = Q()
    has_any_filter = False
    province_field = mapping.get("province")
    province_names = allowed.get("province") or set()
    if province_field and province_names:
        province_q = Q()
        for name in province_names:
            province_q |= Q(**{f"{province_field}__iexact": name})
        combined_q &= province_q
        has_any_filter = True

    lower_level_q = Q()
    for loc_type, field_name in mapping.items():
        if loc_type == "province":
            continue
        names = allowed.get(loc_type)
        if not names:
            continue
        field_q = Q()
        for name in names:
            field_q |= Q(**{f"{field_name}__iexact": name})
        lower_level_q |= field_q

    if lower_level_q.children:
        has_any_filter = True
        if province_names and has_non_province_assignments:
            combined_q &= lower_level_q
        elif not province_names:
            combined_q = lower_level_q

    if not has_any_filter:
        return queryset

    return queryset.filter(combined_q)


def restrict_va_queryset_to_user_locations(queryset, user):
    """
    VerbalAutopsy-specific restriction that supports both:
    - facility VA access via Location tree relation (location FK), and
    - community VA access via persisted admin text fields.
    """
    allowed = _allowed_location_names(user)
    if not allowed:
        return queryset

    locations = getattr(user, "location_restrictions", None)
    if not locations:
        return queryset

    locations_qs = locations.all()
    if not locations_qs.exists():
        return queryset

    # Facility path scoping using location tree nodes.
    location_nodes = set()
    for location in locations_qs:
        for node in _collect_related_nodes(location):
            location_nodes.add(node.pk)
    facility_q = Q(location__in=location_nodes)

    # Community/admin path scoping using text geography fields.
    text_q = Q()
    for loc_type, names in allowed.items():
        if not names:
            continue
        field_q = Q()
        for name in names:
            field_q |= Q(**{f"{loc_type}__iexact": name})
        text_q |= field_q

    combined_q = facility_q
    if text_q.children:
        combined_q |= text_q

    return queryset.filter(combined_q).distinct()
