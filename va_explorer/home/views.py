from collections import defaultdict
from datetime import date, datetime, timedelta
import difflib
import re
from zoneinfo import ZoneInfo

from django.db.models import Count, OuterRef, Q, Subquery
from django.db.models.functions import Substr
from django.http import JsonResponse
from django.utils import timezone
from django.views.generic import TemplateView, View

from va_explorer.home.dashboard_metrics import get_homepage_metrics
from va_explorer.home.va_trends import get_trends_data
from va_explorer.utils.mixins import CustomAuthMixin
from va_explorer.va_data_management.models import (
    CSADailyTracker,
    Location,
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
        ("mean_death_to_va_complete", "Mean Days (Death→Complete)"),
        ("va_total", "VA"),
        ("valid_cod", "Valid COD"),
        ("indeterminate", "Indeterminate"),
        ("error", "Error"),
        ("duration_outliers", "≤15 or ≥90m"),
    )
    geo_filter_values = {"", "national", "lusaka", "southern"}
    geo_filter_map = {
        "lusaka": {
            "names": ("lusaka", "lusaka province"),
            "codes": ("5", "05"),
        },
        "southern": {
            "names": ("southern", "southern province"),
            "codes": ("9", "09"),
        },
    }
    preset_to_ui_id = {
        "all": "timeAll",
        "30": "time30",
        "7": "time7",
        "24": "time24",
    }
    ui_id_to_preset = {v: k for k, v in preset_to_ui_id.items()}

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

    @staticmethod
    def _format_csa_display_name(raw_name):
        name = (raw_name or "").strip().replace("_", " ")
        # Drop trailing numeric token after the last space.
        name = re.sub(r"\s+\d+$", "", name).strip()
        return name or "Unassigned CSA"

    @staticmethod
    def _normalize_name_search_text(value):
        text = (value or "").strip().replace("_", " ")
        text = re.sub(r"\s+\d+$", "", text).strip().lower()
        text = re.sub(r"\s+", " ", text)
        return text

    def _matches_name_search(self, name_value, raw_query):
        query = self._normalize_name_search_text(raw_query)
        if not query:
            return True

        name = self._normalize_name_search_text(name_value)
        if not name:
            return False

        if query in name:
            return True

        if all(token in name for token in query.split()):
            return True

        similarity = difflib.SequenceMatcher(None, query, name).ratio()
        if similarity >= 0.62:
            return True

        return any(
            difflib.SequenceMatcher(None, query, token).ratio() >= 0.8
            for token in name.split()
        )

    def _normalized_geo(self):
        geo = (self.request.GET.get("geo") or self.request.GET.get("geography") or "").strip().lower()
        return geo if geo in self.geo_filter_values else ""

    def _normalized_preset(self):
        preset_raw = (self.request.GET.get("time_preset") or "all").strip().lower()
        if preset_raw in self.ui_id_to_preset:
            return self.ui_id_to_preset[preset_raw]
        return preset_raw if preset_raw in {"all", "30", "7", "24"} else "all"

    def _resolve_time_window(self):
        selected_preset = self._normalized_preset()
        start_value = (self.request.GET.get("start_date") or "").strip()
        end_value = (self.request.GET.get("end_date") or "").strip()

        start_date = self._coerce_date(start_value)
        end_date = self._coerce_date(end_value)
        manual_valid = bool(start_date and end_date and end_date >= start_date)

        now_local = timezone.now().astimezone(ZoneInfo("Africa/Lusaka"))

        if manual_valid:
            start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=ZoneInfo("Africa/Lusaka"))
            end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=ZoneInfo("Africa/Lusaka"))
            time_label = f"{start_date.isoformat()} to {end_date.isoformat()}"
            return {
                "selected_preset": selected_preset,
                "selected_time_preset": self.preset_to_ui_id[selected_preset],
                "start_value": start_value,
                "end_value": end_value,
                "start_dt": start_dt,
                "end_dt": end_dt,
                "start_date_str": start_date.isoformat(),
                "end_date_str": end_date.isoformat(),
                "time_label": time_label,
            }

        if selected_preset == "30":
            start_dt = now_local - timedelta(days=30)
            end_dt = now_local
            time_label = "Last 30 days"
        elif selected_preset == "7":
            start_dt = now_local - timedelta(days=7)
            end_dt = now_local
            time_label = "Last 7 days"
        elif selected_preset == "24":
            start_dt = now_local - timedelta(hours=24)
            end_dt = now_local
            time_label = "Last 24 hours"
        else:
            start_dt = None
            end_dt = None
            time_label = "All time"

        return {
            "selected_preset": selected_preset,
            "selected_time_preset": self.preset_to_ui_id[selected_preset],
            "start_value": start_value,
            "end_value": end_value,
            "start_dt": start_dt,
            "end_dt": end_dt,
            "start_date_str": start_dt.date().isoformat() if start_dt else "",
            "end_date_str": end_dt.date().isoformat() if end_dt else "",
            "time_label": time_label,
        }

    @staticmethod
    def _province_filter_q(field_name, geo_value):
        if not geo_value or geo_value == "national":
            return Q()
        meta = RegionalOperationsComponentContextMixin.geo_filter_map.get(geo_value)
        if not meta:
            return Q()

        query = Q()
        for name in meta["names"]:
            query |= Q(**{f"{field_name}__iexact": name})
        for code in meta["codes"]:
            query |= Q(**{f"{field_name}__exact": code})
        return query

    def _allowed_province_names(self):
        restrictions = list(self.request.user.location_restrictions.all())
        if not restrictions:
            return None

        provinces = set()
        for location in restrictions:
            if getattr(location, "depth", None) == 2:
                provinces.add(location.name.strip().lower())

            for ancestor in location.get_ancestors():
                if getattr(ancestor, "depth", None) == 2:
                    provinces.add(ancestor.name.strip().lower())

            for name in location.get_descendants().filter(depth=2).values_list("name", flat=True):
                if name:
                    provinces.add(name.strip().lower())
        return provinces

    @staticmethod
    def _province_access_q(field_name, province_names):
        if province_names is None:
            return Q()

        query = Q()
        for province_name in province_names:
            query |= Q(**{f"{field_name}__iexact": province_name})
            # CSA/Event rows may omit "Province" suffix.
            if province_name.endswith(" province"):
                query |= Q(
                    **{
                        f"{field_name}__iexact": province_name.replace(
                            " province", ""
                        ).strip()
                    }
                )
        return query

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

    def _build_csa_rows(self, selected_geo, start_date_str, end_date_str, province_scope):
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
        tracker_rows = CSADailyTracker.objects.filter(
            self._province_access_q("province", province_scope)
        ).filter(self._province_filter_q("province", selected_geo))

        if start_date_str and end_date_str:
            tracker_rows = tracker_rows.filter(
                today__gte=start_date_str,
                today__lte=end_date_str,
            )

        tracker_rows = tracker_rows.values(
            "enumerator",
            "today",
            "num_death",
            "num_preg",
            "num_outcome",
        )

        for row in tracker_rows:
            name = self._format_csa_display_name(row.get("enumerator"))
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

        pregnancy_rows = Pregnancy.objects.filter(
            self._province_access_q("province", province_scope)
        ).filter(self._province_filter_q("province", selected_geo))
        pregnancy_rows = pregnancy_rows.filter(PE_10A__lte=overdue_cutoff.isoformat())
        if start_date_str and end_date_str:
            pregnancy_rows = pregnancy_rows.filter(
                PE_10A__gte=start_date_str,
                PE_10A__lte=end_date_str,
            )

        for row in pregnancy_rows.values("key", "enumerator", "PE_10A"):
            due_date = self._coerce_date(row.get("PE_10A"))
            if not due_date or due_date > overdue_cutoff:
                continue

            key = row.get("key")
            if key and key in outcome_pregnancy_ids:
                continue

            name = self._format_csa_display_name(row.get("enumerator"))
            entry = counts_by_csa[name]
            entry["name"] = name
            entry["overdue_without_interview"] += 1

        return list(counts_by_csa.values())

    def _build_mso_rows(
        self,
        selected_geo,
        selected_mso_source,
        va_queryset,
        province_scope,
    ):
        stats_by_mso = defaultdict(
            lambda: {
                "name": "",
                "death_events": 0,
                "va_scheduled": 0,
                "va_not_complete": 0,
                "mean_death_to_va_complete": 0,
                "va_total": 0,
                "valid_cod": 0,
                "indeterminate": 0,
                "error": 0,
                "duration_outliers": 0,
                "_death_to_complete_days": [],
            }
        )

        events = (
            Event.objects.filter(va_id__in=Subquery(va_queryset.values("id")))
            .filter(self._province_access_q("province", province_scope))
            .filter(self._province_filter_q("province", selected_geo))
            .select_related("va_interview_staff", "death", "va")
            .prefetch_related(
                "va__causes",
                "va__coding_issues",
            )
        )

        if selected_mso_source == "community":
            events = events.exclude(household__isnull=True)
        elif selected_mso_source == "facility":
            events = events.filter(household__isnull=True)

        for event in events:
            name = self._staff_name(event.va_interview_staff, fallback=event.supervisor or "")
            entry = stats_by_mso[name]
            entry["name"] = name

            if event.death_id:
                entry["death_events"] += 1

            if event.interview_scheduled_date:
                entry["va_scheduled"] += 1

            if event.interview_scheduled_date and not event.interview_complete_date:
                entry["va_not_complete"] += 1

            sched_to_complete_days = self._safe_days(
                event.interview_scheduled_date,
                event.interview_complete_date,
            )
            if sched_to_complete_days is not None:
                if sched_to_complete_days <= 15 or sched_to_complete_days >= 90:
                    entry["duration_outliers"] += 1

            death_date = self._coerce_date(getattr(event.death, "DE_06", None))
            death_to_complete_days = self._safe_days(
                death_date,
                event.interview_complete_date,
            )
            if death_to_complete_days is not None:
                entry["_death_to_complete_days"].append(death_to_complete_days)

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
            row["mean_death_to_va_complete"] = self._mean(
                row.pop("_death_to_complete_days")
            )
            rows.append(row)
        return rows

    def get_regional_operations_context(self):
        selected_geo = self._normalized_geo()
        time_window = self._resolve_time_window()
        selected_time_preset = time_window["selected_time_preset"]
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
        csa_search = self.request.GET.get("csa_search", "").strip()
        mso_search = self.request.GET.get("mso_search", "").strip()
        csa_dir = self._pick(self.request.GET.get("csa_dir", "desc"), {"asc", "desc"}, "desc")
        mso_sort = self._pick(
            self.request.GET.get("mso_sort", "death_events"),
            {key for key, _ in self.mso_column_map},
            "death_events",
        )
        mso_dir = self._pick(self.request.GET.get("mso_dir", "desc"), {"asc", "desc"}, "desc")
        csa_page = max(1, self._to_int(self.request.GET.get("csa_page", "1")))
        mso_page = max(1, self._to_int(self.request.GET.get("mso_page", "1")))

        province_scope = self._allowed_province_names()
        va_queryset = self.request.user.verbal_autopsies().annotate(
            province_name=Subquery(
                Location.objects.values("name").filter(
                    Q(path=Substr(OuterRef("location__path"), 1, 8)),
                    Q(depth=2),
                )[:1]
            )
        )
        va_queryset = va_queryset.filter(self._province_filter_q("province_name", selected_geo))
        if time_window["start_date_str"] and time_window["end_date_str"]:
            va_queryset = va_queryset.filter(
                Id10012__gte=time_window["start_date_str"],
                Id10012__lte=time_window["end_date_str"],
            )

        csa_rows = self._build_csa_rows(
                selected_geo,
                time_window["start_date_str"],
                time_window["end_date_str"],
                province_scope,
            )
        if csa_search:
            csa_rows = [
                row for row in csa_rows if self._matches_name_search(row.get("name", ""), csa_search)
            ]
        csa_rows_sorted = self._sort_rows(
            csa_rows,
            csa_sort,
            csa_dir,
        )
        mso_rows = self._build_mso_rows(
            selected_geo,
            selected_mso_source,
            va_queryset,
            province_scope,
        )
        if mso_search:
            mso_rows = [
                row for row in mso_rows if self._matches_name_search(row.get("name", ""), mso_search)
            ]
        mso_rows_sorted = self._sort_rows(
            mso_rows,
            mso_sort,
            mso_dir,
        )
        csa_pagination = self._paginate_rows(csa_rows_sorted, csa_page)
        mso_pagination = self._paginate_rows(mso_rows_sorted, mso_page)

        return {
            "geography_options": self.geography_options,
            "selected_geography": selected_geo,
            "time_presets": self.time_presets,
            "selected_time_preset": selected_time_preset,
            "selected_preset": time_window["selected_preset"],
            "start_value": time_window["start_value"],
            "end_value": time_window["end_value"],
            "time_label": time_window["time_label"],
            "selected_start_date": time_window["start_value"],
            "selected_end_date": time_window["end_value"],
            "mso_source_options": self.mso_source_options,
            "selected_mso_source": selected_mso_source,
            "csa_stats": csa_pagination["rows"],
            "csa_rows": csa_pagination["rows"],
            "csa_sort": csa_sort,
            "csa_dir": csa_dir,
            "csa_search": csa_search,
            "csa_page": csa_pagination["page"],
            "csa_total_pages": csa_pagination["total_pages"],
            "csa_has_prev": csa_pagination["has_prev"],
            "csa_has_next": csa_pagination["has_next"],
            "csa_prev_page": csa_pagination["prev_page"],
            "csa_next_page": csa_pagination["next_page"],
            "csa_visible_count": csa_pagination["visible_count"],
            "csa_total_count": csa_pagination["total_count"],
            "mso_stats": mso_pagination["rows"],
            "mso_rows": mso_pagination["rows"],
            "mso_sort": mso_sort,
            "mso_dir": mso_dir,
            "mso_search": mso_search,
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


class RegionalOperationsMapData(
    RegionalOperationsComponentContextMixin, CustomAuthMixin, View
):
    def get(self, request, *args, **kwargs):
        selected_geo = self._normalized_geo()
        time_window = self._resolve_time_window()
        province_scope = self._allowed_province_names()

        va_queryset = request.user.verbal_autopsies().annotate(
            province_name=Subquery(
                Location.objects.values("name").filter(
                    Q(path=Substr(OuterRef("location__path"), 1, 8)),
                    Q(depth=2),
                )[:1]
            ),
            district_name=Subquery(
                Location.objects.values("name").filter(
                    Q(path=Substr(OuterRef("location__path"), 1, 12)),
                    Q(depth=3),
                )[:1]
            ),
        )
        va_queryset = va_queryset.filter(self._province_filter_q("province_name", selected_geo))
        va_queryset = va_queryset.filter(
            self._province_access_q("province_name", province_scope)
        )
        if time_window["start_date_str"] and time_window["end_date_str"]:
            va_queryset = va_queryset.filter(
                Id10012__gte=time_window["start_date_str"],
                Id10012__lte=time_window["end_date_str"],
            )

        geographic_province_sums = (
            va_queryset.filter(causes__isnull=False)
            .exclude(province_name__isnull=True)
            .values("province_name")
            .annotate(count=Count("pk"))
        )
        geographic_district_sums = (
            va_queryset.filter(causes__isnull=False)
            .exclude(district_name__isnull=True)
            .values("district_name")
            .annotate(count=Count("pk"))
        )

        return JsonResponse(
            {
                "geographic_province_sums": list(geographic_province_sums),
                "geographic_district_sums": list(geographic_district_sums),
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
