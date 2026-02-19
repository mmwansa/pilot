from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import RequestFactory, TestCase
from django.urls import reverse

from va_explorer.va_analytics.views import _build_deaths_summary_cards, get_deaths_filter_state
from va_explorer.va_data_management.models import Death


class DeathsFilterParsingTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_defaults(self):
        request = self.factory.get("/va_analytics/outcomes-dashboard/")
        state = get_deaths_filter_state(request)

        self.assertEqual(state["time_preset"], "all_time")
        self.assertEqual(state["start_datetime"], "")
        self.assertEqual(state["end_datetime"], "")
        self.assertEqual(state["sex"], "")
        self.assertEqual(state["age_group"], "")
        self.assertEqual(state["place_of_death"], "")
        self.assertEqual(state["map_view"], "Province")

    def test_invalid_values_are_sanitized(self):
        request = self.factory.get(
            "/va_analytics/outcomes-dashboard/",
            {"time_preset": "bad", "age_group": "retired", "map_view": "ward"},
        )
        state = get_deaths_filter_state(request)

        self.assertEqual(state["time_preset"], "all_time")
        self.assertEqual(state["age_group"], "")
        self.assertEqual(state["map_view"], "Ward")


class DeathsUnder5CalculationTests(TestCase):
    def test_under_5_percentage_handles_missing_age_safely(self):
        Death.objects.create(
            key="death-u5-1",
            DE_04="2024-01-01",
            DE_06="2026-01-01",
            DE_05="Female",
            DE_07="home",
            submissiondate="2026-01-02",
        )
        Death.objects.create(
            key="death-u5-2",
            DE_04="1980-01-01",
            DE_06="2026-01-01",
            DE_05="Male",
            DE_07="hospital",
            submissiondate="2026-01-02",
        )
        Death.objects.create(
            key="death-u5-3",
            DE_04="",
            DE_06="2026-01-01",
            DE_05="",
            DE_07="",
            submissiondate="2026-01-02",
        )

        payload = _build_deaths_summary_cards(Death.objects.all())

        self.assertEqual(payload["death_card_total_events"], 3)
        self.assertAlmostEqual(payload["death_card_under_5_pct"], 33.3, places=1)


class DeathsApiSchemaTests(TestCase):
    def setUp(self):
        permission = Permission.objects.filter(codename="view_dashboard").first()
        group = Group.objects.create(name="deaths-dashboard-test-group")
        if permission:
            group.permissions.add(permission)

        User = get_user_model()
        user = User.objects.create_user(
            username="deaths_dashboard_test_user",
            password="test-password-123",
        )
        user.groups.add(group)
        self.client.force_login(user)

        Death.objects.create(
            key="death-schema-1",
            DE_04="2024-01-01",
            DE_05="Unknown",
            DE_06="2026-02-01",
            DE_07="",
            DE_15="",
            province="Lusaka",
            district="Lusaka",
            submissiondate="2026-02-02",
            today="2026-02-02",
            start="2026-02-02",
        )

    def test_death_endpoints_json_schema(self):
        summary = self.client.get(reverse("va_analytics:outcomes-deaths-summary-api")).json()
        self.assertEqual(
            set(summary.keys()),
            {
                "death_card_last_data_update",
                "death_card_last_death_date",
                "death_card_total_events",
                "death_card_mean_age",
                "death_card_under_5_pct",
                "death_card_median_delay_days",
            },
        )

        trend = self.client.get(reverse("va_analytics:outcomes-deaths-trend-api")).json()
        self.assertEqual(set(trend.keys()), {"labels", "data"})

        map_payload = self.client.get(reverse("va_analytics:outcomes-deaths-map-api")).json()
        self.assertTrue(
            {
                "map_view",
                "counts",
                "province_counts",
                "district_counts",
                "constituency_counts",
                "ward_counts",
                "ea_counts",
                "map_total_events",
                "map_province_sums",
                "map_district_sums",
                "map_constituency_sums",
                "map_ward_sums",
                "map_ea_sums",
            }.issubset(set(map_payload.keys()))
        )

        age_sex = self.client.get(reverse("va_analytics:outcomes-deaths-age-sex-api")).json()
        self.assertEqual(set(age_sex.keys()), {"labels", "male", "female", "other"})

        place = self.client.get(reverse("va_analytics:outcomes-deaths-place-api")).json()
        self.assertEqual(set(place.keys()), {"labels", "count_data", "percentage_data"})

        timeliness = self.client.get(reverse("va_analytics:outcomes-deaths-timeliness-api")).json()
        self.assertEqual(set(timeliness.keys()), {"labels", "data", "median_delay_days"})

        top_causes = self.client.get(reverse("va_analytics:outcomes-deaths-top-causes-api")).json()
        self.assertEqual(
            set(top_causes.keys()),
            {"has_coded", "labels", "count_data", "percentage_data"},
        )

        cause_trend = self.client.get(reverse("va_analytics:outcomes-deaths-cause-trend-api")).json()
        self.assertEqual(set(cause_trend.keys()), {"has_coded", "labels", "datasets"})

        signals = self.client.get(reverse("va_analytics:outcomes-deaths-signals-api")).json()
        self.assertEqual(
            set(signals.keys()),
            {
                "threshold_pct",
                "baseline_min",
                "all_deaths_7d",
                "all_deaths_30d",
                "under5_deaths_7d",
                "under5_deaths_30d",
            },
        )

    def test_non_death_tab_guard_on_death_endpoint(self):
        response = self.client.get(
            reverse("va_analytics:outcomes-deaths-summary-api"),
            {"tab": "pregnancy_outcomes"},
        )
        self.assertEqual(response.status_code, 400)


class OutcomesTabsIsolationTests(TestCase):
    def setUp(self):
        permission = Permission.objects.filter(codename="view_dashboard").first()
        group = Group.objects.create(name="outcomes-tabs-isolation-group")
        if permission:
            group.permissions.add(permission)

        User = get_user_model()
        user = User.objects.create_user(
            username="outcomes_tabs_test_user",
            password="test-password-123",
        )
        user.groups.add(group)
        self.client.force_login(user)

    def test_pregnancy_tabs_render_without_deaths_container(self):
        response = self.client.get(reverse("va_analytics:outcomes-dashboard"), {"tab": "pregnancies"})
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="pregnancyDashboardApp"', content)
        self.assertNotIn('id="deathsDashboardApp"', content)
