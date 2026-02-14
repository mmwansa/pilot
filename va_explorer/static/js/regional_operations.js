(function() {
  var mapEl = document.getElementById('regionalMap');
  var hasMap = Boolean(mapEl && window.L);

  var componentsEl = document.getElementById('regionalOperationsComponents');
  var componentUrls = {
    filters: componentsEl ? componentsEl.getAttribute('data-filters-url') : '',
    csa: componentsEl ? componentsEl.getAttribute('data-csa-url') : '',
    mso: componentsEl ? componentsEl.getAttribute('data-mso-url') : ''
  };
  var csaComponentEl = document.getElementById('regionalCsaComponent');
  var msoComponentEl = document.getElementById('regionalMsoComponent');
  var tableSortState = {
    csa_sort: csaComponentEl ? (csaComponentEl.getAttribute('data-csa-sort') || 'visits') : 'visits',
    csa_dir: csaComponentEl ? (csaComponentEl.getAttribute('data-csa-dir') || 'desc') : 'desc',
    csa_page: csaComponentEl ? (csaComponentEl.getAttribute('data-csa-page') || '1') : '1',
    mso_sort: msoComponentEl ? (msoComponentEl.getAttribute('data-mso-sort') || 'death_events') : 'death_events',
    mso_dir: msoComponentEl ? (msoComponentEl.getAttribute('data-mso-dir') || 'desc') : 'desc',
    mso_page: msoComponentEl ? (msoComponentEl.getAttribute('data-mso-page') || '1') : '1'
  };

  var label = document.getElementById('geographyTimeLabel');
  var mapUrl = mapEl ? mapEl.getAttribute('data-map-url') : '';
  var geojsonUrl = window.location.origin + '/static/data/zambia_geojson.json';

  var colorScale = [
    '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#ffffbf',
    '#fee090', '#fdae61', '#f46d43', '#d73027'
  ];

  var state = {
    map: null,
    layer: null,
    geojson: null,
    geographic_province_sums: null,
    geographic_district_sums: null,
    geoScale: null,
    hasFit: false
  };

  var mapping = {
    timeAll: 'All Time',
    time30: 'Last 30 days',
    time7: 'Last 7 days',
    time24: 'Last 24 hours'
  };

  function getEl(id) {
    return document.getElementById(id);
  }

  function formatDate(date) {
    return date.toISOString().slice(0, 10);
  }

  function getSelectedPreset() {
    return document.querySelector('input[name="timePreset"]:checked');
  }

  function getPresetDates() {
    var selected = getSelectedPreset();
    if (!selected) return {start: '', end: ''};

    var now = new Date();

    if (selected.id === 'timeAll') {
      return {start: '', end: ''};
    }

    if (selected.id === 'time30') {
      var d30 = new Date(now);
      d30.setDate(d30.getDate() - 30);
      return {start: formatDate(d30), end: formatDate(now)};
    }

    if (selected.id === 'time7') {
      var d7 = new Date(now);
      d7.setDate(d7.getDate() - 7);
      return {start: formatDate(d7), end: formatDate(now)};
    }

    if (selected.id === 'time24') {
      var d1 = new Date(now);
      d1.setDate(d1.getDate() - 1);
      return {start: formatDate(d1), end: formatDate(now)};
    }

    return {start: '', end: ''};
  }

  function getDateRange() {
    var startInput = getEl('timeStartDate');
    var endInput = getEl('timeEndDate');
    var startVal = startInput ? startInput.value : '';
    var endVal = endInput ? endInput.value : '';

    if (startVal && endVal) {
      return {start: startVal, end: endVal};
    }

    return getPresetDates();
  }

  function getFilterParams() {
    var params = new URLSearchParams();
    var geoSelect = getEl('geographyFilterSelect');
    var sourceSelect = getEl('msoSourceSelect');
    var selectedPreset = getSelectedPreset();
    var range = getDateRange();

    if (geoSelect && geoSelect.value) params.set('geography', geoSelect.value);
    if (sourceSelect && sourceSelect.value) params.set('source', sourceSelect.value);
    if (selectedPreset && selectedPreset.id) params.set('time_preset', selectedPreset.id);
    if (range.start) params.set('start_date', range.start);
    if (range.end) params.set('end_date', range.end);
    if (tableSortState.csa_sort) params.set('csa_sort', tableSortState.csa_sort);
    if (tableSortState.csa_dir) params.set('csa_dir', tableSortState.csa_dir);
    if (tableSortState.csa_page) params.set('csa_page', tableSortState.csa_page);
    if (tableSortState.mso_sort) params.set('mso_sort', tableSortState.mso_sort);
    if (tableSortState.mso_dir) params.set('mso_dir', tableSortState.mso_dir);
    if (tableSortState.mso_page) params.set('mso_page', tableSortState.mso_page);

    return params;
  }

  function refreshComponent(containerId, url) {
    var container = getEl(containerId);
    if (!container || !url) return Promise.resolve();

    var params = getFilterParams();
    var requestUrl = url + (params.toString() ? '?' + params.toString() : '');

    return fetch(requestUrl, {method: 'GET'})
      .then(function(res) {
        if (!res.ok) throw new Error('Failed to load component');
        return res.text();
      })
      .then(function(html) {
        container.innerHTML = html;
      })
      .catch(function() {
        // Keep last-rendered component if refresh fails.
      });
  }

  function refreshDataComponents(options) {
    var opts = options || {csa: true, mso: true};
    var requests = [];

    if (opts.filters) {
      requests.push(refreshComponent('regionalFiltersComponent', componentUrls.filters));
    }
    if (opts.csa) {
      requests.push(refreshComponent('regionalCsaComponent', componentUrls.csa));
    }
    if (opts.mso) {
      requests.push(refreshComponent('regionalMsoComponent', componentUrls.mso));
    }

    return Promise.all(requests);
  }

  function updateLabel() {
    if (!label) return;

    var range = getDateRange();
    if (range.start && range.end) {
      label.textContent = 'Geography: ' + range.start + ' - ' + range.end;
      return;
    }

    var selected = getSelectedPreset();
    if (!selected || !mapping[selected.id]) return;
    label.textContent = 'Geography: ' + mapping[selected.id];
  }

  function getBorderType() {
    var geoSelect = getEl('geographyFilterSelect');
    if (!geoSelect || !geoSelect.value || geoSelect.value === 'national') {
      return 'Province';
    }
    return 'District';
  }

  function computeGeoScale(geoSums) {
    if (!geoSums || !geoSums.length) return null;
    var geoMax = Math.max.apply(null, geoSums.map(function(item) { return +item.count; })) + 100;
    var geoMin = 1;
    var n = 10;
    var step = (geoMax - geoMin) / (n - 1);
    return Array.from({length: n}, function(_, i) {
      return Math.round(geoMin + step * i);
    });
  }

  function getColor(feature) {
    var borderType = getBorderType();
    var areaName = feature.properties.area_name;
    var areaLabel = feature.properties.area_level_label;
    var area = areaName + ' ' + areaLabel;

    var geoSums = borderType === 'Province' ? state.geographic_province_sums : state.geographic_district_sums;
    var accessor = borderType === 'Province' ? 'province_name' : 'district_name';

    if (!geoSums) return '#c0c0c0';

    var result = geoSums.find(function(item) { return item[accessor] === area; });
    if (result) {
      var count = result.count;
      for (var i = 0; i < state.geoScale.length; i++) {
        if (count >= state.geoScale[i] && count < state.geoScale[i + 1]) {
          return colorScale[i];
        }
      }
    }
    return '#c0c0c0';
  }

  function addGeoJsonLayer() {
    if (!hasMap || !state.geojson || !state.geoScale || !state.map) return;

    var borderType = getBorderType();
    var borders = ['Country', borderType];
    var geojson = JSON.parse(JSON.stringify(state.geojson));
    geojson.features = state.geojson.features.filter(function(feature) {
      return borders.indexOf(feature.properties.area_level_label) !== -1;
    });

    if (state.layer) state.map.removeLayer(state.layer);

    state.layer = L.geoJson(geojson, {
      style: function(feature) {
        if (feature.properties.area_level_label !== 'Country') {
          var color = getColor(feature);
          return {stroke: true, weight: 1.5, color: color, opacity: 1, fillColor: color, fillOpacity: 0.75};
        }
        return {weight: 2.2, opacity: 1, color: '#666', stroke: true};
      }
    }).addTo(state.map);

    if (!state.hasFit) {
      try {
        state.map.fitBounds(state.layer.getBounds(), {padding: [6, 6]});
        var currentZoom = state.map.getZoom();
        if (typeof currentZoom === 'number') {
          state.map.setZoom(Math.max(currentZoom - 1, 3));
        }
        state.hasFit = true;
      } catch (e) {
        // ignore fit errors for empty bounds
      }
    }
  }

  function initializeMap() {
    if (!hasMap) return Promise.resolve();

    state.map = L.map('regionalMap', {
      zoomControl: false,
      attributionControl: false,
      scrollWheelZoom: false,
      doubleClickZoom: false,
      dragging: true,
      maxBounds: [
        [-6, 20],
        [-20, 34]
      ]
    }).setView([-13, 27], 6);

    return fetch(geojsonUrl)
      .then(function(res) { return res.json(); })
      .then(function(geojson) {
        state.geojson = geojson;
        return updateMapData();
      })
      .then(function() {
        setTimeout(function() {
          if (state.map) state.map.invalidateSize();
        }, 0);
      });
  }

  function updateMapData() {
    if (!hasMap || !mapUrl) return Promise.resolve();

    var range = getDateRange();
    var params = new URLSearchParams();
    if (range.start) params.set('start_date', range.start);
    if (range.end) params.set('end_date', range.end);

    var url = mapUrl + (params.toString() ? '?' + params.toString() : '');

    return fetch(url, {method: 'GET'})
      .then(function(res) { return res.json(); })
      .then(function(data) {
        state.geographic_province_sums = data.geographic_province_sums || [];
        state.geographic_district_sums = data.geographic_district_sums || [];
        state.geoScale = computeGeoScale(
          getBorderType() === 'Province' ? state.geographic_province_sums : state.geographic_district_sums
        );
        addGeoJsonLayer();
      });
  }

  function wireEvents() {
    document.addEventListener('click', function(event) {
      var link = event.target.closest('.regional-sort-link, .regional-page-link');
      if (!link) return;
      if (link.classList.contains('disabled') || link.getAttribute('aria-disabled') === 'true') return;

      event.preventDefault();
      var href = link.getAttribute('href') || '';
      var table = link.getAttribute('data-table');
      if (!href || !table) return;

      var params = new URLSearchParams(href.replace('?', ''));
      if (table === 'csa') {
        tableSortState.csa_sort = params.get('csa_sort') || tableSortState.csa_sort;
        tableSortState.csa_dir = params.get('csa_dir') || tableSortState.csa_dir;
        tableSortState.csa_page = params.get('csa_page') || tableSortState.csa_page;
        refreshDataComponents({csa: true});
        return;
      }

      if (table === 'mso') {
        tableSortState.mso_sort = params.get('mso_sort') || tableSortState.mso_sort;
        tableSortState.mso_dir = params.get('mso_dir') || tableSortState.mso_dir;
        tableSortState.mso_page = params.get('mso_page') || tableSortState.mso_page;
        refreshDataComponents({mso: true});
      }
    });

    document.addEventListener('change', function(event) {
      var target = event.target;
      if (!target) return;

      var isPrimaryFilter =
        target.id === 'geographyFilterSelect' ||
        target.id === 'timeStartDate' ||
        target.id === 'timeEndDate' ||
        target.name === 'timePreset';

      if (isPrimaryFilter) {
        tableSortState.csa_page = '1';
        tableSortState.mso_page = '1';
        updateLabel();
        updateMapData();
        refreshDataComponents({csa: true, mso: true});
        return;
      }

      if (target.id === 'msoSourceSelect') {
        tableSortState.mso_page = '1';
        refreshDataComponents({mso: true});
      }
    });

    window.addEventListener('resize', function() {
      if (state.map) state.map.invalidateSize();
    });
  }

  updateLabel();
  initializeMap();
  wireEvents();
})();
