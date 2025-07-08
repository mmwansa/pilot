from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, UpdateView, DeleteView, TemplateView
from django.views.generic.detail import SingleObjectMixin
from django.shortcuts import redirect

from va_explorer.utils.mixins import CustomAuthMixin
from va_explorer.va_data_management.models import Household
from va_explorer.va_data_management.forms import HouseholdForm
from va_explorer.va_data_management.filters import HouseholdFilter


class HouseholdAccessMixin(SingleObjectMixin):
    def get_queryset(self):
        return Household.objects.all()


class Households(CustomAuthMixin, PermissionRequiredMixin, ListView):
    permission_required = "va_data_management.view_household"
    model = Household
    template_name = "va_data_management/households.html"
    paginate_by = 15

    def get_queryset(self):
        # Set up filter with GET params
        self.filter = HouseholdFilter(self.request.GET, queryset=Household.objects.all().order_by("-uuid"))
        return self.filter.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter'] = self.filter
        return context


class HouseholdDetail(CustomAuthMixin, PermissionRequiredMixin, HouseholdAccessMixin, DetailView):
    permission_required = "va_data_management.view_household"
    model = Household
    pk_url_kwarg = "id"
    template_name = "va_data_management/household_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["id"] = self.object.id

        history = self.object.history.all().reverse()
        context["history"] = history
        return context


class HouseholdEdit(CustomAuthMixin, PermissionRequiredMixin, HouseholdAccessMixin, SuccessMessageMixin, UpdateView):
    permission_required = "va_data_management.change_household"
    model = Household
    form_class = HouseholdForm
    template_name = "va_data_management/household_edit.html"
    pk_url_kwarg = "id"
    success_message = "Household successfully updated."

    def get_success_url(self):
        return reverse("va_data_management:household_detail", kwargs={"id": self.object.id})


class HouseholdDelete(CustomAuthMixin, PermissionRequiredMixin, DeleteView):
    permission_required = "va_data_management.delete_household"
    model = Household
    success_url = reverse_lazy("va_data_management:households")
    template_name = "va_data_management/household_confirm_delete.html"
    success_message = "Household %(id)s was deleted successfully."

    def form_valid(self, form):
        messages.success(self.request, self.success_message % self.get_object().__dict__)
        return super().form_valid(form)


class HouseholdDeleteAll(CustomAuthMixin, PermissionRequiredMixin, TemplateView):
    permission_required = "va_data_management.bulk_delete"
    template_name = "va_data_management/household_confirm_delete_all.html"
    success_message = "All households successfully deleted."

    def post(self, request, *args, **kwargs):
        Household.objects.all().delete()
        messages.success(request, self.success_message)
        return redirect(reverse("va_data_management:households"))
