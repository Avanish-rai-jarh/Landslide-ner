// ============================================================
// LANDSLIDEGUARD - EARLY WARNING MONITOR
// NER ONLY
// ============================================================
//
// IMPORTANT:
// This file is protected against accidental duplicate loading.
// Your HTML previously contained early-warning.js twice.
// ============================================================

if (!window.__LANDSLIDEGUARD_EARLY_WARNING_LOADED__) {

    window.__LANDSLIDEGUARD_EARLY_WARNING_LOADED__ = true;


    // ========================================================
    // WAIT UNTIL HTML IS READY
    // ========================================================

    document.addEventListener("DOMContentLoaded", function () {


        // ====================================================
        // HELPER
        // ====================================================

        const $ = function (id) {
            return document.getElementById(id);
        };


        // ====================================================
        // ELEMENTS
        // ====================================================

        const input =
            $("location-search");

        const searchButton =
            $("search-button");

        const status =
            $("search-status");

        const locationName =
            $("location-name");

        const stateName =
            $("state-name");

        const coordinates =
            $("coordinates");

        const warningLevel =
            $("warning-level");

        const warningDescription =
            $("warning-description");

        const riskValue =
            $("risk-value");

        const riskLevel =
            $("risk-level");

        const rainfall24 =
            $("rainfall-24h");

        const rainfall3 =
            $("rainfall-3day");

        const rainfall7 =
            $("rainfall-7day");

        const riskBar =
            $("risk-bar");

        const riskScore =
            $("risk-score");

        const rainfallBar =
            $("rainfall-bar");

        const rainfallSignal =
            $("rainfall-signal");

        const guidance =
            $("guidance");

        const elevation =
            $("elevation");

        const slope =
            $("slope");

        const aspect =
            $("aspect");

        const annualRainfall =
            $("annual-rainfall");

        const soilPh =
            $("soil-ph");


        // ====================================================
        // WARNING SIGNAL ENGINE
        // ====================================================

        const engineStatus =
            $("engine-status");

        const engineStatusTitle =
            $("engine-status-title");

        const engineStatusText =
            $("engine-status-text");

        const engineRisk =
            $("engine-risk");

        const engineRiskStatus =
            $("engine-risk-status");

        const engineRain24 =
            $("engine-rain24");

        const engineRain24Status =
            $("engine-rain24-status");

        const engineRain3 =
            $("engine-rain3");

        const engineRain3Status =
            $("engine-rain3-status");

        const engineRain7 =
            $("engine-rain7");

        const engineRain7Status =
            $("engine-rain7-status");


        // ====================================================
        // LOADER
        // ====================================================

        function showEarlyWarningLoader() {

            const loader =
                $("ew-loader");

            if (loader) {
                loader.classList.add("active");
            }

        }


        function hideEarlyWarningLoader() {

            const loader =
                $("ew-loader");

            if (loader) {
                loader.classList.remove("active");
            }

        }


        // ====================================================
        // TEXT HELPER
        // ====================================================

        function setText(
            element,
            value
        ) {

            if (element) {

                element.textContent =
                    value;

            }

        }


        // ====================================================
        // STATUS
        // ====================================================

        function setStatus(message) {

            setText(
                status,
                message
            );

        }


        // ====================================================
        // RESET PAGE
        // ====================================================

        function resetPage() {

            setText(
                locationName,
                "No location selected"
            );

            setText(
                stateName,
                "--"
            );

            setText(
                coordinates,
                "--"
            );

            setText(
                warningLevel,
                "NO LOCATION"
            );

            if (warningLevel) {

                warningLevel.className =
                    "status-neutral";

            }


            setText(
                warningDescription,
                "Select a location in Northeast India to calculate its current susceptibility and rainfall signals."
            );


            setText(
                riskValue,
                "--"
            );

            setText(
                riskLevel,
                "No assessment available."
            );


            setText(
                rainfall24,
                "--"
            );

            setText(
                rainfall3,
                "--"
            );

            setText(
                rainfall7,
                "--"
            );


            setText(
                riskScore,
                "--"
            );

            setText(
                rainfallSignal,
                "--"
            );


            setText(
                guidance,
                "Select a location to receive location-specific monitoring information."
            );


            setText(
                elevation,
                "--"
            );

            setText(
                slope,
                "--"
            );

            setText(
                aspect,
                "--"
            );

            setText(
                annualRainfall,
                "--"
            );

            setText(
                soilPh,
                "--"
            );


            if (riskBar) {

                riskBar.style.width =
                    "0%";

            }


            if (rainfallBar) {

                rainfallBar.style.width =
                    "0%";

            }


            if (engineStatus) {

                engineStatus.className =
                    "engine-status engine-neutral";

            }


            setText(
                engineStatusTitle,
                "NO ASSESSMENT"
            );

            setText(
                engineStatusText,
                "Select a location to evaluate monitoring signals."
            );

            setText(
                engineRisk,
                "--"
            );

            setText(
                engineRiskStatus,
                "--"
            );

            setText(
                engineRain24,
                "--"
            );

            setText(
                engineRain24Status,
                "--"
            );

            setText(
                engineRain3,
                "--"
            );

            setText(
                engineRain3Status,
                "--"
            );

            setText(
                engineRain7,
                "--"
            );

            setText(
                engineRain7Status,
                "--"
            );


            // Reset chart values

            setText(
                $("chart-risk-value"),
                "--"
            );

            setText(
                $("chart-rain24-value"),
                "--"
            );

            setText(
                $("chart-rain3-value"),
                "--"
            );

            setText(
                $("chart-rain7-value"),
                "--"
            );


            if ($("chart-risk-bar")) {
                $("chart-risk-bar").style.width = "0%";
            }

            if ($("chart-rain24-bar")) {
                $("chart-rain24-bar").style.width = "0%";
            }

            if ($("chart-rain3-bar")) {
                $("chart-rain3-bar").style.width = "0%";
            }

            if ($("chart-rain7-bar")) {
                $("chart-rain7-bar").style.width = "0%";
            }

        }


        // ====================================================
        // RAINFALL VISUAL SCALE
        // ====================================================

        function rainfallSignalPercent(
            rainfall
        ) {

            const value =
                Number(rainfall);


            if (
                !Number.isFinite(value) ||
                value <= 0
            ) {

                return 0;

            }


            return Math.min(
                100,
                value
            );

        }


        // ====================================================
        // RAINFALL BAND
        // ====================================================

        function getRainfallBand(
            rainfall
        ) {

            const value =
                Number(rainfall);


            if (
                !Number.isFinite(value)
            ) {

                return {
                    label: "--",
                    className: "signal-neutral"
                };

            }


            if (value < 25) {

                return {
                    label: "LOW",
                    className: "signal-low"
                };

            }


            if (value < 50) {

                return {
                    label: "ELEVATED",
                    className: "signal-elevated"
                };

            }


            return {
                label: "HIGH",
                className: "signal-high"
            };

        }


        // ====================================================
        // WARNING SIGNAL ENGINE
        // ====================================================

        function updateWarningEngine(
            risk,
            rain24,
            rain3,
            rain7
        ) {

            const numericRisk =
                Number(risk);


            const safeRisk =
                Number.isFinite(numericRisk)
                    ? Math.max(
                        0,
                        Math.min(
                            100,
                            numericRisk
                        )
                    )
                    : 0;


            const band24 =
                getRainfallBand(
                    rain24
                );

            const band3 =
                getRainfallBand(
                    rain3
                );

            const band7 =
                getRainfallBand(
                    rain7
                );


            // -----------------------------------------------
            // AI RISK
            // -----------------------------------------------

            setText(
                engineRisk,
                safeRisk.toFixed(1) + "%"
            );


            if (safeRisk >= 70) {

                setText(
                    engineRiskStatus,
                    "HIGH"
                );

                if (engineRiskStatus) {
                    engineRiskStatus.className =
                        "signal-high";
                }

            }

            else if (safeRisk >= 40) {

                setText(
                    engineRiskStatus,
                    "MODERATE"
                );

                if (engineRiskStatus) {
                    engineRiskStatus.className =
                        "signal-elevated";
                }

            }

            else {

                setText(
                    engineRiskStatus,
                    "LOW"
                );

                if (engineRiskStatus) {
                    engineRiskStatus.className =
                        "signal-low";
                }

            }


            // -----------------------------------------------
            // 24 HOUR RAINFALL
            // -----------------------------------------------

            setText(
                engineRain24,
                Number.isFinite(Number(rain24))
                    ? Number(rain24).toFixed(2) + " mm"
                    : "--"
            );

            setText(
                engineRain24Status,
                band24.label
            );

            if (engineRain24Status) {
                engineRain24Status.className =
                    band24.className;
            }


            // -----------------------------------------------
            // 3 DAY RAINFALL
            // -----------------------------------------------

            setText(
                engineRain3,
                Number.isFinite(Number(rain3))
                    ? Number(rain3).toFixed(2) + " mm"
                    : "--"
            );

            setText(
                engineRain3Status,
                band3.label
            );

            if (engineRain3Status) {
                engineRain3Status.className =
                    band3.className;
            }


            // -----------------------------------------------
            // 7 DAY RAINFALL
            // -----------------------------------------------

            setText(
                engineRain7,
                Number.isFinite(Number(rain7))
                    ? Number(rain7).toFixed(2) + " mm"
                    : "--"
            );

            setText(
                engineRain7Status,
                band7.label
            );

            if (engineRain7Status) {
                engineRain7Status.className =
                    band7.className;
            }


            // -----------------------------------------------
            // OVERALL STATUS
            // -----------------------------------------------

            let overallClass =
                "engine-low";

            let overallTitle =
                "ROUTINE MONITORING";

            let overallText =
                "The current susceptibility and recent rainfall signals do not indicate an elevated prototype monitoring status.";


            if (safeRisk >= 70) {

                overallClass =
                    "engine-high";

                overallTitle =
                    "HIGH SUSCEPTIBILITY";

                overallText =
                    "The AI model indicates high susceptibility at this location. Recent rainfall is shown alongside the susceptibility result for continued monitoring.";

            }

            else if (safeRisk >= 40) {

                overallClass =
                    "engine-watch";

                overallTitle =
                    "ELEVATED SUSCEPTIBILITY";

                overallText =
                    "The AI model indicates moderate susceptibility. Continue monitoring recent rainfall and local environmental conditions.";

            }


            if (engineStatus) {

                engineStatus.className =
                    "engine-status " +
                    overallClass;

            }


            setText(
                engineStatusTitle,
                overallTitle
            );

            setText(
                engineStatusText,
                overallText
            );

        }


        // ====================================================
        // SHOW RESULT
        // ====================================================

        function showResult(result) {

            if (!result) {

                throw new Error(
                    "No prediction result received."
                );

            }


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


            const environment =
                result.environment || {};


            // -----------------------------------------------
            // LOCATION
            // -----------------------------------------------

            setText(
                locationName,
                result.display_name ||
                result.state ||
                "Selected NER location"
            );


            setText(
                stateName,
                result.state ||
                "--"
            );


            const resultLat =
                Number(result.latitude);

            const resultLon =
                Number(result.longitude);


            if (
                Number.isFinite(resultLat) &&
                Number.isFinite(resultLon)
            ) {

                setText(
                    coordinates,
                    resultLat.toFixed(5) +
                    ", " +
                    resultLon.toFixed(5)
                );

            }


            // -----------------------------------------------
            // RISK
            // -----------------------------------------------

            setText(
                riskValue,
                safeRisk.toFixed(1) + "%"
            );


            setText(
                riskLevel,
                result.level ||
                "Risk assessment completed."
            );


            if (riskBar) {

                riskBar.style.width =
                    safeRisk + "%";

            }


            setText(
                riskScore,
                safeRisk.toFixed(1) + "%"
            );


            // -----------------------------------------------
            // WARNING LEVEL
            // -----------------------------------------------

            const level =
                String(
                    result.level ||
                    ""
                ).toUpperCase();


            if (level.includes("HIGH")) {

                setText(
                    warningLevel,
                    "HIGH SUSCEPTIBILITY"
                );

                if (warningLevel) {
                    warningLevel.className =
                        "status-high";
                }


                setText(
                    warningDescription,
                    "The selected location has a high prototype susceptibility score. Continued monitoring of rainfall and local conditions is recommended."
                );


                setText(
                    guidance,
                    "High susceptibility is present. Monitor rainfall and local ground conditions closely. This prototype does not issue an operational emergency alert."
                );

            }

            else if (
                level.includes("MODERATE")
            ) {

                setText(
                    warningLevel,
                    "MODERATE SUSCEPTIBILITY"
                );

                if (warningLevel) {
                    warningLevel.className =
                        "status-moderate";
                }


                setText(
                    warningDescription,
                    "The selected location has a moderate prototype susceptibility score. Continue monitoring changing environmental conditions."
                );


                setText(
                    guidance,
                    "Moderate susceptibility is present. Watch recent rainfall and changes in local slope conditions."
                );

            }

            else {

                setText(
                    warningLevel,
                    "LOW SUSCEPTIBILITY"
                );

                if (warningLevel) {
                    warningLevel.className =
                        "status-low";
                }


                setText(
                    warningDescription,
                    "The selected location currently has a lower prototype susceptibility score."
                );


                setText(
                    guidance,
                    "Continue routine monitoring. A low susceptibility score does not mean that landslides are impossible."
                );

            }


            // -----------------------------------------------
            // RAINFALL
            // -----------------------------------------------

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


            updateWarningEngine(
                safeRisk,
                rain24,
                rain3,
                rain7
            );


            // -----------------------------------------------
            // RISK CHART
            // -----------------------------------------------

            setText(
                $("chart-risk-value"),
                safeRisk.toFixed(1) + "%"
            );


            if ($("chart-risk-bar")) {

                $("chart-risk-bar").style.width =
                    safeRisk + "%";

            }


            // -----------------------------------------------
            // 24 HOUR CHART
            // -----------------------------------------------

            setText(
                $("chart-rain24-value"),
                Number.isFinite(rain24)
                    ? rain24.toFixed(2) + " mm"
                    : "--"
            );


            if ($("chart-rain24-bar")) {

                $("chart-rain24-bar").style.width =
                    Number.isFinite(rain24)
                        ? Math.min(
                            (rain24 / 100) * 100,
                            100
                        ) + "%"
                        : "0%";

            }


            // -----------------------------------------------
            // 3 DAY CHART
            // -----------------------------------------------

            setText(
                $("chart-rain3-value"),
                Number.isFinite(rain3)
                    ? rain3.toFixed(2) + " mm"
                    : "--"
            );


            if ($("chart-rain3-bar")) {

                $("chart-rain3-bar").style.width =
                    Number.isFinite(rain3)
                        ? Math.min(
                            (rain3 / 200) * 100,
                            100
                        ) + "%"
                        : "0%";

            }


            // -----------------------------------------------
            // 7 DAY CHART
            // -----------------------------------------------

            setText(
                $("chart-rain7-value"),
                Number.isFinite(rain7)
                    ? rain7.toFixed(2) + " mm"
                    : "--"
            );


            if ($("chart-rain7-bar")) {

                $("chart-rain7-bar").style.width =
                    Number.isFinite(rain7)
                        ? Math.min(
                            (rain7 / 300) * 100,
                            100
                        ) + "%"
                        : "0%";

            }


            // -----------------------------------------------
            // RAINFALL CARDS
            // -----------------------------------------------

            setText(
                rainfall24,
                Number.isFinite(rain24)
                    ? rain24.toFixed(2)
                    : "--"
            );


            setText(
                rainfall3,
                Number.isFinite(rain3)
                    ? rain3.toFixed(2)
                    : "--"
            );


            setText(
                rainfall7,
                Number.isFinite(rain7)
                    ? rain7.toFixed(2)
                    : "--"
            );


            setText(
                rainfallSignal,
                Number.isFinite(rain24)
                    ? rain24.toFixed(1) + " mm"
                    : "--"
            );


            if (rainfallBar) {

                rainfallBar.style.width =
                    rainfallSignalPercent(
                        rain24
                    ) + "%";

            }


            // -----------------------------------------------
            // ENVIRONMENT
            // -----------------------------------------------

            setText(
                elevation,
                environment.elevation !== undefined
                    ? environment.elevation + " m"
                    : "--"
            );


            setText(
                slope,
                environment.slope !== undefined
                    ? environment.slope + "°"
                    : "--"
            );


            setText(
                aspect,
                environment.aspect !== undefined
                    ? environment.aspect + "°"
                    : "--"
            );


            setText(
                annualRainfall,
                environment.annual_rainfall !== undefined
                    ? environment.annual_rainfall + " mm"
                    : "--"
            );


            setText(
                soilPh,
                environment.soil_ph !== undefined
                    ? environment.soil_ph
                    : "--"
            );


            setStatus(
                "Live monitoring data updated successfully."
            );

        }


        // ====================================================
        // PREDICTION
        // ====================================================

        async function predict(
            lat,
            lon
        ) {

            setStatus(
                "Collecting environmental data and running AI assessment..."
            );


            if (searchButton) {

                searchButton.disabled =
                    true;

                searchButton.textContent =
                    "Analysing...";

            }


            showEarlyWarningLoader();


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
                                        lon

                                }),

                            signal:
                                controller.signal

                        }
                    );


                clearTimeout(
                    timeout
                );


                let result;

                try {

                    result =
                        await response.json();

                }

                catch (jsonError) {

                    throw new Error(
                        "Server returned an invalid response."
                    );

                }


                if (!response.ok) {

                    throw new Error(

                        result.details ||
                        result.error ||
                        "Prediction failed."

                    );

                }


                showResult(
                    result
                );


            }

            catch (error) {

                console.error(
                    "Early warning prediction error:",
                    error
                );


                setStatus(

                    error.name === "AbortError"

                        ? "Weather/AI request timed out. Please try again."

                        : error.message ||
                          "Prediction failed."

                );


                setText(
                    warningLevel,
                    "MONITORING UNAVAILABLE"
                );


                if (warningLevel) {

                    warningLevel.className =
                        "status-neutral";

                }


                setText(
                    warningDescription,
                    "The live assessment could not be completed. Please try the location again."
                );

            }

            finally {

                if (searchButton) {

                    searchButton.disabled =
                        false;

                    searchButton.textContent =
                        "Monitor Location";

                }


                hideEarlyWarningLoader();

            }

        }


        // ====================================================
        // LOCATION SEARCH
        // ====================================================

        async function searchLocation() {

            const query =
                input
                    ? input.value.trim()
                    : "";


            // -----------------------------------------------
            // EMPTY SEARCH
            // -----------------------------------------------

            if (!query) {

                setStatus(
                    "Please enter a location."
                );

                if (input) {
                    input.focus();
                }

                return;

            }


            // -----------------------------------------------
            // BUTTON STATE
            // -----------------------------------------------

            if (searchButton) {

                searchButton.disabled =
                    true;

                searchButton.textContent =
                    "Searching...";

            }


            setStatus(
                `Searching for "${query}"...`
            );


            try {

                // -------------------------------------------
                // LOCATION SEARCH REQUEST
                // -------------------------------------------

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


                let result;

                try {

                    result =
                        await response.json();

                }

                catch (jsonError) {

                    throw new Error(
                        "Location search returned an invalid server response."
                    );

                }


                if (!response.ok) {

                    throw new Error(

                        result.error ||
                        result.details ||
                        "Location search failed."

                    );

                }


                // -------------------------------------------
                // COORDINATES
                // -------------------------------------------

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
                        "Invalid coordinates returned by location search."
                    );

                }


                // -------------------------------------------
                // NER CHECK
                // -------------------------------------------

                if (
                    result.supported === false
                ) {

                    resetPage();


                    setStatus(
                        "This location is outside the supported Northeast India region."
                    );


                    setText(
                        warningLevel,
                        "NER ONLY"
                    );


                    if (warningLevel) {

                        warningLevel.className =
                            "status-moderate";

                    }


                    setText(
                        warningDescription,
                        "Early-warning monitoring is currently limited to Arunachal Pradesh, Assam, Manipur, Meghalaya, Mizoram, Nagaland, Sikkim and Tripura."
                    );


                    return;

                }


                // -------------------------------------------
                // SHOW SEARCHED LOCATION
                // -------------------------------------------

                setText(
                    locationName,
                    result.display_name ||
                    query
                );


                setStatus(
                    "Location found. Running AI assessment..."
                );


                // -------------------------------------------
                // RUN PREDICTION
                // -------------------------------------------

                await predict(
                    lat,
                    lon
                );

            }


            catch (error) {

                console.error(
                    "Search error:",
                    error
                );


                setStatus(
                    error.message ||
                    "Location search failed."
                );


                setText(
                    warningLevel,
                    "MONITORING UNAVAILABLE"
                );


                if (warningLevel) {

                    warningLevel.className =
                        "status-neutral";

                }

            }


            finally {

                if (searchButton) {

                    searchButton.disabled =
                        false;

                    searchButton.textContent =
                        "Monitor Location";

                }

            }

        }


        // ====================================================
        // MONITOR LOCATION BUTTON
        // ====================================================

        if (searchButton) {

            searchButton.addEventListener(
                "click",
                function (event) {

                    event.preventDefault();

                    searchLocation();

                }
            );

        }

        else {

            console.error(
                "LandslideGuard: #search-button was not found."
            );

        }


        // ====================================================
        // ENTER KEY SEARCH
        // ====================================================

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


        // ====================================================
        // HOW IT WORKS
        // ====================================================

        const aboutButton =
            $("about");


        if (aboutButton) {

            aboutButton.addEventListener(
                "click",
                function () {

                    alert(

                        "LANDSLIDEGUARD EARLY-WARNING MONITOR\n\n" +

                        "1. Search a location inside Northeast India.\n\n" +

                        "2. The system checks whether the location is within the supported NER region.\n\n" +

                        "3. Environmental information is retrieved for the location.\n\n" +

                        "4. Live rainfall from Open-Meteo is included in the assessment.\n\n" +

                        "5. The Random Forest model generates a susceptibility score.\n\n" +

                        "6. The page combines the susceptibility result with recent rainfall for monitoring.\n\n" +

                        "The current prototype is a monitoring and susceptibility system. Operational early warning requires validated trigger thresholds, forecasting, uncertainty calibration and alert delivery."

                    );

                }
            );

        }


        // ====================================================
        // MOBILE NAVIGATION
        // ====================================================

        const menuButton =
            $("menuBtn");

        const mobileNavLinks =
            $("navLinks");


        if (
            menuButton &&
            mobileNavLinks
        ) {

            menuButton.addEventListener(
                "click",
                function (event) {

                    event.preventDefault();


                    const isOpen =
                        mobileNavLinks.classList.toggle(
                            "active"
                        );


                    menuButton.textContent =
                        isOpen
                            ? "✕"
                            : "☰";


                    menuButton.setAttribute(
                        "aria-expanded",
                        isOpen
                            ? "true"
                            : "false"
                    );


                    menuButton.setAttribute(
                        "aria-label",
                        isOpen
                            ? "Close navigation menu"
                            : "Open navigation menu"
                    );

                }
            );


            mobileNavLinks
                .querySelectorAll("a")
                .forEach(
                    function (link) {

                        link.addEventListener(
                            "click",
                            function () {

                                mobileNavLinks.classList.remove(
                                    "active"
                                );


                                menuButton.textContent =
                                    "☰";


                                menuButton.setAttribute(
                                    "aria-expanded",
                                    "false"
                                );


                                menuButton.setAttribute(
                                    "aria-label",
                                    "Open navigation menu"
                                );

                            }
                        );

                    }
                );

        }


        // ====================================================
        // INITIAL PAGE STATE
        // ====================================================

        resetPage();


        // ====================================================
        // DEBUG CONFIRMATION
        // ====================================================

        console.log(
            "LandslideGuard Early Warning JavaScript loaded successfully."
        );


        if (searchButton) {

            console.log(
                "Monitor Location button connected successfully."
            );

        }


    });

}