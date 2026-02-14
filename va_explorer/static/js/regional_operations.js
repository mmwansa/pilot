(function() {
  var mapEl = document.getElementById('regionalMap');
  if (!mapEl || !window.L) return;

  var label = document.getElementById('geographyTimeLabel');
  var startInput = document.getElementById('timeStartDate');
  var endInput = document.getElementById('timeEndDate');
  var geoSelect = document.getElementById('geographyFilterSelect');

  var mapUrl = mapEl.getAttribute('data-map-url');
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

  function formatDate(date) {
    return date.toISOString().slice(0, 10);
  }

  function getPresetDates() {
    var selected = document.querySelector('input[name="timePreset"]:checked');
    if (!selected) return {start: '', end: ''};

    var now = new Date();
    var start = '';
    var end = '';

    if (selected.id === 'timeAll') {
      return {start: '', end: ''};
    }

    if (selected.id === 'time30') {
      var d30 = new Date(now);
      d30.setDate(d30.getDate() - 30);
      start = formatDate(d30);
      end = formatDate(now);
    } else if (selected.id === 'time7') {
      var d7 = new Date(now);
      d7.setDate(d7.getDate() - 7);
      start = formatDate(d7);
      end = formatDate(now);
    } else if (selected.id === 'time24') {
      var d1 = new Date(now);
      d1.setDate(d1.getDate() - 1);
      start = formatDate(d1);
      end = formatDate(now);
    }

    return {start: start, end: end};
  }

  function getDateRange() {
    var startVal = startInput ? startInput.value : '';
    var endVal = endInput ? endInput.value : '';

    if (startVal && endVal) {
      return {start: startVal, end: endVal};
    }

    return getPresetDates();
  }

  function updateLabel() {
    if (!label) return;
    var range = getDateRange();
    if (range.start && range.end) {
      label.textContent = 'Geography: ' + range.start + ' - ' + range.end;
      return;
    }

    var selected = document.querySelector('input[name="timePreset"]:checked');
    if (!selected || !mapping[selected.id]) return;
    label.textContent = 'Geography: ' + mapping[selected.id];
  }

  function getBorderType() {
    if (!geoSelect) return 'Province';
    return geoSelect.value === 'Regional' ? 'District' : 'Province';
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
    if (!state.geojson || !state.geoScale || !state.map) return;

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

    fetch(geojsonUrl)
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
    if (!mapUrl) return Promise.resolve();

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
    var radios = document.querySelectorAll('input[name="timePreset"]');
    radios.forEach(function(radio) {
      radio.addEventListener('change', function() {
        updateLabel();
        updateMapData();
      });
    });

    if (startInput) startInput.addEventListener('change', function() {
      updateLabel();
      updateMapData();
    });

    if (endInput) endInput.addEventListener('change', function() {
      updateLabel();
      updateMapData();
    });

    if (geoSelect) geoSelect.addEventListener('change', function() {
      updateMapData();
    });

    window.addEventListener('resize', function() {
      if (state.map) state.map.invalidateSize();
    });
  }

  updateLabel();
  initializeMap();
  wireEvents();
})();
