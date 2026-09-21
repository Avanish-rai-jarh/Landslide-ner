# Global LandslideGuard — Final SIH Prototype

## Setup
1. Put your trained `landslide_model.pkl` in `models/`.
2. Open a terminal in this folder.
3. Run: `python -m pip install -r requirements.txt`
4. Run: `python app.py`
5. Open: `http://127.0.0.1:5000`

## Included
- Worldwide Leaflet map
- Search by location name + Enter/Search button
- Map click prediction
- Flask REST API
- Random Forest model loading
- Risk percentage and Low/Moderate/High display
- Responsive SIH-style dashboard
- Workflow explanation
- Model health check at `/health`

## Required model features
The saved model must have been trained with:
latitude, longitude, latitude_abs, latitude_squared,
longitude_squared, terrain_index, climate_index

## Important
This is the current prototype model. Do not describe its score as a guaranteed real-time landslide probability.
