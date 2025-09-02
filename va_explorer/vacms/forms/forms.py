from django import forms
from va_explorer.users.models import User
from bootstrap_datepicker_plus.widgets import DatePickerInput

class ScheduleDeathForm(forms.Form):
    id = forms.CharField(
        label="Death ID",
        required=True,
        widget=forms.TextInput(attrs={"readonly": "readonly"}),
    )
    name = forms.CharField(
        label="DE-03 Name of the deceased",
        required=True,
        widget=forms.TextInput(attrs={"readonly": "readonly"}),
    )
    dob = forms.CharField(
        label="DE-04 Date of Birth of the deceased",
        required=True,
        widget=forms.TextInput(attrs={"readonly": "readonly"}),
    )
    sex = forms.CharField(
        label="E-05 Sex of the deceased",
        required=True,
        widget=forms.TextInput(attrs={"readonly": "readonly"}),
    )
    dod = forms.CharField(
        label="DE-06 Date of death of the deceased",
        required=True,
        widget=forms.TextInput(attrs={"readonly": "readonly"}),
    )
    interview_scheduled_date = forms.DateField(
        label="VA Interview Scheduled Date",
        required=True,
        widget=DatePickerInput()
    )
    va_interview_staff = forms.ModelChoiceField(
        label="VA Interview Staff", queryset=User.objects.filter(groups__name='Mortality Surveillance Officer'), required=True
    )
    interview_contact_name = forms.CharField(
        max_length=255, label="VA Interview Contact Name", required=False
    )
    interview_contact_tel = forms.CharField(
        max_length=255, label="VA Interview Contact Phone", required=False
    )
    interview_comments = forms.CharField(
        max_length=255, label="VA Interview Comments", required=False
    )

    #
    def clean_id(self):
        id = self.cleaned_data["id"]
        if not id:
            raise forms.ValidationError("Please choose a date to schedule a VA for")
