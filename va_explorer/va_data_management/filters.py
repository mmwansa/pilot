from django import forms
from django.core.exceptions import ValidationError
from django.forms import Select, TextInput
from django_filters import BooleanFilter, CharFilter, DateFilter, FilterSet
from fuzzywuzzy import fuzz
from .models import VerbalAutopsy, Pregnancy, Household,  PregnancyOutcome, Death


TRUE_FALSE_CHOICES = (
    (False, "No"),
    (True, "Yes"),
)


def validate_integer(value):
    if not value.isdigit():
        raise ValidationError(
            ("%(value)s is invalid or negative. Please enter only numbers"),
            params={"value": value},
        )


class DateInput(forms.DateInput):
    input_type = "date"


class VAFilter(FilterSet):
    id = CharFilter(
        field_name="id",
        label="ID",
        validators=[validate_integer],
        widget=TextInput(attrs={"class": "form-text"}),
    )
    interviewer = CharFilter(
        field_name="Id10010",
        lookup_expr="icontains",
        label="Interviewer",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    deceased = CharFilter(
        method="filter_deceased",
        label="Deceased",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    start_date = DateFilter(
        field_name="Id10023",
        lookup_expr="gte",
        label="Earliest Date",
        widget=DateInput(attrs={"class": "form-date datepicker"}),
    )
    end_date = DateFilter(
        field_name="Id10023",
        lookup_expr="lte",
        label="Latest Date",
        widget=DateInput(attrs={"class": "form-date datepicker"}),
    )
    location = CharFilter(
        field_name="location__name",
        lookup_expr="icontains",
        label="Facility",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    cause = CharFilter(
        field_name="causes__cause",
        lookup_expr="icontains",
        label="Cause",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    only_errors = BooleanFilter(
        method="filter_errors",
        label="Only Errors",
        widget=Select(choices=TRUE_FALSE_CHOICES, attrs={"class": "custom-select"}),
    )

    class Meta:
        model = VerbalAutopsy
        fields = []

    def filter_deceased(self, queryset, name, value):
        if value:
            threshold = 75
            vas = queryset.values("id", "Id10017", "Id10018")
            matches = [
                va.get("id")
                for va in vas
                if fuzz.token_set_ratio(
                    value, " ".join([va.get("Id10017"), va.get("Id10018")])
                )
                > threshold
            ]
            return queryset.filter(id__in=matches)
        return queryset

    def filter_errors(self, queryset, name, value):
        if value:
            return queryset.filter(coding_issues__severity="error")
        return queryset


class PregnancyFilter(FilterSet):
    province = CharFilter(
        field_name="province",
        lookup_expr="icontains",
        label="Province",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    district = CharFilter(
        field_name="district",
        lookup_expr="icontains",
        label="District",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    ward = CharFilter(
        field_name="ward",
        lookup_expr="icontains",
        label="Ward",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    enumerator = CharFilter(
        field_name="enumerator",
        lookup_expr="icontains",
        label="Enumerator",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    start_date = DateFilter(
        field_name="created",
        lookup_expr="gte",
        label="Earliest Record Date",
        widget=DateInput(attrs={"class": "form-date datepicker"}),
    )
    end_date = DateFilter(
        field_name="created",
        lookup_expr="lte",
        label="Latest Record Date",
        widget=DateInput(attrs={"class": "form-date datepicker"}),
    )

    class Meta:
        model = Pregnancy
        fields = []

    def filter_respondent(self, queryset, name, value):
        """Fuzzy search by respondent name (PE_02)."""
        if value:
            threshold = 75
            qs = queryset.values("id", "PE_02")
            matches = [
                row.get("id")
                for row in qs
                if row.get("PE_02") and fuzz.token_set_ratio(value, row.get("PE_02")) > threshold
            ]
            return queryset.filter(id__in=matches)
        return queryset


class HouseholdFilter(FilterSet):
    # Simple text and icontains filters
    province = CharFilter(
        field_name="province",
        lookup_expr="icontains",
        label="Province",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    district = CharFilter(
        field_name="district",
        lookup_expr="icontains",
        label="District",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    ward = CharFilter(
        field_name="ward",
        lookup_expr="icontains",
        label="Ward",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    enumerator = CharFilter(
        field_name="enumerator",
        lookup_expr="icontains",
        label="Enumerator",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    supervisor = CharFilter(
        field_name="supervisor",
        lookup_expr="icontains",
        label="Supervisor",
        widget=TextInput(attrs={"class": "form-text"}),
    )

    respondent = CharFilter(
        method="filter_respondent_fuzzy",
        label="Respondent",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    hhn = CharFilter(
        field_name="hhn",
        lookup_expr="icontains",
        label="Household Number (HHN)",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    hun = CharFilter(
        field_name="hun",
        lookup_expr="icontains",
        label="Housing Unit Number (HUN)",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    only_errors = BooleanFilter(
        method="filter_errors",
        label="Only Errors",
        widget=Select(choices=TRUE_FALSE_CHOICES, attrs={"class": "custom-select"}),
    )

    class Meta:
        model = Household
        fields = []  # Explicit field list if you want to limit, otherwise empty

    def filter_respondent_fuzzy(self, queryset, name, value):
        if value:
            threshold = 75
            households = queryset.values("member_id", "respondent", "first_name", "last_name")
            matches = [
                h["member_id"]
                for h in households
                if fuzz.token_set_ratio(
                    value,
                    " ".join([str(h.get("respondent") or ""), str(h.get("first_name") or ""), str(h.get("last_name") or "")])
                ) > threshold
            ]
            return queryset.filter(member_id__in=matches)
        return queryset


class PregnancyOutcomeFilter(FilterSet):
    province = CharFilter(
        field_name="province",
        lookup_expr="icontains",
        label="Province",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    district = CharFilter(
        field_name="district",
        lookup_expr="icontains",
        label="District",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    ward = CharFilter(
        field_name="ward",
        lookup_expr="icontains",
        label="Ward",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    enumerator = CharFilter(
        field_name="enumerator",
        lookup_expr="icontains",
        label="Enumerator",
        widget=TextInput(attrs={"class": "form-text"}),
    )        
    outcome_type = CharFilter(
        field_name="po_group",
        lookup_expr="icontains",
        label="Pregnancy Outcome",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    start_date = DateFilter(
        field_name="PO_41",
        lookup_expr="gte",
        label="Earliest Date of Delivery",
        widget=DateInput(attrs={"class": "form-date datepicker"}),
    )
    end_date = DateFilter(
        field_name="PO_41",
        lookup_expr="lte",
        label="Latest Date of Delivery",
        widget=DateInput(attrs={"class": "form-date datepicker"}),
    )

    class Meta:
        model = PregnancyOutcome
        fields = []

    def filter_respondent_fuzzy(self, queryset, name, value):
        """Fuzzy match on respondent's name and related fields."""
        if value:
            threshold = 75
            outcomes = queryset.values("id", "PO_01", "PO_04", "PO_23")
            matches = [
                outcome["id"]
                for outcome in outcomes
                if fuzz.token_set_ratio(
                    value,
                    " ".join([
                        str(outcome.get("PO_01") or ""),
                        str(outcome.get("PO_04") or ""),
                        str(outcome.get("PO_23") or ""),
                    ])
                ) > threshold
            ]
            return queryset.filter(id__in=matches)
        return queryset


class DeathFilter(FilterSet):
    province = CharFilter(
        field_name="province",
        lookup_expr="icontains",
        label="Province",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    district = CharFilter(
        field_name="district",
        lookup_expr="icontains",
        label="District",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    ward = CharFilter(
        field_name="ward",
        lookup_expr="icontains",
        label="Ward",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    enumerator = CharFilter(
        field_name="enumerator",
        lookup_expr="icontains",
        label="Enumerator",
        widget=TextInput(attrs={"class": "form-text"}),
    )
    start_date = DateFilter(
        field_name="DE_06",
        lookup_expr="gte",
        label="Earliest Date of Death",
        widget=DateInput(attrs={"class": "form-date datepicker"}),
    )
    end_date = DateFilter(
        field_name="DE_06",
        lookup_expr="lte",
        label="Latest Date of Death",
        widget=DateInput(attrs={"class": "form-date datepicker"}),
    )


    class Meta:
        model = Death
        fields = []

    def filter_respondent_fuzzy(self, queryset, name, value):
        if value:
            threshold = 75
            records = queryset.values("id", "respondent")
            matches = [
                record["id"]
                for record in records
                if fuzz.token_set_ratio(value, record.get("respondent") or "") > threshold
            ]
            return queryset.filter(id__in=matches)
        return queryset

    def filter_deceased_fuzzy(self, queryset, name, value):
        if value:
            threshold = 75
            records = queryset.values("id", "DE_03")
            matches = [
                record["id"]
                for record in records
                if fuzz.token_set_ratio(value, record.get("DE_03") or "") > threshold
            ]
            return queryset.filter(id__in=matches)
        return queryset
