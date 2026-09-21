// ============================================================
// GLOBAL LANDSLIDEGUARD
// FINAL CORRECTED FRONTEND JAVASCRIPT
// ============================================================


// ============================================================
// MAP
// ============================================================

const map = L.map("map", {

    worldCopyJump: true,

    preferCanvas: true

}).setView(

    [25.5, 93.5],

    6

);


// ============================================================
// OPENSTREETMAP
// ============================================================

L.tileLayer(

    "https://tile.openstreetmap.org/{z}/{x}/{y}.png",

    {

        maxZoom: 19,

        attribution:
            "&copy; OpenStreetMap contributors"

    }

).addTo(map);


// ============================================================
// DOM HELPER
// ============================================================

const $ = id =>
    document.getElementById(id);


// ============================================================
// DOM ELEMENTS
// ============================================================

const input =
    $("location-search");

const searchBtn =
    $("search-button");

const status =
    $("search-status");

const nameEl =
    $("location-name");

const stateEl =
    $("state-name");

const latEl =
    $("latitude");

const lonEl =
    $("longitude");

const riskEl =
    $("risk-value");

const levelEl =
    $("risk-level");

const gauge =
    $("gauge");

const warningEl =
    $("warning");

const titleEl =
    $("analysis-title");

const textEl =
    $("analysis-text");

const reasonsEl =
    $("reasons");


// ============================================================
// ENVIRONMENT ELEMENTS
// ============================================================

const envElevation =
    $("env-elevation");

const envSlope =
    $("env-slope");

const envAspect =
    $("env-aspect");

const envRainfall =
    $("env-rainfall");

const envClay =
    $("env-clay");

const envSand =
    $("env-sand");

const envPh =
    $("env-ph");


// ============================================================
// DYNAMIC RAINFALL ELEMENTS
// ============================================================

const rainfall24h =
    $("dynamic-rainfall-24h");

const rainfall3day =
    $("dynamic-rainfall-3day");

const rainfall7day =
    $("dynamic-rainfall-7day");


// ============================================================
// VARIABLES
// ============================================================

let marker = null;

let regionLayer = null;

let regionReady = false;

let predictionInProgress = false;


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

        .replace(
            /[\u0300-\u036f]/g,
            ""
        )

        .trim()

        .toLowerCase()

        .replace(
            /\s+/g,
            " "
        );

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

        feature &&
            feature.properties

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


    for (
        const key of possibleKeys
    ) {

        const value =
            properties[key];


        if (

            value !== undefined &&

            value !== null &&

            String(value).trim() !== ""

        ) {

            return String(
                value
            ).trim();

        }

    }


    for (
        const key of Object.keys(properties)
    ) {

        const value = String(

            properties[key] ?? ""

        ).trim();


        if (

            value &&

            SUPPORTED_STATE_NAMES.includes(

                normalizeStateName(
                    value
                )

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

        status.textContent =
            message;

    }

    console.log(
        message
    );

}


// ============================================================
// SAFE TEXT
// ============================================================

function setText(
    element,
    value
) {

    if (element) {

        element.textContent =
            value;

    }

}


// ============================================================
// RESET ENVIRONMENT
// ============================================================

function resetEnvironment() {

    setText(
        envElevation,
        "--"
    );

    setText(
        envSlope,
        "--"
    );

    setText(
        envAspect,
        "--"
    );

    setText(
        envRainfall,
        "--"
    );

    setText(
        envClay,
        "--"
    );

    setText(
        envSand,
        "--"
    );

    setText(
        envPh,
        "--"
    );


    setText(
        rainfall24h,
        "--"
    );

    setText(
        rainfall3day,
        "--"
    );

    setText(
        rainfall7day,
        "--"
    );

}


// ============================================================
// UPDATE ENVIRONMENT
// IMPORTANT:
// This function ONLY updates existing HTML.
// It does NOT create or move cards.
// ============================================================

function updateEnvironment(
    environment
) {

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


    // --------------------------------------------------------
    // LIVE RAINFALL
    // --------------------------------------------------------

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

        console.log(
            "Loading Northeast India boundaries..."
        );


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

            geo.type !==
            "FeatureCollection" ||

            !Array.isArray(
                geo.features
            )

        ) {

            throw new Error(
                "Invalid NER GeoJSON received from Flask."
            );

        }


        if (
            geo.features.length === 0
        ) {

            throw new Error(
                "No Northeast India boundaries were returned."
            );

        }


        console.log(
            "NER features received:",
            geo.features.length
        );


        if (regionLayer) {

            map.removeLayer(
                regionLayer
            );

            regionLayer = null;

        }


        // ====================================================
        // CREATE NER GEOJSON LAYER
        // ====================================================

        regionLayer = L.geoJSON(

            geo,

            {

                interactive: true,


                style: function () {

                    return {

                        color:
                            "#20dff2",

                        weight:
                            4,

                        opacity:
                            1,

                        fillColor:
                            "#20dff2",

                        fillOpacity:
                            0.10,

                        lineCap:
                            "round",

                        lineJoin:
                            "round"

                    };

                },


                onEachFeature:
                    function (
                        feature,
                        layer
                    ) {

                        const stateName =
                            getFeatureStateName(
                                feature
                            );


                        layer.stateName =
                            stateName;


                        // ------------------------------------------------
                        // TOOLTIP
                        // ------------------------------------------------

                        if (stateName) {

                            layer.bindTooltip(

                                stateName,

                                {

                                    sticky:
                                        true,

                                    direction:
                                        "top"

                                }

                            );

                        }


                        // ------------------------------------------------
                        // MOUSE OVER
                        // ------------------------------------------------

                        layer.on(

                            "mouseover",

                            function () {

                                layer.setStyle({

                                    color:
                                        "#ffffff",

                                    weight:
                                        5,

                                    opacity:
                                        1,

                                    fillColor:
                                        "#20dff2",

                                    fillOpacity:
                                        0.20

                                });


                                layer.bringToFront();

                            }

                        );


                        // ------------------------------------------------
                        // MOUSE OUT
                        // ------------------------------------------------

                        layer.on(

                            "mouseout",

                            function () {

                                if (
                                    regionLayer
                                ) {

                                    regionLayer.resetStyle(
                                        layer
                                    );

                                }

                            }

                        );


                        // ------------------------------------------------
                        // IMPORTANT:
                        // STOP EVENT FROM REACHING MAP CLICK
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


        regionLayer.addTo(
            map
        );


        regionReady = true;


        map.invalidateSize(
            true
        );


        regionLayer.bringToFront();


        // --------------------------------------------------------
        // LOG MATCHED STATES
        // --------------------------------------------------------

        const matchedStates = [];


        regionLayer.eachLayer(

            function (layer) {

                if (
                    layer.stateName
                ) {

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


        console.log(
            "Northeast India boundaries loaded."
        );


        setStatus(
            "Northeast India boundaries loaded."
        );


        // --------------------------------------------------------
        // MAP SIZE REFRESH
        // --------------------------------------------------------

        setTimeout(

            function () {

                map.invalidateSize(
                    true
                );

                if (
                    regionLayer
                ) {

                    regionLayer.bringToFront();

                }

            },

            250

        );


        setTimeout(

            function () {

                map.invalidateSize(
                    true
                );

                if (
                    regionLayer
                ) {

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

function getStateFromPoint(
    lat,
    lon
) {

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

                bounds.contains(
                    [lat, lon]
                )

            ) {

                foundState =
                    layer.stateName;

            }

        }

    );


    return foundState;

}



/* =========================================================
   PREDICTION LOADER
   ========================================================= */

function showPredictionLoader() {
    const loader = document.getElementById(
        "prediction-loader"
    );

    if (loader) {
        loader.classList.add("active");
    }
}

function hidePredictionLoader() {
    const loader = document.getElementById(
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

        levelEl.className =
            "neutral";

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

        reasonsEl.innerHTML =
            "";

    }


    resetEnvironment();

}


// ============================================================
// GAUGE UPDATE
// ============================================================

function gaugeUpdate(
    risk
) {

    const value = Math.max(

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


    if (
        value >= 70
    ) {

        color =
            "#ff6575";

    }

    else if (
        value >= 40
    ) {

        color =
            "#ffc857";

    }


    if (gauge) {

        gauge.style.background =

            `conic-gradient(

                ${color}
                ${degrees}deg,

                rgba(255,255,255,.07)
                ${degrees}deg

            )`;

    }

}


// ============================================================
// SHOW UNSUPPORTED LOCATION
// ============================================================

function showUnsupported(
    state
) {

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

        levelEl.className =
            "neutral";

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

        reasonsEl.innerHTML =
            "";


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
// SHOW PREDICTION RESULT
// ============================================================

function showResult(
    result
) {

    const risk =
        Number(
            result.risk
        );


    const safeRisk =

        Number.isFinite(
            risk
        )

            ? risk

            : 0;


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

            "LOW"

        ).toUpperCase();


    setText(

        levelEl,

        level

    );


    if (levelEl) {

        if (
            safeRisk >= 70
        ) {

            levelEl.className =
                "high";

        }

        else if (
            safeRisk >= 40
        ) {

            levelEl.className =
                "moderate";

        }

        else {

            levelEl.className =
                "low";

        }

    }

    // ========================================================
    // HIGH RISK ALERT POPUP
    // ========================================================

    if (safeRisk >= 60) {

        const environment =
            result.environment || {};

        const elevation =
            Number(environment.elevation);

        const rainfall24h =
            Number(environment.rainfall_24h);

        const rainfall3day =
            Number(environment.rainfall_3day);

        const rainfall7day =
            Number(environment.rainfall_7day);


        const elevationText =
            Number.isFinite(elevation)
                ? elevation.toFixed(2) + " m"
                : "--";


        const rainfall24hText =
            Number.isFinite(rainfall24h)
                ? rainfall24h.toFixed(2) + " mm"
                : "--";


        const rainfall3dayText =
            Number.isFinite(rainfall3day)
                ? rainfall3day.toFixed(2) + " mm"
                : "--";


        const rainfall7dayText =
            Number.isFinite(rainfall7day)
                ? rainfall7day.toFixed(2) + " mm"
                : "--";


        setTimeout(function () {

            alert(
                "⚠ HIGH LANDSLIDE RISK\n\n" +
                "Risk Score: " + safeRisk.toFixed(1) + "%\n\n" +
                "Elevation: " +
                (Number.isFinite(elevation)
                    ? elevation.toFixed(2) + " m"
                    : "--") +
                "\n\n" +
                "Live Rainfall:\n" +
                "Last 24 Hours: " +
                (Number.isFinite(rainfall24h)
                    ? rainfall24h.toFixed(2) + " mm"
                    : "--") +
                "\n" +
                "Last 3 Days: " +
                (Number.isFinite(rainfall3day)
                    ? rainfall3day.toFixed(2) + " mm"
                    : "--") +
                "\n" +
                "Last 7 Days: " +
                (Number.isFinite(rainfall7day)
                    ? rainfall7day.toFixed(2) + " mm"
                    : "--") +
                "\n\n" +
                "This location has a high landslide susceptibility score.\n" +
                "Please monitor the location and current environmental conditions."
            );

        }, 150);

    }


    // --------------------------------------------------------
    // WARNING
    // --------------------------------------------------------

    if (warningEl) {

        if (
            safeRisk >= 70
        ) {

            setText(

                warningEl,

                "HIGH LANDSLIDE SUSCEPTIBILITY"

            );


            warningEl.className =
                "warning warning-high";

        }

        else if (
            safeRisk >= 40
        ) {

            setText(

                warningEl,

                "MODERATE LANDSLIDE SUSCEPTIBILITY"

            );


            warningEl.className =
                "warning warning-moderate";

        }

        else {

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

        reasonsEl.innerHTML =
            "";


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

async function predict(
    lat,
    lon,
    state = null
) {

    /* -----------------------------------------------------
       SHOW LOADER IMMEDIATELY
       ----------------------------------------------------- */

    showPredictionLoader();

    loading();


    setStatus(
        "Analyzing location and retrieving live rainfall..."
    );


    try {

        const controller =
            new AbortController();


        const timeout =
            setTimeout(
                function () {

                    controller.abort();

                },
                30000
            );

        // showPredictionLoader();

        const response =
            await fetch(
                "/predict",
                {

                    method:
                        "POST",

                    headers: {

                        "Content-Type":
                            "application/json"

                    },

                    body:
                        JSON.stringify({

                            latitude:
                                lat,

                            longitude:
                                lon,

                            state:
                                state

                        }),

                    signal:
                        controller.signal

                }
            );


        clearTimeout(
            timeout
        );


        const result =
            await response.json();


        console.log(
            "Prediction response:",
            result
        );


        if (!response.ok) {

            throw new Error(

                result.error ||

                result.details ||

                "Prediction failed."

            );

        }


        // Data has loaded successfully.
        // Hide the loader BEFORE showing the result,
        // because showResult() may display the high-risk alert.
        hidePredictionLoader();

        showResult(result);


    } catch (error) {

        console.error(
            "Prediction error:",
            error
        );


        if (
            error.name ===
            "AbortError"
        ) {

            setStatus(
                "Rainfall service is taking longer than expected. Please try again."
            );

        } else {

            setStatus(
                error.message ||
                "Prediction unavailable."
            );

        }


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
            "WAITING"
        );


        if (levelEl) {

            levelEl.className =
                "neutral";

        }


        setText(
            warningEl,
            "WAITING FOR ANALYSIS"
        );


        if (warningEl) {

            warningEl.className =
                "warning warning-neutral";

        }


        setText(
            titleEl,
            "Analysis temporarily unavailable"
        );


        setText(
            textEl,
            error.message ||
            "The rainfall service did not respond. Please try the location again."
        );

    } finally {
        /* -------------------------------------------------
           ALWAYS REMOVE LOADER
           ------------------------------------------------- */

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
    // MARKER
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

        Latitude:
        ${lat.toFixed(4)}<br>

        Longitude:
        ${lon.toFixed(4)}

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

        lat.toFixed(6)

    );


    setText(

        lonEl,

        lon.toFixed(6)

    );


    // --------------------------------------------------------
    // PREDICTION
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

                    method:
                        "POST",

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


        const result =
            await response.json();


        if (
            !response.ok
        ) {

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

            !Number.isFinite(
                lat
            )

            ||

            !Number.isFinite(
                lon
            )

        ) {

            throw new Error(

                "Invalid coordinates returned by search."

            );

        }


        // ----------------------------------------------------
        // MOVE MAP
        // ----------------------------------------------------

        map.setView(

            [

                lat,

                lon

            ],

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

                [

                    lat,

                    lon

                ]

            ).addTo(
                map
            );


        marker.bindPopup(

            `<b>

                ${result.state ||

            result.display_name ||

            query

            }

             </b>`

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
        // UNSUPPORTED
        // ----------------------------------------------------

        if (
            result.supported === false
        ) {

            showUnsupported(

                result.state

            );

            return;

        }


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

            error.message

        );

    }

    finally {

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

                event.key ===
                "Enter"

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

                event.target ===
                modal

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

                health.model_loaded ===
                false

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





// ======================================================
// MOBILE NAVBAR
// ======================================================

const menuBtn = document.getElementById("menuBtn");
const navLinks = document.getElementById("navLinks");

if (menuBtn && navLinks) {

    menuBtn.addEventListener("click", () => {

        navLinks.classList.toggle("active");

        // Change hamburger to X
        if (navLinks.classList.contains("active")) {
            menuBtn.textContent = "✕";
        } else {
            menuBtn.textContent = "☰";
        }

    });

}