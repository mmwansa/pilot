GRAPH_OPTIONS = {
  responsive: true,
  scales: { y: { beginAtZero: true } },
  plugins: { legend: { display: false } }
};

BORDER_COLOR = "#037BFE"
let novEventsChartInstance = null;
let novFiltersBound = false;
let novFilterRequestId = 0;
let novChartHeightSynced = false;

const setVATrendsTableData = (vaTableData) => {
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
  codingIssuesData.forEach(row => setVARow(root, row, isFieldWorker));
}

const setIndeterminateCODTableData = (codingIssuesData, isFieldWorker) => {
  const root = document.getElementById('indeterminate-cod-root');
  codingIssuesData.forEach(row => setVARow(root, row, isFieldWorker));
}

const setVAChart = (x, y, ctx) => {
  new Chart(ctx, {
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
}

const setVACharts = (graphData) => {
  const interviewedCanvas = document.getElementById("interviewedChart");
  const codedCanvas = document.getElementById("codedChart");
  const notYetCodedCanvas = document.getElementById("notYetCodedChart");
  if (!interviewedCanvas || !codedCanvas || !notYetCodedCanvas) return;
  const interviewedCtx = interviewedCanvas.getContext("2d");
  const codedCtx = codedCanvas.getContext("2d");
  const notYetCodedCtx = notYetCodedCanvas.getContext("2d");

  setVAChart(graphData.collected.x, graphData.collected.y, interviewedCtx);
  setVAChart(graphData.coded.x, graphData.coded.y,codedCtx);
  setVAChart(graphData.uncoded.x, graphData.uncoded.y, notYetCodedCtx);
}

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
          beginAtZero: true,
          title: { display: true, text: "Event count" },
          grid: { display: true, color: "rgba(148, 163, 184, 0.35)" },
          ticks: { precision: 0 },
        },
      },
    },
  });
  syncNovChartHeightToKpiCards();
}

const updateNationalOperationalEventsChart = (labels, pregnancyValues, pregnancyOutcomeValues, deathValues) => {
  const canvas = document.getElementById("novEventsChart");
  if (!canvas || typeof Chart === "undefined") return;

  if (!novEventsChartInstance) {
    initNationalOperationalEventsChart();
  }
  if (!novEventsChartInstance) return;

  novEventsChartInstance.data.labels = labels || [];
  novEventsChartInstance.data.datasets[0].data = pregnancyValues || [];
  novEventsChartInstance.data.datasets[1].data = pregnancyOutcomeValues || [];
  novEventsChartInstance.data.datasets[2].data = deathValues || [];
  novEventsChartInstance.update();
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

const requestNationalOperationalFilterData = () => {
  const root = document.getElementById("national-operational-view");
  if (!root) return;
  const endpoint = root.dataset.filterUrl;
  if (!endpoint) return;

  const startInput = document.getElementById("novStartDatetime");
  const endInput = document.getElementById("novEndDatetime");
  const requestId = ++novFilterRequestId;

  toggleNovLoadingState(true);
  $.ajax({
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
        jsonResponse.death_values || []
      );
      updateNationalOperationalKpis(jsonResponse.kpis || {});
    },
    complete: () => {
      if (requestId === novFilterRequestId) {
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
      requestNationalOperationalFilterData();
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
      requestNationalOperationalFilterData();
    });
  }

  if (locationValue) {
    locationValue.addEventListener("change", () => {
      requestNationalOperationalFilterData();
    });
  }

  [startInput, endInput].forEach((input) => {
    if (!input) return;
    input.addEventListener("change", () => {
      clearPresetSelection();
      requestNationalOperationalFilterData();
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
  setVAChart(x, y, canvas.getContext("2d"));
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

const loadAllData = () => {
  const endpoint = "/trends";
  $.ajax({
    url: endpoint,
    type: "GET",
    dataType: "json",
    success: (jsonResponse) => {
      // Set VA Table data
      setVATrendsTableData(jsonResponse.vaTable);
      // Set VA Charts
      setVACharts(jsonResponse.graphs);
      // Set household/pregnancy/pregnancy outcome/death trends
      setModelTrendVisualizations(jsonResponse.modelTrends);
      // Set Coding Issues Table data
      if(jsonResponse.issueList.length > 0) {
        setCodingIssuesTableData(jsonResponse.issueList, jsonResponse.isFieldWorker);
        $('#coding-issues').removeClass('hidden');

        if(jsonResponse.additionalIssues > 0) {
          document.getElementById('additional-issues-count').innerHTML =
              jsonResponse.additionalIssues;
          $('#additional-issues-msg').removeClass('hidden');
        }
      }
      else {
        $('#no-coding-issues').removeClass('hidden');
      }
      // Set Indeterminate COD data
      if(jsonResponse.indeterminateCodList.length > 0) {
        setIndeterminateCODTableData(jsonResponse.indeterminateCodList, jsonResponse.isFieldWorker);
        $('#indeterminate-cod').removeClass('hidden');

        if(jsonResponse.additionalIndeterminateCods > 0){
          document.getElementById('additional-indeterminate-cods-count').innerHTML =
              jsonResponse.additionalIndeterminateCods;
          $('#additional-indeterminate-cods-msg').removeClass('hidden');
        }
      }
      else {
        $('#no-indeterminate-cod').removeClass('hidden');
      }
    },
    error: () => console.log("Failed to fetch chart data from " + endpoint + "!")
  });
}

loadAllData();
initNationalOperationalEventsChart();
initNationalOperationalFilters();
initNovChartHeightSync();
