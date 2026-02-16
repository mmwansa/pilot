GRAPH_OPTIONS = {
  responsive: true,
  scales: { y: { beginAtZero: true } },
  plugins: { legend: { display: false } }
};

BORDER_COLOR = "#037BFE"
let novEventsChartInstance = null;

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
