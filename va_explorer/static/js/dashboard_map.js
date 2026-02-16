// Drill-down map dashboard with lazy loading and caching

Vue.use('stacked-bar-chart', 'line-chart', 'loader-spinning')

const LEVEL_CONFIG = {
    0: { label: 'Country', file: 'level_0_country.geojson', accessor: 'area_name' },
    1: { label: 'Province', file: 'level_1_provinces.geojson', accessor: 'area_name' },
    2: { label: 'District', file: 'level_2_districts.geojson', accessor: 'area_name' },
    3: { label: 'Constituency', file: 'level_3_constituencies.geojson', accessor: 'area_name' },
    4: { label: 'Ward', file: 'level_4_wards.geojson', accessor: 'area_name' },
    5: { label: 'EA', file: 'level_5_ea.geojson', accessor: 'area_name' },
}

const MAX_DRILL_LEVEL = 5; // EA is the last drillable level

const dashboard = new Vue({
    el: '#dashboardApp',
    delimiters: ["<%", "%>"],
    data() {
        return {
            csrftoken: "",

            // map related values
            map: null,
            geojsonCache: {}, // Cache loaded GeoJSON by level
            layer: null,
            currentLevel: 1, // Start with provinces (1=Province)
            drilldownPath: [], // Track hierarchy: [{level: 0, name: 'Zambia'}, {level: 1, name: 'Lusaka'}, ...]

            // default values for all the charts
            COD_grouping: [],
            COD_trend: [],
            place_of_death: [],
            demographics: [],
            geographic_level_sums: {}, // Store aggregates by level for current drill state
            uncoded_vas: 0,
            update_stats: {
                last_update: 0,
                last_interview: 0,
            },

            // chart sizes
            demographicsHeight: 0,
            demographicsWidth: 0,
            codHeight: 0,
            codWidth: 0,

            // dropdowns options and selected values
            listOfCausesDropdownOptions: [],
            deathDateDropdownOptions: ["Any Time", "Within 1 Month", "Within 3 months", "Within 1 year", "Custom"],
            deathDateSelected: "Any Time",
            startDate: "",
            endDate: "",
            causeSelected: "",
            ageSelected: "",
            sexSelected: "",

            colorScale: [
                "#4575b4", "#74add1", "#abd9e9", "#e0f3f8", "#ffffbf",
                "#fee090", "#fdae61", "#f46d43", "#d73027"
            ],

            demographicsLegendData: [
                {
                    name: "Female",
                    color: "#440154FF",
                },
                {
                    name: "Male",
                    color: "#404788FF",
                }
            ],

            loading: true,
            suppressWarning: false,
            placeOfDeathValue: "count",
            causeOfDeathValue: "count",
        }
    },
    computed: {
        highlightsSummaries() {
            return {
                "Last Data Update": this.update_stats.last_update || "-",
                "Last VA Interview": this.update_stats.last_interview || "-",
                "Coded VAs": d3.sum(this.COD_grouping.map(item => item.count)),
                "Uncoded VAs": this.uncoded_vas,
            }
        },
        currentLevelLabel() {
            return LEVEL_CONFIG[this.currentLevel].label;
        },
        parentLevelLabel() {
            if (this.currentLevel > 0) {
                return LEVEL_CONFIG[this.currentLevel - 1].label;
            }
            return "Country";
        },
        drilldownBreadcrumbs() {
            // Return breadcrumb path including current location
            return [
                { level: LEVEL_CONFIG[0].label, name: 'Zambia', levelIndex: 0 },
                ...this.drilldownPath
            ];
        },
        geoScale() {
            if (!this.geographic_level_sums || Object.keys(this.geographic_level_sums).length === 0) return;
            const counts = Object.values(this.geographic_level_sums).map(item => item.count || 0);
            if (counts.length === 0) return;
            
            const geoMax = Math.max(...counts) + 100;
            const geoMin = 1;
            const n = 10;
            const step = (geoMax - geoMin) / (n - 1);
            return Array.from({length: n}, (_, i) => Math.round(geoMin + step * i));
        },
        placeOfDeathData() {
            if (!this.place_of_death) return [];
            if (this.placeOfDeathValue === "count") return this.place_of_death;
            const totalCount = d3.sum(this.place_of_death.map(item => item.count));
            return JSON.parse(JSON.stringify(this.place_of_death)).map(d => {
                d.percentage = Math.round(d.count * 1000 / totalCount) / 10;
                delete d.count;
                return d;
            })
        },
        causeOfDeathData() {
            if (!this.COD_grouping) return [];
            if (this.causeOfDeathValue === "count") return this.COD_grouping;
            const totalCount = d3.sum(this.COD_grouping.map(item => item.count));
            return JSON.parse(JSON.stringify(this.COD_grouping)).map(d => {
                d.percentage = Math.round(d.count * 1000 / totalCount) / 10;
                delete d.count;
                return d;
            })
        },
    },
    async created() {
        // Initialize breadcrumb with provinces (start at provincial level)
        this.drilldownPath = [];
        
        // Request data from API endpoint
        await this.getData();

        // Pre-load province level GeoJSON
        await this.loadGeojsonLevel(1);
    },
    async mounted() {
        this.resizeCharts();
        window.addEventListener('resize', this.resizeCharts);

        await this.initializeBaseMap();
        await this.addGeoJSONToMap();
    },
    beforeDestroy() {
        window.removeEventListener('resize', this.resizeCharts);
    },
    methods: {
        // Function to reproject from EPSG:3857 (Web Mercator) to EPSG:4326 (WGS84)
        reproject3857to4326(geojson) {
            // Check CRS - if it's already WGS84/CRS84, don't reproject
            if (geojson.crs) {
                const crsName = geojson.crs.properties?.name || '';
                // CRS84 and EPSG:4326 are both WGS84 (just different axis order)
                if (crsName.includes('CRS84') || crsName.includes('4326') || crsName.includes('WGS84')) {
                    console.log(`[Reproject] GeoJSON is already in WGS84 (CRS: ${crsName}), skipping reprojection`);
                    delete geojson.crs;
                    return geojson;
                }
                // Only reproject if it's EPSG:3857
                if (!crsName.includes('3857')) {
                    console.log(`[Reproject] Unknown CRS: ${crsName}, checking coordinates to determine if reprojection needed`);
                }
            }
            
            // Check if coordinates look like they're already in WGS84 (lat/lng range)
            // WGS84: lat -90 to 90, lng -180 to 180
            // EPSG:3857: x -20037508 to 20037508, y -20037508 to 20037508
            let sampleCoords = null;
            if (geojson.features && geojson.features.length > 0) {
                const firstFeature = geojson.features[0];
                if (firstFeature.geometry && firstFeature.geometry.coordinates) {
                    const coords = firstFeature.geometry.coordinates;
                    // Get first coordinate
                    if (Array.isArray(coords[0])) {
                        if (Array.isArray(coords[0][0])) {
                            sampleCoords = coords[0][0][0];
                        } else {
                            sampleCoords = coords[0];
                        }
                    } else {
                        sampleCoords = coords;
                    }
                }
            }
            
            const looksLikeWGS84 = sampleCoords && 
                Math.abs(sampleCoords[0]) <= 180 && 
                Math.abs(sampleCoords[1]) <= 90;
            
            if (looksLikeWGS84) {
                console.log(`[Reproject] Coordinates appear to already be in WGS84 (sample: [${sampleCoords[0]}, ${sampleCoords[1]}]), skipping reprojection`);
                delete geojson.crs;
                return geojson;
            }
            
            console.log(`[Reproject] Reprojecting from EPSG:3857 to EPSG:4326. Sample coords before: [${sampleCoords ? sampleCoords.join(', ') : 'N/A'}]`);
            
            const R = 6378137; // Earth's radius in meters
            const reprojectCoords = (coords) => {
                if (Array.isArray(coords[0])) {
                    // It's an array of arrays (polygon rings or multipolygon)
                    return coords.map(reprojectCoords);
                } else {
                    // It's a coordinate pair [x, y]
                    const x = coords[0];
                    const y = coords[1];
                    const lng = (x / R) * (180 / Math.PI);
                    const lat = (2 * Math.atan(Math.exp(y / R)) - Math.PI / 2) * (180 / Math.PI);
                    return [lng, lat];
                }
            };

            const reprojectGeometry = (geometry) => {
                if (geometry.type === 'Point') {
                    geometry.coordinates = reprojectCoords(geometry.coordinates);
                } else if (geometry.type === 'LineString') {
                    geometry.coordinates = geometry.coordinates.map(coord => reprojectCoords(coord));
                } else if (geometry.type === 'Polygon') {
                    geometry.coordinates = geometry.coordinates.map(ring => ring.map(coord => reprojectCoords(coord)));
                } else if (geometry.type === 'MultiPolygon') {
                    geometry.coordinates = geometry.coordinates.map(polygon => polygon.map(ring => ring.map(coord => reprojectCoords(coord))));
                }
                return geometry;
            };

            // Reproject each feature's geometry
            geojson.features.forEach(feature => {
                feature.geometry = reprojectGeometry(feature.geometry);
            });

            // Remove or update CRS to indicate WGS84
            delete geojson.crs;
            
            if (sampleCoords && geojson.features.length > 0) {
                const reprojectedSample = geojson.features[0].geometry.coordinates;
                let reprojectedCoords = null;
                if (Array.isArray(reprojectedSample[0])) {
                    if (Array.isArray(reprojectedSample[0][0])) {
                        reprojectedCoords = reprojectedSample[0][0][0];
                    } else {
                        reprojectedCoords = reprojectedSample[0];
                    }
                } else {
                    reprojectedCoords = reprojectedSample;
                }
                console.log(`[Reproject] Sample coords after: [${reprojectedCoords[0]}, ${reprojectedCoords[1]}]`);
            }

            return geojson;
        },
        async loadGeojsonLevel(level, forceReload = false) {
            // Lazy load GeoJSON for a specific level with caching
            if (this.geojsonCache[level] && !forceReload) {
                console.log(`[Cache] Using cached GeoJSON for level ${level}`);
                return this.geojsonCache[level];
            }

            try {
                const url = `${window.location.protocol}//${window.location.hostname}:${window.location.port}/static/data/geojson/`;
                const filename = LEVEL_CONFIG[level].file;
                // Add cache busting to ensure we get fresh data
                const cacheBuster = `?v=${Date.now()}`;
                const response = await fetch(`${url}${filename}${cacheBuster}`);
                const geojson = await response.json();
                
                console.log(`[Load] Loaded ${geojson.features.length} features from ${filename}`);
                // Log sample area_ids for debugging
                if (geojson.features.length > 0) {
                    const sampleIds = geojson.features.slice(0, 5).map(f => ({
                        area_id: f.properties.area_id,
                        area_name: f.properties.area_name,
                        parent_id: f.properties.parent_id
                    }));
                    console.log(`[Load] Sample features from ${filename}:`, sampleIds);
                }
                
                // Reproject from EPSG:3857 to EPSG:4326
                const reprojectedGeojson = this.reproject3857to4326(geojson);
                
                // Cache it
                this.geojsonCache[level] = reprojectedGeojson;
                return reprojectedGeojson;
            } catch (error) {
                console.error(`Failed to load GeoJSON for level ${level}:`, error);
                return null;
            }
        },
        async getData() {
            // Fetch data from API with current drill-down context
            this.loading = true;

            const {age, sex} = this.getAgeAndSex();
            const {startDate, endDate} = this.getStartAndEndDates();

            this.csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

            // Construct parent region filter based on current drill-down path
            // Use the deepest breadcrumb when available (e.g., Province, District, Constituency...)
            let parentRegion = null;
            if (this.drilldownPath.length >= 1) {
                const lastDrill = this.drilldownPath[this.drilldownPath.length - 1];
                parentRegion = `${lastDrill.name} ${lastDrill.level}`;
            }

            const data_url = `${window.location.origin}/va_analytics/api/dashboard?`;
            const dataReq = await fetch(data_url + new URLSearchParams({
                start_date: startDate,
                end_date: endDate,
                cause_of_death: this.causeSelected,
                region_of_interest: parentRegion || "",
                age, sex
            }), {
                method: 'GET',
                headers: {'X-CSRFToken': this.csrftoken, 'Content-Type': 'application/json'},
                mode: 'same-origin'
            });

            const jsonRes = await dataReq.json();
            this.COD_grouping = jsonRes.COD_grouping;
            this.COD_trend = jsonRes.COD_trend;
            this.place_of_death = jsonRes.place_of_death.map(d => {
                d.place = d.place.replace(/_/g, " ");
                return d;
            });
            this.demographics = jsonRes.demographics;
            
            // Get aggregates for current drill level
            this.geographic_level_sums = this.getAggregatesForLevel(jsonRes);
            
            this.uncoded_vas = jsonRes.uncoded_vas;
            this.update_stats = jsonRes.update_stats;
            this.listOfCausesDropdownOptions = jsonRes.all_causes_list;

            // Ensure all age groups are present
            const ageGroups = ["neonate", "child", "adult"];
            for (const ageGroup of ageGroups) {
                let index = this.demographics.map(d => d.age_group).indexOf(ageGroup);
                if (index === -1) {
                    this.demographics.push({
                        female: 0,
                        male: 0,
                    });
                    index = this.demographics.length - 1;
                }
                if (!this.demographics[index].hasOwnProperty("female")) {
                    this.demographics[index].female = 0;
                }
                if (!this.demographics[index].hasOwnProperty("male")) {
                    this.demographics[index].male = 0;
                }
                this.demographics[index].age_group = ageGroup === "neonate" ? "Neonate (< 28 days)" :
                    ageGroup === "child" ? "Child (≤ 12 years)" : "Adult (> 12 years)";
                this.demographics[index].order = ageGroups.indexOf(ageGroup);
            }
            this.demographics.sort((a, b) => a.order > b.order ? 1 : b.order > a.order ? -1 : 0);
            this.demographics.forEach(d => {
                delete d.order;
            });

            // Warning for small sample size
            if (!this.suppressWarning && d3.sum(this.COD_grouping.map(item => item.count)) < 50) {
                if (typeof $("#small-sample-size-warning") !== 'undefined') {
                    $("#small-sample-size-warning").modal().show();
                }
            }

            this.loading = false;
        },
        getAggregatesForLevel(jsonRes) {
            // Based on current level, extract appropriate aggregates
            let aggregates = {};
            
            // The API returns geographic_province_sums and geographic_district_sums
            // For drill-down, we need to map to current level
            if (this.currentLevel === 0) {
                // Country level - sum all
                const allCounts = [
                    ...(jsonRes.geographic_province_sums || []),
                    ...(jsonRes.geographic_district_sums || [])
                ];
                aggregates['Zambia Country'] = {
                    count: d3.sum(allCounts.map(item => item.count || 0))
                };
            } else if (this.currentLevel === 1) {
                // Province level
                (jsonRes.geographic_province_sums || []).forEach(item => {
                    aggregates[`${item.province_name} Province`] = { count: item.count };
                });
            } else if (this.currentLevel >= 2) {
                // District and below - use district sums
                (jsonRes.geographic_district_sums || []).forEach(item => {
                    aggregates[`${item.district_name} District`] = { count: item.count };
                });
            }
            
            return aggregates;
        },
        async initializeBaseMap() {
            this.map = L.map('map', {
                zoomControl: false,
                maxBounds: [
                    [-6, 20],
                    [-20, 34],
                ]
            }).setView([-13, 27], 6);

            this.map.attributionControl.setPrefix('');
            this.map.keyboard.disable();

            const tiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19, // Allow deep zooming for EA level features
                attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            }).addTo(this.map);

            // Add explicit zoom control at top-left (prevent CSS/layout moving it)
            // Enable zoom controls with higher max zoom for EA level features
            try {
                L.control.zoom({ 
                    position: 'topleft',
                    zoomInTitle: 'Zoom in',
                    zoomOutTitle: 'Zoom out'
                }).addTo(this.map);
                // Ensure zoom is enabled
                this.map.scrollWheelZoom.enable();
                this.map.doubleClickZoom.enable();
            } catch (err) {
                console.warn('Could not add zoom control:', err);
            }

            // Add Leaflet.fullscreen control (provided via CDN in template)
            try {
                if (typeof L !== 'undefined') {
                    if (L.control && typeof L.control.fullscreen === 'function') {
                        L.control.fullscreen({ position: 'topright', title: 'Show Fullscreen', titleCancel: 'Exit Fullscreen' }).addTo(this.map);
                    } else if (L.Control && typeof L.Control.FullScreen === 'function') {
                        // Some builds expose the class as L.Control.FullScreen
                        new L.Control.FullScreen({ position: 'topright', title: 'Show Fullscreen', titleCancel: 'Exit Fullscreen' }).addTo(this.map);
                    } else if (L.Control && typeof L.Control.Fullscreen === 'function') {
                        // Alternate capitalization
                        new L.Control.Fullscreen({ position: 'topright', title: 'Show Fullscreen', titleCancel: 'Exit Fullscreen' }).addTo(this.map);
                    } else {
                        console.warn('Leaflet.fullscreen plugin not available; fullscreen control not added. L.Control keys:', L.Control ? Object.keys(L.Control) : undefined, 'window keys:', Object.keys(window).filter(k => k.toLowerCase().includes('full')));
                    }
                } else {
                    console.warn('Leaflet (L) is not defined; cannot initialize fullscreen control.');
                }
            } catch (err) {
                console.warn('Error while attempting to add fullscreen control:', err);
            }
        },
        async addGeoJSONToMap() {
            // Load and add GeoJSON for current level with drill-down support
            const vm = this;
            if (this.layer) this.map.removeLayer(this.layer);

            const geojson = await this.loadGeojsonLevel(this.currentLevel);
            if (!geojson) return;

            // Filter features based on current drill-down path
            let filteredGeojson = JSON.parse(JSON.stringify(geojson));
            
            // Log drilldown path for debugging
            console.log(`[Level ${this.currentLevel}] Drilldown path:`, this.drilldownPath.map(p => ({
                level: p.level,
                name: p.name,
                levelIndex: p.levelIndex,
                area_id: p.id
            })));
            
            filteredGeojson.features = filteredGeojson.features.filter(feature => {
                // For provincial level with no drill-down, show all provinces (parent_id null)
                if (this.drilldownPath.length === 0) {
                    return feature.properties.parent_id == null;
                }
                
                // For all levels, filter by parent_id of the most recent drill-down
                const parent = this.drilldownPath[this.drilldownPath.length - 1];
                const matches = feature.properties.parent_id === parent.id;
                
                // Log first few features for debugging
                if (filteredGeojson.features.indexOf(feature) < 3) {
                    console.log(`[Level ${this.currentLevel}] Feature: area_id=${feature.properties.area_id}, area_name="${feature.properties.area_name}", parent_id=${feature.properties.parent_id}, looking for parent.id=${parent.id}, matches=${matches}`);
                }
                
                return matches;
            });

            console.log(`[Level ${this.currentLevel}] Filtered features: ${filteredGeojson.features.length} out of ${geojson.features.length} total`);
            
            // Log which features were found
            if (filteredGeojson.features.length > 0) {
                console.log(`[Level ${this.currentLevel}] Found features:`, filteredGeojson.features.map(f => {
                    // Check geometry type and get sample coordinates
                    let sampleCoords = 'N/A';
                    if (f.geometry && f.geometry.coordinates) {
                        if (f.geometry.type === 'Point') {
                            sampleCoords = f.geometry.coordinates;
                        } else if (f.geometry.type === 'Polygon' || f.geometry.type === 'MultiPolygon') {
                            // Get first coordinate from first ring
                            const coords = f.geometry.coordinates;
                            if (coords && coords[0] && coords[0][0] && coords[0][0][0]) {
                                sampleCoords = coords[0][0][0];
                            }
                        }
                    }
                    return {
                        area_id: f.properties.area_id,
                        area_name: f.properties.area_name,
                        parent_id: f.properties.parent_id,
                        geometry_type: f.geometry ? f.geometry.type : 'missing',
                        sample_coords: sampleCoords
                    };
                }));
            }
            
            // If no features found, log more details
            if (filteredGeojson.features.length === 0 && this.drilldownPath.length > 0) {
                const parent = this.drilldownPath[this.drilldownPath.length - 1];
                console.warn(`[Level ${this.currentLevel}] No features found! Looking for parent_id=${parent.id} (${parent.name} ${parent.level}), but available parent_ids in data:`, 
                    [...new Set(geojson.features.slice(0, 10).map(f => f.properties.parent_id))]);
            }

            this.layer = L.geoJson(filteredGeojson, {
                style: function (feature) {
                    const color = vm.getColor(feature);
                    return {
                        stroke: true,
                        weight: 3,
                        color: 'black',
                        opacity: 1,
                        fillColor: color,
                        fillOpacity: 0.6
                    };
                },
                onEachFeature: function (feature, layer) {
                    const html_tooltip = vm.generateTooltip(feature);
                    layer.bindTooltip(html_tooltip);
                    
                    // Single click: show details (currently just shows tooltip)
                    layer.on("click", (e) => {
                        // Do nothing on single click
                    });

                    // Double-click: drill down
                    layer.on("dblclick", async (e) => {
                        await vm.drillIntoRegion(e.target.feature);
                    });
                }
            }).addTo(this.map);

            // Ensure Leaflet knows the container size (important after CSS changes)
            try {
                // force Leaflet to recalculate size before fitting bounds
                this.map.invalidateSize();
            } catch (err) {
                console.warn('invalidateSize failed:', err);
            }

            // Center and zoom to the current layer's full extent.
            // Run inside a short timeout so the browser has applied layout changes.
            setTimeout(() => {
                if (this.layer && filteredGeojson.features.length > 0) {
                    const bounds = this.layer.getBounds();
                    console.log(`[Bounds] Calculated bounds for level ${this.currentLevel}:`, bounds ? {
                        isValid: bounds.isValid(),
                        north: bounds.getNorth(),
                        south: bounds.getSouth(),
                        east: bounds.getEast(),
                        west: bounds.getWest()
                    } : 'null');
                    
                    if (bounds && bounds.isValid()) {
                        // Validate bounds are within Zambia's approximate boundaries
                        // Zambia is roughly: lat -8 to -18, lng 22 to 33
                        const north = bounds.getNorth();
                        const south = bounds.getSouth();
                        const east = bounds.getEast();
                        const west = bounds.getWest();
                        
                        const isWithinZambia = north < -8 && south > -18 && east < 33 && west > 22;
                        
                        if (!isWithinZambia) {
                            console.warn(`[Bounds] Calculated bounds are outside Zambia! North: ${north}, South: ${south}, East: ${east}, West: ${west}`);
                            console.warn(`[Bounds] Resetting to Zambia bounds instead`);
                            this.map.setView([-13, 27], 6);
                            this.map.setMaxBounds([
                                [-6, 20],
                                [-20, 34],
                            ]);
                        } else {
                            // Use minimal padding for tighter zoom to features
                            // For level 5 (EA), use even tighter padding since features are very small
                            const padding = this.currentLevel === 5 ? [3, 3] : [5, 5];
                            this.map.fitBounds(bounds, { 
                                padding: padding,
                                maxZoom: 18 // Allow deeper zoom for small features
                            });
                            // second invalidate to ensure tiles render correctly after fit
                            try { this.map.invalidateSize(); } catch (e) {}
                            
                            // For level 5, ensure we can zoom in even more if needed
                            if (this.currentLevel === 5) {
                                // Check if we're at max zoom and features are still small
                                const currentZoom = this.map.getZoom();
                                const boundsSize = bounds.getNorthEast().distanceTo(bounds.getSouthWest());
                                console.log(`[Bounds] Level 5 - Current zoom: ${currentZoom}, bounds size: ${boundsSize.toFixed(2)}m`);
                                
                                // If bounds are very small and we're not at max zoom, try to zoom in more
                                if (boundsSize < 50000 && currentZoom < 18) {
                                    // Manually zoom in a bit more
                                    setTimeout(() => {
                                        const newZoom = Math.min(currentZoom + 2, 18);
                                        this.map.setZoom(newZoom, { animate: true });
                                        console.log(`[Bounds] Level 5 - Zooming in to ${newZoom} for better feature visibility`);
                                    }, 100);
                                }
                            }
                        }
                    } else {
                        console.warn(`[Bounds] Invalid bounds calculated, resetting to Zambia bounds`);
                        this.map.setView([-13, 27], 6);
                        this.map.setMaxBounds([
                            [-6, 20],
                            [-20, 34],
                        ]);
                    }
                } else {
                    // If no features, reset to Zambia bounds to prevent zooming outside
                    console.warn(`[Bounds] No features found for level ${this.currentLevel}, resetting to Zambia bounds`);
                    this.map.setView([-13, 27], 6);
                    this.map.setMaxBounds([
                        [-6, 20],
                        [-20, 34],
                    ]);
                }
            }, 50);
        },
        setupFullscreen() {
            // Removed: custom fullscreen implementation. Using Leaflet.fullscreen control instead.
        },
        async drillIntoRegion(feature) {
            // Handle double-click drill-down
            if (this.currentLevel >= MAX_DRILL_LEVEL) {
                console.log("Already at deepest drill level (Ward)");
                return;
            }

            const regionName = feature.properties.area_name;
            const regionLevel = LEVEL_CONFIG[this.currentLevel].label;
            const regionAreaId = feature.properties.area_id;

            console.log(`[Drill Down] Clicked on ${regionLevel}: "${regionName}" with area_id=${regionAreaId}, parent_id=${feature.properties.parent_id}`);
            
            // Verify the clicked feature's area_id matches what's in the current GeoJSON cache
            // This helps detect cache mismatches
            const currentGeojson = this.geojsonCache[this.currentLevel];
            if (currentGeojson) {
                const matchingFeature = currentGeojson.features.find(f => 
                    f.properties.area_name === regionName && 
                    f.properties.area_id === regionAreaId
                );
                if (!matchingFeature) {
                    console.warn(`[Drill Down] WARNING: Clicked feature (area_id=${regionAreaId}) not found in cached GeoJSON for level ${this.currentLevel}. Possible cache mismatch!`);
                    // Try to find by name only
                    const byName = currentGeojson.features.find(f => f.properties.area_name === regionName);
                    if (byName) {
                        console.warn(`[Drill Down] Found feature with same name but different area_id: ${byName.properties.area_id}. Using this instead.`);
                        // Use the correct area_id from the cache
                        const correctedAreaId = byName.properties.area_id;
                        this.drilldownPath.push({
                            level: regionLevel,
                            name: regionName,
                            levelIndex: this.currentLevel,
                            id: correctedAreaId
                        });
                        console.log(`[Drill Down] Using corrected area_id=${correctedAreaId} instead of ${regionAreaId}`);
                    } else {
                        // Fallback: use the clicked feature's area_id
                        this.drilldownPath.push({
                            level: regionLevel,
                            name: regionName,
                            levelIndex: this.currentLevel,
                            id: regionAreaId
                        });
                    }
                } else {
                    // Feature matches, use it
                    this.drilldownPath.push({
                        level: regionLevel,
                        name: regionName,
                        levelIndex: this.currentLevel,
                        id: regionAreaId
                    });
                }
            } else {
                // No cache, use clicked feature
                this.drilldownPath.push({
                    level: regionLevel,
                    name: regionName,
                    levelIndex: this.currentLevel,
                    id: regionAreaId
                });
            }

            console.log(`[Drill Down] Moving from level ${this.currentLevel} to level ${this.currentLevel + 1}`);

            // Move to next level
            this.currentLevel += 1;

            // Load and display map for next level
            await this.updateDataAndMap();
        },
        async drillBack() {
            // Go back one level
            if (this.currentLevel > 0) {
                this.drilldownPath.pop();
                this.currentLevel -= 1;
                await this.updateDataAndMap();
            }
        },
        async drillbackToLevel(breadcrumbIndex) {
            // Jump back to specific breadcrumb level
            // breadcrumbIndex 0 = Country (Zambia), breadcrumbIndex 1 = Province, breadcrumbIndex 2 = District, etc.
            // drilldownBreadcrumbs structure: [Country, ...drilldownPath]
            // drilldownPath structure: [Province, District, Constituency, ...]
            
            console.log(`[Breadcrumb] Clicked on breadcrumb index ${breadcrumbIndex}`);
            
            if (breadcrumbIndex === 0) {
                // Clicked on Country (Zambia) - show all provinces (level 1)
                this.currentLevel = 1;
                this.drilldownPath = [];
                console.log(`[Breadcrumb] Navigating to level 1 (Provinces), cleared drilldown path`);
            } else {
                // Get the breadcrumb that was clicked
                const breadcrumbs = this.drilldownBreadcrumbs;
                const clickedBreadcrumb = breadcrumbs[breadcrumbIndex];
                
                if (!clickedBreadcrumb) {
                    console.warn(`[Breadcrumb] Invalid breadcrumb index ${breadcrumbIndex}`);
                    return;
                }
                
                // The clicked breadcrumb's levelIndex tells us what level to show
                const targetLevel = clickedBreadcrumb.levelIndex;
                
                // When clicking on a breadcrumb, we want to show the NEXT level's features
                // Click Province -> show Districts (level 2) of that province
                // Click District -> show Constituencies (level 3) of that district
                // So we need to keep breadcrumbs up to the clicked one, and show level targetLevel + 1
                
                // Keep breadcrumbs up to and including the clicked one
                // breadcrumbIndex 1 = Province -> keep drilldownPath[0] (the province)
                // breadcrumbIndex 2 = District -> keep drilldownPath[0,1] (province and district)
                // Since breadcrumbIndex 0 is Country, breadcrumbIndex - 1 gives us the drilldownPath slice end
                this.drilldownPath = this.drilldownPath.slice(0, breadcrumbIndex);
                
                // Set currentLevel to show the children of the clicked breadcrumb
                // If clicked Province (level 1), show Districts (level 2)
                // If clicked District (level 2), show Constituencies (level 3)
                this.currentLevel = targetLevel + 1;
                
                console.log(`[Breadcrumb] Clicked on ${clickedBreadcrumb.name} (level ${targetLevel}), navigating to level ${this.currentLevel} (${LEVEL_CONFIG[this.currentLevel].label}), drilldownPath:`, this.drilldownPath.map(p => p.name));
            }
            
            await this.updateDataAndMap();
        },
        getColor(feature) {
            // Color based on count data
            const areaName = feature.properties.area_name;
            const fullName = `${areaName} ${LEVEL_CONFIG[this.currentLevel].label}`;
            
            const result = this.geographic_level_sums[fullName];
            if (result) {
                const count = result.count;
                for (let i = 0; i < this.geoScale.length; i++) {
                    if (count >= this.geoScale[i] && count < this.geoScale[i + 1]) {
                        return this.colorScale[i];
                    }
                }
            }
            return '#c0c0c0'; // Gray for no data
        },
        getAgeAndSex() {
            const age = this.ageSelected.toLowerCase();
            const sex = this.sexSelected.toLowerCase();
            return {age, sex};
        },
        getStartAndEndDates() {
            let date;
            switch (this.deathDateSelected) {
                case "Any Time":
                    return {startDate: "", endDate: ""};
                case "Within 1 Month":
                    date = new Date();
                    date.setMonth(date.getMonth() - 1);
                    return {startDate: date.toISOString().slice(0, 10), endDate: ""};
                case "Within 3 months":
                    date = new Date();
                    date.setMonth(date.getMonth() - 3);
                    return {startDate: date.toISOString().slice(0, 10), endDate: ""};
                case "Within 1 year":
                    date = new Date();
                    date.setFullYear(date.getFullYear() - 1);
                    return {startDate: date.toISOString().slice(0, 10), endDate: ""};
                case "Custom":
                    return {startDate: this.startDate, endDate: this.endDate};
            }
        },
        generateTooltip(feature) {
            const areaName = feature.properties.area_name;
            const level = LEVEL_CONFIG[this.currentLevel].label;
            const fullName = `${areaName} ${level}`;
            
            const count = this.geographic_level_sums[fullName]?.count || 0;
            
            const drillHint = this.currentLevel < MAX_DRILL_LEVEL ? 
                '<br><small style="font-style: italic;">(Double-click to drill down)</small>' : 
                '<br><small style="font-style: italic;">(Max drill level reached)</small>';
            
            const html_tooltip = `
                <div class="mapTooltip">
                    <h4>${areaName}</h4>
                    <p><strong>VAs:</strong> ${count}</p>
                    ${drillHint}
                </div>
            `;
            return html_tooltip;
        },
        resizeCharts() {
            const demographicsRef = this.$refs.demographics;
            const codRef = this.$refs.cod;

            if (demographicsRef) {
                this.demographicsWidth = demographicsRef.clientWidth - 1;
                this.demographicsHeight = Math.max(demographicsRef.clientHeight - 1, 185);
            }

            if (codRef) {
                this.codWidth = codRef.clientWidth - 1;
                this.codHeight = Math.max(codRef.clientHeight - 1, 185);
            }
        },
        async updateDataAndMap() {
            await this.getData();
            await this.addGeoJSONToMap();
        },
        async resetAllDataToActive() {
            // Reset all filters and drill-down to country level
            this.startDate = "";
            this.endDate = "";
            this.causeSelected = "";
            this.deathDateSelected = "Any Time";
            this.ageSelected = "";
            this.sexSelected = "";
            
            // Reset drill-down to provincial level
            this.currentLevel = 1;
            this.drilldownPath = [];
            
            // Clear GeoJSON cache to force reload with fresh data
            this.geojsonCache = {};
            console.log("[Reset] Cleared GeoJSON cache");
            
            await this.updateDataAndMap();
        },
        clearGeojsonCache() {
            // Method to manually clear the cache if needed
            this.geojsonCache = {};
            console.log("[Cache] GeoJSON cache cleared manually");
        },
    },
    watch: {
        // Trigger map update when geojson is loaded
        currentLevel() {
            if (this.geojsonCache[this.currentLevel]) {
                this.addGeoJSONToMap();
            }
        }
    }
});
