from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
from typing import Any

import streamlit as st

from heatlens.scoring import prioritize_samples

LOCATION_PRESETS = {
    "Keller": {"latitude": 32.9444, "longitude": -97.2285, "description": "North of Fort Worth with mixed commercial corridors and residential edges."},
    "Fort Worth": {"latitude": 32.7555, "longitude": -97.3308, "description": "Downtown and central corridors with heavy pavement and limited canopy."},
    "Dallas": {"latitude": 32.7767, "longitude": -96.7970, "description": "An urban core comparison area for the DFW region."},
    "North Richland Hills": {"latitude": 32.8350, "longitude": -97.2147, "description": "Commercial retail corridors and mix-use nodes in the metro area."},
}
MIN_REAL_DATA_ZOOM = 11


def summarize_hotspots(hotspots: list[dict[str, Any]]) -> dict[str, Any]:
    if not hotspots:
        return {
            "avg_surface_temp_c": None,
            "avg_vegetation_index": None,
            "max_surface_temp_c": None,
            "hotspot_count": 0,
            "infrastructure_score": None,
            "avg_priority_score": None,
            "max_priority_score": None,
            "risk_summary": "No hotspot data available.",
        }

    temperatures = [item["surface_temp_c"] for item in hotspots]
    vegetation_indices = [
        item["vegetation_index"]
        for item in hotspots
        if item.get("vegetation_index") is not None
    ]
    priority_scores = [
        item["priority_score"]
        for item in hotspots
        if item.get("priority_score") is not None
    ]
    infrastructure_scores = [
        item["infrastructure_score"]
        for item in hotspots
        if item.get("infrastructure_score") is not None
    ]
    average_temp = sum(temperatures) / len(temperatures)
    average_veg = (
        sum(vegetation_indices) / len(vegetation_indices)
        if vegetation_indices
        else None
    )
    max_temp = max(temperatures)
    infra_score = (
        round(sum(infrastructure_scores) / len(infrastructure_scores), 1)
        if infrastructure_scores
        else None
    )

    risk_summary = "The monitored hotspots have elevated thermal conditions relative to nearby vegetated areas."
    return {
        "avg_surface_temp_c": round(average_temp, 2),
        "avg_vegetation_index": round(average_veg, 3) if average_veg is not None else None,
        "max_surface_temp_c": round(max_temp, 2),
        "hotspot_count": len(hotspots),
        "infrastructure_score": infra_score,
        "avg_priority_score": (
            round(sum(priority_scores) / len(priority_scores), 1)
            if priority_scores
            else None
        ),
        "max_priority_score": max(priority_scores) if priority_scores else None,
        "risk_summary": risk_summary,
    }


def zoom_to_analysis_scale(zoom: float) -> int:
    if zoom < 9:
        return 2000
    if zoom < 11:
        return 1000
    if zoom < 13:
        return 500
    if zoom < 15:
        return 250
    return 120


def initial_map_view(location_name: str, zoom: float = 12.5) -> dict[str, Any]:
    base = LOCATION_PRESETS.get(location_name, LOCATION_PRESETS["Keller"])
    latitude = float(base["latitude"])
    longitude = float(base["longitude"])
    return {
        "center": {"lat": latitude, "lng": longitude},
        "zoom": zoom,
        "bounds": viewport_bounds_for_center(latitude, longitude, zoom),
    }


def viewport_bounds_for_center(
    latitude: float,
    longitude: float,
    zoom: float,
    width: int = 900,
    height: int = 520,
) -> dict[str, float]:
    safe_latitude = max(-85.0, min(85.0, latitude))
    world_pixels = 256 * (2**zoom)
    longitude_delta = 360 * width / world_pixels / 2
    mercator_y = math.log(
        math.tan(math.pi / 4 + math.radians(safe_latitude) / 2)
    )
    mercator_delta = math.pi * height / world_pixels

    def mercator_to_latitude(value: float) -> float:
        return math.degrees(2 * math.atan(math.exp(value)) - math.pi / 2)

    return {
        "south": mercator_to_latitude(mercator_y - mercator_delta),
        "west": max(-180.0, longitude - longitude_delta),
        "north": mercator_to_latitude(mercator_y + mercator_delta),
        "east": min(180.0, longitude + longitude_delta),
    }


def parse_map_view(map_data: Any) -> dict[str, Any] | None:
    if not isinstance(map_data, dict):
        return None
    bounds = map_data.get("bounds")
    if not isinstance(bounds, dict):
        return None
    southwest = bounds.get("_southWest")
    northeast = bounds.get("_northEast")
    if not isinstance(southwest, dict) or not isinstance(northeast, dict):
        return None

    try:
        south = float(southwest["lat"])
        west = float(southwest["lng"])
        north = float(northeast["lat"])
        east = float(northeast["lng"])
        zoom = float(map_data["zoom"])
    except (KeyError, TypeError, ValueError):
        return None

    if not all(map(math.isfinite, (south, west, north, east, zoom))):
        return None
    if not (-90 <= south < north <= 90):
        return None
    if not (-180 <= west < east <= 180):
        return None
    if not (0 <= zoom <= 20):
        return None

    center_data = map_data.get("center", {})
    try:
        latitude = float(center_data["lat"])
        longitude = float(center_data["lng"])
    except (KeyError, TypeError, ValueError):
        latitude = (south + north) / 2
        longitude = (west + east) / 2
    if not all(map(math.isfinite, (latitude, longitude))):
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None

    return {
        "center": {"lat": latitude, "lng": longitude},
        "zoom": zoom,
        "bounds": {
            "south": south,
            "west": west,
            "north": north,
            "east": east,
        },
    }


def recommendations_for_hotspot(hotspot: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []

    if hotspot["vegetation_index"] < 0.35:
        recommendations.append(
            "Increase tree canopy and landscaped planting strips near pedestrian pathways and parking edges to reduce direct solar exposure."
        )
    if hotspot["infrastructure_score"] >= 72:
        recommendations.append(
            "Prioritize shade structures, permeable surface upgrades, and reduced-pavement islands in large parking areas with concentrated heat retention."
        )
    if hotspot["shade_index"] < 35:
        recommendations.append(
            "Add shade where people are waiting, walking, or parked for extended periods, especially near entrances and bus stops."
        )
    if hotspot["surface_temp_c"] >= 43:
        recommendations.append(
            "Evaluate pavement replacement or cooling strategies in the hottest segments, giving priority to pedestrian routes and high-use intersections."
        )

    if not recommendations:
        recommendations.append(
            "Maintain and expand existing vegetated buffers while keeping access routes shaded and well-ventilated in a North Texas climate."
        )

    return recommendations


def build_demo_results(
    location_name: str,
    center: tuple[float, float] | None = None,
    bounds: dict[str, float] | None = None,
    zoom: float | None = None,
) -> dict[str, Any]:
    base = LOCATION_PRESETS.get(location_name, LOCATION_PRESETS["Keller"])
    center_lat, center_lon = (
        center
        if center is not None
        else (base["latitude"], base["longitude"])
    )
    sample_label = "Visible map demo sample" if center is not None else f"{location_name} demo sample"
    if bounds is None:
        latitude_offset = 0.008
        longitude_offset = 0.007
    else:
        latitude_offset = (bounds["north"] - bounds["south"]) * 0.2
        longitude_offset = (bounds["east"] - bounds["west"]) * 0.2
    marker_radius = (
        max(180, zoom_to_analysis_scale(zoom) * 0.45)
        if zoom is not None
        else 180
    )

    hotspots = [
        {
            "id": "hotspot-01",
            "name": f"{sample_label} 1",
            "latitude": center_lat + latitude_offset,
            "longitude": center_lon - longitude_offset,
            "surface_temp_c": 45.1,
            "vegetation_index": 0.21,
            "infrastructure_score": 84,
            "shade_index": 22,
            "parking_extent": 76,
            "road_density": 83,
            "area_type": "Parking lot / retail edge",
            "notes": "Synthetic demonstration point; this is not a measured site or satellite observation.",
        },
        {
            "id": "hotspot-02",
            "name": f"{sample_label} 2",
            "latitude": center_lat + latitude_offset * 0.25,
            "longitude": center_lon + longitude_offset,
            "surface_temp_c": 43.8,
            "vegetation_index": 0.28,
            "infrastructure_score": 77,
            "shade_index": 27,
            "parking_extent": 67,
            "road_density": 88,
            "area_type": "Major intersection / road corridor",
            "notes": "Synthetic demonstration point; this is not a measured site or satellite observation.",
        },
        {
            "id": "hotspot-03",
            "name": f"{sample_label} 3",
            "latitude": center_lat - latitude_offset * 0.6,
            "longitude": center_lon - longitude_offset * 0.3,
            "surface_temp_c": 42.4,
            "vegetation_index": 0.33,
            "infrastructure_score": 71,
            "shade_index": 31,
            "parking_extent": 68,
            "road_density": 74,
            "area_type": "Office park / paved circulation",
            "notes": "Synthetic demonstration point; this is not a measured site or satellite observation.",
        },
        {
            "id": "hotspot-04",
            "name": f"{sample_label} 4",
            "latitude": center_lat - latitude_offset,
            "longitude": center_lon + longitude_offset * 0.9,
            "surface_temp_c": 41.6,
            "vegetation_index": 0.26,
            "infrastructure_score": 74,
            "shade_index": 24,
            "parking_extent": 73,
            "road_density": 79,
            "area_type": "Retail center / mall edge",
            "notes": "Synthetic demonstration point; this is not a measured site or satellite observation.",
        },
    ]

    for hotspot in hotspots:
        hotspot["recommendations"] = recommendations_for_hotspot(hotspot)
        hotspot["risk_level"] = "High" if hotspot["surface_temp_c"] >= 43 else "Moderate"
        if center is not None:
            hotspot["radius_m"] = marker_radius

    summary = summarize_hotspots(hotspots)
    return {
        "location_name": location_name,
        "center_lat": center_lat,
        "center_lon": center_lon,
        "mode": "demo",
        "data_mode": "demo",
        "source_note": "Demonstration data only. These hotspot values are synthetic and intended for interface validation and educational use. Real satellite observations should be used for operational analysis.",
        "hotspots": hotspots,
        "samples": hotspots,
        "summary": summary,
    }


def _format_real_results(
    location_name: str,
    features: list[dict[str, Any]],
    start_date: str,
    end_date: str,
    bounds: dict[str, float] | None = None,
    zoom: float | None = None,
    scale_m: int | None = None,
) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    for feature in features:
        properties = feature.get("properties", {})
        coordinates = feature.get("geometry", {}).get("coordinates", [])
        if len(coordinates) < 2:
            continue

        try:
            temperature = float(properties["surface_temp_c"])
            vegetation_index = float(properties["vegetation_index"])
            longitude, latitude = float(coordinates[0]), float(coordinates[1])
        except (KeyError, TypeError, ValueError):
            continue

        if not all(map(math.isfinite, (temperature, vegetation_index, latitude, longitude))):
            continue

        samples.append(
            {
                "latitude": latitude,
                "longitude": longitude,
                "surface_temp_c": round(temperature, 2),
                "vegetation_index": round(vegetation_index, 3),
            }
        )

    if not samples:
        return {
            "mode": "unavailable",
            "note": "Earth Engine found imagery, but there were no valid cloud-free temperature and vegetation pixels in this study area and date range.",
        }

    temperatures = sorted(sample["surface_temp_c"] for sample in samples)
    moderate_threshold = temperatures[int((len(temperatures) - 1) * 0.7)]
    high_threshold = temperatures[int((len(temperatures) - 1) * 0.9)]

    for index, sample in enumerate(samples, start=1):
        temperature = sample["surface_temp_c"]
        sample["id"] = f"landsat-sample-{index:03d}"
        sample["name"] = f"Sample {index:03d}"
        sample["radius_m"] = (scale_m or 120) * 0.45
        sample["risk_level"] = (
            "High"
            if temperature >= high_threshold
            else "Moderate"
            if temperature >= moderate_threshold
            else "Lower"
        )
        sample["notes"] = (
            f"Cloud-masked Landsat pixel sample in the visible map area near {location_name}. "
            f"Composite period: {start_date} through {end_date}."
        )
        sample["recommendations"] = []
        if sample["vegetation_index"] < 0.3:
            sample["recommendations"].append(
                "This sampled pixel has relatively low vegetation index; inspect the imagery and local land cover before considering shade or planting interventions."
            )
        if sample["risk_level"] == "High":
            sample["recommendations"].append(
                "This pixel is among the warmer sampled locations for this study area and period; verify it against additional dates before prioritizing action."
            )
        if not sample["recommendations"]:
            sample["recommendations"].append(
                "Use this observation as a screening signal and compare it with other dates and local land-cover information."
            )

    samples = prioritize_samples(samples)
    samples.sort(
        key=lambda item: (
            item["priority_score"] is None,
            -(item["priority_score"] or 0),
        )
    )
    hotspots = samples[:12]
    summary = summarize_hotspots(samples)
    summary["hotspot_count"] = len(hotspots)

    return {
        "mode": "real",
        "location_name": location_name,
        "center_lat": (
            (bounds["south"] + bounds["north"]) / 2
            if bounds
            else LOCATION_PRESETS[location_name]["latitude"]
        ),
        "center_lon": (
            (bounds["west"] + bounds["east"]) / 2
            if bounds
            else LOCATION_PRESETS[location_name]["longitude"]
        ),
        "bounds": bounds,
        "zoom": zoom,
        "analysis_scale_m": scale_m,
        "source": "USGS Landsat 8/9 Collection 2 Level-2 Surface Temperature and Surface Reflectance",
        "source_note": (
            f"Cloud-masked Landsat median composite from {start_date} through {end_date}, "
            f"sampled only within the current map bounds at approximately {scale_m or 120} m. "
            f"Summary statistics use {len(samples)} sampled pixels; "
            "the map and hotspot details show the 12 highest-priority sampled pixels. "
            "Priority scores combine relative temperature and vegetation ranks. "
            "Risk levels are relative to this sample, not health or regulatory thresholds."
        ),
        "sample_count": len(samples),
        "hotspots": hotspots,
        "samples": samples,
        "summary": summary,
    }


@st.cache_data(ttl=21600, max_entries=32, show_spinner=False)
def _fetch_landsat_features(
    project_id: str,
    bounds_tuple: tuple[float, float, float, float],
    start_date: str,
    end_date: str,
    scale_m: int,
) -> list[dict[str, Any]]:
    import ee  # type: ignore

    ee.Initialize(project=project_id)
    west, south, east, north = bounds_tuple
    region = ee.Geometry.Rectangle([west, south, east, north], geodesic=False)

    def mask_and_scale(image: Any) -> Any:
        qa = image.select("QA_PIXEL")
        clear = qa.bitwiseAnd(63).eq(0)
        surface_temp_c = (
            image.select("ST_B10")
            .multiply(0.00341802)
            .add(149.0)
            .subtract(273.15)
            .rename("surface_temp_c")
        )
        red = image.select("SR_B4").multiply(0.0000275).add(-0.2)
        nir = image.select("SR_B5").multiply(0.0000275).add(-0.2)
        vegetation_index = (
            nir.subtract(red)
            .divide(nir.add(red))
            .rename("vegetation_index")
        )
        return surface_temp_c.addBands(vegetation_index).updateMask(clear)

    collection = (
        ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        .merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2"))
        .filterBounds(region)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUD_COVER", 80))
    )
    if collection.size().getInfo() == 0:
        return []

    composite = collection.map(mask_and_scale).median()
    projection = collection.first().select("ST_B10").projection()
    composite = composite.setDefaultProjection(projection)
    if scale_m > 120:
        composite = composite.reduceResolution(
            reducer=ee.Reducer.mean(),
            maxPixels=16384,
        )
    feature_collection = composite.sample(
        region=region,
        scale=scale_m,
        numPixels=500,
        seed=7,
        dropNulls=True,
        tileScale=4,
        geometries=True,
    )
    return feature_collection.getInfo().get("features", [])


def maybe_load_real_data(
    location_name: str,
    project_id: str | None = None,
    bounds: dict[str, float] | None = None,
    zoom: float = 12.5,
) -> dict[str, Any]:
    if location_name not in LOCATION_PRESETS:
        raise ValueError(f"Unknown study area: {location_name}")
    if not project_id:
        return {
            "mode": "unavailable",
            "note": "Set EARTHENGINE_PROJECT or [earth_engine].project_id in Streamlit secrets to a Google Cloud project registered for Earth Engine.",
        }
    if zoom < MIN_REAL_DATA_ZOOM:
        return {
            "mode": "unavailable",
            "note": (
                "Zoom in to level 11 or closer to analyze one city at a time. "
                "Broader regional Landsat requests exceed the available processing limit."
            ),
        }

    try:
        import ee  # type: ignore  # noqa: F401
    except ImportError:
        return {
            "mode": "unavailable",
            "note": "Google Earth Engine is not installed. Install the project requirements before using real satellite data.",
        }

    if bounds is None:
        bounds = initial_map_view(location_name, zoom)["bounds"]
    try:
        west = float(bounds["west"])
        south = float(bounds["south"])
        east = float(bounds["east"])
        north = float(bounds["north"])
    except (KeyError, TypeError, ValueError):
        return {"mode": "unavailable", "note": "The map viewport bounds are invalid."}
    if not all(map(math.isfinite, (west, south, east, north))):
        return {"mode": "unavailable", "note": "The map viewport bounds are invalid."}
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        return {"mode": "unavailable", "note": "The map viewport bounds are invalid."}

    scale_m = zoom_to_analysis_scale(zoom)
    today = datetime.now(timezone.utc).date()
    start_date = (today - timedelta(days=730)).isoformat()
    end_date = today.isoformat()
    display_end_date = (today - timedelta(days=1)).isoformat()

    try:
        features = _fetch_landsat_features(
            project_id,
            (west, south, east, north),
            start_date,
            end_date,
            scale_m,
        )
    except Exception as error:
        return {
            "mode": "unavailable",
            "note": (
                "Earth Engine could not retrieve Landsat imagery for the current map "
                f"view: {error}"
            ),
        }

    if not features:
        return {
            "mode": "unavailable",
            "note": (
                f"No clear Landsat pixels were available in the visible map bounds "
                f"between {start_date} and {display_end_date}."
            ),
        }

    return _format_real_results(
        location_name,
        features,
        start_date,
        display_end_date,
        bounds=bounds,
        zoom=zoom,
        scale_m=scale_m,
    )
