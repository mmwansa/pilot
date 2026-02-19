(function () {
  const app = document.getElementById("outcomesDashboardApp");
  if (!app) return;

  const endpoints = {
    summary: app.dataset.summaryEndpoint,
    trend: app.dataset.trendEndpoint,
    birthOutcomes: app.dataset.birthOutcomesEndpoint,
    gestationalAge: app.dataset.gestationalAgeEndpoint,
    ancVisits: app.dataset.ancVisitsEndpoint,
    kpis: app.dataset.kpisEndpoint,
    placeOfBirth: app.dataset.placeOfBirthEndpoint,
    map: app.dataset.mapEndpoint,
  };

  const chartState = {
    trend: null,
    birthOutcomes: null,
    gestationalAge: null,
    ancVisits: null,
    placeOfBirth: null,
    birthOutcomesPayload: null,
    placeOfBirthPayload: null,
  };

  const getEl = (id) => document.getElementById(id);

  const filterElements = {
    form: getEl("poFiltersForm"),
    outcome: getEl("poFilterPregnancyOutcome"),
    preset: getEl("poFilterTimePreset"),
    start: getEl("poFilterStartDatetime"),
    end: getEl("poFilterEndDatetime"),
    mapViewSelect: getEl("poMapViewSelect"),
    mapViewHidden: getEl("poFilterMapView"),
    reset: getEl("poFiltersReset"),
    birthCount: getEl("poBirthModeCount"),
    birthPct: getEl("poBirthModePercentage"),
    placeCount: getEl("poPlaceBirthModeCount"),
    placePct: getEl("poPlaceBirthModePercentage"),
  };

  const getFilters = () => ({
    pregnancy_outcome: filterElements.outcome?.value || "",
    time_preset: filterElements.preset?.value || "all_time",
    start_datetime: filterElements.start?.value || "",
    end_datetime: filterElements.end?.value || "",
    map_view: filterElements.mapViewSelect?.value || "Province",
  });

  const buildParams = (filters) => {
    const params = new URLSearchParams();
    if (filters.pregnancy_outcome) params.set("pregnancy_outcome", filters.pregnancy_outcome);
    if (filters.time_preset && filters.time_preset !== "all_time") params.set("time_preset", filters.time_preset);
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
    const currentTab = new URLSearchParams(window.location.search).get("tab");
    if (currentTab) params.set("tab", currentTab);
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

  const mapController =
    typeof window.createHierarchicalDashboardMap === "function"
      ? window.createHierarchicalDashboardMap({
          containerId: "poMapContainer",
          legendId: "poMapLegend",
          breadcrumbId: "poMapBreadcrumb",
          emptyStateId: "poMapEmpty",
          endpoint: endpoints.map,
          buildParams,
          styleVariant: "va",
          noDataMessage: "No mapped outcomes in current filter range.",
        })
      : null;

  const setText = (id, value) => {
    const el = getEl(id);
    if (el) el.textContent = value;
  };

  const setEmptyState = (id, isEmpty) => {
    const el = getEl(id);
    if (el) el.hidden = !isEmpty;
  };

  const isValidDateValue = (value) => /^\d{4}-\d{2}-\d{2}$/.test(value || "");
  const shouldApplyDateRangeChange = () => {
    if (!filterElements.preset || filterElements.preset.value !== "custom") return true;
    const start = filterElements.start?.value || "";
    const end = filterElements.end?.value || "";
    if (!isValidDateValue(start) || !isValidDateValue(end)) return false;
    return start <= end;
  };
  const setupDateInputs = (inputs) => {
    const dateInputs = (inputs || []).filter(Boolean);
    if (!dateInputs.length) return;

    const iconOnlyThresholdPx = 170;
    const updateIconMode = () => {
      dateInputs.forEach((input) => {
        input.classList.toggle("is-icon-only", input.offsetWidth <= iconOnlyThresholdPx);
      });
    };

    dateInputs.forEach((input) => {
      input.addEventListener("pointerdown", () => {
        if (typeof input.showPicker === "function") {
          try {
            input.showPicker();
          } catch (_error) {
            input.focus();
          }
          return;
        }
        input.focus();
      });
    });

    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(updateIconMode);
      dateInputs.forEach((input) => observer.observe(input));
    } else {
      window.addEventListener("resize", updateIconMode);
    }
    updateIconMode();
  };

  const renderSummary = (data) => {
    setText("poCardLastDataUpdate", data.card_last_data_update || "N/A");
    setText("poCardLastEventDate", data.card_last_event_date || "N/A");
    setText("poCardNumberOfEvents", data.card_number_of_events ?? 0);
    setText("poCardMultipleBirthPct", `${data.card_multiple_birth_pct ?? 0}%`);
    setEmptyState("poSummaryEmpty", (data.card_number_of_events ?? 0) === 0);
  };

  const renderKpis = (data) => {
    setText("poCardMeanAge", data.mean_age ?? 0);
    setText("poCardHivPct", `${data.hiv_positive_pct ?? 0}%`);
  };

  const ensureLineChart = () => {
    if (chartState.trend) return chartState.trend;
    const canvas = getEl("poTrendChart");
    if (!canvas || typeof Chart === "undefined") return null;
    chartState.trend = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: { labels: [], datasets: [{ label: "Pregnancy Outcomes", data: [], borderColor: "#2d6cdf", backgroundColor: "rgba(45,108,223,0.2)", pointRadius: 2, tension: 0.25, fill: false }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: true, position: "top" }, tooltip: { enabled: true } },
        scales: {
          x: { grid: { display: true, color: "rgba(148, 163, 184, 0.35)" } },
          y: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: "Count" }, grid: { display: true, color: "rgba(148, 163, 184, 0.35)" } },
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
    setEmptyState("poTrendEmpty", sum === 0);
  };

  const currentBirthMode = () => (filterElements.birthPct?.checked ? "percentage" : "count");
  const currentPlaceMode = () => (filterElements.placePct?.checked ? "percentage" : "count");

  const renderBirthOutcomes = (payload) => {
    chartState.birthOutcomesPayload = payload;
    const chart = ensureBarChart("birthOutcomes", "poBirthOutcomesChart", {
      type: "pie",
      data: { labels: [], datasets: [{ label: "Birth Outcomes", data: [], backgroundColor: ["#2d6cdf", "#f46d43"], borderColor: ["#2d6cdf", "#f46d43"], borderWidth: 1 }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: true, position: "bottom" }, tooltip: { enabled: true } },
      },
    });
    if (!chart) return;
    const mode = currentBirthMode();
    chart.data.labels = payload.labels || [];
    chart.data.datasets[0].data = mode === "percentage" ? (payload.percentage_data || []) : (payload.count_data || []);
    chart.data.datasets[0].label = mode === "percentage" ? "Birth Outcomes (%)" : "Birth Outcomes";
    chart.update();
    const sum = (payload.count_data || []).reduce((acc, value) => acc + Number(value || 0), 0);
    setEmptyState("poBirthOutcomesEmpty", sum === 0);
  };

  const renderGestationalAge = (payload) => {
    const chart = ensureBarChart("gestationalAge", "poGestationalAgeChart", {
      type: "bar",
      data: { labels: [], datasets: [{ label: "Outcomes", data: [], backgroundColor: ["#9ecae1", "#6baed6", "#3182bd", "#08519c"], borderColor: ["#9ecae1", "#6baed6", "#3182bd", "#08519c"], borderWidth: 1 }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: true } },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: "Count" }, grid: { display: true, color: "rgba(148,163,184,0.35)" } },
        },
      },
    });
    if (!chart) return;
    chart.data.labels = payload.labels || [];
    chart.data.datasets[0].data = payload.data || [];
    chart.update();
    const sum = (payload.data || []).reduce((acc, value) => acc + Number(value || 0), 0);
    setEmptyState("poGestationalAgeEmpty", sum === 0);
  };

  const renderAncVisits = (payload) => {
    const chart = ensureBarChart("ancVisits", "poAncVisitsChart", {
      type: "bar",
      data: { labels: [], datasets: [{ label: "Outcomes", data: [], backgroundColor: "#4CAF50", borderColor: "#2E7D32", borderWidth: 1 }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: true } },
        scales: {
          x: { grid: { display: false }, title: { display: true, text: "ANC Visits" } },
          y: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: "Count" }, grid: { display: true, color: "rgba(148,163,184,0.35)" } },
        },
      },
    });
    if (!chart) return;
    chart.data.labels = payload.labels || [];
    chart.data.datasets[0].data = payload.data || [];
    chart.update();
    const sum = (payload.data || []).reduce((acc, value) => acc + Number(value || 0), 0);
    setEmptyState("poAncVisitsEmpty", sum === 0);
  };

  const renderPlaceOfBirth = (payload) => {
    chartState.placeOfBirthPayload = payload;
    const chart = ensureBarChart("placeOfBirth", "poPlaceOfBirthChart", {
      type: "bar",
      data: { labels: [], datasets: [{ label: "Place of Birth", data: [], backgroundColor: "#8e44ad", borderColor: "#6c3483", borderWidth: 1 }] },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: true } },
        scales: {
          x: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: "Count" }, grid: { display: true, color: "rgba(148,163,184,0.35)" } },
          y: { grid: { display: false } },
        },
      },
    });
    if (!chart) return;
    const mode = currentPlaceMode();
    chart.data.labels = payload.labels || [];
    chart.data.datasets[0].data = mode === "percentage" ? (payload.percentage_data || []) : (payload.count_data || []);
    chart.options.scales.x.title.text = mode === "percentage" ? "Percentage (%)" : "Count";
    chart.update();
    const sum = (payload.count_data || []).reduce((acc, value) => acc + Number(value || 0), 0);
    setEmptyState("poPlaceOfBirthEmpty", sum === 0);
  };

  const refreshMapOnly = async () => {
    const filters = getFilters();
    syncFilterHiddenFields();
    syncUrl(filters);
    if (mapController) {
      await mapController.refresh(filters);
      return;
    }
    const mapData = await fetchJSON(endpoints.map, filters);
    setEmptyState("poMapEmpty", (mapData.counts || []).length === 0);
  };

  const refreshAll = async () => {
    const filters = getFilters();
    syncFilterHiddenFields();
    syncUrl(filters);

    const [summary, trend, birthOutcomes, gestAge, anc, kpis, place] = await Promise.all([
      fetchJSON(endpoints.summary, filters),
      fetchJSON(endpoints.trend, filters),
      fetchJSON(endpoints.birthOutcomes, filters),
      fetchJSON(endpoints.gestationalAge, filters),
      fetchJSON(endpoints.ancVisits, filters),
      fetchJSON(endpoints.kpis, filters),
      fetchJSON(endpoints.placeOfBirth, filters),
    ]);

    renderSummary(summary);
    renderTrend(trend);
    renderBirthOutcomes(birthOutcomes);
    renderGestationalAge(gestAge);
    renderAncVisits(anc);
    renderKpis(kpis);
    renderPlaceOfBirth(place);
    await refreshMapOnly();
  };

  const bindEvents = () => {
    if (filterElements.form) {
      filterElements.form.addEventListener("submit", (event) => {
        event.preventDefault();
        refreshAll().catch((err) => console.error(err));
      });
    }

    if (filterElements.outcome) {
      filterElements.outcome.addEventListener("change", () =>
        refreshAll().catch((err) => console.error(err))
      );
    }
    if (filterElements.preset) {
      filterElements.preset.addEventListener("change", () => {
        if (!shouldApplyDateRangeChange()) return;
        refreshAll().catch((err) => console.error(err));
      });
    }
    if (filterElements.start) {
      filterElements.start.addEventListener("change", () => {
        if (!shouldApplyDateRangeChange()) return;
        refreshAll().catch((err) => console.error(err));
      });
    }
    if (filterElements.end) {
      filterElements.end.addEventListener("change", () => {
        if (!shouldApplyDateRangeChange()) return;
        refreshAll().catch((err) => console.error(err));
      });
    }

    if (filterElements.mapViewSelect) {
      filterElements.mapViewSelect.addEventListener("change", () => refreshMapOnly().catch((err) => console.error(err)));
    }

    if (filterElements.reset) {
      filterElements.reset.addEventListener("click", () => {
        if (filterElements.outcome) filterElements.outcome.value = "";
        if (filterElements.preset) filterElements.preset.value = "all_time";
        if (filterElements.start) filterElements.start.value = "";
        if (filterElements.end) filterElements.end.value = "";
        if (filterElements.mapViewSelect) filterElements.mapViewSelect.value = "Province";
        if (filterElements.birthCount) filterElements.birthCount.checked = true;
        if (filterElements.placeCount) filterElements.placeCount.checked = true;
        refreshAll().catch((err) => console.error(err));
      });
    }

    const rerenderBirth = () => {
      if (chartState.birthOutcomesPayload) renderBirthOutcomes(chartState.birthOutcomesPayload);
    };
    if (filterElements.birthCount) filterElements.birthCount.addEventListener("change", rerenderBirth);
    if (filterElements.birthPct) filterElements.birthPct.addEventListener("change", rerenderBirth);

    const rerenderPlace = () => {
      if (chartState.placeOfBirthPayload) renderPlaceOfBirth(chartState.placeOfBirthPayload);
    };
    if (filterElements.placeCount) filterElements.placeCount.addEventListener("change", rerenderPlace);
    if (filterElements.placePct) filterElements.placePct.addEventListener("change", rerenderPlace);
  };

  const init = async () => {
    setupDateInputs([filterElements.start, filterElements.end]);
    bindEvents();
    await refreshAll();
  };

  const resizeVisuals = () => {
    if (chartState.trend) chartState.trend.resize();
    if (chartState.birthOutcomes) chartState.birthOutcomes.resize();
    if (chartState.gestationalAge) chartState.gestationalAge.resize();
    if (chartState.ancVisits) chartState.ancVisits.resize();
    if (chartState.placeOfBirth) chartState.placeOfBirth.resize();
    if (mapController) mapController.resize();
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
