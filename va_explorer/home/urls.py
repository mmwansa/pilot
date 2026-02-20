from django.urls import path

from . import views
from .views import national_operational_filter_data_view, trends_endpoint_view

app_name = "home"

urlpatterns = [
    path("", view=views.Index.as_view(), name="index"),
    path(
        "regional-operations/",
        view=views.RegionalOperations.as_view(),
        name="regional_operations",
    ),
    path(
        "regional-operations/map-data/",
        view=views.RegionalOperationsMapData.as_view(),
        name="regional_operations_map_data",
    ),
    path(
        "regional-operations/components/filters/",
        view=views.RegionalOperationsFiltersComponent.as_view(),
        name="regional_operations_filters_component",
    ),
    path(
        "regional-operations/components/csa/",
        view=views.RegionalOperationsCsaComponent.as_view(),
        name="regional_operations_csa_component",
    ),
    path(
        "regional-operations/components/mso/",
        view=views.RegionalOperationsMsoComponent.as_view(),
        name="regional_operations_mso_component",
    ),
    path("about/", view=views.About.as_view(), name="about"),
    path("trends/", trends_endpoint_view, name="charts"),
    path(
        "national-operational/filter-data/",
        national_operational_filter_data_view,
        name="national_operational_filter_data",
    ),
    path(
        "national-operational/map-data/",
        views.home_overview_map_data_view,
        name="home_overview_map_data",
    ),
    path(
        "components/overview/events/",
        views.home_overview_events_component_view,
        name="home_overview_events_component",
    ),
    path(
        "components/overview/kpis/",
        views.home_overview_kpis_component_view,
        name="home_overview_kpis_component",
    ),
    path(
        "components/trends/",
        views.home_trends_component_view,
        name="home_trends_component",
    ),
    path(
        "components/va-statistics/",
        views.home_va_statistics_component_view,
        name="home_va_statistics_component",
    ),
]
