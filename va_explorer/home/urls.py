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
    path("about/", view=views.About.as_view(), name="about"),
    path("trends/", trends_endpoint_view, name="charts"),
]
