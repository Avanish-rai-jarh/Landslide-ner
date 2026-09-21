import os

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


# ============================================================
# FLASK APPLICATION
# ============================================================

app = Flask(__name__)


# ============================================================
# PROJECT PATHS
# ============================================================

BASE = Path(__file__).resolve().parent

MODEL_PATH = (
    BASE /
    "models" /
    "landslide_model_dynamic.pkl"
)

DATASET_PATH = (
    BASE /
    "data" /
    "ner_dataset.csv"
)

GEOJSON_PATH = (
    BASE /
    "data" /
    "india_states.geojson"
)


# ============================================================
# EXTERNAL SERVICES
# ============================================================

OPEN_METEO_URL = (
    "https://api.open-meteo.com/v1/forecast"
)

NOMINATIM_URL = (
    "https://nominatim.openstreetmap.org/search"
)


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
# SUPPORTED NORTHEAST INDIA STATES
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


# ============================================================
# NORMALIZE TEXT
# ============================================================

def norm(value):

    text = unicodedata.normalize(
        "NFKD",
        str(value or "")
    )

    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )

    return " ".join(
        text.strip().lower().split()
    )


SUPPORTED_NORMALIZED = {
    norm(state)
    for state in SUPPORTED_STATES
}


# ============================================================
# GLOBAL DATA
# ============================================================

model = None

environment_data = None

india_geojson = None

NER_GEOJSON_TEXT = "{}"


# ============================================================
# MODEL THRESHOLD
# ============================================================

MODEL_THRESHOLD = 0.50


# ============================================================
# WEATHER CACHE
# ============================================================

WEATHER_CACHE = {}

WEATHER_CACHE_TTL = 300

# Keep the last successful weather response even after the short TTL.
# This lets the app continue working when Open-Meteo temporarily returns 429.
WEATHER_STALE_CACHE = {}

WEATHER_RETRY_AFTER_DEFAULT = 2


# ============================================================
# HTTP SESSION
# ============================================================

HTTP = requests.Session()

HTTP.headers.update({

    "User-Agent":
        "Global-LandslideGuard/1.0 educational prototype"

})


# ============================================================
# GET STATE NAME FROM GEOJSON PROPERTIES
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

            return str(value).strip()


    for value in properties.values():

        if norm(value) in SUPPORTED_NORMALIZED:

            return str(value).strip()


    return "Unknown"


# ============================================================
# POINT ON LINE SEGMENT
# ============================================================

def point_on_segment(
    point,
    start,
    end,
    tol=1e-9
):

    x, y = point

    x1, y1 = start

    x2, y2 = end


    cross = (
        (x - x1) * (y2 - y1)
        -
        (y - y1) * (x2 - x1)
    )


    if abs(cross) > tol:

        return False


    return (

        min(x1, x2) - tol
        <= x
        <=
        max(x1, x2) + tol

        and

        min(y1, y2) - tol
        <= y
        <=
        max(y1, y2) + tol

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


    for i in range(len(ring)):

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

            if abs(denominator) > 1e-12:

                xcross = (
                    (xj - xi)
                    *
                    (y - yi)
                    /
                    denominator
                    +
                    xi
                )

                if x < xcross:

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

        for polygon in (
            multipolygon or []
        )

    )


# ============================================================
# GET STATE FROM COORDINATES
# ============================================================

def get_state_from_coordinates(
    latitude,
    longitude
):

    point = (
        float(longitude),
        float(latitude)
    )


    if not india_geojson:

        return None


    for feature in india_geojson.get(
        "features",
        []
    ):

        geometry = (
            feature.get("geometry")
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
            ) or {}
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
# CHECK SUPPORTED LOCATION
# ============================================================

def is_supported_location(
    latitude,
    longitude
):

    state = get_state_from_coordinates(
        latitude,
        longitude
    )


    supported = (

        bool(state)

        and

        norm(state)
        in
        SUPPORTED_NORMALIZED

    )


    return supported, state


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

            f"Dynamic model not found: "
            f"{MODEL_PATH}"

        )


    model = joblib.load(
        MODEL_PATH
    )


    model_features = getattr(
        model,
        "feature_names_in_",
        None
    )


    if model_features is not None:

        model_features = list(
            model_features
        )


        if model_features != FEATURES:

            raise ValueError(

                "MODEL FEATURE MISMATCH.\n"

                f"Model expects: "
                f"{model_features}\n"

                f"Backend provides: "
                f"{FEATURES}\n"

                "Use "
                "models/landslide_model_dynamic.pkl "
                "created from the dynamic notebook."

            )


    # --------------------------------------------------------
    # DATASET
    # --------------------------------------------------------

    if not DATASET_PATH.exists():

        raise FileNotFoundError(

            f"Dataset not found: "
            f"{DATASET_PATH}"

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

        for column in required_columns

        if column not in environment_data.columns

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
            "ner_dataset.csv contains no valid rows."
        )


    # --------------------------------------------------------
    # GEOJSON
    # --------------------------------------------------------

    if not GEOJSON_PATH.exists():

        raise FileNotFoundError(

            f"GeoJSON not found: "
            f"{GEOJSON_PATH}"

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
    # CREATE NER GEOJSON
    # --------------------------------------------------------

    ner_features = []


    for feature in india_geojson.get(
        "features",
        []
    ):

        state = get_state_name(

            feature.get(
                "properties"
            ) or {}

        )


        if norm(state) not in SUPPORTED_NORMALIZED:

            continue


        copy_feature = dict(
            feature
        )


        geometry = feature.get(
            "geometry"
        )


        if geometry:

            try:

                copy_feature["geometry"] = mapping(

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


    # --------------------------------------------------------
    # STARTUP INFORMATION
    # --------------------------------------------------------

    print(
        "============================================"
    )

    print(
        "LANDSLIDEGUARD STARTED"
    )

    print(
        "Model:",
        MODEL_PATH.name
    )

    print(
        "Model type:",
        type(model).__name__
    )

    print(
        "Dataset rows:",
        len(environment_data)
    )

    print(
        "NER states:",
        len(ner_features)
    )

    print(
        "Features:",
        FEATURES
    )

    print(
        "Live rainfall: ENABLED"
    )

    print(
        "============================================"
    )


# ============================================================
# WEATHER CACHE KEY
# ============================================================

def weather_key(
    latitude,
    longitude
):

    return (

        round(
            float(latitude),
            4
        ),

        round(
            float(longitude),
            4
        )

    )


# ============================================================
# GET LIVE RAINFALL
# ============================================================

def get_live_rainfall(lat, lon, fallback_row=None):

    key = weather_key(
        lat,
        lon
    )

    now = time.time()

    # --------------------------------------------------------
    # USE FRESH CACHE FIRST
    # --------------------------------------------------------

    cached = WEATHER_CACHE.get(
        key
    )

    if cached:

        age = (
            now -
            cached["time"]
        )

        if age < WEATHER_CACHE_TTL:

            print(
                "Using cached weather:",
                key
            )

            return cached["data"]

    print(
        f"Fetching live rainfall: "
        f"{lat:.5f}, {lon:.5f}"
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
            0,

        "timezone":
            "auto",

        "cell_selection":
            "land"
    }

    last_error = None
    rate_limited = False

    # --------------------------------------------------------
    # TRY OPEN-METEO
    # --------------------------------------------------------

    for attempt in range(1, 3):

        try:

            start_time = time.time()

            print(
                f"Open-Meteo attempt "
                f"{attempt}/2"
            )

            response = HTTP.get(

                OPEN_METEO_URL,

                params=params,

                timeout=(
                    5,
                    12
                )
            )

            elapsed = round(
                time.time() -
                start_time,
                2
            )

            print(
                "Open-Meteo:",
                response.status_code,
                "in",
                elapsed,
                "sec"
            )

            # HTTP 429 means the upstream service is rate limiting
            # the deployment. Retrying immediately is usually not useful.
            if response.status_code == 429:

                rate_limited = True
                last_error = requests.HTTPError(
                    "Open-Meteo returned HTTP 429 (Too Many Requests)."
                )

                retry_after = response.headers.get(
                    "Retry-After"
                )

                print(
                    "Open-Meteo rate limited the request.",
                    "Retry-After:",
                    retry_after or "not provided"
                )

                break

            response.raise_for_status()

            data = response.json()

            # ------------------------------------------------
            # RAINFALL DATA
            # ------------------------------------------------

            rain_values = (
                data.get("hourly") or {}
            ).get(
                "rain"
            )

            if rain_values is None:

                raise RuntimeError(
                    "Open-Meteo returned "
                    "no hourly rainfall data."
                )

            rain = np.asarray(
                rain_values,
                dtype=float
            )

            rain = np.nan_to_num(
                rain,
                nan=0.0,
                posinf=0.0,
                neginf=0.0
            )

            if len(rain) < 168:

                raise RuntimeError(
                    "Open-Meteo returned only "
                    f"{len(rain)} hourly values."
                )

            current = (
                data.get("current")
                or {}
            )

            result = {

                "rainfall_24h":
                    round(
                        float(
                            np.sum(
                                rain[-24:]
                            )
                        ),
                        2
                    ),

                "rainfall_3day":
                    round(
                        float(
                            np.sum(
                                rain[-72:]
                            )
                        ),
                        2
                    ),

                "rainfall_7day":
                    round(
                        float(
                            np.sum(
                                rain[-168:]
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
                            ) or 0
                        ),
                        2
                    ),

                "current_precipitation":
                    round(
                        float(
                            current.get(
                                "precipitation",
                                0
                            ) or 0
                        ),
                        2
                    ),

                "source":
                    "Open-Meteo",

                "live":
                    True
            }

            # Fresh cache
            WEATHER_CACHE[key] = {

                "time":
                    time.time(),

                "data":
                    result
            }

            # Stale cache survives the short TTL while the process is alive.
            WEATHER_STALE_CACHE[key] = {

                "time":
                    time.time(),

                "data":
                    result
            }

            print(
                "LIVE RAINFALL:",
                result
            )

            return result

        except requests.Timeout as exc:

            last_error = exc

            print(
                f"Open-Meteo timeout "
                f"on attempt {attempt}/2"
            )

            if attempt < 2:
                time.sleep(0.5)

        except requests.RequestException as exc:

            last_error = exc

            print(
                "Open-Meteo request error:",
                repr(exc)
            )

            if attempt < 2:
                time.sleep(0.5)

        except Exception as exc:

            last_error = exc

            print(
                "Rainfall processing error:",
                repr(exc)
            )

            break

    # --------------------------------------------------------
    # FALLBACK 1: STALE SUCCESSFUL WEATHER CACHE
    # --------------------------------------------------------

    stale = WEATHER_STALE_CACHE.get(
        key
    )

    if stale:

        stale_data = dict(
            stale["data"]
        )

        stale_data["source"] = (
            "Open-Meteo (last successful cached data)"
        )

        stale_data["live"] = False

        print(
            "Live rainfall unavailable."
        )
        print(
            "Using last successful cached rainfall for this location."
        )

        return stale_data

    # --------------------------------------------------------
    # FALLBACK 2: DATASET DYNAMIC RAINFALL, IF AVAILABLE
    # --------------------------------------------------------

    if fallback_row is not None:

        dynamic_columns = {
            "rainfall_24h",
            "rainfall_3day",
            "rainfall_7day"
        }

        if dynamic_columns.issubset(
            set(fallback_row.index)
        ):

            try:

                result = {

                    "rainfall_24h":
                        round(
                            float(
                                fallback_row[
                                    "rainfall_24h"
                                ]
                            ),
                            2
                        ),

                    "rainfall_3day":
                        round(
                            float(
                                fallback_row[
                                    "rainfall_3day"
                                ]
                            ),
                            2
                        ),

                    "rainfall_7day":
                        round(
                            float(
                                fallback_row[
                                    "rainfall_7day"
                                ]
                            ),
                            2
                        ),

                    "current_rain":
                        0.0,

                    "current_precipitation":
                        0.0,

                    "source":
                        "Dataset fallback (Open-Meteo unavailable)",

                    "live":
                        False
                }

                print(
                    "Using dataset rainfall fallback:",
                    result
                )

                return result

            except (
                TypeError,
                ValueError
            ):
                pass

    # --------------------------------------------------------
    # FALLBACK 3: CLIMATOLOGICAL BASELINE
    # --------------------------------------------------------
    # This is only used when there is no successful weather cache
    # and the dataset has no dynamic rainfall columns. It is NOT
    # presented as live rainfall. The annual rainfall is converted
    # into a simple daily climatological baseline so the model can
    # still respond instead of returning HTTP 500.

    if fallback_row is not None:

        try:

            annual = float(
                fallback_row[
                    "annual_rainfall"
                ]
            )

            if np.isfinite(annual) and annual >= 0:

                daily = annual / 365.25

                result = {

                    "rainfall_24h":
                        round(
                            daily,
                            2
                        ),

                    "rainfall_3day":
                        round(
                            daily * 3,
                            2
                        ),

                    "rainfall_7day":
                        round(
                            daily * 7,
                            2
                        ),

                    "current_rain":
                        0.0,

                    "current_precipitation":
                        0.0,

                    "source":
                        "Climatological baseline (Open-Meteo unavailable)",

                    "live":
                        False
                }

                print(
                    "WARNING: Open-Meteo unavailable."
                )
                print(
                    "Using climatological rainfall baseline "
                    "derived from annual rainfall."
                )

                return result

        except (
            TypeError,
            ValueError,
            KeyError
        ):
            pass

    # --------------------------------------------------------
    # NO SAFE FALLBACK
    # --------------------------------------------------------

    if rate_limited:
        raise RuntimeError(
            "Open-Meteo is temporarily rate limiting requests "
            "and no rainfall fallback is available yet."
        )

    raise RuntimeError(
        "Live rainfall service is temporarily unavailable "
        "and no rainfall fallback is available."
    )


# ============================================================
# FIND NEAREST ENVIRONMENTAL DATASET POINT
# ============================================================

def nearest_environment(
    latitude,
    longitude
):

    distance = (

        (
            environment_data["latitude"]
            -
            latitude
        ) ** 2

        +

        (
            environment_data["longitude"]
            -
            longitude
        ) ** 2

    )


    index = distance.idxmin()


    row = environment_data.loc[
        index
    ]


    print(
        "Nearest environmental point found."
    )


    return row


# ============================================================
# RISK INFORMATION
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
# BUILD EXPLANATION REASONS
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

        "This is a prototype susceptibility indicator, "
        "not a guarantee of an imminent landslide."

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
            type(model).__name__
            if model is not None
            else None,

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
# NER STATES
# ============================================================

@app.route("/ner-states")
def ner_states():

    return Response(

        NER_GEOJSON_TEXT,

        status=200,

        mimetype="application/geo+json",

        headers={

            "Cache-Control":
                "public, max-age=3600"

        }

    )


# ============================================================
# ALL INDIA STATES
# ============================================================

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

        mimetype="application/geo+json"

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

            NOMINATIM_URL,

            params={

                "q":
                    query,

                "format":
                    "jsonv2",

                "limit":
                    1

            },

            timeout=(5, 10)

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

        return jsonify({

            "error":
                "Location search timed out. Please try again."

        }), 503


    except requests.RequestException:

        return jsonify({

            "error":
                "Location search is temporarily unavailable."

        }), 503


# ============================================================
# PREDICTION
# ============================================================

@app.route(
    "/predict",
    methods=["POST"]
)
def predict():

    start_time = time.time()


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

        latitude = float(
            data["latitude"]
        )

        longitude = float(
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

        -90
        <= latitude
        <= 90

        and

        -180
        <= longitude
        <= 180

    ):

        return jsonify({

            "error":
                "Invalid Earth coordinates."

        }), 400


    try:

        # ----------------------------------------------------
        # CHECK NER
        # ----------------------------------------------------

        supported, state = (
            is_supported_location(
                latitude,
                longitude
            )
        )


        print(

            f"Prediction request: "
            f"lat={latitude:.6f}, "
            f"lon={longitude:.6f}, "
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
                    "Prediction is available only "
                    "for Northeast India.",

                "title":
                    "Northeast India only",

                "message":
                    f"Selected location is in "
                    f"{state_text}.",

                "supported_states":
                    sorted(
                        SUPPORTED_STATES
                    )

            }), 403


        # ----------------------------------------------------
        # ENVIRONMENT
        # ----------------------------------------------------

        row = nearest_environment(

            latitude,

            longitude

        )


        # ----------------------------------------------------
        # LIVE RAINFALL
        # ----------------------------------------------------

        weather = get_live_rainfall(

            latitude,

            longitude,

            fallback_row=row

        )


        # ----------------------------------------------------
        # MODEL INPUT
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

            weather[
                "rainfall_24h"
            ],

            weather[
                "rainfall_3day"
            ],

            weather[
                "rainfall_7day"
            ]

        ]


        features = pd.DataFrame(

            [values],

            columns=FEATURES

        )


        print(
            "Model input:",
            features.iloc[0].to_dict()
        )


        # ----------------------------------------------------
        # RANDOM FOREST
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # RISK CATEGORY
        # ----------------------------------------------------

        level, css_level, summary = (
            risk_info(
                risk
            )
        )


        # ----------------------------------------------------
        # WARNING
        # ----------------------------------------------------

        if probability >= MODEL_THRESHOLD:

            warning = (
                "LANDSLIDE SUSCEPTIBILITY DETECTED"
            )

            warning_css = "high"


        else:

            warning = (
                "LOWER LANDSLIDE SUSCEPTIBILITY"
            )

            warning_css = "low"


        elapsed = round(

            time.time()
            -
            start_time,

            2

        )


        print(

            f"Prediction complete in "
            f"{elapsed}s | "
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
                    latitude,
                    6
                ),

            "longitude":
                round(
                    longitude,
                    6
                ),

            "summary":
                summary,

            "message":
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

                "weather_live":
                    bool(
                        weather.get(
                            "live",
                            False
                        )
                    )

            }

        })


    except Exception as error:

        elapsed = round(

            time.time()
            -
            start_time,

            2

        )


        print(

            f"PREDICTION ERROR after "
            f"{elapsed}s:",
            repr(error)

        )


        return jsonify({

            "error":
                "Prediction failed.",

            "details":
                str(error),

            "elapsed_seconds":
                elapsed

        }), 500


# ============================================================
# LOAD EVERYTHING
# ============================================================

load_project()


# ============================================================
# RUN FLASK
# ============================================================

if __name__ == "__main__":

    port= int(os.environ.get("PORT",2005))

    app.run(

        host="0.0.0.0",

        port=port,

        debug=False,

        threaded=True

    )