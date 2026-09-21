// ============================================================
// GLOBAL LANDSLIDEGUARD
// FINAL CORRECTED FRONTEND JAVASCRIPT
// ============================================================
//
// IMPORTANT:
// 1. This keeps the existing NER map, boundary, search, prediction,
//    risk gauge, environment data, alerts, modal and mobile navbar.
// 2. LIVE RAINFALL IS NOW REQUESTED FROM THE BROWSER.
// 3. The browser sends rainfall_24h / rainfall_3day / rainfall_7day
//    to Flask in the /predict request.
// 4. This avoids Render -> Open-Meteo 429 problems.
//
// ============================================================


// ============================================================
// MAP
// ============================================================

const map = L.map("map", {
    worldCopyJump: true,
    preferCanvas: true
}).setView([25.5, 93.5], 6);


// ============================================================
// OPENSTREETMAP
// ============================================================

L.tileLayer(
    "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors"
    }
).addTo(map);


// ============================================================
// DOM HELPER
// ============================================================

const $ = id => document.getElementById(id);


// ============================================================
// DOM ELEMENTS
// ============================================================

const input = $("location-search");
const searchBtn = $("search-button");
const status = $("search-status");

const nameEl = $("location-name");
const stateEl = $("state-name");
const latEl = $("latitude");
const lonEl = $("longitude");

const riskEl = $("risk-value");
const levelEl = $("risk-level");
const gauge = $("gauge");

const warningEl = $("warning");
const titleEl = $("analysis-title");
const textEl = $("analysis-text");
const reasonsEl = $("reasons");


// ============================================================
// ENVIRONMENT ELEMENTS
// ============================================================

const envElevation = $("env-elevation");
const envSlope = $("env-slope");
const envAspect = $("env-aspect");
const envRainfall = $("env-rainfall");
const envClay = $("env-clay");
const envSand = $("env-sand");
const envPh = $("env-ph");


// ============================================================
// DYNAMIC RAINFALL ELEMENTS
// ============================================================

const rainfall24h = $("dynamic-rainfall-24h");
const rainfall3day = $("dynamic-rainfall-3day");
const rainfall7day = $("dynamic-rainfall-7day");


// ============================================================
// VARIABLES
// ============================================================

let marker = null;
let regionLayer = null;
let regionReady = false;
let predictionInProgress = false;


// ============================================================
// BROWSER WEATHER CACHE
// ============================================================
//
// Render was receiving HTTP 429 from Open-Meteo.
// Therefore rainfall is requested by the user's browser.
//
// Cache:
// 5 minutes for the same coordinate.
//
// Minimum request interval:
// about 1.1 seconds to avoid unnecessary repeated requests.
//

const BROWSER_WEATHER_CACHE = new Map();

const BROWSER_WEATHER_CACHE_TTL =
    5 * 60 * 1000;

let lastBrowserWeatherRequest = 0;


// ============================================================
// SUPPORTED NORTHEAST STATES
// ============================================================

const NORTHEAST_STATES = [
    "Arunachal Pradesh",
    "Assam",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Sikkim",
    "Tripura"
];


// ============================================================
// NORMALIZE STATE NAME
// ============================================================

function normalizeStateName(name) {

    return String(name || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .trim()
        .toLowerCase()
        .replace(/\s+/g, " ");

}


// ============================================================
// SUPPORTED NORMALIZED STATES
// ============================================================

const SUPPORTED_STATE_NAMES =
    NORTHEAST_STATES.map(
        normalizeStateName
    );


// ============================================================
// GET STATE NAME FROM GEOJSON
// ============================================================

function getFeatureStateName(feature) {

    const properties =
        feature && feature.properties
            ? feature.properties
            : {};

    const possibleKeys = [
        "shapeName",
        "shape_name",
        "NAME_1",
        "NAME1",
        "st_nm",
        "ST_NM",
        "state_name",
        "STATE_NAME",
        "STATE",
        "State",
        "name",
        "NAME",
        "admin1Name",
        "province",
        "region"
    ];

    for (const key of possibleKeys) {

        const value = properties[key];

        if (
            value !== undefined &&
            value !== null &&
            String(value).trim() !== ""
        ) {
            return String(value).trim();
        }

    }

    for (const key of Object.keys(properties)) {

        const value =
            String(properties[key] ?? "").trim();

        if (
            value &&
            SUPPORTED_STATE_NAMES.includes(
                normalizeStateName(value)
            )
        ) {
            return value;
        }

    }

    return "";

}


// ============================================================
// STATUS
// ============================================================

function setStatus(message) {

    if (status) {
        status.textContent = message;
    }

    console.log(message);

}


// ============================================================
// SAFE TEXT
// ============================================================

function setText(element, value) {

    if (element) {
        element.textContent =
            value === undefined || value === null
                ? "--"
                : value;
    }

}


// ============================================================
// RESET ENVIRONMENT
// ============================================================

function resetEnvironment() {

    setText(envElevation, "--");
    setText(envSlope, "--");
    setText(envAspect, "--");
    setText(envRainfall, "--");
    setText(envClay, "--");
    setText(envSand, "--");
    setText(envPh, "--");

    setText(rainfall24h, "--");
    setText(rainfall3day, "--");
    setText(rainfall7day, "--");

}


// ============================================================
// UPDATE ENVIRONMENT
// ============================================================

function updateEnvironment(environment) {

    if (!environment) {
        resetEnvironment();
        return;
    }

    setText(
        envElevation,
        environment.elevation ?? "--"
    );

    setText(
        envSlope,
        environment.slope ?? "--"
    );

    setText(
        envAspect,
        environment.aspect ?? "--"
    );

    setText(
        envRainfall,
        environment.annual_rainfall ?? "--"
    );

    setText(
        envClay,
        environment.soil_clay ?? "--"
    );

    setText(
        envSand,
        environment.soil_sand ?? "--"
    );

    setText(
        envPh,
        environment.soil_ph ?? "--"
    );

    setText(
        rainfall24h,
        environment.rainfall_24h ?? "--"
    );

    setText(
        rainfall3day,
        environment.rainfall_3day ?? "--"
    );

    setText(
        rainfall7day,
        environment.rainfall_7day ?? "--"
    );

}


// ============================================================
// LOAD NORTHEAST INDIA BOUNDARIES
// ============================================================

async function loadRegion() {

    try {

        setStatus(
            "Loading Northeast India boundaries..."
        );

        const response =
            await fetch(
                "/ner-states",
                {
                    method: "GET",
                    cache: "default",
                    headers: {
                        "Accept":
                            "application/geo+json, application/json"
                    }
                }
            );

        if (!response.ok) {

            throw new Error(
                `NER boundary request failed: HTTP ${response.status}`
            );

        }

        const geo =
            await response.json();

        if (
            !geo ||
            geo.type !== "FeatureCollection" ||
            !Array.isArray(geo.features)
        ) {

            throw new Error(
                "Invalid NER GeoJSON received from Flask."
            );

        }

        if (geo.features.length === 0) {

            throw new Error(
                "No Northeast India boundaries were returned."
            );

        }

        console.log(
            "NER features received:",
            geo.features.length
        );

        if (regionLayer) {

            map.removeLayer(regionLayer);
            regionLayer = null;

        }

        regionLayer =
            L.geoJSON(
                geo,
                {

                    interactive: true,

                    style: function () {

                        return {
                            color: "#20dff2",
                            weight: 4,
                            opacity: 1,
                            fillColor: "#20dff2",
                            fillOpacity: 0.10,
                            lineCap: "round",
                            lineJoin: "round"
                        };

                    },

                    onEachFeature:
                        function (feature, layer) {

                            const stateName =
                                getFeatureStateName(
                                    feature
                                );

                            layer.stateName =
                                stateName;

                            if (stateName) {

                                layer.bindTooltip(
                                    stateName,
                                    {
                                        sticky: true,
                                        direction: "top"
                                    }
                                );

                            }

                            layer.on(
                                "mouseover",
                                function () {

                                    layer.setStyle({
                                        color: "#ffffff",
                                        weight: 5,
                                        opacity: 1,
                                        fillColor: "#20dff2",
                                        fillOpacity: 0.20
                                    });

                                    layer.bringToFront();

                                }
                            );

                            layer.on(
                                "mouseout",
                                function () {

                                    if (regionLayer) {
                                        regionLayer.resetStyle(
                                            layer
                                        );
                                    }

                                }
                            );

                            // ------------------------------------------------
                            // CLICKING A STATE
                            // ------------------------------------------------

                            layer.on(
                                "click",
                                function (event) {

                                    L.DomEvent.stopPropagation(
                                        event
                                    );

                                    const lat =
                                        event.latlng.lat;

                                    const lon =
                                        event.latlng.lng;

                                    selectLocation(
                                        lat,
                                        lon,
                                        stateName
                                    );

                                }
                            );

                        }

                }
            );

        regionLayer.addTo(map);

        regionReady = true;

        map.invalidateSize(true);

        regionLayer.bringToFront();

        const matchedStates = [];

        regionLayer.eachLayer(
            function (layer) {

                if (layer.stateName) {
                    matchedStates.push(
                        layer.stateName
                    );
                }

            }
        );

        console.log(
            "Matched boundary states:",
            matchedStates
        );

        console.log(
            "Matched boundary state count:",
            matchedStates.length
        );

        setStatus(
            "Northeast India boundaries loaded."
        );

        setTimeout(
            function () {

                map.invalidateSize(true);

                if (regionLayer) {
                    regionLayer.bringToFront();
                }

            },
            250
        );

        setTimeout(
            function () {

                map.invalidateSize(true);

                if (regionLayer) {
                    regionLayer.bringToFront();
                }

            },
            1000
        );

    } catch (error) {

        regionReady = false;

        console.error(
            "Boundary loading error:",
            error
        );

        setStatus(
            "⚠ Northeast India boundaries could not be loaded."
        );

    }

}


// ============================================================
// GET STATE FROM MAP POINT
// ============================================================

function getStateFromPoint(lat, lon) {

    if (!regionLayer) {
        return null;
    }

    let foundState = null;

    regionLayer.eachLayer(
        function (layer) {

            if (
                foundState ||
                !layer.getBounds ||
                !layer.stateName
            ) {
                return;
            }

            const bounds =
                layer.getBounds();

            if (
                bounds &&
                bounds.isValid() &&
                bounds.contains([lat, lon])
            ) {

                foundState =
                    layer.stateName;

            }

        }
    );

    return foundState;

}


// ============================================================
// PREDICTION LOADER
// ============================================================

function showPredictionLoader() {

    const loader =
        document.getElementById(
            "prediction-loader"
        );

    if (loader) {
        loader.classList.add("active");
    }

}


function hidePredictionLoader() {

    const loader =
        document.getElementById(
            "prediction-loader"
        );

    if (loader) {
        loader.classList.remove("active");
    }

}


// ============================================================
// LOADING UI
// ============================================================

function loading() {

    setText(
        riskEl,
        "..."
    );

    if (gauge) {

        gauge.style.background =
            "conic-gradient(" +
            "#20dff2 0deg, " +
            "rgba(255,255,255,.07) 0deg)";

    }

    setText(
        levelEl,
        "ANALYZING"
    );

    if (levelEl) {
        levelEl.className = "neutral";
    }

    setText(
        warningEl,
        "ANALYZING LOCATION"
    );

    if (warningEl) {
        warningEl.className =
            "warning warning-neutral";
    }

    setText(
        titleEl,
        "AI is analyzing this location"
    );

    setText(
        textEl,
        "Retrieving environmental data and live rainfall for the Random Forest prediction..."
    );

    if (reasonsEl) {
        reasonsEl.innerHTML = "";
    }

    resetEnvironment();

}


// ============================================================
// GAUGE UPDATE
// ============================================================

function gaugeUpdate(risk) {

    const value =
        Math.max(
            0,
            Math.min(
                100,
                Number(risk) || 0
            )
        );

    const degrees =
        value * 3.6;

    let color =
        "#27e5b8";

    if (value >= 70) {

        color =
            "#ff6575";

    } else if (value >= 40) {

        color =
            "#ffc857";

    }

    if (gauge) {

        gauge.style.background =
            `conic-gradient(
                ${color} ${degrees}deg,
                rgba(255,255,255,.07) ${degrees}deg
            )`;

    }

}


// ============================================================
// SHOW UNSUPPORTED LOCATION
// ============================================================

function showUnsupported(state) {

    setText(
        riskEl,
        "--"
    );

    if (gauge) {

        gauge.style.background =
            "conic-gradient(" +
            "#ff6575 0deg, " +
            "rgba(255,255,255,.07) 0deg)";

    }

    setText(
        levelEl,
        "UNSUPPORTED REGION"
    );

    if (levelEl) {
        levelEl.className = "neutral";
    }

    setText(
        warningEl,
        "LOCATION NOT SUPPORTED"
    );

    if (warningEl) {
        warningEl.className =
            "warning warning-high";
    }

    setText(
        titleEl,
        "Northeast India only"
    );

    setText(
        textEl,
        state
            ? `Selected location is in ${state}, which is outside the supported model region.`
            : "This location is outside the supported Northeast India model region."
    );

    if (reasonsEl) {

        reasonsEl.innerHTML = "";

        const reason1 =
            document.createElement(
                "div"
            );

        reason1.className =
            "reason";

        reason1.textContent =
            "📍 Prediction is available only for Northeast India.";

        reasonsEl.appendChild(
            reason1
        );

        const reason2 =
            document.createElement(
                "div"
            );

        reason2.className =
            "reason";

        reason2.textContent =
            "Supported: Arunachal Pradesh, Assam, Manipur, Meghalaya, Mizoram, Nagaland, Sikkim and Tripura.";

        reasonsEl.appendChild(
            reason2
        );

    }

    resetEnvironment();

    setStatus(
        "⚠ Location is outside the supported Northeast India model region."
    );

}


// ============================================================
// BROWSER-SIDE OPEN-METEO
// ============================================================
//
// THIS IS THE IMPORTANT FIX FOR RENDER.
//
// Browser:
//     ↓
// Open-Meteo
//     ↓
// rainfall_24h / rainfall_3day / rainfall_7day
//     ↓
// Render Flask /predict
//     ↓
// Random Forest
//
// Render itself no longer needs to contact Open-Meteo
// for dashboard predictions.
//

async function getBrowserRainfall(lat, lon) {

    const numericLat =
        Number(lat);

    const numericLon =
        Number(lon);

    if (
        !Number.isFinite(numericLat) ||
        !Number.isFinite(numericLon)
    ) {

        throw new Error(
            "Invalid coordinates for rainfall request."
        );

    }

    const key =
        `${numericLat.toFixed(4)},${numericLon.toFixed(4)}`;

    const now =
        Date.now();

    // --------------------------------------------------------
    // CACHE
    // --------------------------------------------------------

    const cached =
        BROWSER_WEATHER_CACHE.get(key);

    if (
        cached &&
        now - cached.time <
            BROWSER_WEATHER_CACHE_TTL
    ) {

        console.log(
            "Using cached Open-Meteo rainfall:",
            key
        );

        return {
            ...cached.data,
            mode: "browser-cache"
        };

    }

    // --------------------------------------------------------
    // RATE LIMIT REQUESTS
    // --------------------------------------------------------

    const elapsed =
        Date.now() -
        lastBrowserWeatherRequest;

    const wait =
        1100 - elapsed;

    if (wait > 0) {

        await new Promise(
            function (resolve) {
                setTimeout(
                    resolve,
                    wait
                );
            }
        );

    }

    lastBrowserWeatherRequest =
        Date.now();

    // --------------------------------------------------------
    // OPEN-METEO URL
    // --------------------------------------------------------

    const url =
        "https://api.open-meteo.com/v1/forecast" +
        `?latitude=${encodeURIComponent(numericLat)}` +
        `&longitude=${encodeURIComponent(numericLon)}` +
        "&current=rain,precipitation" +
        "&hourly=rain" +
        "&past_hours=168" +
        "&forecast_hours=1" +
        "&timezone=auto" +
        "&cell_selection=land";

    console.log(
        "Fetching browser-side Open-Meteo:",
        url
    );

    const response =
        await fetch(
            url,
            {
                method: "GET",
                headers: {
                    "Accept":
                        "application/json"
                }
            }
        );

    if (!response.ok) {

        throw new Error(
            `Open-Meteo returned HTTP ${response.status}.`
        );

    }

    const data =
        await response.json();

    const hourly =
        data.hourly || {};

    const rainfall =
        Array.isArray(hourly.rain)
            ? hourly.rain.map(Number)
            : [];

    if (rainfall.length < 168) {

        throw new Error(
            "Open-Meteo did not return enough hourly rainfall data."
        );

    }

    const cleanRainfall =
        rainfall.map(
            function (value) {

                return Number.isFinite(value)
                    ? value
                    : 0;

            }
        );

    const current =
        data.current || {};

    const rainfall_24h =
        Number(
            cleanRainfall
                .slice(-24)
                .reduce(
                    (sum, value) =>
                        sum + value,
                    0
                )
                .toFixed(2)
        );

    const rainfall_3day =
        Number(
            cleanRainfall
                .slice(-72)
                .reduce(
                    (sum, value) =>
                        sum + value,
                    0
                )
                .toFixed(2)
        );

    const rainfall_7day =
        Number(
            cleanRainfall
                .slice(-168)
                .reduce(
                    (sum, value) =>
                        sum + value,
                    0
                )
                .toFixed(2)
        );

    const result = {

        rainfall_24h,

        rainfall_3day,

        rainfall_7day,

        current_rain:
            Number(
                current.rain || 0
            ),

        current_precipitation:
            Number(
                current.precipitation || 0
            ),

        source:
            "Open-Meteo",

        mode:
            "browser-live"

    };

    // --------------------------------------------------------
    // SAVE CACHE
    // --------------------------------------------------------

    BROWSER_WEATHER_CACHE.set(
        key,
        {
            time: Date.now(),
            data: result
        }
    );

    console.log(
        "Browser rainfall:",
        result
    );

    return result;

}


// ============================================================
// SHOW PREDICTION RESULT
// ============================================================

function showResult(result) {

    const risk =
        Number(result.risk);

    const safeRisk =
        Number.isFinite(risk)
            ? Math.max(
                0,
                Math.min(
                    100,
                    risk
                )
            )
            : 0;

    // --------------------------------------------------------
    // LOCATION
    // --------------------------------------------------------

    if (result.state) {

        setText(
            stateEl,
            result.state
        );

    }

    if (
        result.latitude !==
        undefined
    ) {

        setText(
            latEl,
            Number(
                result.latitude
            ).toFixed(6)
        );

    }

    if (
        result.longitude !==
        undefined
    ) {

        setText(
            lonEl,
            Number(
                result.longitude
            ).toFixed(6)
        );

    }

    // --------------------------------------------------------
    // RISK
    // --------------------------------------------------------

    setText(
        riskEl,
        safeRisk.toFixed(1)
    );

    gaugeUpdate(
        safeRisk
    );

    const level =
        String(
            result.level ||
            (
                safeRisk >= 70
                    ? "HIGH"
                    : safeRisk >= 40
                        ? "MODERATE"
                        : "LOW"
            )
        ).toUpperCase();

    setText(
        levelEl,
        level
    );

    if (levelEl) {

        if (safeRisk >= 70) {

            levelEl.className =
                "high";

        } else if (safeRisk >= 40) {

            levelEl.className =
                "moderate";

        } else {

            levelEl.className =
                "low";

        }

    }

    // --------------------------------------------------------
    // HIGH RISK ALERT
    // --------------------------------------------------------

    if (safeRisk >= 60) {

        const environment =
            result.environment || {};

        const elevation =
            Number(
                environment.elevation
            );

        const rain24 =
            Number(
                environment.rainfall_24h
            );

        const rain3 =
            Number(
                environment.rainfall_3day
            );

        const rain7 =
            Number(
                environment.rainfall_7day
            );

        setTimeout(
            function () {

                alert(
                    "⚠ HIGH LANDSLIDE RISK\n\n" +
                    "Location: " +
                    (
                        result.state ||
                        "Selected location"
                    ) +
                    "\n\n" +
                    "Risk Score: " +
                    safeRisk.toFixed(1) +
                    "%\n\n" +
                    "Elevation: " +
                    (
                        Number.isFinite(elevation)
                            ? elevation.toFixed(2) + " m"
                            : "--"
                    ) +
                    "\n\n" +
                    "Live Rainfall:\n" +
                    "Last 24 Hours: " +
                    (
                        Number.isFinite(rain24)
                            ? rain24.toFixed(2) + " mm"
                            : "--"
                    ) +
                    "\n" +
                    "Last 3 Days: " +
                    (
                        Number.isFinite(rain3)
                            ? rain3.toFixed(2) + " mm"
                            : "--"
                    ) +
                    "\n" +
                    "Last 7 Days: " +
                    (
                        Number.isFinite(rain7)
                            ? rain7.toFixed(2) + " mm"
                            : "--"
                    ) +
                    "\n\n" +
                    "This location has a high landslide susceptibility score.\n" +
                    "Please monitor the location and current environmental conditions."
                );

            },
            150
        );

    }

    // --------------------------------------------------------
    // WARNING
    // --------------------------------------------------------

    if (warningEl) {

        if (safeRisk >= 70) {

            setText(
                warningEl,
                "HIGH LANDSLIDE SUSCEPTIBILITY"
            );

            warningEl.className =
                "warning warning-high";

        } else if (safeRisk >= 40) {

            setText(
                warningEl,
                "MODERATE LANDSLIDE SUSCEPTIBILITY"
            );

            warningEl.className =
                "warning warning-moderate";

        } else {

            setText(
                warningEl,
                "LOWER LANDSLIDE SUSCEPTIBILITY"
            );

            warningEl.className =
                "warning warning-low";

        }

    }

    // --------------------------------------------------------
    // ANALYSIS
    // --------------------------------------------------------

    setText(
        titleEl,
        level + " RISK"
    );

    setText(
        textEl,
        result.message ||
        result.summary ||
        `${level} model susceptibility score.`
    );

    // --------------------------------------------------------
    // REASONS
    // --------------------------------------------------------

    if (reasonsEl) {

        reasonsEl.innerHTML = "";

        if (
            Array.isArray(
                result.reasons
            )
        ) {

            result.reasons.forEach(
                function (reason) {

                    const item =
                        document.createElement(
                            "div"
                        );

                    item.className =
                        "reason";

                    item.textContent =
                        "• " + reason;

                    reasonsEl.appendChild(
                        item
                    );

                }
            );

        }

    }

    // --------------------------------------------------------
    // ENVIRONMENT
    // --------------------------------------------------------

    updateEnvironment(
        result.environment
    );

    setStatus(
        "Prediction completed."
    );

}


// ============================================================
// PREDICTION
// ============================================================
//
// IMPORTANT:
// Browser gets rainfall first.
// Then rainfall is included in /predict.
//
// This is the Render fix.
//

async function predict(
    lat,
    lon,
    state = null
) {

    if (predictionInProgress) {

        console.log(
            "Prediction already running."
        );

        return;

    }

    predictionInProgress = true;

    showPredictionLoader();

    loading();

    try {

        // ----------------------------------------------------
        // VALIDATE NER
        // ----------------------------------------------------

        const detectedState =
            state ||
            getStateFromPoint(
                lat,
                lon
            );

        if (!detectedState) {

            showUnsupported(
                null
            );

            return;

        }

        if (
            !SUPPORTED_STATE_NAMES.includes(
                normalizeStateName(
                    detectedState
                )
            )
        ) {

            showUnsupported(
                detectedState
            );

            return;

        }

        // ----------------------------------------------------
        // GET RAINFALL FROM BROWSER
        // ----------------------------------------------------

        setStatus(
            "Fetching live rainfall data..."
        );

        const weather =
            await getBrowserRainfall(
                lat,
                lon
            );

        // ----------------------------------------------------
        // SEND EVERYTHING TO FLASK
        // ----------------------------------------------------

        setStatus(
            weather.mode ===
            "browser-cache"
                ? "Using cached rainfall data. Running AI analysis..."
                : "Live rainfall received. Running AI analysis..."
        );

        const controller =
            new AbortController();

        const timeout =
            setTimeout(
                function () {
                    controller.abort();
                },
                30000
            );

        let response;

        try {

            response =
                await fetch(
                    "/predict",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body:
                            JSON.stringify({

                                latitude:
                                    Number(lat),

                                longitude:
                                    Number(lon),

                                state:
                                    detectedState,

                                weather: {

                                    rainfall_24h:
                                        weather.rainfall_24h,

                                    rainfall_3day:
                                        weather.rainfall_3day,

                                    rainfall_7day:
                                        weather.rainfall_7day,

                                    current_rain:
                                        weather.current_rain,

                                    current_precipitation:
                                        weather.current_precipitation,

                                    source:
                                        weather.source,

                                    mode:
                                        weather.mode

                                }

                            }),

                        signal:
                            controller.signal
                    }
                );

        } finally {

            clearTimeout(
                timeout
            );

        }

        // ----------------------------------------------------
        // READ JSON SAFELY
        // ----------------------------------------------------

        let result = {};

        try {

            result =
                await response.json();

        } catch (jsonError) {

            throw new Error(
                `Server returned HTTP ${response.status}.`
            );

        }

        console.log(
            "Prediction response:",
            result
        );

        // ----------------------------------------------------
        // UNSUPPORTED REGION
        // ----------------------------------------------------

        if (
            response.status === 403 ||
            result.supported === false
        ) {

            showUnsupported(
                result.state ||
                detectedState
            );

            return;

        }

        // ----------------------------------------------------
        // SERVER ERROR
        // ----------------------------------------------------

        if (!response.ok) {

            throw new Error(
                result.error ||
                result.details ||
                `Prediction failed with HTTP ${response.status}.`
            );

        }

        // ----------------------------------------------------
        // SUCCESS
        // ----------------------------------------------------

        showResult(
            result
        );

    } catch (error) {

        console.error(
            "Prediction error:",
            error
        );

        setText(
            riskEl,
            "--"
        );

        if (gauge) {

            gauge.style.background =
                "conic-gradient(" +
                "rgba(255,255,255,.10) 0deg, " +
                "rgba(255,255,255,.07) 0deg)";

        }

        setText(
            levelEl,
            "ERROR"
        );

        if (levelEl) {
            levelEl.className =
                "neutral";
        }

        setText(
            warningEl,
            "PREDICTION UNAVAILABLE"
        );

        if (warningEl) {
            warningEl.className =
                "warning warning-high";
        }

        setText(
            titleEl,
            "Analysis temporarily unavailable"
        );

        setText(
            textEl,
            error.name === "AbortError"
                ? "The prediction request took too long. Please try the location again."
                : (
                    error.message ||
                    "The prediction could not be completed."
                )
        );

        if (reasonsEl) {
            reasonsEl.innerHTML = "";
        }

        resetEnvironment();

        setStatus(
            "Prediction failed. Please try again."
        );

    } finally {

        predictionInProgress = false;

        hidePredictionLoader();

    }

}


// ============================================================
// SELECT LOCATION
// ============================================================

async function selectLocation(
    lat,
    lon,
    state = null
) {

    const detectedState =
        state ||
        getStateFromPoint(
            lat,
            lon
        );

    if (!detectedState) {

        showUnsupported(
            null
        );

        return;

    }

    if (
        !SUPPORTED_STATE_NAMES.includes(
            normalizeStateName(
                detectedState
            )
        )
    ) {

        showUnsupported(
            detectedState
        );

        return;

    }

    // --------------------------------------------------------
    // MAP MARKER
    // --------------------------------------------------------

    if (marker) {

        map.removeLayer(
            marker
        );

    }

    marker =
        L.marker(
            [
                lat,
                lon
            ]
        ).addTo(
            map
        );

    marker.bindPopup(
        `
        <b>${detectedState}</b><br>
        Latitude: ${Number(lat).toFixed(4)}<br>
        Longitude: ${Number(lon).toFixed(4)}
        `
    ).openPopup();

    // --------------------------------------------------------
    // LOCATION UI
    // --------------------------------------------------------

    setText(
        nameEl,
        detectedState
    );

    setText(
        stateEl,
        detectedState
    );

    setText(
        latEl,
        Number(lat).toFixed(6)
    );

    setText(
        lonEl,
        Number(lon).toFixed(6)
    );

    // --------------------------------------------------------
    // PREDICT
    // --------------------------------------------------------

    await predict(
        lat,
        lon,
        detectedState
    );

}


// ============================================================
// MAP CLICK
// ============================================================

map.on(
    "click",
    function (event) {

        const lat =
            event.latlng.lat;

        const lon =
            event.latlng.lng;

        const state =
            getStateFromPoint(
                lat,
                lon
            );

        if (!state) {

            showUnsupported(
                null
            );

            return;

        }

        selectLocation(
            lat,
            lon,
            state
        );

    }
);


// ============================================================
// SEARCH LOCATION
// ============================================================

async function searchLocation() {

    const query =
        input
            ? input.value.trim()
            : "";

    if (!query) {

        setStatus(
            "Please enter a location."
        );

        return;

    }

    if (searchBtn) {

        searchBtn.disabled =
            true;

        searchBtn.textContent =
            "Searching...";

    }

    setStatus(
        `Searching for "${query}"...`
    );

    try {

        const response =
            await fetch(
                "/search-location",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify({
                            location:
                                query
                        })
                }
            );

        let result = {};

        try {

            result =
                await response.json();

        } catch (error) {

            throw new Error(
                `Location service returned HTTP ${response.status}.`
            );

        }

        if (!response.ok) {

            throw new Error(
                result.error ||
                "Location not found."
            );

        }

        const lat =
            Number(
                result.latitude
            );

        const lon =
            Number(
                result.longitude
            );

        if (
            !Number.isFinite(lat) ||
            !Number.isFinite(lon)
        ) {

            throw new Error(
                "Invalid coordinates returned by search."
            );

        }

        // ----------------------------------------------------
        // CHECK SUPPORTED REGION BEFORE PREDICTION
        // ----------------------------------------------------

        if (
            result.supported === false
        ) {

            map.setView(
                [lat, lon],
                10
            );

            setText(
                nameEl,
                result.display_name ||
                query
            );

            setText(
                stateEl,
                result.state ||
                "--"
            );

            setText(
                latEl,
                lat.toFixed(6)
            );

            setText(
                lonEl,
                lon.toFixed(6)
            );

            showUnsupported(
                result.state
            );

            return;

        }

        // ----------------------------------------------------
        // MOVE MAP
        // ----------------------------------------------------

        map.setView(
            [lat, lon],
            10
        );

        // ----------------------------------------------------
        // MARKER
        // ----------------------------------------------------

        if (marker) {

            map.removeLayer(
                marker
            );

        }

        marker =
            L.marker(
                [lat, lon]
            ).addTo(
                map
            );

        marker.bindPopup(
            `<b>${
                result.state ||
                result.display_name ||
                query
            }</b>`
        ).openPopup();

        // ----------------------------------------------------
        // LOCATION UI
        // ----------------------------------------------------

        setText(
            nameEl,
            result.display_name ||
            query
        );

        setText(
            stateEl,
            result.state ||
            "--"
        );

        setText(
            latEl,
            lat.toFixed(6)
        );

        setText(
            lonEl,
            lon.toFixed(6)
        );

        // ----------------------------------------------------
        // PREDICTION
        // ----------------------------------------------------

        await predict(
            lat,
            lon,
            result.state || null
        );

        setStatus(
            "📍 " +
            (
                result.display_name ||
                query
            )
        );

    } catch (error) {

        console.error(
            "Search error:",
            error
        );

        setStatus(
            "❌ " +
            (
                error.message ||
                "Location search failed."
            )
        );

    } finally {

        if (searchBtn) {

            searchBtn.disabled =
                false;

            searchBtn.textContent =
                "Search";

        }

    }

}


// ============================================================
// SEARCH BUTTON
// ============================================================

if (searchBtn) {

    searchBtn.addEventListener(
        "click",
        searchLocation
    );

}


// ============================================================
// ENTER KEY
// ============================================================

if (input) {

    input.addEventListener(
        "keydown",
        function (event) {

            if (
                event.key === "Enter"
            ) {

                event.preventDefault();

                searchLocation();

            }

        }
    );

}


// ============================================================
// ABOUT MODAL
// ============================================================

const aboutButton =
    $("about");

const closeButton =
    $("close");

const modal =
    $("modal");

if (
    aboutButton &&
    modal
) {

    aboutButton.addEventListener(
        "click",
        function () {

            modal.classList.remove(
                "hidden"
            );

        }
    );

}

if (
    closeButton &&
    modal
) {

    closeButton.addEventListener(
        "click",
        function () {

            modal.classList.add(
                "hidden"
            );

        }
    );

}

if (modal) {

    modal.addEventListener(
        "click",
        function (event) {

            if (
                event.target === modal
            ) {

                modal.classList.add(
                    "hidden"
                );

            }

        }
    );

}


// ============================================================
// INITIALIZE MAP + BOUNDARY
// ============================================================

window.addEventListener(
    "load",
    function () {

        setTimeout(
            function () {

                map.invalidateSize(
                    true
                );

                loadRegion();

            },
            300
        );

    }
);


// ============================================================
// BACKEND HEALTH CHECK
// ============================================================

window.addEventListener(
    "load",
    async function () {

        try {

            const response =
                await fetch(
                    "/health"
                );

            if (!response.ok) {
                return;
            }

            const health =
                await response.json();

            console.log(
                "Backend health:",
                health
            );

            if (
                health.model_loaded === false
            ) {

                setStatus(
                    "⚠ Model not loaded. Check the models folder."
                );

            }

        } catch (error) {

            console.warn(
                "Backend health check unavailable."
            );

        }

    }
);


// ============================================================
// MOBILE NAVBAR
// ============================================================

const menuBtn =
    document.getElementById(
        "menuBtn"
    );

const navLinks =
    document.getElementById(
        "navLinks"
    );

if (
    menuBtn &&
    navLinks
) {

    menuBtn.addEventListener(
        "click",
        function () {

            const isOpen =
                navLinks.classList.toggle(
                    "active"
                );

            menuBtn.textContent =
                isOpen
                    ? "✕"
                    : "☰";

            menuBtn.setAttribute(
                "aria-expanded",
                isOpen
                    ? "true"
                    : "false"
            );

            menuBtn.setAttribute(
                "aria-label",
                isOpen
                    ? "Close navigation menu"
                    : "Open navigation menu"
            );

        }
    );

    navLinks
        .querySelectorAll("a")
        .forEach(
            function (link) {

                link.addEventListener(
                    "click",
                    function () {

                        navLinks.classList.remove(
                            "active"
                        );

                        menuBtn.textContent =
                            "☰";

                        menuBtn.setAttribute(
                            "aria-expanded",
                            "false"
                        );

                        menuBtn.setAttribute(
                            "aria-label",
                            "Open navigation menu"
                        );

                    }
                );

            }
        );

}


// ============================================================
// FINAL
// ============================================================

console.log(
    "LandslideGuard frontend loaded successfully."
);

console.log(
    "NER states:",
    NORTHEAST_STATES
);

console.log(
    "Browser-side Open-Meteo rainfall:",
    "ENABLED"
);