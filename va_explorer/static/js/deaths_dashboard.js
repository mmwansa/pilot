(function () {
  const app = document.getElementById("deathsDashboardApp");
  if (!app) return;

  const endpoints = {
    summary: app.dataset.summaryEndpoint,
    trend: app.dataset.trendEndpoint,
    map: app.dataset.mapEndpoint,
    ageSex: app.dataset.ageSexEndpoint,
    place: app.dataset.placeEndpoint,
    topCauses: app.dataset.topCausesEndpoint,
    causeTrend: app.dataset.causeTrendEndpoint,
    signals: app.dataset.signalsEndpoint,
    timeliness: app.dataset.timelinessEndpoint,
  };

  const filterElements = {
    form: document.getElementById("deathsFiltersForm"),
    preset: document.getElementById("deathsFilterTimePreset"),
    start: document.getElementById("deathsFilterStartDatetime"),
    end: document.getElementById("deathsFilterEndDatetime"),
    sex: document.getElementById("deathsFilterSex"),
    ageGroup: document.getElementById("deathsFilterAgeGroup"),
    place: document.getElementById("deathsFilterPlace"),
    codedOnly: document.getElementById("deathsFilterCodedOnly"),
    mapView: document.getElementById("deathsMapViewSelect"),
    reset: document.getElementById("deathsFiltersReset"),
    ageSexCount: document.getElementById("deathsAgeSexModeCount"),
    ageSexPercentage: document.getElementById("deathsAgeSexModePercentage"),
    placeCount: document.getElementById("deathsPlaceModeCount"),
    placePercentage: document.getElementById("deathsPlaceModePercentage"),
    topCauseCount: document.getElementById("deathsTopCauseModeCount"),
    topCausePercentage: document.getElementById("deathsTopCauseModePercentage"),
  };

  const mapState = {
    map: null,
    layer: null,
    geojson: null,
    colors: ["#4575b4", "#74add1", "#abd9e9", "#e0f3f8", "#fee090", "#fdae61", "#f46d43", "#d73027"],
  };

  let trendChart = null;
  let ageSexChart = null;
  let placeChart = null;
  let topCausesChart = null;
  let causeTrendChart = null;
  let timelinessChart = null;
  let ageSexPayload = null;
  let placePayload = null;
  let topCausesPayload = null;

  const currentAgeSexMode = () =>
    filterElements.ageSexPercentage?.checked ? "percentage" : "count";
  const currentPlaceMode = () =>
    filterElements.placePercentage?.checked ? "percentage" : "count";
  const currentTopCauseMode = () =>
    filterElements.topCausePercentage?.checked ? "percentage" : "count";

  const normalizeGeoName = (value) =>
    (value || "")
      .toString()
      .toLowerCase()
      .replace(/province|district/g, "")
      .replace(/\s+/g, " ")
      .trim();

  const getFilters = () => ({
    time_preset: filterElements.preset?.value || "all_time",
    start_datetime: filterElements.start?.value || "",
    end_datetime: filterElements.end?.value || "",
    sex: filterElements.sex?.value || "",
    age_group: filterElements.ageGroup?.value || "",
    place_of_death: filterElements.place?.value || "",
    coded_only: filterElements.codedOnly?.checked ? "1" : "",
    map_view: filterElements.mapView?.value || "Province",
  });

  const buildParams = (filters) => {
    const params = new URLSearchParams();
    if (filters.time_preset && filters.time_preset !== "all_time") params.set("time_preset", filters.time_preset);
    if (filters.start_datetime) params.set("start_datetime", filters.start_datetime);
    if (filters.end_datetime) params.set("end_datetime", filters.end_datetime);
    if (filters.sex) params.set("sex", filters.sex);
    if (filters.age_group) params.set("age_group", filters.age_group);
    if (filters.place_of_death) params.set("place_of_death", filters.place_of_death);
    if (filters.coded_only) params.set("coded_only", filters.coded_only);
    if (filters.map_view) params.set("map_view", filters.map_view);
    return params;
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

  const setEmpty = (id, isEmpty) => {
    const el = document.getElementById(id);
    if (el) el.hidden = !isEmpty;
  };

  const renderSummary = (payload) => {
    const setText = (id, value) => {
      const el = document.getElementById(id);
      if (el) el.textContent = value;
    };

    setText("deathsCardLastDataUpdate", payload.death_card_last_data_update || "N/A");
    setText("deathsCardLastDeathDate", payload.death_card_last_death_date || "N/A");
    setText("deathsCardTotalEvents", payload.death_card_total_events ?? 0);
    setText("deathsCardUnder5Pct", `${payload.death_card_under_5_pct ?? 0}%`);
    setText(
      "deathsCardMedianDelayDays",
      payload.death_card_median_delay_days != null ? payload.death_card_median_delay_days : "N/A"
    );
  };

  const renderSignals = (payload) => {
    const formatDiff = (value) => {
      const num = Number(value || 0);
      return `${num >= 0 ? "+" : ""}${num}`;
    };

    const formatPct = (value) => {
      if (value == null) return "N/A";
      const num = Number(value);
      return `${num >= 0 ? "+" : ""}${num.toFixed(1)}%`;
    };

    const setSignalText = (id, metric) => {
      const el = document.getElementById(id);
      if (!el) return;
      const status = metric?.flag ? "Alert" : "Normal";
      el.textContent = `Diff: ${formatDiff(metric?.difference)} | Change: ${formatPct(metric?.percent_change)} | Status: ${status}`;
    };

    setSignalText("signalAll7d", payload.all_deaths_7d);
    setSignalText("signalAll30d", payload.all_deaths_30d);
    setSignalText("signalU57d", payload.under5_deaths_7d);
    setSignalText("signalU530d", payload.under5_deaths_30d);
  };

  const renderTrend = (payload) => {
    const canvas = document.getElementById("deathsTrendChart");
    if (!canvas || typeof Chart === "undefined") return;

    if (!trendChart) {
      trendChart = new Chart(canvas.getContext("2d"), {
        type: "line",
        data: {
          labels: [],
          datasets: [{
            label: "Deaths",
            data: [],
            borderColor: "#d73027",
            backgroundColor: "rgba(215, 48, 39, 0.2)",
            pointRadius: 2,
            tension: 0.25,
            fill: false,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: true, position: "top" }, tooltip: { enabled: true } },
          scales: {
            x: { title: { display: true, text: "Month" }, grid: { display: true, color: "rgba(148, 163, 184, 0.35)" } },
            y: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: "Count of deaths" }, grid: { display: true, color: "rgba(148, 163, 184, 0.35)" } },
          },
        },
      });
    }

    trendChart.data.labels = payload.labels || [];
    trendChart.data.datasets[0].data = payload.data || [];
    trendChart.update();

    const total = (payload.data || []).reduce((acc, value) => acc + Number(value || 0), 0);
    setEmpty("deathsTrendEmpty", total === 0);
  };

  const buildLookup = (rows) => {
    const map = new Map();
    (rows || []).forEach((row) => {
      const name = normalizeGeoName(row.name);
      if (name) map.set(name, Number(row.count || 0));
    });
    return map;
  };

  const computeBins = (values) => {
    const nonZero = values.filter((v) => v > 0);
    if (!nonZero.length) return [0];
    const max = Math.max(...nonZero);
    const steps = Math.min(mapState.colors.length, 6);
    const bins = [1];
    const width = Math.max(1, Math.ceil(max / steps));
    for (let i = 1; i <= steps; i += 1) bins.push(i * width);
    return bins;
  };

  const getColorForCount = (count, bins) => {
    if (!count || count <= 0) return "#c0c0c0";
    for (let i = 0; i < bins.length - 1; i += 1) {
      if (count >= bins[i] && count <= bins[i + 1]) return mapState.colors[Math.min(i, mapState.colors.length - 1)];
    }
    return mapState.colors[Math.min(bins.length - 2, mapState.colors.length - 1)];
  };

  const renderMapLegend = (bins) => {
    const legend = document.getElementById("deathsMapLegend");
    if (!legend) return;

    if (!bins || bins.length <= 1) {
      legend.innerHTML = "<div>No mapped deaths in current filter range.</div>";
      setEmpty("deathsMapEmpty", true);
      return;
    }

    let html = "<div><svg width='18' height='14'><rect fill='#c0c0c0' width='14' height='14'></rect></svg>0</div>";
    for (let i = 0; i < bins.length - 1; i += 1) {
      const label = i === bins.length - 2 ? `${bins[i]}+` : `${bins[i]} - ${bins[i + 1]}`;
      html += `<div><svg width='18' height='14'><rect fill='${mapState.colors[i]}' width='14' height='14'></rect></svg>${label}</div>`;
    }
    legend.innerHTML = html;
    setEmpty("deathsMapEmpty", false);
  };

  const ensureMap = async () => {
    if (mapState.map || typeof L === "undefined") return;

    mapState.map = L.map("deathsMapContainer", { maxBounds: [[-6, 20], [-20, 34]] }).setView([-13, 27], 6);
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
    const bins = computeBins(Array.from(lookup.values()));

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
        const color = getColorForCount(count, bins);
        return { stroke: true, weight: 2, color, opacity: 1, fillColor: color, fillOpacity: 0.7 };
      },
      onEachFeature: (feature, layer) => {
        const level = feature?.properties?.area_level_label;
        if (level === "Country") return;
        const areaNameRaw = feature?.properties?.area_name || "";
        const areaName = normalizeGeoName(areaNameRaw);
        const count = lookup.get(areaName) || 0;
        layer.bindTooltip(`<div class=\"mapTooltip\"><h4>${areaNameRaw} ${level}</h4><p>${count}</p></div>`);
      },
    }).addTo(mapState.map);

    renderMapLegend(bins);
    mapState.map.invalidateSize();
  };

  const renderAgeSex = (payload) => {
    ageSexPayload = payload;
    const canvas = document.getElementById("deathsAgeSexChart");
    if (!canvas || typeof Chart === "undefined") return;

    if (!ageSexChart) {
      ageSexChart = new Chart(canvas.getContext("2d"), {
        type: "bar",
        data: {
          labels: [],
          datasets: [
            { label: "Male", data: [], backgroundColor: "#4b84ce", borderColor: "#2f6ec2", borderWidth: 1 },
            { label: "Female", data: [], backgroundColor: "#f46d43", borderColor: "#d73027", borderWidth: 1 },
            { label: "Unknown/Other", data: [], backgroundColor: "#9aa4b2", borderColor: "#6b7280", borderWidth: 1 },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: true, position: "top" }, tooltip: { enabled: true } },
          scales: {
            x: { stacked: true, grid: { display: false } },
            y: {
              stacked: true,
              beginAtZero: true,
              ticks: { precision: 0 },
              title: { display: true, text: "Count of deaths" },
              grid: { display: true, color: "rgba(148, 163, 184, 0.35)" },
            },
          },
        },
      });
    }

    const labels = payload.labels || [];
    const male = payload.male || [];
    const female = payload.female || [];
    const other = payload.other || [];
    const mode = currentAgeSexMode();

    let maleData = male;
    let femaleData = female;
    let otherData = other;

    if (mode === "percentage") {
      maleData = [];
      femaleData = [];
      otherData = [];
      for (let i = 0; i < labels.length; i += 1) {
        const m = Number(male[i] || 0);
        const f = Number(female[i] || 0);
        const o = Number(other[i] || 0);
        const total = m + f + o;
        maleData.push(total ? Number(((m / total) * 100).toFixed(1)) : 0);
        femaleData.push(total ? Number(((f / total) * 100).toFixed(1)) : 0);
        otherData.push(total ? Number(((o / total) * 100).toFixed(1)) : 0);
      }
      ageSexChart.options.scales.y.max = 100;
      ageSexChart.options.scales.y.title.text = "Percentage (%)";
    } else {
      ageSexChart.options.scales.y.max = undefined;
      ageSexChart.options.scales.y.title.text = "Count of deaths";
    }

    ageSexChart.data.labels = labels;
    ageSexChart.data.datasets[0].data = maleData;
    ageSexChart.data.datasets[1].data = femaleData;
    ageSexChart.data.datasets[2].data = otherData;
    ageSexChart.update();

    const total = []
      .concat(payload.male || [], payload.female || [], payload.other || [])
      .reduce((acc, value) => acc + Number(value || 0), 0);
    setEmpty("deathsAgeSexEmpty", total === 0);
  };

  const renderPlace = (payload) => {
    placePayload = payload;
    const canvas = document.getElementById("deathsPlaceChart");
    if (!canvas || typeof Chart === "undefined") return;

    if (!placeChart) {
      placeChart = new Chart(canvas.getContext("2d"), {
        type: "bar",
        data: {
          labels: [],
          datasets: [{
            label: "Place of Death",
            data: [],
            backgroundColor: "#8e44ad",
            borderColor: "#6c3483",
            borderWidth: 1,
          }],
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: { enabled: true } },
          scales: {
            x: {
              beginAtZero: true,
              ticks: { precision: 0 },
              title: { display: true, text: "Count" },
              grid: { display: true, color: "rgba(148,163,184,0.35)" },
            },
            y: { grid: { display: false } },
          },
        },
      });
    }

    const mode = currentPlaceMode();
    placeChart.data.labels = payload.labels || [];
    placeChart.data.datasets[0].data =
      mode === "percentage" ? (payload.percentage_data || []) : (payload.count_data || []);
    placeChart.options.scales.x.title.text = mode === "percentage" ? "Percentage (%)" : "Count";
    if (mode === "percentage") {
      placeChart.options.scales.x.max = 100;
    } else {
      placeChart.options.scales.x.max = undefined;
    }
    placeChart.update();

    const total = (payload.count_data || []).reduce((acc, value) => acc + Number(value || 0), 0);
    setEmpty("deathsPlaceEmpty", total === 0);
  };

  const renderTimeliness = (payload) => {
    const canvas = document.getElementById("deathsTimelinessChart");
    if (!canvas || typeof Chart === "undefined") return;

    if (!timelinessChart) {
      timelinessChart = new Chart(canvas.getContext("2d"), {
        type: "bar",
        data: {
          labels: [],
          datasets: [{
            label: "Deaths",
            data: [],
            backgroundColor: "#6c8ebf",
            borderColor: "#4b6b9c",
            borderWidth: 1,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: { enabled: true } },
          scales: {
            x: { title: { display: true, text: "Delay category (days)" }, grid: { display: false } },
            y: {
              beginAtZero: true,
              ticks: { precision: 0 },
              title: { display: true, text: "Count of reports" },
              grid: { display: true, color: "rgba(148, 163, 184, 0.35)" },
            },
          },
        },
      });
    }

    timelinessChart.data.labels = payload.labels || [];
    timelinessChart.data.datasets[0].data = payload.data || [];
    timelinessChart.update();

    const total = (payload.data || []).reduce((acc, value) => acc + Number(value || 0), 0);
    setEmpty("deathsTimelinessEmpty", total === 0);
  };

  const renderTopCauses = (payload) => {
    topCausesPayload = payload;
    const canvas = document.getElementById("deathsTopCausesChart");
    if (!canvas || typeof Chart === "undefined") return;

    if (!topCausesChart) {
      topCausesChart = new Chart(canvas.getContext("2d"), {
        type: "bar",
        data: {
          labels: [],
          datasets: [{
            label: "Top causes",
            data: [],
            backgroundColor: "#556b8e",
            borderColor: "#3f516b",
            borderWidth: 1,
          }],
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: { enabled: true } },
          scales: {
            x: {
              beginAtZero: true,
              ticks: { precision: 0 },
              title: { display: true, text: "Count" },
              grid: { display: true, color: "rgba(148,163,184,0.35)" },
            },
            y: { grid: { display: false } },
          },
        },
      });
    }

    const mode = currentTopCauseMode();
    topCausesChart.data.labels = payload.labels || [];
    topCausesChart.data.datasets[0].data =
      mode === "percentage" ? (payload.percentage_data || []) : (payload.count_data || []);
    topCausesChart.options.scales.x.title.text = mode === "percentage" ? "Percentage (%)" : "Count";
    topCausesChart.options.scales.x.max = mode === "percentage" ? 100 : undefined;
    topCausesChart.update();

    const hasCoded = !!payload.has_coded;
    const total = (payload.count_data || []).reduce((acc, value) => acc + Number(value || 0), 0);
    setEmpty("deathsTopCausesEmpty", !hasCoded || total === 0);
  };

  const renderCauseTrend = (payload) => {
    const canvas = document.getElementById("deathsCauseTrendChart");
    if (!canvas || typeof Chart === "undefined") return;

    if (!causeTrendChart) {
      causeTrendChart = new Chart(canvas.getContext("2d"), {
        type: "line",
        data: { labels: [], datasets: [] },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: true, position: "top" }, tooltip: { enabled: true } },
          scales: {
            x: { title: { display: true, text: "Month" }, grid: { display: true, color: "rgba(148, 163, 184, 0.35)" } },
            y: {
              beginAtZero: true,
              ticks: { precision: 0 },
              title: { display: true, text: "Count of deaths" },
              grid: { display: true, color: "rgba(148, 163, 184, 0.35)" },
            },
          },
        },
      });
    }

    const palette = ["#d73027", "#4575b4", "#4CAF50", "#f46d43", "#8e44ad"];
    causeTrendChart.data.labels = payload.labels || [];
    causeTrendChart.data.datasets = (payload.datasets || []).map((series, idx) => ({
      label: series.label,
      data: series.data || [],
      borderColor: palette[idx % palette.length],
      backgroundColor: palette[idx % palette.length],
      pointRadius: 2,
      tension: 0.25,
      fill: false,
    }));
    causeTrendChart.update();

    const hasCoded = !!payload.has_coded;
    const total = (payload.datasets || [])
      .flatMap((series) => series.data || [])
      .reduce((acc, value) => acc + Number(value || 0), 0);
    setEmpty("deathsCauseTrendEmpty", !hasCoded || total === 0);
  };

  const refreshAll = async () => {
    const filters = getFilters();
    const [
      summaryPayload,
      trendPayload,
      mapPayload,
      ageSexPayloadResp,
      placePayloadResp,
      topCausesPayloadResp,
      causeTrendPayloadResp,
      signalsPayload,
      timelinessPayload,
    ] = await Promise.all([
      fetchJSON(endpoints.summary, filters),
      fetchJSON(endpoints.trend, filters),
      fetchJSON(endpoints.map, filters),
      fetchJSON(endpoints.ageSex, filters),
      fetchJSON(endpoints.place, filters),
      fetchJSON(endpoints.topCauses, filters),
      fetchJSON(endpoints.causeTrend, filters),
      fetchJSON(endpoints.signals, filters),
      fetchJSON(endpoints.timeliness, filters),
    ]);

    renderSummary(summaryPayload);
    renderSignals(signalsPayload);
    renderTrend(trendPayload);
    await renderMap(mapPayload);
    renderAgeSex(ageSexPayloadResp);
    renderPlace(placePayloadResp);
    renderTopCauses(topCausesPayloadResp);
    renderCauseTrend(causeTrendPayloadResp);
    renderTimeliness(timelinessPayload);
  };

  const bindEvents = () => {
    if (filterElements.form) {
      filterElements.form.addEventListener("submit", (event) => {
        event.preventDefault();
        refreshAll().catch((err) => console.error(err));
      });
    }

    [
      filterElements.preset,
      filterElements.start,
      filterElements.end,
      filterElements.sex,
      filterElements.ageGroup,
      filterElements.place,
      filterElements.codedOnly,
      filterElements.mapView,
    ].forEach((el) => {
      if (!el) return;
      el.addEventListener("change", () => refreshAll().catch((err) => console.error(err)));
    });

    if (filterElements.reset) {
      filterElements.reset.addEventListener("click", () => {
        if (filterElements.preset) filterElements.preset.value = "all_time";
        if (filterElements.start) filterElements.start.value = "";
        if (filterElements.end) filterElements.end.value = "";
        if (filterElements.sex) filterElements.sex.value = "";
        if (filterElements.ageGroup) filterElements.ageGroup.value = "";
        if (filterElements.place) filterElements.place.value = "";
        if (filterElements.codedOnly) filterElements.codedOnly.checked = false;
        if (filterElements.mapView) filterElements.mapView.value = "Province";
        if (filterElements.ageSexCount) filterElements.ageSexCount.checked = true;
        if (filterElements.placeCount) filterElements.placeCount.checked = true;
        if (filterElements.topCauseCount) filterElements.topCauseCount.checked = true;
        refreshAll().catch((err) => console.error(err));
      });
    }

    const rerenderAgeSex = () => {
      if (ageSexPayload) renderAgeSex(ageSexPayload);
    };
    if (filterElements.ageSexCount) {
      filterElements.ageSexCount.addEventListener("change", rerenderAgeSex);
    }
    if (filterElements.ageSexPercentage) {
      filterElements.ageSexPercentage.addEventListener("change", rerenderAgeSex);
    }

    const rerenderPlace = () => {
      if (placePayload) renderPlace(placePayload);
    };
    if (filterElements.placeCount) {
      filterElements.placeCount.addEventListener("change", rerenderPlace);
    }
    if (filterElements.placePercentage) {
      filterElements.placePercentage.addEventListener("change", rerenderPlace);
    }

    const rerenderTopCauses = () => {
      if (topCausesPayload) renderTopCauses(topCausesPayload);
    };
    if (filterElements.topCauseCount) {
      filterElements.topCauseCount.addEventListener("change", rerenderTopCauses);
    }
    if (filterElements.topCausePercentage) {
      filterElements.topCausePercentage.addEventListener("change", rerenderTopCauses);
    }
  };

  const init = async () => {
    bindEvents();
    await refreshAll();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => init().catch((err) => console.error(err)));
  } else {
    init().catch((err) => console.error(err));
  }
})();
