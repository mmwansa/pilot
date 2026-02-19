from django.db.models.signals import post_delete, post_save

from va_explorer.home.cache_utils import bump_home_dashboard_fastpath_version
from va_explorer.home.dashboard_metrics import invalidate_homepage_metrics_cache
from va_explorer.va_data_management.models import (
    Death,
    Household,
    HouseholdMember,
    Pregnancy,
    PregnancyOutcome,
    VerbalAutopsy,
)


def _invalidate_cache(**kwargs):
    invalidate_homepage_metrics_cache()
    bump_home_dashboard_fastpath_version()


def _connect_signals(model):
    post_save.connect(
        _invalidate_cache,
        sender=model,
        dispatch_uid=f"home_metrics_cache_post_save_{model.__name__}",
    )
    post_delete.connect(
        _invalidate_cache,
        sender=model,
        dispatch_uid=f"home_metrics_cache_post_delete_{model.__name__}",
    )


for model in (
    Household,
    HouseholdMember,
    Pregnancy,
    PregnancyOutcome,
    Death,
    VerbalAutopsy,
):
    _connect_signals(model)
