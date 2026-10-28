from pathlib import Path

from streamlit.testing.v1 import AppTest

import heatlens.analysis as analysis
from heatlens.analysis import (
    _format_real_results,
    build_demo_results,
    initial_map_view,
    maybe_load_real_data,
    parse_map_view,
    summarize_hotspots,
    zoom_to_analysis_scale,
)


def test_demo_results_include_hotspots_and_summary():
    result = build_demo_results("Keller")

    assert result["location_name"] == "Keller"
    assert len(result["hotspots"]) >= 3
    assert result["hotspots"][0]["surface_temp_c"] > 25
    assert result["summary"]["hotspot_count"] >= 1


def test_hotspot_summary_is_numeric_and_complete():
    result = build_demo_results("Fort Worth")
    summary = summarize_hotspots(result["hotspots"])

    assert summary["avg_surface_temp_c"] > 0
    assert summary["avg_vegetation_index"] >= 0
    assert summary["max_surface_temp_c"] >= summary["avg_surface_temp_c"]


def test_demo_sample_names_follow_selected_study_area():
    result = build_demo_results("Dallas")

    assert all("Dallas demo sample" in item["name"] for item in result["hotspots"])
    assert all("Keller" not in item["name"] for item in result["hotspots"])


def test_map_view_parser_reads_current_bounds_and_zoom():
    view = parse_map_view(
        {
            "bounds": {
                "_southWest": {"lat": 32.7, "lng": -97.5},
                "_northEast": {"lat": 32.9, "lng": -97.1},
            },
            "zoom": 13,
        }
    )

    assert view == {
        "center": {"lat": 32.8, "lng": -97.3},
        "zoom": 13,
        "bounds": {
            "south": 32.7,
            "west": -97.5,
            "north": 32.9,
            "east": -97.1,
        },
    }


def test_map_view_parser_rejects_invalid_bounds():
    invalid_view = {
        "bounds": {
            "_southWest": {"lat": 33, "lng": -97},
            "_northEast": {"lat": 32, "lng": -96},
        },
        "zoom": 12,
    }

    assert parse_map_view(invalid_view) is None
    assert parse_map_view(None) is None


def test_initial_city_view_is_zoomed_and_has_geographic_bounds():
    view = initial_map_view("Dallas")

    assert view["center"] == {"lat": 32.7767, "lng": -96.797}
    assert view["bounds"]["south"] < view["center"]["lat"] < view["bounds"]["north"]
    assert view["bounds"]["west"] < view["center"]["lng"] < view["bounds"]["east"]
    assert view["zoom"] == 12.5


def test_analysis_grid_gets_coarser_as_map_zooms_out():
    assert zoom_to_analysis_scale(8) == 2000
    assert zoom_to_analysis_scale(10) == 1000
    assert zoom_to_analysis_scale(12) == 500
    assert zoom_to_analysis_scale(14) == 250
    assert zoom_to_analysis_scale(16) == 120


def test_real_results_are_built_from_sampled_satellite_pixels():
    features = [
        {
            "geometry": {"coordinates": [-97.2, 32.9]},
            "properties": {"surface_temp_c": 35.0, "vegetation_index": 0.2},
        },
        {
            "geometry": {"coordinates": [-97.21, 32.91]},
            "properties": {"surface_temp_c": 40.0, "vegetation_index": 0.1},
        },
        {
            "geometry": {"coordinates": [-97.19, 32.89]},
            "properties": {"surface_temp_c": 30.0, "vegetation_index": 0.6},
        },
    ]

    result = _format_real_results("Dallas", features, "2023-01-01", "2026-10-25")

    assert result["mode"] == "real"
    assert result["sample_count"] == 3
    assert len(result["hotspots"]) == 3
    assert result["hotspots"][0]["surface_temp_c"] == 40.0
    assert result["hotspots"][0]["priority_score"] == 100
    assert result["hotspots"][0]["temperature_factor_score"] == 100
    assert result["hotspots"][0]["vegetation_deficit_factor_score"] == 100
    assert result["hotspots"][0]["latitude"] == 32.91
    assert result["hotspots"][0]["risk_level"] == "High"
    assert result["summary"]["avg_surface_temp_c"] == 35.0
    assert result["summary"]["infrastructure_score"] is None
    assert "Keller sample" not in result["hotspots"][0]["name"]


def test_real_results_report_when_no_valid_pixels_exist():
    result = _format_real_results("Dallas", [], "2023-01-01", "2026-10-25")

    assert result["mode"] == "unavailable"
    assert "no valid cloud-free" in result["note"]


def test_real_mode_requires_an_earth_engine_project():
    result = maybe_load_real_data("Dallas")

    assert result["mode"] == "unavailable"
    assert "EARTHENGINE_PROJECT" in result["note"]


def test_real_mode_requires_city_scale_zoom():
    result = maybe_load_real_data(
        "Dallas",
        project_id="configured-project",
        bounds={
            "south": 32.7,
            "west": -97.0,
            "north": 32.9,
            "east": -96.6,
        },
        zoom=10.5,
    )

    assert result["mode"] == "unavailable"
    assert "Zoom in to level 11" in result["note"]


def test_real_mode_renders_satellite_results(monkeypatch):
    features = [
        {
            "geometry": {"coordinates": [-97.2, 32.9]},
            "properties": {"surface_temp_c": 35.0, "vegetation_index": 0.2},
        },
        {
            "geometry": {"coordinates": [-97.21, 32.91]},
            "properties": {"surface_temp_c": 40.0, "vegetation_index": 0.1},
        },
        {
            "geometry": {"coordinates": [-97.19, 32.89]},
            "properties": {"surface_temp_c": 30.0, "vegetation_index": 0.6},
        },
    ]
    real_result = _format_real_results(
        "Keller", features, "2023-01-01", "2026-10-25"
    )
    monkeypatch.setattr(
        analysis,
        "maybe_load_real_data",
        lambda location_name, project_id: real_result,
    )

    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"),
        default_timeout=45,
    ).run()
    app.radio[0].set_value("Real satellite data").run()

    assert not app.exception
    assert any("Sampled pixels" == item.label for item in app.metric)
    assert any("Relative priority score" == item.label for item in app.metric)
    assert any("Temperature rank" == item.label for item in app.metric)
    assert any("Low-vegetation rank" == item.label for item in app.metric)
    assert any(
        "Sample" in option
        for selectbox in app.selectbox
        for option in selectbox.options
    )
    assert any("Intervention scenario lab" in item.value for item in app.subheader)
    assert any(
        "Assumed site area (m²)" == item.label for item in app.number_input
    )
    assert any(
        "These are independent hypothetical options" in item.value
        for item in app.info
    )
    assert not any("Infra. score" == item.label for item in app.metric)


def test_real_mode_keeps_dashboard_available_with_labeled_demo_fallback(monkeypatch):
    monkeypatch.setattr(
        analysis,
        "maybe_load_real_data",
        lambda location_name, project_id: {
            "mode": "unavailable",
            "note": "Test Earth Engine setup is unavailable.",
        },
    )
    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"),
        default_timeout=45,
    ).run()
    app.radio[0].set_value("Real satellite data").run()

    assert not app.exception
    assert any(
        "Test Earth Engine setup is unavailable." in item.value
        for item in app.error
    )
    assert any(
        "Analysis of the visible map area" in item.value
        for item in app.subheader
    )
    assert any(
        "REAL SATELLITE DATA UNAVAILABLE" in item.value
        and "synthetic points near the map center" in item.value
        for item in app.caption
    )
    assert any("Hotspot count" == item.label for item in app.metric)


def test_real_mode_handles_older_loader_and_incomplete_result(monkeypatch):
    def old_loader(location_name):
        return {
            "mode": "real",
            "surface_temp_c": 34.5,
            "source": "Older Earth Engine loader",
        }

    monkeypatch.setattr(analysis, "maybe_load_real_data", old_loader)
    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"),
        default_timeout=45,
    ).run()
    app.radio[0].set_value("Real satellite data").run()

    assert not app.exception
    assert any("loaded Earth Engine module is out of date" in item.value for item in app.error)
    assert any("REAL SATELLITE DATA UNAVAILABLE" in item.value for item in app.caption)
    assert any("Hotspot count" == item.label for item in app.metric)
