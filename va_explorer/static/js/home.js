GRAPH_OPTIONS = {
  responsive: true,
  scales: { y: { beginAtZero: true } },
  plugins: { legend: { display: false } }
};

BORDER_COLOR = "#037BFE"
const chartInstances = new WeakMap();
let novEventsChartInstance = null;
let novFiltersBound = false;
let novFilterRequestId = 0;
let novChartHeightSynced = false;
let novFilterXhr = null;
let overviewInitialized = false;
let vaStatsInitialized = false;
let trendsInitialized = false;
let homeDataPromise = null;
let homeDataCache = null;
let firstRenderMeasured = false;
const tabWarmCache = new Set();

const perfNow = () => (
  window.performance && typeof window.performance.now === "function"
    ? window.performance.now()
    : Date.now()
);
const perfLog = (name, startMs, meta) => {
  const durationMs = perfNow() - startMs;
  if (meta) {
    console.log(`[perf][home] ${name} ${durationMs.toFixed(2)}ms`, meta);
  } else {
    console.log(`[perf][home] ${name} ${durationMs.toFixed(2)}ms`);
  }
};

const getDashboardLoader = () => window.DashboardLoader || null;

const loadSlotOnce = async (slotId) => {
  const slot = document.getElementById(slotId);
  const loader = getDashboardLoader();
  if (!slot || !loader || typeof loader.loadComponentOnce !== "function") return;
  await loader.loadComponentOnce(slot);
}

const refreshSlot = async (slotId) => {
  const slot = document.getElementById(slotId);
  const loader = getDashboardLoader();
  if (!slot || !loader || typeof loader.refreshComponent !== "function") return;
  await loader.refreshComponent(slot);
}

const invalidateScope = (scopeKey) => {
  const loader = getDashboardLoader();
  if (!loader || typeof loader.invalidateComponentsByScope !== "function") return;
  loader.invalidateComponentsByScope(scopeKey);
}

const clearHomeTrendsCache = () => {
  homeDataCache = null;
  homeDataPromise = null;
}

const setVATrendsTableData = (vaTableData) => {
  const started = perfNow();
  document.getElementById('interviewed-past-24-hours').innerHTML = vaTableData.collected["24"];
  document.getElementById('interviewed-past-week').innerHTML = vaTableData.collected["1 week"];
  document.getElementById('interviewed-past-month').innerHTML =  vaTableData.collected["1 month"];
  document.getElementById('interviewed-overall').innerHTML = vaTableData.collected["Overall"];

  document.getElementById('coded-past-24-hours').innerHTML = vaTableData.coded["24"];
  document.getElementById('coded-past-week').innerHTML = vaTableData.coded["1 week"];
  document.getElementById('coded-past-month').innerHTML =  vaTableData.coded["1 month"];
  document.getElementById('coded-overall').innerHTML = vaTableData.coded["Overall"];

  document.getElementById('uncoded-past-24-hours').innerHTML = vaTableData.uncoded["24"];
  document.getElementById('uncoded-past-week').innerHTML = vaTableData.uncoded["1 week"];
  document.getElementById('uncoded-past-month').innerHTML =  vaTableData.uncoded["1 month"];
  document.getElementById('uncoded-overall').innerHTML = vaTableData.uncoded["Overall"];
  perfLog("render.va_statistics.table", started);
}

const setVARow = (root, row, isFieldWorker) => {
  if(isFieldWorker) {
    root.insertAdjacentHTML('beforebegin',
`<tr>
        <td>${row.id}</td>
        <td>${row.interviewed}</td>
        <td>${row.facility}</td>
        <td>${row.deceased}</td>
        <td>${row.dod}</td>
        <td>${row.cause}</td>
        <td>${row.warnings}</td>
        <td>${row.errors}</td>
        <td><a class="btn btn-primary" href="va_data_management/show/${row.id}">View</a></td>
      </tr>`
    )
  }
  else {
    root.insertAdjacentHTML('beforebegin',
`<tr>
        <td>${row.id}</td>
        <td>${row.interviewed}</td>
        <td>${row.interviewer}</td>
        <td>${row.facility}</td>
        <td>${row.deceased}</td>
        <td>${row.dod}</td>
        <td>${row.cause}</td>
        <td>${row.warnings}</td>
        <td>${row.errors}</td>
        <td><a class="btn btn-primary" href="va_data_management/show/${row.id}">View</a></td>
      </tr>`
    )
  }
}

const setCodingIssuesTableData = (codingIssuesData, isFieldWorker) => {
  const root = document.getElementById('coding-issues-root');
  if (!root) return;
  root.parentElement.querySelectorAll("tr:not(#coding-issues-root)").forEach((row) => row.remove());
  codingIssuesData.forEach(row => setVARow(root, row, isFieldWorker));
}

const setIndeterminateCODTableData = (codingIssuesData, isFieldWorker) => {
  const root = document.getElementById('indeterminate-cod-root');
  if (!root) return;
  root.parentElement.querySelectorAll("tr:not(#indeterminate-cod-root)").forEach((row) => row.remove());
  codingIssuesData.forEach(row => setVARow(root, row, isFieldWorker));
}

const setVAChart = (x, y, canvas) => {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const existingChart = chartInstances.get(canvas);
  if (existingChart) {
    existingChart.destroy();
  }

  const chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: x,
      datasets: [{
        data: y,
        borderColor: BORDER_COLOR,
      }]
    },
    options: GRAPH_OPTIONS,
  });
  chartInstances.set(canvas, chart);
}

const setVACharts = (graphData) => {
  const interviewedCanvas = document.getElementById("interviewedChart");
  const codedCanvas = document.getElementById("codedChart");
  const notYetCodedCanvas = document.getElementById("notYetCodedChart");
  if (!interviewedCanvas || !codedCanvas || !notYetCodedCanvas) return;
  setVAChart(graphData.collected.x, graphData.collected.y, interviewedCanvas);
  setVAChart(graphData.coded.x, graphData.coded.y, codedCanvas);
  setVAChart(graphData.uncoded.x, graphData.uncoded.y, notYetCodedCanvas);
}

const buildNovVADataset = (values) => ({
  label: "Verbal Autopsies",
  data: values || [],
  yAxisID: "yVA",
  borderColor: "#7c3aed",
  backgroundColor: "#7c3aed",
  borderWidth: 3,
  pointBackgroundColor: "#7c3aed",
  pointBorderColor: "#ffffff",
  pointBorderWidth: 1,
  tension: 0.25,
  pointRadius: 4,
  pointHoverRadius: 5,
  hidden: false,
  fill: false,
});

const initNationalOperationalEventsChart = () => {
  const canvas = document.getElementById("novEventsChart");
  if (!canvas || typeof Chart === "undefined") return;

  const parseJsonScript = (id) => {
    const node = document.getElementById(id);
    if (!node) return [];
    try {
      const parsed = JSON.parse(node.textContent);
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      console.error(`Failed to parse chart data from ${id}`, error);
      return [];
    }
  };

  const labels = parseJsonScript("nov-chart-labels");
  const pregnancyValues = parseJsonScript("nov-pregnancy-values");
  const pregnancyOutcomeValues = parseJsonScript("nov-pregnancy-outcome-values");
  const deathValues = parseJsonScript("nov-death-values");
  const vaValues = parseJsonScript("nov-va-values");

  if (novEventsChartInstance) {
    novEventsChartInstance.destroy();
  }

  novEventsChartInstance = new Chart(canvas.getContext("2d"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Pregnancy",
          data: pregnancyValues,
          borderColor: "#2d6cdf",
          backgroundColor: "#2d6cdf",
          tension: 0.25,
          pointRadius: 2,
          fill: false,
        },
        {
          label: "Pregnancy Outcome",
          data: pregnancyOutcomeValues,
          borderColor: "#f5c542",
          backgroundColor: "#f5c542",
          tension: 0.25,
          pointRadius: 2,
          fill: false,
        },
        {
          label: "Death",
          data: deathValues,
          borderColor: "#dc3545",
          backgroundColor: "#dc3545",
          tension: 0.25,
          pointRadius: 2,
          fill: false,
        },
        buildNovVADataset(vaValues),
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false,
      },
      plugins: {
        legend: { display: true, position: "top" },
        tooltip: { enabled: true },
      },
      scales: {
        x: {
          title: { display: true, text: "Date" },
          grid: { display: true, color: "rgba(148, 163, 184, 0.35)" },
        },
        y: {
          position: "left",
          beginAtZero: true,
          title: { display: true, text: "Event count" },
          grid: { display: true, color: "rgba(148, 163, 184, 0.35)" },
          ticks: { precision: 0 },
        },
        yVA: {
          position: "right",
          beginAtZero: true,
          title: { display: true, text: "VA count" },
          grid: { drawOnChartArea: false },
          ticks: { precision: 0 },
        },
      },
    },
  });
  syncNovChartHeightToKpiCards();
}

const updateNationalOperationalEventsChart = (
  labels,
  pregnancyValues,
  pregnancyOutcomeValues,
  deathValues,
  vaValues
) => {
  const started = perfNow();
  const canvas = document.getElementById("novEventsChart");
  if (!canvas || typeof Chart === "undefined") return;

  if (!novEventsChartInstance) {
    initNationalOperationalEventsChart();
  }
  if (!novEventsChartInstance) return;

  if (!novEventsChartInstance.data.datasets[3]) {
    novEventsChartInstance.data.datasets.push(buildNovVADataset([]));
  }

  novEventsChartInstance.data.labels = labels || [];
  novEventsChartInstance.data.datasets[0].data = pregnancyValues || [];
  novEventsChartInstance.data.datasets[1].data = pregnancyOutcomeValues || [];
  novEventsChartInstance.data.datasets[2].data = deathValues || [];
  novEventsChartInstance.data.datasets[3].data = vaValues || [];
  novEventsChartInstance.data.datasets[3].hidden = false;
  novEventsChartInstance.update();
  perfLog("render.overview.chart", started, { labels: (labels || []).length });
}

const syncNovChartHeightToKpiCards = () => {
  const chartWrap = document.querySelector("#novEventsChartContainer .events-chart-canvas-wrap");
  const kpiCards = document.querySelectorAll("#novKpiCardsContainer .nov-kpi-card");
  const kpiCardsGrid = document.querySelector("#novKpiCardsContainer .nov-kpi-cards");
  if (!chartWrap || !kpiCardsGrid || kpiCards.length < 4) return;

  // Only force this alignment when the two-column layout is active.
  if (window.matchMedia("(max-width: 991.98px)").matches) {
    chartWrap.style.height = "";
    if (novEventsChartInstance) novEventsChartInstance.resize();
    return;
  }

  const gap = parseFloat(window.getComputedStyle(kpiCardsGrid).rowGap || "0") || 0;
  const totalHeight =
    kpiCards[1].offsetHeight +
    kpiCards[2].offsetHeight +
    kpiCards[3].offsetHeight +
    (gap * 2);

  if (totalHeight > 0) {
    chartWrap.style.height = `${Math.round(totalHeight)}px`;
    if (novEventsChartInstance) novEventsChartInstance.resize();
  }
}

const setElementTextById = (id, value) => {
  const el = document.getElementById(id);
  if (el) el.textContent = value ?? 0;
}

const updateNationalOperationalKpis = (kpis) => {
  const started = perfNow();
  if (!kpis) return;
  const eas = kpis.eas || {};
  const households = kpis.households || {};
  const people = kpis.people || {};
  const pregnancies = kpis.pregnancies || {};
  const pregOutcomes = kpis.preg_outcomes || {};
  const deaths = kpis.deaths || {};
  const vas = kpis.vas || {};

  setElementTextById("nov-kpi-today-eas", eas.today);
  setElementTextById("nov-kpi-week-eas", eas.week);
  setElementTextById("nov-kpi-total-eas", eas.total);

  setElementTextById("nov-kpi-today-households", households.today);
  setElementTextById("nov-kpi-week-households", households.week);
  setElementTextById("nov-kpi-total-households", households.total);

  setElementTextById("nov-kpi-today-people", people.today);
  setElementTextById("nov-kpi-week-people", people.week);
  setElementTextById("nov-kpi-total-people", people.total);

  setElementTextById("nov-kpi-today-pregnancies", pregnancies.today);
  setElementTextById("nov-kpi-week-pregnancies", pregnancies.week);
  setElementTextById("nov-kpi-total-pregnancies", pregnancies.total);

  setElementTextById("nov-kpi-today-preg-outcomes", pregOutcomes.today);
  setElementTextById("nov-kpi-week-preg-outcomes", pregOutcomes.week);
  setElementTextById("nov-kpi-total-preg-outcomes", pregOutcomes.total);

  setElementTextById("nov-kpi-today-deaths", deaths.today);
  setElementTextById("nov-kpi-week-deaths", deaths.week);
  setElementTextById("nov-kpi-total-deaths", deaths.total);

  setElementTextById("nov-kpi-today-vas", vas.today);
  setElementTextById("nov-kpi-week-vas", vas.week);
  setElementTextById("nov-kpi-total-vas", vas.total);
  syncNovChartHeightToKpiCards();
  perfLog("render.overview.kpis", started);
}

const toggleNovLoadingState = (isLoading) => {
  const chartContainer = document.getElementById("novEventsChartContainer");
  const kpiContainer = document.getElementById("novKpiCardsContainer");
  [chartContainer, kpiContainer].forEach((container) => {
    if (!container) return;
    container.style.opacity = isLoading ? "0.6" : "1";
    container.style.pointerEvents = isLoading ? "none" : "auto";
  });
}

const selectedNovPreset = () => {
  if (document.getElementById("novTime30")?.checked) return "30";
  if (document.getElementById("novTime7")?.checked) return "7";
  if (document.getElementById("novTime24")?.checked) return "24";
  return "all";
}

const toDateString = (dateObj) => {
  const pad = (n) => String(n).padStart(2, "0");
  return `${dateObj.getFullYear()}-${pad(dateObj.getMonth() + 1)}-${pad(dateObj.getDate())}`;
}

const applyPresetToDatetimeInputs = (preset) => {
  const startInput = document.getElementById("novStartDatetime");
  const endInput = document.getElementById("novEndDatetime");
  if (!startInput || !endInput) return;

  if (preset === "all") {
    startInput.value = "";
    endInput.value = "";
    return;
  }

  const now = new Date();
  const start = new Date(now);
  if (preset === "30") start.setDate(start.getDate() - 30);
  if (preset === "7") start.setDate(start.getDate() - 7);
  if (preset === "24") start.setHours(start.getHours() - 24);
  startInput.value = toDateString(start);
  endInput.value = toDateString(now);
}

const clearPresetSelection = () => {
  ["novTimeAll", "novTime30", "novTime7", "novTime24"].forEach((id) => {
    const input = document.getElementById(id);
    if (input) input.checked = false;
  });
}

const NOV_LOCATION_OPTIONS = {
  national: [],
  province: ["Central", "Copperbelt", "Eastern", "Southern", "Lusaka", "Western"],
  district: ["Chirundu", "Chongwe", "Kazungula", "Lusaka", "Namwala"],
  constituency: [
    "Chirundu Constituency",
    "Chongwe Constituency",
    "Kazungula Constituency",
    "Lusaka Central Constituency",
    "Namwala Constituency",
  ],
  ward: [
    "Chirundu Ward",
    "Kanakantapa Ward",
    "Kazungula Ward",
    "Kanyama Ward",
    "Namwala Central Ward",
  ],
}

const updateNovLocationValueOptions = () => {
  const levelSelect = document.getElementById("novLocationLevel");
  const valueSelect = document.getElementById("novLocationValue");
  if (!levelSelect || !valueSelect) return;

  const level = levelSelect.value || "national";
  const options = NOV_LOCATION_OPTIONS[level] || [];
  const disableValue = level === "national" || options.length === 0;

  valueSelect.innerHTML = "";
  if (disableValue) {
    valueSelect.disabled = true;
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "All National";
    valueSelect.appendChild(option);
    return;
  }

  valueSelect.disabled = false;
  options.forEach((item, index) => {
    const option = document.createElement("option");
    option.value = item;
    option.textContent = item;
    if (index === 0) option.selected = true;
    valueSelect.appendChild(option);
  });
}

const requestNationalOperationalFilterData = (options = {}) => {
  const started = perfNow();
  const shouldInvalidate = Boolean(options.invalidateScope);
  if (shouldInvalidate) {
    invalidateScope("overview-data");
  }
  const root = document.getElementById("national-operational-view");
  if (!root) return;
  const endpoint = root.dataset.filterUrl;
  if (!endpoint) return;

  const startInput = document.getElementById("novStartDatetime");
  const endInput = document.getElementById("novEndDatetime");
  const requestId = ++novFilterRequestId;

  if (novFilterXhr && typeof novFilterXhr.abort === "function") {
    novFilterXhr.abort();
  }
  toggleNovLoadingState(true);
  novFilterXhr = $.ajax({
    url: endpoint,
    type: "GET",
    dataType: "json",
    data: {
      preset: selectedNovPreset(),
      start: startInput?.value || "",
      end: endInput?.value || "",
      location_level: document.getElementById("novLocationLevel")?.value || "national",
      location_value: document.getElementById("novLocationValue")?.value || "",
    },
    success: (jsonResponse) => {
      if (requestId !== novFilterRequestId) return;
      updateNationalOperationalEventsChart(
        jsonResponse.chart_labels || [],
        jsonResponse.pregnancy_values || [],
        jsonResponse.pregnancy_outcome_values || [],
        jsonResponse.death_values || [],
        jsonResponse.va_values || jsonResponse.verbal_autopsy_values || []
      );
      updateNationalOperationalKpis(jsonResponse.kpis || {});
      perfLog("fetch.overview.filter_data", started, { requestId });
    },
    complete: () => {
      if (requestId === novFilterRequestId) {
        novFilterXhr = null;
        toggleNovLoadingState(false);
      }
    },
    error: () => console.log("Failed to fetch National Operational View filter data"),
  });
}

const initNationalOperationalFilters = () => {
  const root = document.getElementById("national-operational-view");
  if (!root || novFiltersBound) return;
  novFiltersBound = true;

  ["novTimeAll", "novTime30", "novTime7", "novTime24"].forEach((id) => {
    const radio = document.getElementById(id);
    if (!radio) return;
    radio.addEventListener("change", () => {
      if (!radio.checked) return;
      const preset = selectedNovPreset();
      applyPresetToDatetimeInputs(preset);
      requestNationalOperationalFilterData({ invalidateScope: true });
    });
  });

  const startInput = document.getElementById("novStartDatetime");
  const endInput = document.getElementById("novEndDatetime");
  const locationLevel = document.getElementById("novLocationLevel");
  const locationValue = document.getElementById("novLocationValue");

  updateNovLocationValueOptions();

  if (locationLevel) {
    locationLevel.addEventListener("change", () => {
      updateNovLocationValueOptions();
      requestNationalOperationalFilterData({ invalidateScope: true });
    });
  }

  if (locationValue) {
    locationValue.addEventListener("change", () => {
      requestNationalOperationalFilterData({ invalidateScope: true });
    });
  }

  [startInput, endInput].forEach((input) => {
    if (!input) return;
    input.addEventListener("change", () => {
      clearPresetSelection();
      requestNationalOperationalFilterData({ invalidateScope: true });
    });
  });
}

const initNovChartHeightSync = () => {
  if (novChartHeightSynced) return;
  novChartHeightSynced = true;

  const runSync = () => syncNovChartHeightToKpiCards();
  window.addEventListener("resize", runSync);
  runSync();
}

const setSingleMetricTrendsTableData = (prefix, trendTable) => {
  const row = (trendTable && trendTable.recorded) ? trendTable.recorded : {};
  const values = {
    "24-hours": row["24"] || 0,
    "week": row["1 week"] || 0,
    "month": row["1 month"] || 0,
    "overall": row["Overall"] || 0,
  };

  Object.entries(values).forEach(([suffix, value]) => {
    const el = document.getElementById(`${prefix}-past-${suffix}`);
    if (el) el.innerHTML = value;
  });
}

const setSingleMetricTrendChart = (canvasId, trendGraphs) => {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !trendGraphs || !trendGraphs.recorded) return;
  const x = trendGraphs.recorded.x || [];
  const y = trendGraphs.recorded.y || [];
  setVAChart(x, y, canvas);
}

const setModelTrendVisualizations = (modelTrends) => {
  if (!modelTrends) return;

  const households = modelTrends.households || {};
  setSingleMetricTrendsTableData("households", households.table);
  setSingleMetricTrendChart("householdsChart", households.graphs);

  const pregnancies = modelTrends.pregnancies || {};
  setSingleMetricTrendsTableData("pregnancies", pregnancies.table);
  setSingleMetricTrendChart("pregnanciesChart", pregnancies.graphs);

  const pregnancyOutcomes = modelTrends.pregnancy_outcomes || {};
  setSingleMetricTrendsTableData("pregnancy-outcomes", pregnancyOutcomes.table);
  setSingleMetricTrendChart("pregnancyOutcomesChart", pregnancyOutcomes.graphs);

  const deaths = modelTrends.deaths || {};
  setSingleMetricTrendsTableData("deaths", deaths.table);
  setSingleMetricTrendChart("deathsChart", deaths.graphs);
}

const applyVAStatisticsPayload = (jsonResponse) => {
  const started = perfNow();
  if (!jsonResponse) return;

  setVATrendsTableData(jsonResponse.vaTable || {});
  setVACharts(jsonResponse.graphs || {});

  if ((jsonResponse.issueList || []).length > 0) {
    setCodingIssuesTableData(jsonResponse.issueList, jsonResponse.isFieldWorker);
    $('#coding-issues').removeClass('hidden');
    $('#no-coding-issues').addClass('hidden');

    if (jsonResponse.additionalIssues > 0) {
      document.getElementById('additional-issues-count').innerHTML = jsonResponse.additionalIssues;
      $('#additional-issues-msg').removeClass('hidden');
    } else {
      $('#additional-issues-msg').addClass('hidden');
    }
  } else {
    $('#coding-issues').addClass('hidden');
    $('#additional-issues-msg').addClass('hidden');
    $('#no-coding-issues').removeClass('hidden');
  }

  if ((jsonResponse.indeterminateCodList || []).length > 0) {
    setIndeterminateCODTableData(jsonResponse.indeterminateCodList, jsonResponse.isFieldWorker);
    $('#indeterminate-cod').removeClass('hidden');
    $('#no-indeterminate-cod').addClass('hidden');

    if (jsonResponse.additionalIndeterminateCods > 0) {
      document.getElementById('additional-indeterminate-cods-count').innerHTML =
        jsonResponse.additionalIndeterminateCods;
      $('#additional-indeterminate-cods-msg').removeClass('hidden');
    } else {
      $('#additional-indeterminate-cods-msg').addClass('hidden');
    }
  } else {
    $('#indeterminate-cod').addClass('hidden');
    $('#additional-indeterminate-cods-msg').addClass('hidden');
    $('#no-indeterminate-cod').removeClass('hidden');
  }
  perfLog("render.va_statistics.components", started);
}

const applyTrendsPayload = (jsonResponse) => {
  const started = perfNow();
  if (!jsonResponse) return;
  setModelTrendVisualizations(jsonResponse.modelTrends || {});
  perfLog("render.trends.components", started);
}

const fetchHomeTrendsPayload = () => {
  if (homeDataCache) return Promise.resolve(homeDataCache);
  if (homeDataPromise) return homeDataPromise;

  homeDataPromise = new Promise((resolve, reject) => {
    $.ajax({
      url: "/trends/",
      type: "GET",
      dataType: "json",
      success: (jsonResponse) => {
        homeDataCache = jsonResponse;
        resolve(jsonResponse);
      },
      error: () => {
        homeDataPromise = null;
        reject(new Error("Failed to fetch chart data from /trends/"));
      },
    });
  });
  return homeDataPromise;
}

const resizeChartsForTab = (tab) => {
  const mapByTab = {
    overview: ["novEventsChart"],
    trends: ["householdsChart", "pregnanciesChart", "pregnancyOutcomesChart", "deathsChart"],
    va_statistics: ["interviewedChart", "codedChart", "notYetCodedChart"],
  };
  (mapByTab[tab] || []).forEach((id) => {
    const canvas = document.getElementById(id);
    if (!canvas) return;
    const chart = chartInstances.get(canvas);
    if (chart) chart.resize();
  });
  if (tab === "overview" && novEventsChartInstance) novEventsChartInstance.resize();
}

const initOverviewTab = async () => {
  await Promise.all([
    loadSlotOnce("novEventsComponentSlot"),
    loadSlotOnce("novKpisComponentSlot"),
  ]);

  if (overviewInitialized) {
    syncNovChartHeightToKpiCards();
    resizeChartsForTab("overview");
    return;
  }
  overviewInitialized = true;
  initNationalOperationalEventsChart();
  initNationalOperationalFilters();
  initNovChartHeightSync();
  requestNationalOperationalFilterData();
}

const initVAStatisticsTab = async () => {
  await loadSlotOnce("homeVAStatisticsComponentSlot");

  if (vaStatsInitialized) {
    resizeChartsForTab("va_statistics");
    return;
  }
  vaStatsInitialized = true;
  try {
    const payload = await fetchHomeTrendsPayload();
    applyVAStatisticsPayload(payload);
    resizeChartsForTab("va_statistics");
  } catch (error) {
    console.error(error);
  }
}

const initTrendsTab = async () => {
  await loadSlotOnce("homeTrendsComponentSlot");

  if (trendsInitialized) {
    resizeChartsForTab("trends");
    return;
  }
  trendsInitialized = true;
  try {
    const payload = await fetchHomeTrendsPayload();
    applyTrendsPayload(payload);
    resizeChartsForTab("trends");
  } catch (error) {
    console.error(error);
  }
}

const initOperationsTab = async () => {
  await Promise.all([
    loadSlotOnce("regionalFiltersComponent"),
    loadSlotOnce("regionalCsaComponent"),
    loadSlotOnce("regionalMsoComponent"),
  ]);
}

const initHomeTab = async (tab) => {
  const started = perfNow();
  if (tab === "overview") {
    await initOverviewTab();
    perfLog("tab.init.overview", started);
    return;
  }
  if (tab === "va_statistics") {
    await initVAStatisticsTab();
    perfLog("tab.init.va_statistics", started);
    return;
  }
  if (tab === "trends") {
    await initTrendsTab();
    perfLog("tab.init.trends", started);
    return;
  }
  if (tab === "operations_supervision") {
    await initOperationsTab();
    perfLog("tab.init.operations_supervision", started);
  }
}

const detectActiveHomeTab = () =>
  document.querySelector(".dashboard-shell[data-shell='home'] .dashboard-tab-panel.show.active")?.dataset?.tabPanel
  || "overview";

const initialStarted = perfNow();
initHomeTab(detectActiveHomeTab())
  .then(() => {
    perfLog("initial.page_bootstrap", initialStarted, { activeTab: detectActiveHomeTab() });
    if (!firstRenderMeasured) {
      firstRenderMeasured = true;
      console.log("[perf][acceptance] home.first_render_ms", {
        durationMs: Number((perfNow() - initialStarted).toFixed(2)),
      });
    }
  })
  .catch((error) => console.error(error));

document.querySelectorAll(".dashboard-shell[data-shell='home'] [data-tab]").forEach((tabLink) => {
  tabLink.addEventListener("click", () => {
    console.log("[perf][home] ui.tab_click", { tab: tabLink.dataset.tab });
  });
});

document.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-action='refresh-component']");
  if (!trigger) return;
  const targetSelector = trigger.dataset.target || "";
  if (targetSelector === "#homeTrendsComponentSlot" || targetSelector === "#homeVAStatisticsComponentSlot") {
    clearHomeTrendsCache();
    invalidateScope("trends-data");
  }
  if (targetSelector === "#novEventsComponentSlot" || targetSelector === "#novKpisComponentSlot") {
    invalidateScope("overview-data");
  }
});

document.addEventListener("dashboard:component-loaded", (event) => {
  const slot = event.target;
  if (!slot || !slot.id) return;

  if (slot.id === "homeTrendsComponentSlot" && trendsInitialized) {
    fetchHomeTrendsPayload()
      .then((payload) => {
        applyTrendsPayload(payload);
        resizeChartsForTab("trends");
      })
      .catch((error) => console.error(error));
    return;
  }

  if (slot.id === "homeVAStatisticsComponentSlot" && vaStatsInitialized) {
    fetchHomeTrendsPayload()
      .then((payload) => {
        applyVAStatisticsPayload(payload);
        resizeChartsForTab("va_statistics");
      })
      .catch((error) => console.error(error));
    return;
  }

  if (slot.id === "novEventsComponentSlot" && overviewInitialized) {
    if (novEventsChartInstance) {
      novEventsChartInstance.destroy();
      novEventsChartInstance = null;
    }
    initNationalOperationalEventsChart();
    requestNationalOperationalFilterData();
    return;
  }

  if (slot.id === "novKpisComponentSlot" && overviewInitialized) {
    requestNationalOperationalFilterData();
  }
});

document.addEventListener("dashboard:refresh-tab", (event) => {
  const detail = event?.detail || {};
  if (detail.shell !== "home") return;
  const tab = detail.tab || "";
  const started = perfNow();
  initHomeTab(tab)
    .then(() => {
      const durationMs = perfNow() - started;
      if (tabWarmCache.has(tab)) {
        const nearInstantThresholdMs = 220;
        const pass = durationMs <= nearInstantThresholdMs;
        console.log("[perf][acceptance] tab_switch_cached", {
          tab,
          durationMs: Number(durationMs.toFixed(2)),
          thresholdMs: nearInstantThresholdMs,
          pass,
        });
      } else {
        tabWarmCache.add(tab);
      }
    })
    .catch((error) => console.error(error));
});
