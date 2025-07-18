# blog/urls.py
from django.urls import path
from va_explorer.vacms.views import (
    StaffListView,
    StaffCreateView,
    StaffDetailView,
    StaffUpdateView,
    EventListView,
    EventListScheduledView,
    EventListCompletedView,
    EventCreateView,
    EventCreateDeathView,
    EventUpdateView,
    EventScheduleDataCollectionView,
    EventScheduleVAInterviewView,
    EventDetailView,
    EventLinkDataView,
    EventLinkVA,
)

urlpatterns = [
    # staff
    path("staff/list", StaffListView.as_view(), name="cms-staff-list"),
    path("staff/create", StaffCreateView.as_view(), name="cms-staff-create"),
    path("staff/update/<int:pk>", StaffUpdateView.as_view(), name="cms-staff-update"),
    path("staff/detail/<int:pk>", StaffDetailView.as_view(), name="cms-staff-detail"),
    # event
    path("event/list", EventListView.as_view(), name="cms-event-list"),
    path(
        "event/scheduled/list",
        EventListScheduledView.as_view(),
        name="cms-event-scheduled-list",
    ),
    path(
        "event/complete/list",
        EventListCompletedView.as_view(),
        name="cms-event-completed-list",
    ),
    path("event/create", EventCreateView.as_view(), name="cms-event-create"),
    path("event/create-death/<int:death>", EventCreateDeathView, name="cms-event-death-create"),
    path("event/update/<int:pk>", EventUpdateView.as_view(), name="cms-event-update"),
    path(
        "event/schedule/data-collection/<int:pk>",
        EventScheduleDataCollectionView.as_view(),
        name="cms-event-datacollection-schedule",
    ),
    path(
        "event/schedule/va-interview/<int:pk>",
        EventScheduleVAInterviewView.as_view(),
        name="cms-event-vainterview-schedule",
    ),
    path(
        "event/link-data/<int:pk>",
        EventLinkDataView.as_view(),
        name="cms-event-link",
    ),
    path(
        "event/link-va/<int:pk>",
        EventLinkVA.as_view(),
        name="cms-event-linkva",
    ),
    path("event/detail/<int:pk>", EventDetailView.as_view(), name="cms-event-detail"),
]
