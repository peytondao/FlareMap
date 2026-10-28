from __future__ import annotations

import inspect
import os
import tomllib
from pathlib import Path
from typing import Any

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from streamlit_folium import st_folium

from heatlens.analysis import (
    LOCATION_PRESETS,
    build_demo_results,
    initial_map_view,
    maybe_load_real_data,
    parse_map_view,
    summarize_hotspots,
)
from heatlens.scenarios import simulate_interventions
from heatlens.scoring import DEFAULT_TEMPERATURE_WEIGHT, prioritize_samples


def get_earth_engine_project_id() -> str | None:
    project_id = os.getenv("EARTHENGINE_PROJECT")
    if project_id:
        return project_id

    try:
        secrets = st.secrets
    except StreamlitSecretNotFoundError:
        secrets = {}

    earth_engine_secrets = secrets.get("earth_engine", {})
    if isinstance(earth_engine_secrets, dict):
        project_id = earth_engine_secrets.get("project_id")
        if project_id:
            return str(project_id)
    project_id = secrets.get("EARTHENGINE_PROJECT")
    if project_id:
        return str(project_id)

    local_secrets_path = Path(__file__).resolve().parent / ".streamlit" / "secrets.toml"
    if not local_secrets_path.is_file():
        return None

    local_secrets = tomllib.loads(local_secrets_path.read_text(encoding="utf-8"))
    earth_engine_secrets = local_secrets.get("earth_engine", {})
    if isinstance(earth_engine_secrets, dict):
        project_id = earth_engine_secrets.get("project_id")
        if project_id:
            return str(project_id)
    project_id = local_secrets.get("EARTHENGINE_PROJECT")
    return str(project_id) if project_id else None


def load_real_data(
    location_name: str,
    project_id: str | None,
    bounds: dict[str, float],
    zoom: float,
) -> dict[str, Any]:
    loader_parameters = inspect.signature(maybe_load_real_data).parameters
    loader_kwargs: dict[str, Any] = {}
    if "project_id" in loader_parameters:
        loader_kwargs["project_id"] = project_id
    if "bounds" in loader_parameters:
        loader_kwargs["bounds"] = bounds
    if "zoom" in loader_parameters:
        loader_kwargs["zoom"] = zoom
    if "project_id" in loader_parameters:
        result = maybe_load_real_data(location_name, **loader_kwargs)
    else:
        result = maybe_load_real_data(location_name)

    if result.get("mode") == "real":
        required_fields = {"hotspots", "samples", "summary", "source", "source_note"}
        missing_fields = required_fields.difference(result)
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            return {
                "mode": "unavailable",
                "note": (
                    "The loaded Earth Engine module is out of date and returned an "
                    f"incomplete result (missing: {missing}). Restart Streamlit and "
                    "make sure it is running this workspace's heatlens/analysis.py."
                ),
            }

    return result


def reset_map_view_for_city() -> None:
    location_name = st.session_state["study_area"]
    st.session_state["map_view"] = initial_map_view(location_name)
    st.session_state["map_location"] = location_name


def update_map_view() -> None:
    map_view = parse_map_view(st.session_state.get("heatlens_map"))
    if map_view is not None:
        st.session_state["map_view"] = map_view
        st.session_state["map_location"] = st.session_state["study_area"]


st.set_page_config(
    page_title="HeatLens TX",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "map_view" not in st.session_state:
    st.session_state["map_view"] = initial_map_view("Keller")
if "study_area" not in st.session_state:
    st.session_state["study_area"] = "Keller"


def build_map(
    center: dict[str, float],
    zoom: float,
    hotspots: list[dict[str, Any]],
) -> folium.Map:
    map_obj = folium.Map(
        location=[center["lat"], center["lng"]],
        zoom_start=zoom,
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community",
    )

    for hotspot in hotspots:
        color = {
            "High": "red",
            "Moderate": "orange",
            "Lower": "yellow",
        }.get(hotspot.get("risk_level"), "orange")
        popup_details = [
            f"<b>{hotspot['name']}</b>",
            f"Surface temp: {hotspot['surface_temp_c']:.1f}°C",
            f"Vegetation index: {hotspot['vegetation_index']:.2f}",
        ]
        if hotspot.get("infrastructure_score") is not None:
            popup_details.append(f"Infrastructure score: {hotspot['infrastructure_score']}")
        if hotspot.get("priority_score") is not None:
            popup_details.append(f"Relative priority score: {hotspot['priority_score']}/100")

        folium.Circle(
            location=[hotspot["latitude"], hotspot["longitude"]],
            radius=hotspot.get("radius_m", max(180, hotspot["surface_temp_c"] * 18)),
            color=color,
            fill=True,
            fill_opacity=0.55,
            popup="<br>".join(popup_details),
        ).add_to(map_obj)

        folium.Marker(
            location=[hotspot["latitude"], hotspot["longitude"]],
            tooltip=f"{hotspot['name']} • {hotspot['surface_temp_c']:.1f}°C",
            icon=folium.Icon(color="darkred", icon="info-sign"),
        ).add_to(map_obj)

    folium.LayerControl().add_to(map_obj)
    return map_obj


st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(180deg, #091522 0%, #0d1e2d 100%); }
    div[data-testid="stSidebar"] { background: #0b1725; }
    .block-container { padding-top: 1.5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


st.title("HeatLens TX")
st.caption("Mapping urban heat. Informing smarter infrastructure.")

with st.sidebar:
    st.header("Location")
    location_name = st.selectbox(
        "Jump to a study area",
        list(LOCATION_PRESETS.keys()),
        key="study_area",
        on_change=reset_map_view_for_city,
    )
    data_mode = st.radio("Data mode", ["Demo mode", "Real satellite data"], index=0)
    temperature_weight = DEFAULT_TEMPERATURE_WEIGHT
    if data_mode == "Real satellite data":
        temperature_weight = st.slider(
            "Surface temperature weight",
            min_value=0.0,
            max_value=1.0,
            value=DEFAULT_TEMPERATURE_WEIGHT,
            step=0.05,
            help=(
                "The remaining weight is assigned to low vegetation rank. "
                "Both inputs are relative to the currently visible map area."
            ),
        )
        st.caption(
            f"Temperature: {temperature_weight:.0%} · "
            f"low vegetation: {1 - temperature_weight:.0%}"
        )
    st.caption(
        "Pan or zoom the map to analyze only the visible area. "
        "Real mode uses Landsat observations; demo mode uses synthetic points."
    )

    real_status = None
    if data_mode == "Real satellite data":
        current_view = st.session_state["map_view"]
        real_status = load_real_data(
            location_name,
            get_earth_engine_project_id(),
            current_view["bounds"],
            current_view["zoom"],
        )
        if real_status["mode"] == "real":
            st.success("Landsat observations loaded for the visible map area.")
            st.caption(f"Source: {real_status['source']}")
            st.caption(
                f"Map zoom {current_view['zoom']:.1f} · "
                f"analysis grid approximately {real_status['analysis_scale_m']} m"
            )
        else:
            st.error(real_status["note"])

    st.markdown("---")
    st.markdown(
        """
        Data note: land-surface temperature is not the same as air temperature. 
        This tool highlights thermal patterns and compares them with vegetation and impervious surfaces.
        """
    )

if data_mode == "Real satellite data" and real_status is not None and real_status["mode"] == "real":
    result = real_status
elif data_mode == "Real satellite data":
    current_view = st.session_state["map_view"]
    result = build_demo_results(
        location_name,
        center=(
            current_view["center"]["lat"],
            current_view["center"]["lng"],
        ),
        bounds=current_view["bounds"],
        zoom=current_view["zoom"],
    )
    result["source_note"] = (
        f"REAL SATELLITE DATA UNAVAILABLE — showing synthetic points near the map center, not measurements. "
        f"{real_status['note']} {result['source_note']}"
    )
else:
    current_view = st.session_state["map_view"]
    result = build_demo_results(
        location_name,
        center=(
            current_view["center"]["lat"],
            current_view["center"]["lng"],
        ),
        bounds=current_view["bounds"],
        zoom=current_view["zoom"],
    )

hotspots = result["hotspots"]
summary = result["summary"]
observations = result.get("samples", hotspots)
if result["mode"] == "real":
    observations = prioritize_samples(
        observations,
        temperature_weight=temperature_weight,
    )
    observations.sort(
        key=lambda item: (
            item["priority_score"] is None,
            -(item["priority_score"] or 0),
        )
    )
    hotspots = observations[:12]
    result["samples"] = observations
    result["hotspots"] = hotspots
    summary = summarize_hotspots(observations)

st.subheader("Analysis of the visible map area")
st.caption(result["source_note"])

metric_cols = st.columns(4)
metric_cols[0].metric("Avg. surface temp", f"{summary['avg_surface_temp_c']}°C")
if result["mode"] == "real":
    metric_cols[1].metric("Sampled pixels", result["sample_count"])
    metric_cols[2].metric("Avg. vegetation index", f"{summary['avg_vegetation_index']:.3f}")
    metric_cols[3].metric("Warmest sampled pixel", f"{summary['max_surface_temp_c']}°C")
else:
    metric_cols[1].metric("Hotspot count", summary["hotspot_count"])
    metric_cols[2].metric("Avg. vegetation index", f"{summary['avg_vegetation_index']:.3f}")
    metric_cols[3].metric(
        "Demo infra. score",
        f"{summary['infrastructure_score']}/100",
    )

map_col, side_col = st.columns([2.2, 1.1])

with map_col:
    st.caption(
        f"Map center {current_view['center']['lat']:.4f}, "
        f"{current_view['center']['lng']:.4f} · zoom {current_view['zoom']:.1f}"
    )
    map_obj = build_map(current_view["center"], current_view["zoom"], hotspots)
    st_folium(
        map_obj,
        width=900,
        height=520,
        key="heatlens_map",
        returned_objects=["bounds", "zoom"],
        on_change=update_map_view,
    )

with side_col:
    st.subheader("Hotspot focus")
    hotspot_names = [hotspot["name"] for hotspot in hotspots]
    selected_name = st.selectbox("Select hotspot", hotspot_names, index=0)
    selected_hotspot = next(item for item in hotspots if item["name"] == selected_name)

    st.metric("Surface temp", f"{selected_hotspot['surface_temp_c']:.1f}°C")
    st.metric("Vegetation index", f"{selected_hotspot['vegetation_index']:.2f}")
    if result["mode"] == "real":
        if selected_hotspot["priority_score"] is not None:
            st.metric(
                "Relative priority score",
                f"{selected_hotspot['priority_score']}/100",
            )
        factor_cols = st.columns(2)
        temperature_factor = selected_hotspot["temperature_factor_score"]
        vegetation_factor = selected_hotspot["vegetation_deficit_factor_score"]
        factor_cols[0].metric(
            "Temperature rank",
            f"{temperature_factor}/100" if temperature_factor is not None else "N/A",
        )
        factor_cols[1].metric(
            "Low-vegetation rank",
            f"{vegetation_factor}/100" if vegetation_factor is not None else "N/A",
        )
        st.caption(
            "These are relative ranks within the visible map sample, not validated "
            "risk thresholds. Temperature and vegetation can be related; the score "
            "does not establish causation or infrastructure failure."
        )
    else:
        st.metric("Shade index", f"{selected_hotspot['shade_index']}/100")
        st.metric("Infrastructure score", f"{selected_hotspot['infrastructure_score']}/100")

    st.markdown("### Factors")
    st.write(selected_hotspot["notes"])

    st.markdown("### Recommendations")
    for recommendation in selected_hotspot["recommendations"]:
        st.markdown(f"- {recommendation}")

st.markdown("---")
st.subheader("Intervention scenario lab")
st.caption(
    f"Scenarios for selected point: {selected_hotspot['name']}. This is a sampled "
    "pixel, not a mapped parcel or project boundary. Enter an assumed site area "
    "below; these calculations estimate affected area only and do not predict "
    "temperature, health outcomes, feasibility, or cost."
)

site_area_m2 = st.number_input(
    "Assumed site area (m²)",
    min_value=100.0,
    max_value=1_000_000.0,
    value=5_000.0,
    step=500.0,
    help="User-entered scenario assumption; the application does not measure a site boundary.",
)
tree_controls, shade_controls, pavement_controls = st.columns(3)
with tree_controls:
    tree_count = st.number_input(
        "Number of proposed trees",
        min_value=0,
        max_value=500,
        value=10,
        step=1,
        key="scenario_tree_count",
    )
    canopy_diameter_m = st.number_input(
        "Assumed mature canopy diameter (m)",
        min_value=0.0,
        max_value=30.0,
        value=6.0,
        step=0.5,
        key="scenario_canopy_diameter",
    )
with shade_controls:
    shade_structure_area_m2 = st.number_input(
        "Shade structure footprint (m²)",
        min_value=0.0,
        max_value=1_000_000.0,
        value=200.0,
        step=25.0,
        key="scenario_structure_area",
    )
with pavement_controls:
    pavement_conversion_area_m2 = st.number_input(
        "Pavement area converted (m²)",
        min_value=0.0,
        max_value=1_000_000.0,
        value=500.0,
        step=50.0,
        key="scenario_pavement_area",
    )
    permeable_conversion_percent = st.slider(
        "Converted area that is permeable",
        min_value=0,
        max_value=100,
        value=100,
        step=5,
        format="%d%%",
        key="scenario_permeable_percent",
    )

scenario_results = simulate_interventions(
    site_area_m2=float(site_area_m2),
    tree_count=int(tree_count),
    tree_canopy_diameter_m=float(canopy_diameter_m),
    shade_structure_area_m2=float(shade_structure_area_m2),
    pavement_conversion_area_m2=float(pavement_conversion_area_m2),
    permeable_conversion_percent=float(permeable_conversion_percent),
)
scenario_columns = st.columns(3)
for column, scenario in zip(
    scenario_columns, scenario_results["scenarios"].values()
):
    with column.container(border=True):
        st.markdown(f"#### {scenario['label']}")
        st.metric(scenario["metric_label"], f"{scenario['area_m2']:,.1f} m²")
        st.caption(f"{scenario['site_area_percent']:.1f}% of assumed site area")
        if "permeable_area_m2" in scenario:
            st.metric(
                "Permeable area gained",
                f"{scenario['permeable_area_m2']:,.1f} m²",
                help=(
                    "Assumes the converted area is currently impervious. It is not "
                    "a measurement of existing site surface."
                ),
            )
        st.caption(scenario["assumption"])

st.info(
    "These are independent hypothetical options, not a combined design. Tree "
    "species, establishment, water needs, utility conflicts, existing cover, "
    "overlap, and maintenance require site-specific review. No cooling benefit "
    "or cost is estimated.",
    title="Scenario assumptions and limitations",
)

st.markdown("---")

chart_col, comparison_col = st.columns(2)

with chart_col:
    df = pd.DataFrame(observations)
    scatter_options = {
        "x": "vegetation_index",
        "y": "surface_temp_c",
        "color": "risk_level",
        "hover_name": "name",
        "labels": {
            "surface_temp_c": "Surface temperature (°C)",
            "vegetation_index": "Vegetation index",
        },
        "title": "Surface temperature vs. vegetation coverage",
        "template": "plotly_dark",
    }
    if result["mode"] != "real":
        scatter_options["size"] = "infrastructure_score"
    scatter = px.scatter(df, **scatter_options)
    st.plotly_chart(
        scatter,
        width="stretch",
        alt="Sampled surface temperature plotted against vegetation index",
    )

with comparison_col:
    if result["mode"] == "real":
        comparison_df = pd.DataFrame(
            {
                "Metric": ["Sample mean", "Warmest sampled pixel"],
                "Value": [
                    summary["avg_surface_temp_c"],
                    summary["max_surface_temp_c"],
                ],
            }
        )
    else:
        comparison_df = pd.DataFrame(
            {
                "Metric": ["Hotspot average", "Nearest vegetation", "Commercial pavement intensity"],
                "Value": [summary["avg_surface_temp_c"], round(summary["avg_vegetation_index"] * 100, 1), round(summary["infrastructure_score"], 1)],
            }
        )
    bar = px.bar(
        comparison_df,
        x="Metric",
        y="Value",
        color="Metric",
        title="Comparative heat indicators",
        template="plotly_dark",
    )
    st.plotly_chart(
        bar,
        width="stretch",
        alt="Surface temperature summary comparison",
    )

st.markdown("---")

info_col, method_col = st.columns([1.2, 1.8])
with info_col:
    st.subheader("Methodology")
    if result["mode"] == "real":
        st.write(
            "Landsat 8/9 Collection 2 Level-2 scenes are cloud-masked and composited only within the visible map bounds. "
            "Surface temperature and NDVI are satellite-derived observations; the mapped points are sampled pixels, not parcel or street-level measurements. "
            "The priority score is a configurable weighted combination of within-viewport percentile ranks for warmer surface temperature and lower NDVI. "
            "It is an exploratory screening aid, not a validated heat-risk or infrastructure-condition metric."
        )
    else:
        st.write(
            "Demo mode uses a synthetic sample dataset to exercise the interface. "
            "It does not describe measured conditions in the selected study area."
        )
with method_col:
    st.subheader("What the colors mean")
    if result["mode"] == "real":
        st.write(
            "Red, orange, and yellow points rank the sampled pixels from warmer to cooler relative to the selected study area and composite period. "
            "The relative priority score combines each sample's temperature percentile rank and inverse NDVI percentile rank using the selected weights. "
            "NDVI is not a direct measurement of tree canopy, pavement, shade, or infrastructure."
        )
    else:
        st.write(
            "Demo hotspot colors indicate synthetic temperature bands. Vegetation values and infrastructure scores are illustrative, not satellite measurements."
        )

st.caption(
    "Land-surface temperature is not air temperature. Map zoom changes the aggregation grid, not the native resolution of Landsat thermal measurements. "
    "Observations depend on cloud masking, revisit timing, and composite period; use them for screening, not parcel-level decisions."
)
