import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "data" / "india_states.geojson"
OUTPUT_FILE = BASE_DIR / "data" / "ner_states.geojson"

NER_STATES = {
    "arunachal pradesh",
    "assam",
    "manipur",
    "meghalaya",
    "mizoram",
    "nagaland",
    "sikkim",
    "tripura"
}


def normalize(name):
    return (
        str(name or "")
        .strip()
        .lower()
        .replace("ā", "a")
        .replace("ī", "i")
        .replace("ū", "u")
    )


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

    # Fallback: search all properties
    for value in properties.values():

        if normalize(value) in NER_STATES:
            return str(value).strip()

    return ""


print("Loading India GeoJSON...")

with open(
    INPUT_FILE,
    "r",
    encoding="utf-8"
) as f:

    india = json.load(f)


ner_features = []

for feature in india.get("features", []):

    properties = (
        feature.get("properties")
        or {}
    )

    state = get_state_name(
        properties
    )

    if normalize(state) in NER_STATES:

        ner_features.append(feature)

        print(
            "Found:",
            state
        )


ner_geojson = {
    "type": "FeatureCollection",
    "features": ner_features
}


with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        ner_geojson,
        f,
        ensure_ascii=False,
        separators=(",", ":")
    )


print()
print(
    "========================================"
)
print(
    "NER GEOJSON CREATED"
)
print(
    "States found:",
    len(ner_features)
)
print(
    "Output:",
    OUTPUT_FILE
)
print(
    "Size:",
    round(
        OUTPUT_FILE.stat().st_size / 1024 / 1024,
        2
    ),
    "MB"
)
print(
    "========================================"
)