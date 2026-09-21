from flask import Flask, render_template, request, jsonify, Response
import joblib
import pandas as pd
import numpy as np
import requests
import json
import unicodedata
import time
from pathlib import Path
from shapely.geometry import shape, mapping


app = Flask(__name__)


# ============================================================
# PATHS
# ============================================================

BASE = Path(__file__).resolve().parent

MODEL_PATH = BASE / "models" / "landslide_model_dynamic.pkl"
DATASET_PATH = BASE / "data" / "ner_dataset.csv"
GEOJSON_PATH = BASE / "data" / "india_states.geojson"

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


# ============================================================
# EXACT FEATURES USED BY YOUR DYNAMIC MODEL
# ============================================================

FEATURES = [
    "elevation",
    "slope",
    "aspect",
    "annual_rainfall",
    "soil_clay",
    "soil_sand",
    "soil_ph",
    "rainfall_24h",
    "rainfall_3day",
    "rainfall_7day"
]


STATIC_FEATURES = [
    "elevation",
    "slope",
    "aspect",
    "annual_rainfall",
    "soil_clay",
    "soil_sand",
    "soil_ph"
]


# ============================================================
# NER STATES
# ============================================================

SUPPORTED_STATES = {
    "Arunachal Pradesh",
    "Assam",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Sikkim",
    "Tripura"
}


def norm(value):

    text = unicodedata.normalize(
        "NFKD",
        str(value or "")
    )

    text = "".join(
        c for c in text
        if not unicodedata.combining(c)
    )

    return " ".join(
        text.strip().lower().split()
    )


SUPPORTED_NORMALIZED = {
    norm(x)
    for x in SUPPORTED_STATES
}


# ============================================================
# GLOBAL VARIABLES
# ============================================================

model = None
environment_data = None
india_geojson = None

NER_GEOJSON_TEXT = "{}"


# Warning threshold only.
# This is NOT a calibrated probability threshold.
MODEL_THRESHOLD = 0.50


# ============================================================
# WEATHER CACHE
# ============================================================

WEATHER_CACHE = {}

WEATHER_CACHE_TTL = 300


HTTP = requests.Session()

HTTP.headers.update({
    "User-Agent":
        "Global-LandslideGuard/1.0 educational prototype"
})


# ============================================================
# STATE NAME
# ============================================================

def get_state_name(properties):

    keys = [

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
        "NAME"

    ]

    for key in keys:

        value = properties.get(key)

        if value:

            return str(
                value
            ).strip()


    for value in properties.values():

        if norm(value) in SUPPORTED_NORMALIZED:

            return str(
                value
            ).strip()


    return "Unknown"


# ============================================================
# POINT IN POLYGON
# ============================================================

def point_on_segment(
    point,
    a,
    b,
    tolerance=1e-9
):

    x, y = point

    x1, y1 = a

    x2, y2 = b

    cross = (
        (x - x1) * (y2 - y1)
        -
        (y - y1) * (x2 - x1)
    )

    if abs(cross) > tolerance:

        return False


    return (
        min(x1, x2) - tolerance
        <= x
        <=
        max(x1, x2) + tolerance

        and

        min(y1, y2) - tolerance
        <= y
        <=
        max(y1, y2) + tolerance
    )


def point_in_ring(
    point,
    ring
):

    if not ring or len(ring) < 3:

        return False


    x, y = point

    inside = False

    j = len(ring) - 1


    for i in range(
        len(ring)
    ):

        xi, yi = ring[i]

        xj, yj = ring[j]


        if point_on_segment(
            point,
            (xi, yi),
            (xj, yj)
        ):

            return True


        if (yi > y) != (yj > y):

            denominator = yj - yi

            if abs(
                denominator
            ) > 1e-12:

                x_intersection = (
                    (xj - xi)
                    *
                    (y - yi)
                    /
                    denominator
                    +
                    xi
                )

                if x < x_intersection:

                    inside = not inside


        j = i


    return inside


def point_in_polygon(
    point,
    polygon
):

    if not polygon:

        return False


    if not point_in_ring(
        point,
        polygon[0]
    ):

        return False


    for hole in polygon[1:]:

        if point_in_ring(
            point,
            hole
        ):

            return False


    return True


def point_in_multipolygon(
    point,
    multipolygon
):

    return any(
        point_in_polygon(
            point,
            polygon
        )

        for polygon
        in
        (multipolygon or [])
    )


def get_state_from_coordinates(
    lat,
    lon
):

    point = (
        float(lon),
        float(lat)
    )


    for feature in india_geojson.get(
        "features",
        []
    ):

        geometry = (
            feature.get(
                "geometry"
            )
            or {}
        )

        coordinates = geometry.get(
            "coordinates"
        )


        if not coordinates:

            continue


        state = get_state_name(
            feature.get(
                "properties"
            )
            or {}
        )


        try:

            if geometry.get(
                "type"
            ) == "Polygon":

                if point_in_polygon(
                    point,
                    coordinates
                ):

                    return state


            elif geometry.get(
                "type"
            ) == "MultiPolygon":

                if point_in_multipolygon(
                    point,
                    coordinates
                ):

                    return state


        except (
            TypeError,
            ValueError,
            IndexError
        ):

            pass


    return None


def is_supported_location(
    lat,
    lon
):

    state = get_state_from_coordinates(
        lat,
        lon
    )


    return (
        bool(state)
        and
        norm(state)
        in
        SUPPORTED_NORMALIZED,

        state
    )


# ============================================================
# LOAD PROJECT
# ============================================================

def load_project():

    global model
    global environment_data
    global india_geojson
    global NER_GEOJSON_TEXT


    # --------------------------------------------------------
    # MODEL
    # --------------------------------------------------------

    if not MODEL_PATH.exists():

        raise FileNotFoundError(

            f"""
Dynamic model not found:

{MODEL_PATH}

Make sure this file exists:

models/landslide_model_dynamic.pkl
"""
        )


    model = joblib.load(
        MODEL_PATH
    )


    print(
        "Model loaded:",
        MODEL_PATH.name
    )

    print(
        "Model type:",
        type(model).__name__
    )


    # --------------------------------------------------------
    # VERIFY MODEL FEATURES
    # --------------------------------------------------------

    model_features = getattr(
        model,
        "feature_names_in_",
        None
    )


    if model_features is not None:

        model_features = list(
            model_features
        )


        print(
            "Model features:",
            model_features
        )


        if model_features != FEATURES:

            raise ValueError(

                "MODEL FEATURE MISMATCH.\n\n"

                f"Model expects:\n"
                f"{model_features}\n\n"

                f"Backend provides:\n"
                f"{FEATURES}\n\n"

                "Use the dynamic model generated "
                "from ner_dataset_dynamic.csv."
            )


    # --------------------------------------------------------
    # DATASET
    # --------------------------------------------------------

    if not DATASET_PATH.exists():

        raise FileNotFoundError(
            f"Dataset not found:\n{DATASET_PATH}"
        )


    environment_data = pd.read_csv(
        DATASET_PATH
    )


    required_columns = [
        "latitude",
        "longitude"
    ] + STATIC_FEATURES


    missing_columns = [
        column
        for column
        in required_columns

        if column
        not in
        environment_data.columns
    ]


    if missing_columns:

        raise ValueError(

            "ner_dataset.csv is missing:\n"
            +
            ", ".join(
                missing_columns
            )
        )


    for column in required_columns:

        environment_data[column] = pd.to_numeric(
            environment_data[column],
            errors="coerce"
        )


    environment_data = (
        environment_data
        .dropna(
            subset=required_columns
        )
        .reset_index(
            drop=True
        )
    )


    print(
        "Environmental rows:",
        len(environment_data)
    )


    # --------------------------------------------------------
    # GEOJSON
    # --------------------------------------------------------

    if not GEOJSON_PATH.exists():

        raise FileNotFoundError(
            f"GeoJSON not found:\n{GEOJSON_PATH}"
        )


    with open(
        GEOJSON_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        india_geojson = json.load(
            file
        )


    # --------------------------------------------------------
    # BUILD NER GEOJSON
    # --------------------------------------------------------

    ner_features = []


    for feature in india_geojson.get(
        "features",
        []
    ):

        state = get_state_name(
            feature.get(
                "properties"
            )
            or {}
        )


        if (
            norm(state)
            not in
            SUPPORTED_NORMALIZED
        ):

            continue


        copy_feature = dict(
            feature
        )


        geometry = feature.get(
            "geometry"
        )


        if geometry:

            try:

                copy_feature[
                    "geometry"
                ] = mapping(

                    shape(
                        geometry
                    ).simplify(
                        0.005,
                        preserve_topology=True
                    )

                )

            except Exception:

                pass


        ner_features.append(
            copy_feature
        )


    NER_GEOJSON_TEXT = json.dumps(

        {
            "type":
                "FeatureCollection",

            "features":
                ner_features
        },

        ensure_ascii=False,

        separators=(
            ",",
            ":"
        )
    )


    print(
        "NER boundary features:",
        len(ner_features)
    )


    print(
        "============================================"
    )

    print(
        "LANDSLIDEGUARD READY"
    )

    print(
        "Dynamic model: ENABLED"
    )

    print(
        "Live rainfall: ENABLED"
    )

    print(
        "============================================"
    )


# ============================================================
# LIVE RAINFALL
# ============================================================

def weather_key(
    lat,
    lon
):

    return (
        round(
            float(lat),
            4
        ),

        round(
            float(lon),
            4
        )
    )


def get_live_rainfall(
    lat,
    lon
):

    key = weather_key(
        lat,
        lon
    )


    now = time.time()


    cached = WEATHER_CACHE.get(
        key
    )


    if cached:

        age = (
            now
            -
            cached["time"]
        )


        if age < WEATHER_CACHE_TTL:

            print(
                "Using cached live weather"
            )

            return cached["data"]


    print(
        f"Fetching live rainfall "
        f"for {lat:.5f}, {lon:.5f}"
    )


    params = {

        "latitude":
            lat,

        "longitude":
            lon,

        "current":
            "rain,precipitation",

        "hourly":
            "rain",

        "past_hours":
            168,

        "forecast_hours":
            1,

        "timezone":
            "auto",

        "cell_selection":
            "land"
    }


    try:

        start = time.time()


        response = HTTP.get(

            OPEN_METEO_URL,

            params=params,

            timeout=(
                3,
                6
            )
        )


        elapsed = round(
            time.time()
            -
            start,
            2
        )


        print(
            "Open-Meteo status:",
            response.status_code,
            "| time:",
            elapsed,
            "seconds"
        )


        response.raise_for_status()


        data = response.json()


        hourly = (
            data.get(
                "hourly"
            )
            or {}
        )


        rainfall_values = (
            hourly.get(
                "rain"
            )
        )


        if rainfall_values is None:

            raise RuntimeError(
                "Open-Meteo returned no hourly rainfall."
            )


        rainfall = np.asarray(
            rainfall_values,
            dtype=float
        )


        rainfall = np.nan_to_num(
            rainfall,
            nan=0.0,
            posinf=0.0,
            neginf=0.0
        )


        if len(rainfall) < 168:

            raise RuntimeError(

                f"Only {len(rainfall)} "
                "hourly rainfall values were returned."
            )


        rainfall_24h = float(
            np.sum(
                rainfall[-24:]
            )
        )


        rainfall_3day = float(
            np.sum(
                rainfall[-72:]
            )
        )


        rainfall_7day = float(
            np.sum(
                rainfall[-168:]
            )
        )


        current = (
            data.get(
                "current"
            )
            or {}
        )


        result = {

            "rainfall_24h":
                round(
                    rainfall_24h,
                    2
                ),

            "rainfall_3day":
                round(
                    rainfall_3day,
                    2
                ),

            "rainfall_7day":
                round(
                    rainfall_7day,
                    2
                ),

            "current_rain":
                round(
                    float(
                        current.get(
                            "rain",
                            0
                        )
                        or
                        0
                    ),
                    2
                ),

            "current_precipitation":
                round(
                    float(
                        current.get(
                            "precipitation",
                            0
                        )
                        or
                        0
                    ),
                    2
                ),

            "source":
                "Open-Meteo"
        }


        WEATHER_CACHE[key] = {

            "time":
                now,

            "data":
                result
        }


        print(
            "LIVE RAINFALL:",
            result
        )


        return result


    except requests.Timeout:

        raise RuntimeError(

            "Live rainfall request timed out. "
            "Please try again."
        )


    except requests.RequestException:

        raise RuntimeError(

            "Live rainfall service is temporarily unavailable."
        )


    except Exception as exc:

        raise RuntimeError(

            f"Live rainfall processing failed: {exc}"
        )


# ============================================================
# ENVIRONMENT LOOKUP
# ============================================================

def nearest_environment(
    lat,
    lon
):

    distance = (

        (
            environment_data[
                "latitude"
            ]
            -
            lat
        ) ** 2

        +

        (
            environment_data[
                "longitude"
            ]
            -
            lon
        ) ** 2

    )


    return environment_data.loc[
        distance.idxmin()
    ]





# ============================================================
# EARLY WARNING TRIGGER
# ============================================================

def early_warning_info(
    rainfall_24h,
    rainfall_3day,
    rainfall_7day
):

    rainfall_24h = float(rainfall_24h)
    rainfall_3day = float(rainfall_3day)
    rainfall_7day = float(rainfall_7day)


    # --------------------------------------------------------
    # PROTOTYPE RAINFALL TRIGGER
    # --------------------------------------------------------
    #
    # These are prototype operational thresholds.
    # They are NOT calibrated NER warning thresholds.
    #
    # They will later be replaced by validated
    # rainfall-trigger thresholds for NER.
    # --------------------------------------------------------

    if (
        rainfall_24h >= 100
        or rainfall_3day >= 200
        or rainfall_7day >= 300
    ):

        return {
            "level": "ALERT",
            "css_level": "high",
            "triggered": True,
            "message":
                "High recent rainfall may increase "
                "landslide triggering potential.",
            "reason":
                "Rainfall trigger threshold exceeded."
        }


    if (
        rainfall_24h >= 50
        or rainfall_3day >= 100
        or rainfall_7day >= 200
    ):

        return {
            "level": "WATCH",
            "css_level": "moderate",
            "triggered": True,
            "message":
                "Recent rainfall requires continued "
                "monitoring of landslide-prone terrain.",
            "reason":
                "Rainfall monitoring threshold exceeded."
        }


    return {
        "level": "NORMAL",
        "css_level": "low",
        "triggered": False,
        "message":
            "Recent rainfall is below the prototype "
            "monitoring thresholds.",
        "reason":
            "No prototype rainfall trigger detected."
    }




# ============================================================
# RISK
# ============================================================

def risk_info(
    risk
):

    if risk >= 70:

        return (
            "HIGH RISK",
            "high",
            "High model susceptibility score."
        )


    if risk >= 40:

        return (
            "MODERATE RISK",
            "moderate",
            "Moderate model susceptibility score."
        )


    return (
        "LOW RISK",
        "low",
        "Lower model susceptibility score."
    )


# ============================================================
# REASONS
# ============================================================

def build_reasons(
    row,
    state,
    weather
):

    reasons = [
        f"State: {state}"
    ]


    slope = float(
        row["slope"]
    )


    if slope >= 30:

        reasons.append(
            f"Steep terrain detected "
            f"(slope: {slope:.2f}°)."
        )

    elif slope >= 15:

        reasons.append(
            f"Moderately steep terrain detected "
            f"(slope: {slope:.2f}°)."
        )

    else:

        reasons.append(
            f"Relatively gentle terrain detected "
            f"(slope: {slope:.2f}°)."
        )


    reasons.append(
        f"Elevation: "
        f"{float(row['elevation']):.2f} m."
    )


    reasons.append(
        f"Annual rainfall baseline: "
        f"{float(row['annual_rainfall']):.2f} mm."
    )


    reasons.append(
        f"Live rainfall, last 24h: "
        f"{weather['rainfall_24h']:.2f} mm."
    )


    reasons.append(
        f"Live rainfall, last 3 days: "
        f"{weather['rainfall_3day']:.2f} mm."
    )


    reasons.append(
        f"Live rainfall, last 7 days: "
        f"{weather['rainfall_7day']:.2f} mm."
    )


    reasons.append(
        f"Soil: clay "
        f"{float(row['soil_clay']):.2f}%, "
        f"sand "
        f"{float(row['soil_sand']):.2f}%, "
        f"pH "
        f"{float(row['soil_ph']):.2f}."
    )


    reasons.append(
        "This is a prototype susceptibility "
        "indicator, not a guarantee of an "
        "imminent landslide."
    )


    return reasons


# ============================================================
# HOME
# ============================================================

# ============================================================
# MAIN PAGES
# ============================================================

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/early-warning")
def early_warning():
    return render_template("early-warning.html")


@app.route("/sources")
def sources():
    return render_template("sources.html")


@app.route("/about")
def about():
    return render_template("about.html")


# ============================================================
# HEALTH
# ============================================================

@app.route("/health")
def health():

    model_features = getattr(
        model,
        "feature_names_in_",
        None
    )


    return jsonify({

        "status":
            "ok",

        "model_loaded":
            model is not None,

        "model":
            type(model).__name__,

        "dynamic_model":
            True,

        "live_rainfall":
            True,

        "feature_count":
            len(FEATURES),

        "features":
            FEATURES,

        "model_features":
            (
                list(model_features)
                if model_features is not None
                else FEATURES
            ),

        "threshold":
            MODEL_THRESHOLD,

        "supported_states":
            sorted(
                SUPPORTED_STATES
            )
    })


# ============================================================
# NER GEOJSON
# ============================================================

@app.route("/ner-states")
def ner_states():

    return Response(

        NER_GEOJSON_TEXT,

        status=200,

        mimetype=
            "application/geo+json",

        headers={
            "Cache-Control":
                "public, max-age=3600"
        }
    )


@app.route("/india-states")
def india_states():

    return Response(

        json.dumps(
            india_geojson,
            ensure_ascii=False,
            separators=(
                ",",
                ":"
            )
        ),

        status=200,

        mimetype=
            "application/geo+json"
    )


# ============================================================
# LOCATION SEARCH
# ============================================================

@app.route(
    "/search-location",
    methods=["POST"]
)
def search_location():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )


    query = str(
        data.get(
            "location",
            ""
        )
    ).strip()


    if not query:

        return jsonify({
            "error":
                "Enter a location to search."
        }), 400


    try:

        response = HTTP.get(

            "https://nominatim.openstreetmap.org/search",

            params={

                "q":
                    query,

                "format":
                    "jsonv2",

                "limit":
                    1
            },

            timeout=(
                3,
                6
            )
        )


        response.raise_for_status()


        results = response.json()


        if not results:

            return jsonify({

                "error":
                    f'No location found for "{query}".'

            }), 404


        result = results[0]


        lat = float(
            result["lat"]
        )


        lon = float(
            result["lon"]
        )


        supported, state = (
            is_supported_location(
                lat,
                lon
            )
        )


        return jsonify({

            "latitude":
                lat,

            "longitude":
                lon,

            "display_name":
                result.get(
                    "display_name",
                    query
                ),

            "state":
                state,

            "supported":
                supported
        })


    except requests.RequestException:

        return jsonify({

            "error":
                "Location search is temporarily unavailable."

        }), 503


# ============================================================
# PREDICTION
# ============================================================

# ============================================================
# PREDICTION
# ============================================================

@app.route(
    "/predict",
    methods=["POST"]
)
def predict():

    start = time.time()

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    # --------------------------------------------------------
    # GET COORDINATES
    # --------------------------------------------------------

    try:

        lat = float(
            data["latitude"]
        )

        lon = float(
            data["longitude"]
        )

    except (
        KeyError,
        TypeError,
        ValueError
    ):

        return jsonify({

            "error":
                "Valid latitude and longitude are required."

        }), 400


    # --------------------------------------------------------
    # VALIDATE COORDINATES
    # --------------------------------------------------------

    if not (
        -90 <= lat <= 90
        and
        -180 <= lon <= 180
    ):

        return jsonify({

            "error":
                "Invalid Earth coordinates."

        }), 400


    try:

        # ====================================================
        # CHECK NER
        # ====================================================

        supported, state = (
            is_supported_location(
                lat,
                lon
            )
        )


        print(
            f"Prediction request: "
            f"lat={lat:.6f}, "
            f"lon={lon:.6f}, "
            f"state={state}, "
            f"supported={supported}"
        )


        if not supported:

            state_text = (
                state
                or
                "outside the supported "
                "Northeast India region"
            )


            return jsonify({

                "supported":
                    False,

                "state":
                    state_text,

                "error":
                    "Prediction is available "
                    "only for Northeast India.",

                "title":
                    "Northeast India only",

                "message":
                    f"Selected location is "
                    f"in {state_text}.",

                "supported_states":
                    sorted(
                        SUPPORTED_STATES
                    )

            }), 403


        # ====================================================
        # STATIC ENVIRONMENT
        # ====================================================

        row = nearest_environment(
            lat,
            lon
        )


        print(
            "Nearest environmental "
            "point found."
        )


        # ====================================================
        # WEATHER INPUT
        # ====================================================
        #
        # Dashboard and Early Warning now obtain live rainfall
        # directly from Open-Meteo in the browser.
        #
        # Browser:
        #
        #     Open-Meteo
        #          ↓
        #     JavaScript
        #          ↓
        #     /predict
        #
        # Therefore Render does NOT need to call Open-Meteo
        # when valid browser weather is supplied.
        #
        # Server-side Open-Meteo remains as a fallback for
        # older clients or requests without weather data.
        # ====================================================

        client_weather = data.get(
            "weather"
        )


        if isinstance(
            client_weather,
            dict
        ):

            try:

                weather = {

                    "rainfall_24h":
                        round(
                            float(
                                client_weather[
                                    "rainfall_24h"
                                ]
                            ),
                            2
                        ),

                    "rainfall_3day":
                        round(
                            float(
                                client_weather[
                                    "rainfall_3day"
                                ]
                            ),
                            2
                        ),

                    "rainfall_7day":
                        round(
                            float(
                                client_weather[
                                    "rainfall_7day"
                                ]
                            ),
                            2
                        ),

                    "current_rain":
                        round(
                            float(
                                client_weather.get(
                                    "current_rain",
                                    0
                                )
                                or
                                0
                            ),
                            2
                        ),

                    "current_precipitation":
                        round(
                            float(
                                client_weather.get(
                                    "current_precipitation",
                                    0
                                )
                                or
                                0
                            ),
                            2
                        ),

                    "source":
                        str(
                            client_weather.get(
                                "source",
                                "Open-Meteo"
                            )
                        ),

                    "mode":
                        str(
                            client_weather.get(
                                "mode",
                                "browser-live"
                            )
                        )

                }


                # --------------------------------------------
                # VALIDATE WEATHER NUMBERS
                # --------------------------------------------

                for key in (
                    "rainfall_24h",
                    "rainfall_3day",
                    "rainfall_7day",
                    "current_rain",
                    "current_precipitation"
                ):

                    if not np.isfinite(
                        weather[key]
                    ):

                        raise ValueError(
                            f"Invalid weather value: {key}"
                        )


                print(
                    "Using browser-supplied "
                    "Open-Meteo rainfall:",
                    weather
                )


            except (
                KeyError,
                TypeError,
                ValueError
            ) as exc:

                print(
                    "Invalid browser weather "
                    "payload; falling back "
                    "to server weather:",
                    repr(exc)
                )


                weather = get_live_rainfall(
                    lat,
                    lon
                )


        else:

            print(
                "No browser weather supplied. "
                "Using server-side weather fallback."
            )


            weather = get_live_rainfall(
                lat,
                lon
            )


        # ====================================================
        # EXACT 10 MODEL FEATURES
        # ====================================================

        values = [

            float(
                row["elevation"]
            ),

            float(
                row["slope"]
            ),

            float(
                row["aspect"]
            ),

            float(
                row["annual_rainfall"]
            ),

            float(
                row["soil_clay"]
            ),

            float(
                row["soil_sand"]
            ),

            float(
                row["soil_ph"]
            ),

            float(
                weather[
                    "rainfall_24h"
                ]
            ),

            float(
                weather[
                    "rainfall_3day"
                ]
            ),

            float(
                weather[
                    "rainfall_7day"
                ]
            )

        ]


        features = pd.DataFrame(

            [values],

            columns=FEATURES

        )


        print(
            "Model input:",
            features.to_dict(
                orient="records"
            )[0]
        )


        # ====================================================
        # RANDOM FOREST
        # ====================================================

        probability = float(

            model.predict_proba(
                features
            )[0][1]

        )


        risk = float(

            np.clip(
                probability * 100,
                0,
                100
            )

        )


        # ====================================================
        # EARLY WARNING
        # ====================================================

        early_warning = early_warning_info(

            weather[
                "rainfall_24h"
            ],

            weather[
                "rainfall_3day"
            ],

            weather[
                "rainfall_7day"
            ]

        )


        # ====================================================
        # RISK LEVEL
        # ====================================================

        level, css_level, summary = (
            risk_info(
                risk
            )
        )


        # ====================================================
        # MODEL WARNING
        # ====================================================

        if (
            probability
            >=
            MODEL_THRESHOLD
        ):

            warning = (
                "LANDSLIDE SUSCEPTIBILITY DETECTED"
            )

            warning_css = "high"

        else:

            warning = (
                "LOWER LANDSLIDE SUSCEPTIBILITY"
            )

            warning_css = "low"


        # ====================================================
        # PROCESSING TIME
        # ====================================================

        elapsed = round(
            time.time()
            -
            start,
            2
        )


        print(
            f"Prediction complete "
            f"in {elapsed}s | "
            f"Risk={risk:.2f}%"
        )


        # ====================================================
        # RESPONSE
        # ====================================================

        return jsonify({

            "supported":
                True,

            "state":
                state,

            "risk":
                round(
                    risk,
                    2
                ),

            "early_warning":
                early_warning,

            "probability":
                round(
                    probability,
                    4
                ),

            "threshold":
                MODEL_THRESHOLD,

            "level":
                level,

            "warning":
                warning,

            "warning_css":
                warning_css,

            "css_level":
                css_level,

            "latitude":
                round(
                    lat,
                    6
                ),

            "longitude":
                round(
                    lon,
                    6
                ),

            "summary":
                summary,

            "reasons":
                build_reasons(
                    row,
                    state,
                    weather
                ),

            "model":
                "Random Forest",

            "feature_count":
                len(FEATURES),

            "environment": {

                "elevation":
                    round(
                        float(
                            row["elevation"]
                        ),
                        2
                    ),

                "slope":
                    round(
                        float(
                            row["slope"]
                        ),
                        2
                    ),

                "aspect":
                    round(
                        float(
                            row["aspect"]
                        ),
                        2
                    ),

                "annual_rainfall":
                    round(
                        float(
                            row[
                                "annual_rainfall"
                            ]
                        ),
                        2
                    ),

                "soil_clay":
                    round(
                        float(
                            row["soil_clay"]
                        ),
                        2
                    ),

                "soil_sand":
                    round(
                        float(
                            row["soil_sand"]
                        ),
                        2
                    ),

                "soil_ph":
                    round(
                        float(
                            row["soil_ph"]
                        ),
                        2
                    ),

                # --------------------------------------------
                # LIVE RAINFALL
                # --------------------------------------------

                "rainfall_24h":
                    weather[
                        "rainfall_24h"
                    ],

                "rainfall_3day":
                    weather[
                        "rainfall_3day"
                    ],

                "rainfall_7day":
                    weather[
                        "rainfall_7day"
                    ],

                "current_rain":
                    weather[
                        "current_rain"
                    ],

                "current_precipitation":
                    weather[
                        "current_precipitation"
                    ],

                "weather_source":
                    weather.get(
                        "source",
                        "Open-Meteo"
                    ),

                "weather_mode":
                    weather.get(
                        "mode",
                        "server-live"
                    )

            }

        })


    except Exception as exc:

        elapsed = round(
            time.time()
            -
            start,
            2
        )


        print(
            f"PREDICTION ERROR "
            f"after {elapsed}s:",
            repr(exc)
        )


        return jsonify({

            "error":
                "Prediction failed.",

            "details":
                str(exc),

            "elapsed_seconds":
                elapsed

        }), 500

# ============================================================
# START APPLICATION
# ============================================================

load_project()


if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=2005,

        debug=False,

        threaded=True
    )