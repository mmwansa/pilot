(function () {
  const app = document.getElementById("pregnancyDashboardApp");
  if (!app) return;

  const endpoints = {
    summary: app.dataset.summaryEndpoint,
    trend: app.dataset.trendEndpoint,
    gestationalAge: app.dataset.gestationalAgeEndpoint,
    ancVisits: app.dataset.ancVisitsEndpoint,
    map: app.dataset.mapEndpoint,
  };

  const chartState = {
    trend: null,
    gestationalAge: null,
    ancVisits: null,
  };

  const mapState = {
    map: null,
    layer: null,
    geojson: null,
    colors: [
      "#e8f1fb",
      "#d4e4f7",
      "#bdd5f1",
      "#a2c3ea",
      "#84afe2",
      "#679ad9",
      "#4b84ce",
      "#2f6ec2",
      "#1f4f8f",
    ],
  };

  const FIXED_BINS = [1, 39, 76, 113, 150, 187, 224, 261, 302];

  const getEl = (id) => document.getElementById(id);

  const filterElements = {
    form: getEl("peFiltersForm"),
    preset: getEl("peFilterTimePreset"),
    start: getEl("peFilterStartDatetime"),
    end: getEl("peFilterEndDatetime"),
    mapViewSelect: getEl("peMapViewSelect"),
    mapViewHidden: getEl("peFilterMapView"),
    reset: getEl("peFiltersReset"),
  };

  const getFilters = () => ({
    time_preset: filterElements.preset?.value || "all_time",
    start_datetime: filterElements.start?.value || "",
    end_datetime: filterElements.end?.value || "",
    map_view: filterElements.mapViewSelect?.value || "Province",
  });

  const buildParams = (filters) => {
    const params = new URLSearchParams();
    if (filters.time_preset && filters.time_preset !== "all_time") {
      params.set("time_preset", filters.time_preset);
    }
    if (filters.start_datetime) params.set("start_datetime", filters.start_datetime);
    if (filters.end_datetime) params.set("end_datetime", filters.end_datetime);
    if (filters.map_view && filters.map_view !== "Province") params.set("map_view", filters.map_view);
    return params;
  };

  const syncFilterHiddenFields = () => {
    if (filterElements.mapViewHidden && filterElements.mapViewSelect) {
      filterElements.mapViewHidden.value = filterElements.mapViewSelect.value;
    }
  };

  const syncUrl = (filters) => {
    const params = buildParams(filters);
    const query = params.toString();
    const nextUrl = query ? `${window.location.pathname}?${query}` : window.location.pathname;
    window.history.replaceState({}, "", nextUrl);
  };

  const fetchJSON = async (url, filters) => {
    const params = buildParams(filters);
    const requestUrl = params.toString() ? `${url}?${params.toString()}` : url;
    const response = await fetch(requestUrl, {
      method: "GET",
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
    });
    if (!response.ok) throw new Error(`Request failed: ${requestUrl}`);
    return response.json();
  };

  const setText = (id, value) => {
    const el = getEl(id);
    if (el) el.textContent = value;
  };

  const setEmptyState = (id, isEmpty) => {
    const el = getEl(id);
    if (el) el.hidden = !isEmpty;
  };

  const renderSummary = (data) => {
    setText("peCardLastDataUpdate", data.card_last_data_update || "N/A");
    setText("peCardLastEventDate", data.card_last_event_date || "N/A");
    setText("peCardNumberOfEvents", data.card_number_of_events ?? 0);
    setText("peCardMeanAge", data.card_mean_age ?? 0);
    setEmptyState("peSummaryEmpty", (data.card_number_of_events ?? 0) === 0);
  };

  const ensureLineChart = () => {
    if (chartState.trend) return chartState.trend;
    const canvas = getEl("peTrendChart");
    if (!canvas || typeof Chart === "undefined") return null;
    chartState.trend = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels: [],
        datasets: [{
          label: "Pregnancy Events",
          data: [],
          borderColor: "#2d6cdf",
          backgroundColor: "rgba(45,108,223,0.2)",
          pointRadius: 2,
          tension: 0.25,
          fill: false,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: true, position: "top" },
          tooltip: { enabled: true },
          title: { display: true, text: "National Pregnancy Event Trend" },
        },
        scales: {
          x: { title: { display: true, text: "Month" }, grid: { display: true, color: "rgba(148, 163, 184, 0.35)" } },
          y: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: "Count of pregnancy events" }, grid: { display: true, color: "rgba(148, 163, 184, 0.35)" } },
        },
      },
    });
    return chartState.trend;
  };

  const ensureBarChart = (key, canvasId, options) => {
    if (chartState[key]) return chartState[key];
    const canvas = getEl(canvasId);
    if (!canvas || typeof Chart === "undefined") return null;
    chartState[key] = new Chart(canvas.getContext("2d"), options);
    return chartState[key];
  };

  const renderTrend = (data) => {
    const chart = ensureLineChart();
    if (!chart) return;
    chart.data.labels = data.labels || [];
    chart.data.datasets[0].data = data.data || [];
    chart.update();
    const sum = (data.data || []).reduce((acc, value) => acc + Number(value || 0), 0);
    setEmptyState("peTrendEmpty", sum === 0);
  };

  const renderGestationalAge = (payload) => {
    const chart = ensureBarChart("gestationalAge", "peGestationalAgeChart", {
      type: "bar",
      data: {
        labels: [],
        datasets: [{
          label: "Pregnancy Events",
          data: [],
          backgroundColor: "#6baed6",
          borderColor: "#3182bd",
          borderWidth: 1,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: true } },
        scales: {
          x: { title: { display: true, text: "Gestational age at detection (weeks)" }, grid: { display: false } },
          y: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: "Number of pregnancy events" }, grid: { display: true, color: "rgba(148,163,184,0.35)" } },
        },
      },
    });
    if (!chart) return;
    chart.data.labels = payload.labels || [];
    chart.data.datasets[0].data = payload.data || [];
    chart.update();
    const sum = (payload.data || []).reduce((acc, value) => acc + Number(value || 0), 0);
    setEmptyState("peGestationalAgeEmpty", sum === 0);
  };

  const renderAncVisits = (payload) => {
    const chart = ensureBarChart("ancVisits", "peAncVisitsChart", {
      type: "scatter",
      data: {
        datasets: [{
          label: "Pregnancy Events",
          data: [],
          pointRadius: 3,
          pointHoverRadius: 4,
          borderWidth: 0,
          backgroundColor: "rgba(46, 125, 50, 0.45)",
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: true } },
        scales: {
          x: {
            type: "linear",
            min: 1,
            max: 40,
            ticks: { precision: 0 },
            title: { display: true, text: "Gestational age at detection (weeks)" },
            grid: { display: true, color: "rgba(148,163,184,0.25)" },
          },
          y: {
            beginAtZero: true,
            ticks: { precision: 0 },
            title: { display: true, text: "ANC visit count" },
            grid: { display: true, color: "rgba(148,163,184,0.35)" },
          },
        },
      },
    });

    if (!chart) return;

    const points = (payload.points || []).map((point, idx) => {
      const jitter = ((idx % 5) - 2) * 0.06;
      return { x: Number(point.x || 0) + jitter, y: Number(point.y || 0) };
    });

    chart.data.datasets[0].data = points;
    if (payload.x_min != null && payload.x_max != null) {
      chart.options.scales.x.min = Number(payload.x_min);
      chart.options.scales.x.max = Number(payload.x_max);
    }
    chart.update();
    setEmptyState("peAncVisitsEmpty", points.length === 0);
  };

  const normalizeGeoName = (value) =>
    (value || "")
      .toString()
      .toLowerCase()
      .replace(/province|district/g, "")
      .replace(/\s+/g, " ")
      .trim();

  const buildLookup = (rows) => {
    const map = new Map();
    (rows || []).forEach((row) => {
      const name = normalizeGeoName(row.name);
      if (name) map.set(name, Number(row.count || 0));
    });
    return map;
  };

  const getColorForCount = (count) => {
    if (!count || count <= 0) return "#c0c0c0";

    for (let i = 0; i < FIXED_BINS.length - 1; i += 1) {
      const low = FIXED_BINS[i];
      const high = FIXED_BINS[i + 1] - 1;
      if (count >= low && count <= high) {
        return mapState.colors[Math.min(i, mapState.colors.length - 1)];
      }
    }

    if (count >= FIXED_BINS[FIXED_BINS.length - 1]) {
      return mapState.colors[mapState.colors.length - 1];
    }

    return mapState.colors[0];
  };

  const renderMapLegend = () => {
    const legend = getEl("peMapLegend");
    if (!legend) return;

    let html = "<div><svg width='18' height='14'><rect fill='#c0c0c0' width='14' height='14'></rect></svg>0</div>";
    for (let i = 0; i < FIXED_BINS.length - 1; i += 1) {
      const low = FIXED_BINS[i];
      const high = FIXED_BINS[i + 1] - 1;
      html += `<div><svg width='18' height='14'><rect fill='${mapState.colors[i]}' width='14' height='14'></rect></svg>${low} - ${high}</div>`;
    }
    html += `<div><svg width='18' height='14'><rect fill='${mapState.colors[mapState.colors.length - 1]}' width='14' height='14'></rect></svg>${FIXED_BINS[FIXED_BINS.length - 1]}+</div>`;

    legend.innerHTML = html;
  };

  const ensureMap = async () => {
    if (mapState.map || typeof L === "undefined") return;
    mapState.map = L.map("peMapContainer", { maxBounds: [[-6, 20], [-20, 34]] }).setView([-13, 27], 6);
    mapState.map.attributionControl.setPrefix("");
    mapState.map.keyboard.disable();
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 10,
      attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(mapState.map);

    const res = await fetch(`${window.location.origin}/static/data/zambia_geojson.json`);
    mapState.geojson = await res.json();
  };

  const renderMap = async (payload) => {
    await ensureMap();
    if (!mapState.map || !mapState.geojson) return;

    const mapView = payload.map_view === "District" ? "District" : "Province";
    const lookup = buildLookup(payload.counts || []);
    const geojson = JSON.parse(JSON.stringify(mapState.geojson));
    geojson.features = geojson.features.filter((f) => {
      const level = f?.properties?.area_level_label;
      return level === "Country" || level === mapView;
    });

    if (mapState.layer) mapState.map.removeLayer(mapState.layer);

    mapState.layer = L.geoJson(geojson, {
      style: (feature) => {
        const level = feature?.properties?.area_level_label;
        if (level === "Country") {
          return { weight: 2.5, opacity: 1, color: "grey", stroke: true, fillOpacity: 0 };
        }
        const areaName = normalizeGeoName(feature?.properties?.area_name);
        const count = lookup.get(areaName) || 0;
        const color = getColorForCount(count);
        return { stroke: true, weight: 2, color, opacity: 1, fillColor: color, fillOpacity: 0.7 };
      },
      onEachFeature: (feature, layer) => {
        const level = feature?.properties?.area_level_label;
        if (level === "Country") return;
        const areaNameRaw = feature?.properties?.area_name || "";
        const areaName = normalizeGeoName(areaNameRaw);
        const count = lookup.get(areaName) || 0;
        layer.bindTooltip(`<div class="mapTooltip"><h4>${areaNameRaw} ${level}</h4><p>${count}</p></div>`);
      },
    }).addTo(mapState.map);

    setEmptyState("peMapEmpty", (payload.counts || []).length === 0);
    renderMapLegend();
  };

  const refreshMapOnly = async () => {
    const filters = getFilters();
    syncFilterHiddenFields();
    syncUrl(filters);
    const mapData = await fetchJSON(endpoints.map, filters);
    await renderMap(mapData);
  };

  const refreshAll = async () => {
    const filters = getFilters();
    syncFilterHiddenFields();
    syncUrl(filters);

    const [summary, trend, gestAge, anc, map] = await Promise.all([
      fetchJSON(endpoints.summary, filters),
      fetchJSON(endpoints.trend, filters),
      fetchJSON(endpoints.gestationalAge, filters),
      fetchJSON(endpoints.ancVisits, filters),
      fetchJSON(endpoints.map, filters),
    ]);

    renderSummary(summary);
    renderTrend(trend);
    renderGestationalAge(gestAge);
    renderAncVisits(anc);
    await renderMap(map);
  };

  const bindEvents = () => {
    if (filterElements.form) {
      filterElements.form.addEventListener("submit", (event) => {
        event.preventDefault();
        refreshAll().catch((err) => console.error(err));
      });
    }

    [filterElements.preset, filterElements.start, filterElements.end].forEach((el) => {
      if (!el) return;
      el.addEventListener("change", () => refreshAll().catch((err) => console.error(err)));
    });

    if (filterElements.mapViewSelect) {
      filterElements.mapViewSelect.addEventListener("change", () => refreshMapOnly().catch((err) => console.error(err)));
    }

    if (filterElements.reset) {
      filterElements.reset.addEventListener("click", () => {
        if (filterElements.preset) filterElements.preset.value = "all_time";
        if (filterElements.start) filterElements.start.value = "";
        if (filterElements.end) filterElements.end.value = "";
        if (filterElements.mapViewSelect) filterElements.mapViewSelect.value = "Province";
        refreshAll().catch((err) => console.error(err));
      });
    }
  };

  const init = async () => {
    bindEvents();
    await refreshAll();
  };

  const resizeVisuals = () => {
    if (chartState.trend) chartState.trend.resize();
    if (chartState.gestationalAge) chartState.gestationalAge.resize();
    if (chartState.ancVisits) chartState.ancVisits.resize();
    if (mapState.map) mapState.map.invalidateSize();
  };

  const pane = app.closest(".tab-pane");
  if (pane && !pane.classList.contains("show")) {
    let initializedFromTab = false;
    const activateHandler = (event) => {
      const targetSelector =
        event?.target?.getAttribute("data-bs-target") ||
        event?.target?.getAttribute("data-target");
      if (targetSelector !== `#${pane.id}`) return;
      if (!initializedFromTab) {
        initializedFromTab = true;
        init()
          .then(() => setTimeout(resizeVisuals, 0))
          .catch((err) => console.error(err));
      } else {
        setTimeout(resizeVisuals, 0);
      }
    };

    if (window.jQuery) {
      window.jQuery(document).on("shown.bs.tab", activateHandler);
    } else {
      document.addEventListener("shown.bs.tab", activateHandler);
    }
    return;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      init()
        .then(() => setTimeout(resizeVisuals, 0))
        .catch((err) => console.error(err));
    });
  } else {
    init()
      .then(() => setTimeout(resizeVisuals, 0))
      .catch((err) => console.error(err));
  }
})();
