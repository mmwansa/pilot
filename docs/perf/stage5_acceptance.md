# Stage 5 Verification: Home Dashboard Fast-Path

Date: 2026-02-19

## Acceptance checks implemented

### Client-side measurable checks
- First render timing log on Home bootstrap:
  - `va_explorer/static/js/home.js`
  - log key: `[perf][acceptance] home.first_render_ms`
- Cached tab switch latency check (pass/fail threshold):
  - `va_explorer/static/js/home.js`
  - log key: `[perf][acceptance] tab_switch_cached`
  - threshold currently `220ms`
- Duplicate network request detection for component slots:
  - `va_explorer/static/js/dashboard_loader.js`
  - log keys:
    - `[perf][acceptance] component.network_fetch`
    - `[perf][acceptance] duplicate_network_fetch_detected`
- In-flight dedupe for concurrent slot loads:
  - `va_explorer/static/js/dashboard_loader.js`
  - guarded by `inFlightLoads`

### Server-side measurable checks
- Existing server timings remain active via profiling middleware/timed blocks.
- Stage 3 cache key normalization fix ensures stable warm cache hits for non-custom ranges.
  - `va_explorer/home/views.py` (`_fastpath_cache_key`)

## Before vs After (local benchmark)

Baseline (from Stage 0): `docs/dashboard_baseline_profiling.md`
- `GET /`: ~5.2s to ~8.3s
- `GET /national-operational/filter-data/`: ~4.9s
- `GET /trends/`: ~0.77s

After (current code, local shell benchmark)

Cold run (post-invalidate):
- `GET /`: `146.47ms`
- `GET /national-operational/filter-data/`: `5173.55ms`
- `GET /trends/`: `807.38ms`
- `GET /va_analytics/home-dashboard/kpis/`: `28.54ms`
- `GET /va_analytics/home-dashboard/tab/overview/chart/events/`: `34.62ms`
- `GET /va_analytics/home-dashboard/tab/va_statistics/table/issues/?page=1&page_size=10`: `36.26ms`

Warm run (5-sample average):
- `GET /`: `46.25ms` (min `35.32ms`, max `77.25ms`)
- `GET /national-operational/filter-data/`: `28.42ms` (min `26.48ms`, max `30.34ms`)
- `GET /trends/`: `43.71ms` (min `24.42ms`, max `82.90ms`)
- `GET /va_analytics/home-dashboard/kpis/`: `26.14ms`
- `GET /va_analytics/home-dashboard/tab/overview/chart/events/`: `23.45ms`
- `GET /va_analytics/home-dashboard/tab/va_statistics/table/issues/?page=1&page_size=10`: `26.09ms`

## Acceptance result summary

- First load time-to-first-render: instrumented and logged in browser console.
- Server view time reduced on warm requests: **pass** (major reduction vs baseline on Home data endpoints).
- Tab switching after first tab load near-instant: instrumented with explicit pass/fail log.
- Duplicate network requests for already-loaded components: instrumented and warning-enabled.
- Filters/permissions/displayed numbers: existing behavior preserved; endpoints remain permission-protected where applicable.
- Map behavior: wrapper-only optimization introduced; internal map logic unchanged.

## Optional: Django Debug Toolbar guidance

If local profiling becomes too heavy:
- Keep timing middleware enabled.
- Disable SQL panel temporarily to reduce profiling overhead.

Example (local settings):

```python
DEBUG_TOOLBAR_PANELS = [
    p for p in DEBUG_TOOLBAR_PANELS
    if p != "debug_toolbar.panels.sql.SQLPanel"
]
```

## Repro command used for after metrics

```bash
python manage.py shell -c "
import time, statistics as s
from django.test import Client
from django.contrib.auth import get_user_model
from va_explorer.home.cache_utils import bump_home_dashboard_fastpath_version

U=get_user_model()
u=U.objects.filter(is_active=True, is_superuser=True).first() or U.objects.filter(is_active=True).first()
c=Client(HTTP_HOST='localhost'); c.force_login(u)
endpoints=['/','/national-operational/filter-data/','/trends/','/va_analytics/home-dashboard/kpis/','/va_analytics/home-dashboard/tab/overview/chart/events/','/va_analytics/home-dashboard/tab/va_statistics/table/issues/?page=1&page_size=10']

def timed_get(path):
    st=time.perf_counter(); r=c.get(path); dur=(time.perf_counter()-st)*1000
    return r.status_code,dur,len(r.content)

print('== Cold run (post-invalidate) ==')
bump_home_dashboard_fastpath_version()
for ep in endpoints:
    code,dur,ln=timed_get(ep)
    print(f'{ep} status={code} ms={dur:.2f} bytes={ln}')

print('== Warm run (5 samples avg) ==')
for ep in endpoints:
    vals=[]
    for _ in range(5):
        code,dur,ln=timed_get(ep)
        vals.append(dur)
    print(f'{ep} avg_ms={s.mean(vals):.2f} min_ms={min(vals):.2f} max_ms={max(vals):.2f}')
"
```
