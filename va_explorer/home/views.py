from collections import defaultdict
from datetime import date, datetime, timedelta

from django.http import JsonResponse
from django.views.generic import TemplateView, View

from va_explorer.home.dashboard_metrics import get_homepage_metrics
from va_explorer.home.va_trends import get_trends_data
from va_explorer.utils.mixins import CustomAuthMixin
from va_explorer.va_analytics.utils.loading import load_va_data
from va_explorer.va_data_management.models import (
    CSADailyTracker,
    Pregnancy,
    PregnancyOutcome,
)
from va_explorer.va_data_management.utils.date_parsing import parse_date
from va_explorer.va_data_management.utils.loading import get_va_summary_stats
from va_explorer.vacms.cmsmodels.events import Event


class Index(CustomAuthMixin, TemplateView):
    template_name = "home/index.html"

    def get_context_data(self, **kwargs):
        # TODO: interviewers should only see their own data
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context.update(get_va_summary_stats(user.verbal_autopsies()))
        context.update(get_homepage_metrics())

        context["locations"] = "All Regions"
        if user.location_restrictions.count() > 0:
            context["locations"] = ", ".join(
                [location.name for location in user.location_restrictions.all()]
            )

        return context


class Trends(CustomAuthMixin, View):
    def get(self, request, *args, **kwargs):
        (
            va_table,
            graphs,
            issue_list,
            indeterminate_cod_list,
            additional_issues,
            additional_indeterminate_cods,
        ) = get_trends_data(request.user)

        return JsonResponse(
            {
                "vaTable": va_table,
                "graphs": graphs,
                "issueList": issue_list,
                "indeterminateCodList": indeterminate_cod_list,
                "additionalIssues": additional_issues,
                "additionalIndeterminateCods": additional_indeterminate_cods,
                "isFieldWorker": request.user.is_fieldworker(),
            }
        )


trends_endpoint_view = Trends.as_view()


class About(CustomAuthMixin, TemplateView):
    template_name = "home/about.html"


class RegionalOperationsComponentContextMixin:
    geography_options = (
        {"value": "national", "label": "National"},
        {"value": "lusaka", "label": "Lusaka"},
        {"value": "southern", "label": "Southern"},
    )
    time_presets = (
        {"id": "timeAll", "label": "All time"},
        {"id": "time30", "label": "Last 30 days"},
        {"id": "time7", "label": "Last 7 days"},
        {"id": "time24", "label": "Last 24 hours"},
    )
    mso_source_options = (
        {"value": "community", "label": "Community"},
        {"value": "facility", "label": "Facility"},
    )
    csa_column_map = (
        ("name", "CSA Name (Search)"),
        ("visits", "Visits"),
        ("events", "Events"),
        ("deaths", "Deaths"),
        ("pregnancies", "Pregnancies"),
        ("pregnancy_outcomes", "Pregnancy Outcomes"),
        (
            "overdue_without_interview",
            "Pregnancies ≥ 6 mo. Past Due Date Without Interview",
        ),
    )
    mso_column_map = (
        ("name", "MSO Name (Search)"),
        ("death_events", "Death Events"),
        ("va_scheduled", "VAs Scheduled"),
        ("va_not_complete", "VA Scheduled but Not Complete"),
        ("mean_event_to_scheduled", "Mean Days (Event→Scheduled)"),
        ("mean_scheduled_to_complete", "Mean Days (Scheduled→Complete)"),
        ("va_total", "VA"),
        ("valid_cod", "Valid COD"),
        ("indeterminate", "Indeterminate"),
        ("error", "Error"),
        ("duration_outliers", "≤15 or ≥90m"),
    )

    @staticmethod
    def _pick(value, valid_values, default):
        return value if value in valid_values else default

    @staticmethod
    def _to_int(value):
        try:
            return int(str(value).strip() or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _coerce_date(value):
        if isinstance(value, date):
            return value
        parsed = parse_date(str(value or ""))
        if not parsed or parsed == "dk":
            return None
        return datetime.strptime(parsed, "%Y-%m-%d").date()

    @staticmethod
    def _safe_days(start_date, end_date):
        if not start_date or not end_date:
            return None
        return (end_date - start_date).days

    @staticmethod
    def _mean(values):
        if not values:
            return 0
        return round(sum(values) / len(values), 1)

    @staticmethod
    def _staff_name(user_obj, fallback=""):
        if user_obj is None:
            return fallback or "Unassigned MSO"
        return (
            user_obj.name
            or user_obj.get_full_name()
            or user_obj.email
            or fallback
            or "Unassigned MSO"
        )

    def _resolved_date_range(self, selected_time_preset):
        start_value = self.request.GET.get("start_date", "")
        end_value = self.request.GET.get("end_date", "")
        start_date = self._coerce_date(start_value)
        end_date = self._coerce_date(end_value)

        if start_date and end_date:
            return start_date, end_date, start_date.isoformat(), end_date.isoformat()

        today = datetime.today().date()
        if selected_time_preset == "time30":
            start_date = today - timedelta(days=30)
            end_date = today
        elif selected_time_preset == "time7":
            start_date = today - timedelta(days=7)
            end_date = today
        elif selected_time_preset == "time24":
            start_date = today - timedelta(days=1)
            end_date = today
        else:
            start_date = None
            end_date = None

        return (
            start_date,
            end_date,
            start_date.isoformat() if start_date else "",
            end_date.isoformat() if end_date else "",
        )

    @staticmethod
    def _sort_rows(rows, sort_key, sort_dir):
        reverse = sort_dir == "desc"
        if sort_key == "name":
            return sorted(rows, key=lambda r: str(r.get("name", "")).lower(), reverse=reverse)
        return sorted(rows, key=lambda r: r.get(sort_key, 0), reverse=reverse)

    @staticmethod
    def _paginate_rows(rows, page, per_page=5):
        total = len(rows)
        total_pages = max(1, (total + per_page - 1) // per_page)
        current_page = min(max(1, page), total_pages)
        start = (current_page - 1) * per_page
        end = start + per_page
        return {
            "rows": rows[start:end],
            "page": current_page,
            "total_pages": total_pages,
            "has_prev": current_page > 1,
            "has_next": current_page < total_pages,
            "prev_page": current_page - 1 if current_page > 1 else 1,
            "next_page": current_page + 1 if current_page < total_pages else total_pages,
            "visible_count": len(rows[start:end]),
            "total_count": total,
        }

    def _build_csa_rows(self, selected_geography, start_date, end_date):
        counts_by_csa = defaultdict(
            lambda: {
                "name": "",
                "visits": 0,
                "events": 0,
                "deaths": 0,
                "pregnancies": 0,
                "pregnancy_outcomes": 0,
                "overdue_without_interview": 0,
            }
        )
        region_label = (
            selected_geography.capitalize()
            if selected_geography and selected_geography != "national"
            else ""
        )

        tracker_rows = CSADailyTracker.objects.values(
            "enumerator",
            "province",
            "today",
            "num_death",
            "num_preg",
            "num_outcome",
        )

        for row in tracker_rows:
            if region_label and str(row.get("province") or "").lower() != region_label.lower():
                continue

            tracker_date = self._coerce_date(row.get("today"))
            if start_date and end_date and (not tracker_date or tracker_date < start_date or tracker_date > end_date):
                continue

            name = (row.get("enumerator") or "").strip() or "Unassigned CSA"
            entry = counts_by_csa[name]
            entry["name"] = name
            entry["visits"] += 1
            deaths = self._to_int(row.get("num_death"))
            pregnancies = self._to_int(row.get("num_preg"))
            outcomes = self._to_int(row.get("num_outcome"))
            entry["deaths"] += deaths
            entry["pregnancies"] += pregnancies
            entry["pregnancy_outcomes"] += outcomes
            entry["events"] += deaths + pregnancies + outcomes

        overdue_cutoff = datetime.today().date() - timedelta(days=180)
        outcome_pregnancy_ids = set(
            PregnancyOutcome.objects.exclude(pregnancy_id__isnull=True)
            .exclude(pregnancy_id__exact="")
            .values_list("pregnancy_id", flat=True)
        )

        for row in Pregnancy.objects.values("key", "enumerator", "province", "PE_10A"):
            if region_label and str(row.get("province") or "").lower() != region_label.lower():
                continue

            due_date = self._coerce_date(row.get("PE_10A"))
            if not due_date or due_date > overdue_cutoff:
                continue

            key = row.get("key")
            if key and key in outcome_pregnancy_ids:
                continue

            name = (row.get("enumerator") or "").strip() or "Unassigned CSA"
            entry = counts_by_csa[name]
            entry["name"] = name
            entry["overdue_without_interview"] += 1

        return list(counts_by_csa.values())

    def _build_mso_rows(
        self,
        selected_geography,
        selected_mso_source,
        start_date,
        end_date,
    ):
        stats_by_mso = defaultdict(
            lambda: {
                "name": "",
                "death_events": 0,
                "va_scheduled": 0,
                "va_not_complete": 0,
                "mean_event_to_scheduled": 0,
                "mean_scheduled_to_complete": 0,
                "va_total": 0,
                "valid_cod": 0,
                "indeterminate": 0,
                "error": 0,
                "duration_outliers": 0,
                "_event_to_sched_days": [],
                "_sched_to_complete_days": [],
            }
        )

        region_label = (
            selected_geography.capitalize()
            if selected_geography and selected_geography != "national"
            else ""
        )
        events = Event.objects.select_related("va_interview_staff", "death", "va").prefetch_related(
            "va__causes",
            "va__coding_issues",
        )

        if selected_mso_source == "community":
            events = events.exclude(household__isnull=True)
        elif selected_mso_source == "facility":
            events = events.filter(household__isnull=True)

        for event in events:
            if region_label and str(event.province or "").lower() != region_label.lower():
                continue

            event_date = event.interview_scheduled_date or event.interview_complete_date
            if start_date and end_date and (
                not event_date or event_date < start_date or event_date > end_date
            ):
                continue

            name = self._staff_name(event.va_interview_staff, fallback=event.supervisor or "")
            entry = stats_by_mso[name]
            entry["name"] = name

            if event.death_id:
                entry["death_events"] += 1

            if event.interview_scheduled_date:
                entry["va_scheduled"] += 1

            if event.interview_scheduled_date and not event.interview_complete_date:
                entry["va_not_complete"] += 1

            event_reference_date = self._coerce_date(getattr(event.death, "DE_06", None))
            event_to_sched_days = self._safe_days(
                event_reference_date,
                event.interview_scheduled_date,
            )
            if event_to_sched_days is not None:
                entry["_event_to_sched_days"].append(event_to_sched_days)

            sched_to_complete_days = self._safe_days(
                event.interview_scheduled_date,
                event.interview_complete_date,
            )
            if sched_to_complete_days is not None:
                entry["_sched_to_complete_days"].append(sched_to_complete_days)
                if sched_to_complete_days <= 15 or sched_to_complete_days >= 90:
                    entry["duration_outliers"] += 1

            va = event.va
            if not va:
                continue

            entry["va_total"] += 1

            causes = [cause.cause for cause in va.causes.all()]
            issues = list(va.coding_issues.all())
            if any(cause and cause != "Indeterminate" for cause in causes):
                entry["valid_cod"] += 1
            if any(cause == "Indeterminate" for cause in causes):
                entry["indeterminate"] += 1
            if any(issue.severity == "error" for issue in issues):
                entry["error"] += 1

        rows = []
        for row in stats_by_mso.values():
            row["mean_event_to_scheduled"] = self._mean(row.pop("_event_to_sched_days"))
            row["mean_scheduled_to_complete"] = self._mean(
                row.pop("_sched_to_complete_days")
            )
            rows.append(row)
        return rows

    def get_regional_operations_context(self):
        selected_geography = self._pick(
            self.request.GET.get("geography", ""),
            {item["value"] for item in self.geography_options} | {""},
            "",
        )
        selected_time_preset = self._pick(
            self.request.GET.get("time_preset", "timeAll"),
            {item["id"] for item in self.time_presets},
            "timeAll",
        )
        selected_mso_source = self._pick(
            self.request.GET.get("source", "community"),
            {item["value"] for item in self.mso_source_options},
            "community",
        )
        csa_sort = self._pick(
            self.request.GET.get("csa_sort", "visits"),
            {key for key, _ in self.csa_column_map},
            "visits",
        )
        csa_dir = self._pick(self.request.GET.get("csa_dir", "desc"), {"asc", "desc"}, "desc")
        mso_sort = self._pick(
            self.request.GET.get("mso_sort", "death_events"),
            {key for key, _ in self.mso_column_map},
            "death_events",
        )
        mso_dir = self._pick(self.request.GET.get("mso_dir", "desc"), {"asc", "desc"}, "desc")
        csa_page = max(1, self._to_int(self.request.GET.get("csa_page", "1")))
        mso_page = max(1, self._to_int(self.request.GET.get("mso_page", "1")))
        start_date, end_date, selected_start_date, selected_end_date = self._resolved_date_range(
            selected_time_preset
        )
        csa_rows_sorted = self._sort_rows(
            self._build_csa_rows(selected_geography, start_date, end_date),
            csa_sort,
            csa_dir,
        )
        mso_rows_sorted = self._sort_rows(
            self._build_mso_rows(
                selected_geography, selected_mso_source, start_date, end_date
            ),
            mso_sort,
            mso_dir,
        )
        csa_pagination = self._paginate_rows(csa_rows_sorted, csa_page)
        mso_pagination = self._paginate_rows(mso_rows_sorted, mso_page)

        return {
            "geography_options": self.geography_options,
            "selected_geography": selected_geography,
            "time_presets": self.time_presets,
            "selected_time_preset": selected_time_preset,
            "selected_start_date": selected_start_date,
            "selected_end_date": selected_end_date,
            "mso_source_options": self.mso_source_options,
            "selected_mso_source": selected_mso_source,
            "csa_rows": csa_pagination["rows"],
            "csa_sort": csa_sort,
            "csa_dir": csa_dir,
            "csa_page": csa_pagination["page"],
            "csa_total_pages": csa_pagination["total_pages"],
            "csa_has_prev": csa_pagination["has_prev"],
            "csa_has_next": csa_pagination["has_next"],
            "csa_prev_page": csa_pagination["prev_page"],
            "csa_next_page": csa_pagination["next_page"],
            "csa_visible_count": csa_pagination["visible_count"],
            "csa_total_count": csa_pagination["total_count"],
            "mso_rows": mso_pagination["rows"],
            "mso_sort": mso_sort,
            "mso_dir": mso_dir,
            "mso_page": mso_pagination["page"],
            "mso_total_pages": mso_pagination["total_pages"],
            "mso_has_prev": mso_pagination["has_prev"],
            "mso_has_next": mso_pagination["has_next"],
            "mso_prev_page": mso_pagination["prev_page"],
            "mso_next_page": mso_pagination["next_page"],
            "mso_visible_count": mso_pagination["visible_count"],
            "mso_total_count": mso_pagination["total_count"],
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_regional_operations_context())
        return context


class RegionalOperations(
    RegionalOperationsComponentContextMixin, CustomAuthMixin, TemplateView
):
    template_name = "home/regional_operations.html"


class RegionalOperationsMapData(CustomAuthMixin, View):
    def get(self, request, *args, **kwargs):
        start_date = request.GET.get("start_date") or "1901-01-01"
        end_date = request.GET.get("end_date") or datetime.today().strftime("%Y-%m-%d")

        data = load_va_data(
            request.user,
            start_date=start_date,
            end_date=end_date,
            cause_of_death=None,
            region_of_interest=None,
            age=None,
            sex=None,
        )

        return JsonResponse(
            {
                "geographic_province_sums": list(
                    data.get("geographic_province_sums", [])
                ),
                "geographic_district_sums": list(
                    data.get("geographic_district_sums", [])
                ),
            }
        )


class RegionalOperationsFiltersComponent(
    RegionalOperationsComponentContextMixin, CustomAuthMixin, TemplateView
):
    template_name = "home/components/_regional_operations_filters.html"


class RegionalOperationsCsaComponent(
    RegionalOperationsComponentContextMixin, CustomAuthMixin, TemplateView
):
    template_name = "home/components/_regional_operations_csa_table.html"


class RegionalOperationsMsoComponent(
    RegionalOperationsComponentContextMixin, CustomAuthMixin, TemplateView
):
    template_name = "home/components/_regional_operations_mso_table.html"
