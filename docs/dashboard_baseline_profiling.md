# Dashboard Baseline Profiling (Stage 0)

Date: 2026-02-19

## Scope Mapped

### Home dashboards
- Routes:
  - `/`
  - `/trends/`
  - `/national-operational/filter-data/`
  - `/regional-operations/*`
- View entrypoints:
  - `va_explorer/home/views.py:Index`
  - `va_explorer/home/views.py:Trends`
  - `va_explorer/home/views.py:NationalOperationalFilterData`
- Template entrypoint:
  - `va_explorer/templates/home/index.html`
- JS entrypoint:
  - `va_explorer/static/js/home.js`

### Outcomes dashboards
- Routes:
  - `/va_analytics/outcomes-dashboard/`
  - `/va_analytics/api/pregnancy-outcomes/*`
  - `/va_analytics/api/outcomes/deaths/*`
  - `/va_analytics/api/pregnancy/*`
  - `/va_analytics/api/pregnancy-events/*`
- View entrypoints:
  - `va_explorer/va_analytics/views.py:OutcomesDashboardView`
  - `va_explorer/va_analytics/views.py:PregnancyOutcomes*APIView`
  - `va_explorer/va_analytics/views.py:Deaths*APIView`
- Template entrypoint:
  - `va_explorer/templates/va_analytics/outcomes_dashboard.html`
- JS entrypoints:
  - `va_explorer/static/js/outcomes_dashboard.js`
  - `va_explorer/static/js/pregnancy_dashboard.js`
  - `va_explorer/static/js/deaths_dashboard.js`

## Instrumentation Added

### Server-side
- Request + DB + render profiler middleware:
  - `va_explorer/utils/middleware.py`
- Timed step helper/context manager:
  - `va_explorer/utils/profiling.py`
- Middleware registration:
  - `config/settings/base.py` (`DashboardProfilingMiddleware`)
- Heavy operation timers added in:
  - `va_explorer/home/views.py`
  - `va_explorer/va_analytics/views.py`

### Client-side
- Home timing logs:
  - `va_explorer/static/js/home.js`
  - Marks around initial load, tab init, filter fetch, chart/table/KPI render calls
- Outcomes timing logs:
  - `va_explorer/static/js/outcomes_dashboard.js`
  - Marks around initial load, refresh cycles, map fetch, chart/KPI render calls

Console log format:
- Server: `[perf][request] ...`
- Client Home: `[perf][home] ...`
- Client Outcomes: `[perf][outcomes] ...`

## Baseline Sample Results (Local)

Sampled using Django test client against profiled routes.

### Top 5 slowest Home operations
1. `home.index.nov_context`: ~4.6s to ~5.5s
2. `home.nov.latest_timestamps.households`: ~1.8s to ~2.6s
3. `home.nov.latest_timestamps.eas`: ~1.8s to ~1.9s
4. `home.nov.people_aggregate`: ~0.68s to ~0.72s
5. `home.trends.model_trends_data`: ~0.71s

Notable total request times:
- `GET /`: ~5.2s to ~8.3s
- `GET /national-operational/filter-data/`: ~4.9s
- `GET /trends/`: ~0.77s

### Outcomes operations for same class of work (summary/trend/map)
- `GET /va_analytics/outcomes-dashboard/?tab=pregnancy_outcomes`: ~93ms total
  - top step: `outcomes.page.summary_cards` ~6.2ms
- `GET /va_analytics/api/pregnancy-outcomes/summary/`: ~24ms total
  - top step: `outcomes.api.summary_cards` ~6.2ms
- `GET /va_analytics/api/pregnancy-outcomes/trend/`: ~21ms total
  - top step: `outcomes.api.trend_series` ~2.3ms
- `GET /va_analytics/api/pregnancy-outcomes/map/`: ~25ms total
  - top step: `outcomes.api.map_hierarchy` ~5.0ms
- `GET /va_analytics/api/outcomes/deaths/map/?tab=deaths`: ~25ms total
  - top step: `outcomes.deaths.map_hierarchy` ~4.8ms

## Observation Summary
- Home NOV aggregation path is the primary bottleneck by a wide margin.
- The largest contributors are repeated full-table timestamp extraction and people aggregation counts.
- Outcomes endpoints are already relatively lightweight and segmented by concern.

## Repro Command

```bash
python manage.py shell -c "
from django.test import Client
from django.contrib.auth import get_user_model
u=get_user_model().objects.filter(is_active=True).first()
c=Client(HTTP_HOST='localhost'); c.force_login(u)
for p in ['/', '/trends/', '/national-operational/filter-data/', '/va_analytics/outcomes-dashboard/?tab=pregnancy_outcomes', '/va_analytics/api/pregnancy-outcomes/summary/', '/va_analytics/api/pregnancy-outcomes/trend/', '/va_analytics/api/pregnancy-outcomes/map/', '/va_analytics/api/outcomes/deaths/summary/?tab=deaths', '/va_analytics/api/outcomes/deaths/trend/?tab=deaths', '/va_analytics/api/outcomes/deaths/map/?tab=deaths']:
    r=c.get(p); print('REQ', p, 'STATUS', r.status_code, 'LEN', len(r.content))
"
```
