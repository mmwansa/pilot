# Outcomes Dashboard Performance Patterns Audit (Stage 1)

## Scope
This audit extracts the performance patterns currently used by Outcomes dashboards and compares them against Home dashboards to identify reusable optimizations.

Outcomes surfaces audited:
- `va_explorer/templates/va_analytics/outcomes_dashboard.html`
- `va_explorer/templates/va_analytics/partials/_pregnancy_outcomes_dashboard.html`
- `va_explorer/templates/va_analytics/partials/_pregnancies_dashboard.html`
- `va_explorer/templates/va_analytics/partials/_deaths_dashboard.html`
- `va_explorer/static/js/outcomes_dashboard.js`
- `va_explorer/static/js/pregnancy_dashboard.js`
- `va_explorer/static/js/deaths_dashboard.js`
- `va_explorer/va_analytics/views.py`

Home surfaces compared:
- `va_explorer/templates/home/index.html`
- `va_explorer/static/js/home.js`
- `va_explorer/home/views.py`

## Outcomes patterns checklist

### 1) Lazy component initialization on tab activation
Status in Outcomes: Present
Evidence:
- Tab pane includes allow independent tab content blocks: `va_explorer/templates/va_analytics/outcomes_dashboard.html:110`
- Component script defers full init until pane is activated: `va_explorer/static/js/outcomes_dashboard.js:453`
- Same lazy init guard for pregnancies and deaths: `va_explorer/static/js/pregnancy_dashboard.js:372`, `va_explorer/static/js/deaths_dashboard.js:502`

Why it helps:
- Avoids paying initial render/fetch cost for inactive tabs.

Status in Home: Partially present
Evidence:
- Home initializes only active tab and lazily initializes Trends/VA Stats: `va_explorer/static/js/home.js:683`, `va_explorer/static/js/home.js:695`, `va_explorer/static/js/home.js:709`
- Tab shell dispatches refresh event on tab activation: `va_explorer/static/js/dashboard_shell_tabs.js:43`

Gap:
- Home still server-renders a large monolithic page for all tabs up front, unlike Outcomes partialized dashboard sections.

### 2) Component-level JSON endpoints (small, focused payloads)
Status in Outcomes: Present
Evidence:
- Per-component endpoints embedded on dashboard root via `data-*`: `va_explorer/templates/va_analytics/partials/_pregnancy_outcomes_dashboard.html:5`
- Pregnancies and deaths use the same endpoint-per-component pattern: `va_explorer/templates/va_analytics/partials/_pregnancies_dashboard.html:5`, `va_explorer/templates/va_analytics/partials/_deaths_dashboard.html:5`
- Server exposes dedicated APIViews per component (summary/trend/map/etc): `va_explorer/va_analytics/views.py:1185`, `va_explorer/va_analytics/views.py:1192`, `va_explorer/va_analytics/views.py:1248`, `va_explorer/va_analytics/views.py:1452`, `va_explorer/va_analytics/views.py:1472`, `va_explorer/va_analytics/views.py:1561`

Why it helps:
- Each refresh fetches only required data for changed components.

Status in Home: Absent for Overview, mixed elsewhere
Evidence:
- Overview relies on one broad endpoint returning chart + all KPI bundles: `va_explorer/home/views.py:472`
- Trends/VA Stats share one combined endpoint returning both VA tables/charts + model trends: `va_explorer/home/views.py:441`

Gap:
- Home does not split large payloads by component for Overview or Trends/VA Stats.

### 3) Parallel fetch orchestration in client
Status in Outcomes: Present
Evidence:
- Outcomes full refresh uses `Promise.all` across component endpoints: `va_explorer/static/js/outcomes_dashboard.js:348`
- Pregnancies full refresh uses `Promise.all`: `va_explorer/static/js/pregnancy_dashboard.js:303`
- Deaths full refresh uses `Promise.all`: `va_explorer/static/js/deaths_dashboard.js:390`

Why it helps:
- Reduces end-to-end latency by overlapping network waits.

Status in Home: Limited
Evidence:
- Home performs one request for Overview filter updates (`$.ajax`): `va_explorer/static/js/home.js:465`
- Home uses one request for Trends+VA stats cache (`/trends/`): `va_explorer/static/js/home.js:652`

Gap:
- No parallelized per-component refresh path because payloads are monolithic.

### 4) Map refresh decoupled from full dashboard refresh
Status in Outcomes: Present
Evidence:
- `refreshMapOnly()` method exists and is bound to map-view selector changes: `va_explorer/static/js/outcomes_dashboard.js:327`, `va_explorer/static/js/outcomes_dashboard.js:401`
- Equivalent map-only flow in pregnancies and deaths: `va_explorer/static/js/pregnancy_dashboard.js:286`, `va_explorer/static/js/deaths_dashboard.js:215`

Why it helps:
- Avoids refetching all non-map widgets when only geographic view changes.

Status in Home: Not applicable in current overview structure
Evidence:
- Home overview currently couples chart+KPI updates in one response: `va_explorer/home/views.py:375`

Gap:
- No independent map/geo component endpoint and no map-only refresh route in Home overview.

### 5) Reuse chart instances instead of recreate-per-update
Status in Outcomes: Present
Evidence:
- Outcomes caches chart instances (`chartState`) and updates datasets in place: `va_explorer/static/js/outcomes_dashboard.js:30`, `va_explorer/static/js/outcomes_dashboard.js:185`
- Pregnancies follows same pattern: `va_explorer/static/js/pregnancy_dashboard.js:13`, `va_explorer/static/js/pregnancy_dashboard.js:150`
- Deaths instantiates once then updates: `va_explorer/static/js/deaths_dashboard.js:31`, `va_explorer/static/js/deaths_dashboard.js:180`

Why it helps:
- Lower CPU/GPU churn and smoother tab/filter interactions.

Status in Home: Mixed
Evidence:
- Overview chart is reused after initial instantiation: `va_explorer/static/js/home.js:249`
- Trends/VA charts are destroyed/recreated on each apply via `setVAChart`: `va_explorer/static/js/home.js:106`, `va_explorer/static/js/home.js:567`

Gap:
- Home Trends and VA Statistics still incur chart teardown/recreate overhead.

### 6) UI mode toggles rerender from cached payload (no refetch)
Status in Outcomes: Present
Evidence:
- Outcomes caches payload and rerenders on count/percentage toggles: `va_explorer/static/js/outcomes_dashboard.js:36`, `va_explorer/static/js/outcomes_dashboard.js:418`
- Deaths caches age/sex and place payload for mode toggles: `va_explorer/static/js/deaths_dashboard.js:35`, `va_explorer/static/js/deaths_dashboard.js:466`

Why it helps:
- Avoids network round-trips for pure presentation toggles.

Status in Home: Mostly absent
Evidence:
- Home applies payload once but does not expose mode toggles for Trends/VA panels; updates depend on endpoint payload application methods.

Gap:
- No equivalent client-side cached-mode switching pattern for Home’s heavy widgets.

### 7) Server-side query shaping and aggregation at DB layer
Status in Outcomes: Present
Evidence:
- Aggregation/annotation-heavy builders for trends and distributions (e.g. `annotate`, `Count`, `TruncMonth`): `va_explorer/va_analytics/views.py:190`, `va_explorer/va_analytics/views.py:416`, `va_explorer/va_analytics/views.py:840`
- Structured filter-state + dedicated queryset builders by dashboard type: `va_explorer/va_analytics/views.py:531`, `va_explorer/va_analytics/views.py:581`, `va_explorer/va_analytics/views.py:692`

Why it helps:
- Pushes computation to DB and reduces Python-loop pressure for many operations.

Status in Home: Weaker for overview path
Evidence:
- Overview does repeated full scans and Python dict accumulation for latest timestamps across models: `va_explorer/home/views.py:83`, `va_explorer/home/views.py:226`, `va_explorer/home/views.py:263`
- Additional expensive people counts against large key sets: `va_explorer/home/views.py:297`

Gap:
- Home Overview relies heavily on Python post-processing instead of denormalized/precomputed summaries.

### 8) Reduced template work via tab partial composition
Status in Outcomes: Present
Evidence:
- Outcomes tab panes include focused partial templates: `va_explorer/templates/va_analytics/outcomes_dashboard.html:118`, `va_explorer/templates/va_analytics/outcomes_dashboard.html:127`, `va_explorer/templates/va_analytics/outcomes_dashboard.html:136`

Why it helps:
- Keeps per-dashboard template segments isolated and supports lighter page-level maintenance.

Status in Home: Absent for major tabs
Evidence:
- Home keeps large Overview/VA Stats/Trends markup inline in one template: `va_explorer/templates/home/index.html:46`, `va_explorer/templates/home/index.html:211`, `va_explorer/templates/home/index.html:351`

Gap:
- Higher initial template payload and heavier DOM at first paint.

### 9) Explicit perf instrumentation per component path
Status in Outcomes: Present
Evidence:
- Client perf marks around render/fetch: `va_explorer/static/js/outcomes_dashboard.js:10`, `va_explorer/static/js/outcomes_dashboard.js:342`
- Server timed blocks on page and API operations: `va_explorer/va_analytics/views.py:1083`, `va_explorer/va_analytics/views.py:1181`, `va_explorer/va_analytics/views.py:1457`

Status in Home: Present (after Stage 0)
Evidence:
- Client perf marks in home scripts: `va_explorer/static/js/home.js:25`
- Server timed blocks in home endpoints: `va_explorer/home/views.py:443`, `va_explorer/home/views.py:475`

Gap:
- Instrumentation exists in both; optimization gap is mostly architectural, not observability.

## Home vs Outcomes gap matrix (quick view)

- Lazy tab init: Home `partial` | Outcomes `yes`
- Component-level endpoints: Home `no (overview), mixed (trends/va bundled)` | Outcomes `yes`
- Parallel fetches: Home `no meaningful per-component path` | Outcomes `yes`
- Map-only refresh: Home `no` | Outcomes `yes`
- Chart instance reuse: Home `mixed` | Outcomes `yes`
- Cached mode rerender (no fetch): Home `limited` | Outcomes `yes`
- DB-level aggregation-centric data path: Home `mixed/weak in NOV` | Outcomes `strong`
- Template partialization: Home `mostly no` | Outcomes `yes`

## Reusable patterns to mirror into Home (priority order)

1. Split Home Overview into component endpoints (chart, KPI groups, map) and fetch in parallel.
2. Keep map implementation unchanged but wrap it with map-only refresh semantics (same as Outcomes controllers).
3. Convert Home Trends/VA chart updates from destroy/recreate to persistent chart instances with dataset updates.
4. Replace Python-heavy overview timestamp scans with pre-aggregated/DB-annotated paths where feasible.
5. Gradually partialize Home tab markup to reduce initial render/DOM cost without changing routes/UI.

## Notes for Stage 2
- Non-negotiable map constraint is compatible with Outcomes pattern reuse: only lifecycle wrapping/caching is required; map rendering logic can remain untouched.
- Existing Stage 0 profiling can be used to verify each migrated pattern incrementally.
