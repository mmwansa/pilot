from typing import Dict, Iterable, Optional, Set

from django.db.models import Q

MSO_GROUP_NAME = "Mortality Surveillance Officer"


def _collect_related_nodes(location) -> Iterable:
    """Yield the location, its descendants, and ancestors."""
    yield location
    for node in location.get_descendants():
        yield node
    for node in location.get_ancestors():
        yield node


def _allowed_location_names(user) -> Optional[Dict[str, Set[str]]]:
    if not getattr(user, "is_authenticated", False):
        return None

    if not user.groups.filter(name=MSO_GROUP_NAME).exists():
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
    Limit queryset rows to the geographic locations assigned to a mortality
    surveillance officer. If the user is not an MSO or has no location
    assignments, the queryset is returned unchanged.
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

    combined_q = Q()
    for loc_type, field_name in mapping.items():
        names = allowed.get(loc_type)
        if not names:
            continue
        field_q = Q()
        for name in names:
            field_q |= Q(**{f"{field_name}__iexact": name})
        combined_q |= field_q

    if not combined_q:
        return queryset

    return queryset.filter(combined_q)
