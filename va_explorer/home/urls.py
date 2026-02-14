from django.urls import path

from . import views
from .views import trends_endpoint_view

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
]
