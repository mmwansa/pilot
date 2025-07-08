from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, UpdateView, DeleteView, TemplateView
from django.views.generic.detail import SingleObjectMixin
from django.shortcuts import redirect

from va_explorer.utils.mixins import CustomAuthMixin
from va_explorer.va_data_management.models import Death
from va_explorer.va_data_management.forms import DeathForm
from va_explorer.va_data_management.filters import DeathFilter


class DeathAccessMixin(SingleObjectMixin):
    def get_queryset(self):
        return Death.objects.all()


class Deaths(CustomAuthMixin, PermissionRequiredMixin, ListView):
    permission_required = "va_data_management.view_death"
    model = Death
    template_name = "va_data_management/deaths.html"
    paginate_by = 15

    def get_queryset(self):
        self.filter = DeathFilter(self.request.GET, queryset=Death.objects.all().order_by("-uuid"))
        return self.filter.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter'] = self.filter
        return context


class DeathDetail(CustomAuthMixin, PermissionRequiredMixin, DeathAccessMixin, DetailView):
    permission_required = "va_data_management.view_death"
    model = Death
    pk_url_kwarg = "id"
    template_name = "va_data_management/death_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["id"] = self.object.id
        context["form"] = DeathForm(None, instance=self.object)
        history = self.object.history.all().reverse()
        context["history"] = history
        return context


class DeathEdit(CustomAuthMixin, PermissionRequiredMixin, DeathAccessMixin, SuccessMessageMixin, UpdateView):
    permission_required = "va_data_management.change_death"
    model = Death
    form_class = DeathForm
    template_name = "va_data_management/death_edit.html"
    pk_url_kwarg = "id"
    success_message = "Death record successfully updated."

    def get_success_url(self):
        return reverse("va_data_management:death_detail", kwargs={"id": self.object.id})


class DeathDelete(CustomAuthMixin, PermissionRequiredMixin, DeleteView):
    permission_required = "va_data_management.delete_death"
    model = Death
    success_url = reverse_lazy("va_data_management:deaths")
    template_name = "va_data_management/death_confirm_delete.html"
    success_message = "Death record %(id)s was deleted successfully."

    def form_valid(self, form):
        messages.success(self.request, self.success_message % self.get_object().__dict__)
        return super().form_valid(form)


class DeathDeleteAll(CustomAuthMixin, PermissionRequiredMixin, TemplateView):
    permission_required = "va_data_management.bulk_delete"
    template_name = "va_data_management/death_confirm_delete_all.html"
    success_message = "All death records successfully deleted."

    def post(self, request, *args, **kwargs):
        Death.objects.all().delete()
        messages.success(request, self.success_message)
        return redirect(reverse("va_data_management:deaths"))
