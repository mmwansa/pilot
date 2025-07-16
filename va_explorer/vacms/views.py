from django.shortcuts import render
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)  # new

# Create your views here.
from va_explorer.vacms.cmsmodels.events import Event
from va_explorer.vacms.cmsmodels.cms import  Staff

# staff
class StaffListView(ListView):
    model = Staff
    template_name = "va_cms\staff_list.html"


class StaffCreateView(CreateView):
    model = Staff
    fields = "__all__"
    template_name = "va_cms\staff_create.html"


class StaffUpdateView(UpdateView):
    model = Staff
    fields = "__all__"
    template_name = "va_cms\staff_update.html"

class StaffDetailView(DetailView):
    model = Staff
    fields = "__all__"
    template_name = "va_cms\staff_detail.html"
    
# event
class EventListView(ListView):
    model = Event
    template_name = "va_cms\event_list.html"
    
class EventListScheduledView(ListView):
    model = Event
    template_name = "va_cms\event_scheduled_list.html"
    
    def get_queryset(self):
        queryset = super().get_queryset()  # Start with the default queryset
        queryset = queryset.filter(event_status=1)

        return queryset
    
class EventListCompletedView(ListView):
    model = Event
    template_name = "va_cms\event_completed_list.html"
    
    def get_queryset(self):
        queryset = super().get_queryset()  # Start with the default queryset
        queryset = queryset.filter(event_status=2)

        return queryset
    

class EventCreateView(CreateView):
    model = Event
    fields = [
        "event_type",
        "event_status",
        "interview_proposed_date",
        "respondent_name",
        "respondent_phone",
        "comment",
        "deviceid",
        "instanceid",
        "today",
        "start",
        "province",
        "district",
        "constituency",
        "ward",
        "ea",
        "supervisor",
        "enumerator",
        "form_version"
    ]
    template_name = "va_cms\event_create.html"
    
class EventUpdateView(UpdateView):
    model = Event
    fields = [
        "event_type",
        "interview_proposed_date",
        "respondent_name",
        "respondent_phone",
        "comment",
        "deviceid",
        "instanceid",
        "today",
        "start",
        "province",
        "district",
        "constituency",
        "ward",
        "ea",
        "supervisor",
        "enumerator",
        "form_version"
    ]
    template_name = "va_cms\event_update.html"

class EventDetailView(DetailView):
    model = Event
    fields = "__all__"
    template_name = "va_cms\event_detail.html"
    
class EventScheduleView(UpdateView):
    model = Event
    fields = [
        "household",
        "interview_scheduled_date",
        "interview_staff",
        "respondent_name",
        "respondent_phone",
        "comment",
    ]
    template_name = "va_cms\event_schedule.html"

    def form_valid(self, form):
        form.instance.event_status = 1

        # Call the parent's form_valid to save the object and handle redirection
        response = super().form_valid(form)

        return response


class EventCompleteView(UpdateView):
    model = Event
    fields = [
        "completion_date",
        "death",
        "pregnancy",
        "pregnancy_outcome",
        "comment",
    ]
    
    template_name = "va_cms\event_complete.html"
    
    def form_valid(self, form):
        form.instance.event_status = 2

        # Call the parent's form_valid to save the object and handle redirection
        response = super().form_valid(form)

        return response




