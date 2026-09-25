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
# MODEL FEATURES
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
    "rainfall_7day",
]


STATIC_FEATURES = [
    "elevation",
    "slope",
    "aspect",
    "annual_rainfall",
    "soil_clay",
    "soil_sand",
    "soil_ph",
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
    "Tripura",
}


def norm(value):

    text = unicodedata.normalize(
        "NFKD",
        str(value or "")
    )

    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )

    return " ".join(
        text.strip().lower().split()
    )


SUPPORTED_NORMALIZED = {
    norm(state)
    for state in SUPPORTED_STATES
}


# ============================================================
# GLOBAL STATE
# ============================================================

model = None

environment_data = None

india_geojson = None

NER_GEOJSON_TEXT = "{}"


# This is a model-output classification threshold.
# It is NOT a calibrated operational landslide-warning threshold.
MODEL_THRESHOLD = 0.50


# ============================================================
# HTTP / WEATHER CACHE
# ============================================================

HTTP = requests.Session()

HTTP.headers.update({
    "User-Agent":
        "LandslideGuard-NER/1.0 educational prototype"
})


WEATHER_CACHE = {}

WEATHER_CACHE_TTL = 300

WEATHER_RETRY_COUNT = 2

WEATHER_RETRY_DELAY = 1.5


# ============================================================
# GEOJSON HELPERS
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
# POINT ON SEGMENT
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


# ============================================================
# POINT IN RING
# ============================================================

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


# ============================================================
# POINT IN POLYGON
# ============================================================

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


# ============================================================
# POINT IN MULTIPOLYGON
# ============================================================

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


# ============================================================
# STATE FROM COORDINATES
# ============================================================

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

            geometry_type = geometry.get(
                "type"
            )


            if geometry_type == "Polygon":

                if point_in_polygon(
                    point,
                    coordinates
                ):

                    return state


            elif geometry_type == "MultiPolygon":

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

            continue


    return None


# ============================================================
# CHECK SUPPORTED NER LOCATION
# ============================================================

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

            "Dynamic model not found:\n"
            f"{MODEL_PATH}\n\n"
            "Make sure models/landslide_model_dynamic.pkl exists."
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
                "from the matching dataset."
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

            "ner_dataset.csv is missing: "
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


    if environment_data.empty:

        raise ValueError(
            "ner_dataset.csv contains no usable environmental rows."
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
        "Browser rainfall support: ENABLED"
    )


    print(
        "Server rainfall fallback: ENABLED"
    )


    print(
        "============================================"
    )


# ============================================================
# WEATHER CACHE KEY
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


# ============================================================
# PARSE OPEN-METEO RESPONSE
# ============================================================

def _parse_open_meteo_response(
    data
):

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


    current = (
        data.get(
            "current"
        )
        or {}
    )


    result = {

        "rainfall_24h":
            round(
                float(
                    np.sum(
                        rainfall[-24:]
                    )
                ),
                2
            ),

        "rainfall_3day":
            round(
                float(
                    np.sum(
                        rainfall[-72:]
                    )
                ),
                2
            ),

        "rainfall_7day":
            round(
                float(
                    np.sum(
                        rainfall[-168:]
                    )
                ),
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
            "Open-Meteo",

        "mode":
            "server-live"
    }


    for key in (

        "rainfall_24h",

        "rainfall_3day",

        "rainfall_7day",

        "current_rain",

        "current_precipitation"

    ):

        if (
            not np.isfinite(
                result[key]
            )
            or
            result[key] < 0
        ):

            raise RuntimeError(
                f"Invalid rainfall value returned for {key}."
            )


    return result


# ============================================================
# SERVER-SIDE LIVE RAINFALL
# ============================================================

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


    if (
        cached
        and
        now - cached["time"]
        <
        WEATHER_CACHE_TTL
    ):

        print(
            "Using cached server weather"
        )

        return dict(
            cached["data"]
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


    last_error = None


    for attempt in range(
        1,
        WEATHER_RETRY_COUNT + 1
    ):

        try:

            print(

                f"Fetching live rainfall "
                f"{lat:.5f}, {lon:.5f} "
                f"(attempt "
                f"{attempt}/"
                f"{WEATHER_RETRY_COUNT})"

            )


            start = time.time()


            response = HTTP.get(

                OPEN_METEO_URL,

                params=params,

                timeout=(
                    4,
                    10
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


            result = _parse_open_meteo_response(
                response.json()
            )


            WEATHER_CACHE[key] = {

                "time":
                    time.time(),

                "data":
                    result

            }


            print(
                "SERVER LIVE RAINFALL:",
                result
            )


            return dict(
                result
            )


        except requests.Timeout as exc:

            last_error = RuntimeError(
                "Live rainfall request timed out."
            )


            print(
                "Open-Meteo timeout:",
                repr(exc)
            )


        except requests.HTTPError as exc:

            last_error = RuntimeError(

                f"Open-Meteo returned "
                f"HTTP {response.status_code}."

            )


            print(
                "Open-Meteo HTTP error:",
                repr(exc)
            )


            if response.status_code not in (
                429,
                500,
                502,
                503,
                504
            ):

                break


        except requests.RequestException as exc:

            last_error = RuntimeError(

                "Live rainfall service "
                "is temporarily unavailable."

            )


            print(
                "Open-Meteo request error:",
                repr(exc)
            )


        except Exception as exc:

            last_error = RuntimeError(

                f"Live rainfall processing failed: {exc}"

            )


            print(
                "Open-Meteo processing error:",
                repr(exc)
            )


            break


        if (
            attempt
            <
            WEATHER_RETRY_COUNT
        ):

            time.sleep(
                WEATHER_RETRY_DELAY
                *
                attempt
            )


    raise (
        last_error
        or
        RuntimeError(
            "Live rainfall service "
            "is temporarily unavailable."
        )
    )


# ============================================================
# VALIDATE BROWSER WEATHER
# ============================================================

def normalize_client_weather(
    client_weather
):

    """
    Validate rainfall supplied by the browser.

    Preferred architecture:

        Browser
          ↓
        Open-Meteo
          ↓
        /predict
          ↓
        Random Forest

    This prevents Render from having to contact Open-Meteo
    for every prediction.
    """

    if not isinstance(
        client_weather,
        dict
    ):

        return None


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


    except (
        KeyError,
        TypeError,
        ValueError
    ):

        return None


    numeric_keys = (

        "rainfall_24h",

        "rainfall_3day",

        "rainfall_7day",

        "current_rain",

        "current_precipitation"

    )


    for key in numeric_keys:

        value = weather[key]


        if (
            not np.isfinite(value)
            or
            value < 0
        ):

            return None


    # Rainfall accumulation should not decrease
    # as the time window becomes larger.

    if (
        weather["rainfall_3day"]
        +
        1e-9
        <
        weather["rainfall_24h"]
    ):

        return None


    if (
        weather["rainfall_7day"]
        +
        1e-9
        <
        weather["rainfall_3day"]
    ):

        return None


    return weather


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
        )
        **
        2

        +

        (
            environment_data[
                "longitude"
            ]
            -
            lon
        )
        **
        2

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

    rainfall_24h = float(
        rainfall_24h
    )

    rainfall_3day = float(
        rainfall_3day
    )

    rainfall_7day = float(
        rainfall_7day
    )


    # --------------------------------------------------------
    # PROTOTYPE RAINFALL THRESHOLDS
    # --------------------------------------------------------
    #
    # These are prototype monitoring thresholds.
    #
    # They are NOT calibrated operational NER
    # landslide-warning thresholds.
    #
    # --------------------------------------------------------

    if (

        rainfall_24h >= 100

        or

        rainfall_3day >= 200

        or

        rainfall_7day >= 300

    ):

        return {

            "level":
                "ALERT",

            "css_level":
                "high",

            "triggered":
                True,

            "message":
                "High recent rainfall may increase "
                "landslide triggering potential.",

            "reason":
                "Rainfall trigger threshold exceeded."
        }


    if (

        rainfall_24h >= 50

        or

        rainfall_3day >= 100

        or

        rainfall_7day >= 200

    ):

        return {

            "level":
                "WATCH",

            "css_level":
                "moderate",

            "triggered":
                True,

            "message":
                "Recent rainfall requires continued "
                "monitoring of landslide-prone terrain.",

            "reason":
                "Rainfall monitoring threshold exceeded."
        }


    return {

        "level":
            "NORMAL",

        "css_level":
            "low",

        "triggered":
            False,

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

@app.route("/")
def home():

    return render_template(
        "index.html"
    )

# ============================================================
# SEPARATE WEBSITE PAGES
# ============================================================

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
            (
                type(model).__name__
                if model is not None
                else None
            ),

        "dynamic_model":
            True,

        "browser_weather":
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


# ============================================================
# INDIA GEOJSON
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

        response = requests.get(
            "https://nominatim.openstreetmap.org/search",

            params={
                "q": query,
                "format": "jsonv2",
                "limit": 1,
                "addressdetails": 1
            },

            headers={
                "User-Agent":
                    "LandslideGuard/1.0 "
                    "(educational disaster-management project)",
                "Accept":
                    "application/json",
                "Accept-Language":
                    "en"
            },

            timeout=20
        )

        response.raise_for_status()

        results = response.json()

        if not results:
            return jsonify({
                "error":
                    f'No location found for "{query}".'
            }), 404

        result = results[0]

        latitude = float(
            result["lat"]
        )

        longitude = float(
            result["lon"]
        )

        supported, state = (
            is_supported_location(
                latitude,
                longitude
            )
        )

        return jsonify({

            "latitude":
                latitude,

            "longitude":
                longitude,

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

    except requests.Timeout:

        print(
            "Nominatim location search timed out."
        )

        return jsonify({
            "error":
                "Location search timed out. Please try again."
        }), 503

    except requests.RequestException as error:

        print(
            "Nominatim location search error:",
            repr(error)
        )

        return jsonify({
            "error":
                "Location search is temporarily unavailable."
        }), 503

    except (KeyError, TypeError, ValueError) as error:

        print(
            "Location response parsing error:",
            repr(error)
        )

        return jsonify({
            "error":
                "Invalid location data received."
        }), 502

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
    # COORDINATES
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


    if not (

        np.isfinite(lat)

        and

        np.isfinite(lon)

        and

        -90 <= lat <= 90

        and

        -180 <= lon <= 180

    ):

        return jsonify({

            "error":
                "Invalid Earth coordinates."

        }), 400


    try:

        # ----------------------------------------------------
        # NER VALIDATION
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # STATIC ENVIRONMENT
        # ----------------------------------------------------

        row = nearest_environment(
            lat,
            lon
        )


        print(
            "Nearest environmental point found."
        )


        # ----------------------------------------------------
        # WEATHER INPUT
        # ----------------------------------------------------
        #
        # PREFERRED:
        #
        # Browser
        #    ↓
        # Open-Meteo
        #    ↓
        # /predict + weather
        #    ↓
        # Random Forest
        #
        # FALLBACK:
        #
        # Older frontend
        #    ↓
        # /predict
        #    ↓
        # Server Open-Meteo
        #
        # This is the important Render fix.
        # ----------------------------------------------------

        client_weather = (
            normalize_client_weather(
                data.get(
                    "weather"
                )
            )
        )


        if client_weather is not None:

            weather = client_weather


            print(

                "Using browser-supplied "
                "Open-Meteo rainfall:",

                weather

            )


        else:

            if "weather" in data:

                print(

                    "Browser weather payload "
                    "was missing/invalid; "
                    "using server weather fallback."

                )

            else:

                print(

                    "No browser weather supplied; "
                    "using server weather fallback."

                )


            weather = get_live_rainfall(
                lat,
                lon
            )


        # ----------------------------------------------------
        # EXACT 10 MODEL FEATURES
        # ----------------------------------------------------

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


        if not np.all(
            np.isfinite(values)
        ):

            raise ValueError(
                "Model input contains non-finite values."
            )


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


        # ----------------------------------------------------
        # RANDOM FOREST
        # ----------------------------------------------------

        probability_values = (
            model.predict_proba(
                features
            )
        )


        if (
            probability_values.shape[1]
            <
            2
        ):

            raise RuntimeError(

                "The loaded model does not "
                "provide two-class probabilities."

            )


        probability = float(

            probability_values[0][1]

        )


        probability = float(

            np.clip(
                probability,
                0.0,
                1.0
            )

        )


        risk = float(

            np.clip(
                probability * 100.0,
                0.0,
                100.0
            )

        )


        # ----------------------------------------------------
        # EARLY WARNING
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # RISK LEVEL
        # ----------------------------------------------------

        level, css_level, summary = (
            risk_info(
                risk
            )
        )


        # ----------------------------------------------------
        # MODEL THRESHOLD WARNING
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # TIMING
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

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
                            row[
                                "elevation"
                            ]
                        ),
                        2
                    ),


                "slope":
                    round(
                        float(
                            row[
                                "slope"
                            ]
                        ),
                        2
                    ),


                "aspect":
                    round(
                        float(
                            row[
                                "aspect"
                            ]
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
                            row[
                                "soil_clay"
                            ]
                        ),
                        2
                    ),


                "soil_sand":
                    round(
                        float(
                            row[
                                "soil_sand"
                            ]
                        ),
                        2
                    ),


                "soil_ph":
                    round(
                        float(
                            row[
                                "soil_ph"
                            ]
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