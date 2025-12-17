import json
from django.contrib import messages
from django.shortcuts import redirect, render
from django.http import HttpResponse, HttpResponseForbidden
from django.urls import reverse
from django.utils import timezone
from django import forms
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)  # new

# Create your views here.
from va_explorer.vacms.cmsmodels.events import Event
from va_explorer.vacms.forms.forms import ScheduleDeathForm, VAInterviewStatusForm
from va_explorer.va_data_management.models import Death
from va_explorer.users.models import UserMessage


# event
class EventListView(ListView):
    model = Event
    template_name = "va_cms/event_list.html"


class EventListScheduledView(ListView):
    model = Event
    template_name = "va_cms/event_scheduled_list.html"

    def get_queryset(self):
        queryset = super().get_queryset()  # Start with the default queryset
        queryset = queryset.filter(event_status=1)

        return queryset


class EventListCompletedView(ListView):
    model = Event
    template_name = "va_cms/event_completed_list.html"

    def get_queryset(self):
        queryset = super().get_queryset()  # Start with the default queryset
        queryset = queryset.filter(event_status=5)

        return queryset


class EventCreateView(CreateView):
    model = Event
    fields = [
        "event_type",
        "event_status",
        "data_collection_staff",
        "data_collect_proposed_date",
        "data_collect_contact_name",
        "data_collect_contact_tel",
        "data_collect_comments",
    ]
    template_name = "va_cms/event_create.html"


def EventCreateDeathView(request, death):

    if request.method == "POST":

        form = ScheduleDeathForm(request.POST)

        if form.is_valid():
            # Process the valid data from form.cleaned_data
            minterview_scheduled_date = form.cleaned_data["interview_scheduled_date"]
            mva_interview_staff = form.cleaned_data["va_interview_staff"]
            minterview_contact_name = form.cleaned_data["interview_contact_name"]
            minterview_contact_tel = form.cleaned_data["interview_contact_tel"]
            minterview_comments = form.cleaned_data["interview_comments"]
            # ...
            context = {
                "message": f"d={minterview_scheduled_date},s={mva_interview_staff.id},n={minterview_contact_name},t={minterview_contact_tel},c={minterview_comments}",
            }

            deathDetail = Death.objects.get(id=death)

            newEvent = Event.objects.create(
                death=deathDetail,
                event_type=3,
                event_status=4,
                interview_scheduled_date=minterview_scheduled_date,
                va_interview_staff=mva_interview_staff,
                interview_contact_name=minterview_contact_name,
                interview_contact_tel=minterview_contact_tel,
                interview_comments=minterview_comments,
            )

            newEvent.save()

            scheduled_date = (
                minterview_scheduled_date.strftime("%Y-%m-%d")
                if hasattr(minterview_scheduled_date, "strftime")
                else str(minterview_scheduled_date)
            )
            event_detail_url = request.build_absolute_uri(
                reverse("cms-event-detail", kwargs={"pk": newEvent.pk})
            )
            deceased_name = deathDetail.DE_03 or f"Death {deathDetail.pk}"

            UserMessage.objects.create(
                user=mva_interview_staff,
                subject="New VA scheduled",
                body=(
                    "A new verbal autopsy for "
                    f"{deceased_name} has been scheduled on {scheduled_date}.\n"
                    f"View the details: {event_detail_url}"
                ),
                metadata={
                    "event_id": newEvent.pk,
                    "death_id": deathDetail.pk,
                    "scheduled_date": scheduled_date,
                },
            )

            deathDetail.eventid = newEvent.id
            deathDetail.save()

            return redirect(reverse("cms-event-list"))

            """
              return HttpResponse(
                json.dumps(context), status=200, content_type="application/json"
            )
            
            """
            # return render(request, "va_cms/event_death_create.html", context)
        else:
            # Form is invalid, re-render with errors
            return render(request, "va_cms/event_death_create.html", {"form": form})
    else:

        initials = {"id": death}

        try:
            deathDetail = Death.objects.get(id=death)
            initials = {
                "id": death,
                "name": deathDetail.DE_03,
                "dob": deathDetail.DE_04,
                "sex": deathDetail.DE_05,
                "dod": deathDetail.DE_06,
                # Prepopulate contact name and phone from DE_28 and DE_29
                "interview_contact_name": deathDetail.DE_28 or "",
                "interview_contact_tel": deathDetail.DE_29 or "",
            }
        except Death.DoesNotExist:
            initials = {}

        return render(
            request,
            "va_cms/event_death_create.html",
            {"form": ScheduleDeathForm(initial=initials)},
        )


class EventUpdateView(UpdateView):
    model = Event
    fields = [
        "event_type",
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
        "form_version",
    ]
    template_name = "va_cms/event_update.html"


class EventDetailView(DetailView):
    model = Event
    fields = "__all__"
    template_name = "va_cms/event_detail.html"

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self._can_update_status(self.object):
            return HttpResponseForbidden("You are not allowed to update this event.")

        form = VAInterviewStatusForm(request.POST, instance=self.object)
        if form.is_valid():
            form.save()
            messages.success(request, "VA interview status updated.")
            return redirect("cms-event-detail", pk=self.object.pk)

        context = self.get_context_data(status_form=form)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event = self.object
        death_record = event.death
        context["death_record"] = death_record
        context["is_death_event"] = (
            bool(death_record) and event.event_type == Event.EventType.DEATH
        )
        interviewer = event.va_interview_staff
        context["interviewer"] = interviewer
        if interviewer:
            context["interviewer_name"] = (
                interviewer.name or interviewer.get_full_name() or interviewer.email
            )
            context["interviewer_contact"] = (
                interviewer.mobile1 or interviewer.mobile2 or interviewer.email
            )
        else:
            context["interviewer_name"] = None
            context["interviewer_contact"] = None
        context["status_form"] = kwargs.get(
            "status_form", VAInterviewStatusForm(instance=event)
        )
        context["can_update_va_status"] = self._can_update_status(event)
        return context

    def _can_update_status(self, event):
        user = self.request.user
        return bool(
            user.is_authenticated
            and event.va_interview_staff_id
            and user.id == event.va_interview_staff_id
        )


class EventScheduleDataCollectionView(UpdateView):
    model = Event
    fields = [
        "event_type",
        "event_status",
        "household",
        "data_collection_staff",
        "data_collect_proposed_date",
        "data_collect_scheduled_date",
        "data_collect_contact_name",
        "data_collect_contact_tel",
        "data_collect_comments",
    ]
    template_name = "va_cms/event_schedule_data.html"

    def form_valid(self, form):
        form.instance.event_status = 1

        # Call the parent's form_valid to save the object and handle redirection
        response = super().form_valid(form)

        return response


class EventScheduleVAInterviewView(UpdateView):
    model = Event
    fields = [
        "household",
        "interview_scheduled_date",
        "va_interview_staff",
        "interview_contact_name",
        "interview_contact_tel",
        "interview_comments",
    ]
    template_name = "va_cms/event_schedule_va.html"

    def form_valid(self, form):
        form.instance.event_status = 4
        form.instance.va_interview_status = Event.VAInterviewStatus.SCHEDULED
        form.instance.va_not_done_reason = None
        form.instance.va_not_done_other = None

        # Call the parent's form_valid to save the object and handle redirection
        response = super().form_valid(form)

        return response


class EventLinkNone(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            "data_collect_complete_date",
            "data_collect_contact_name",
            "data_collect_contact_tel",
            "data_collect_comments",
        ]


class EventLinkDeath(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            "data_collect_complete_date",
            "data_collect_contact_name",
            "data_collect_contact_tel",
            "data_collect_comments",
            "death",
        ]


class EventLinkPregnancy(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            "data_collect_complete_date",
            "data_collect_contact_name",
            "data_collect_contact_tel",
            "data_collect_comments",
            "pregnancy",
        ]


class EventLinkPregnancyOutcome(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            "data_collect_complete_date",
            "data_collect_contact_name",
            "data_collect_contact_tel",
            "data_collect_comments",
            "pregnancy_outcome",
        ]


class EventLinkDataView(UpdateView):
    model = Event
    template_name = "va_cms/event_link.html"

    def form_valid(self, form):
        form.instance.event_status = 2

        # close event if its not a death
        if self.object.event_type != 3:
            form.instance.completion_date = timezone.now().strftime("%Y-%m-%d")

        # Call the parent's form_valid to save the object and handle redirection
        response = super().form_valid(form)

        return response

    def get_form_class(self):
        obj = self.get_object()  # Get the instance being updated

        if obj.event_type == 1:
            return EventLinkPregnancy

        elif obj.event_type == 2:
            return EventLinkPregnancyOutcome

        elif obj.event_type == 3:
            return EventLinkDeath
        else:
            return EventLinkNone


class EventLinkVA(UpdateView):
    model = Event
    fields = [
        "interview_complete_date",
        "va",
        "interview_comments",
    ]

    template_name = "va_cms/event_complete.html"

    def form_valid(self, form):
        form.instance.event_status = 5
        form.instance.va_interview_status = Event.VAInterviewStatus.COMPLETED
        form.instance.va_not_done_reason = None
        form.instance.va_not_done_other = None
        form.instance.completion_date = timezone.now().strftime("%Y-%m-%d")
        # Call the parent's form_valid to save the object and handle redirection
        response = super().form_valid(form)

        return response
