# HeatLens TX

HeatLens TX is a Streamlit application for exploring urban heat hotspots in Texas. It is designed for the Texas Congressional App Challenge and focuses on surface temperature patterns, vegetation, and infrastructure conditions.

## Overview

The app provides:

- An interactive map that starts at a selected North Texas study area and follows the current pan/zoom viewport
- Synthetic demo hotspot data for an MVP without external credentials
- A hotspot detail panel with temperature, vegetation, and recommendation information
- An explainable, configurable hotspot-prioritization score for real satellite samples
- Exploratory guidance for shade, landscaping, and pavement planning
- A clear data-integrity notice when live Earth Engine data is not available

## Features

- Heat hotspot detection and comparison
- Data mode toggle for demo vs. real satellite analysis
- Folium map with selectable study-area starting points and viewport-driven results
- Zoom-dependent aggregation: wider analysis cells at city scale and Landsat-scale sampling when zoomed in
- Cached Earth Engine requests keyed by map bounds, date range, and analysis scale
- Plotly-based comparison charts
- Guidance for reducing urban heat using North Texas-appropriate planning strategies
- A transparent, hypothetical intervention scenario comparison for canopy, shade structures, and pavement conversion

## Hotspot prioritization

Real satellite samples are ranked with a screening score from 0 to 100:

`score = 100 × (temperature_weight × temperature_percentile + vegetation_weight × (1 − NDVI_percentile))`

Percentile ranks are calculated against valid samples in the current viewport and composite. The default temperature weight is 0.65; the remaining weight is assigned to low NDVI, and the temperature weight can be adjusted in the sidebar. Equal measurements receive the average rank; a single valid measurement receives a neutral percentile rank of 0.5. If one input is missing, the available factor's weight is renormalized; if both are missing, no score is shown.

The score answers which samples are relatively warmer and/or less vegetated than others in the visible sample. It is not a validated heat-risk, health, canopy, pavement, or infrastructure-condition metric. Temperature and NDVI may be related, so the weights are transparent exploratory assumptions, not calibrated causal effects. No impervious-surface or pedestrian-shade factor is currently included because the real-data pipeline does not yet measure those inputs. The synthetic demo's infrastructure score is illustrative only.

## Intervention scenario lab

The scenario lab compares three independent hypothetical options: added tree-canopy projection, shade-structure footprint, and pavement conversion. Users enter an assumed site area and intervention parameters. The module calculates affected area and its share of the entered site area. For pavement conversion, only the entered permeable fraction is counted as a possible impervious-area reduction, assuming the converted surface is currently impervious.

These are user-supplied scenario assumptions, not mapped site measurements or a combined design. Tree canopy uses a circular projected footprint based on an assumed mature canopy diameter, assumes no overlap, and is capped at the assumed site area. Shade structure area is only a footprint proxy. Existing vegetation, shade, surface types, feasibility, water needs, maintenance, costs, and temperature effects are not modeled. Review drought tolerance, establishment watering, utilities, access, and maintenance with local professionals before considering a real project.

## Quick start

1. Create and activate a virtual environment (optional but recommended):

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Launch the app:

   ```bash
   streamlit run app.py
   ```

4. Open the local Streamlit URL in your browser.

## Real-data configuration

Real satellite mode queries Landsat 8 and 9 Collection 2 Level-2 scenes through Google Earth Engine for the current map viewport. It applies a pixel-level cloud/shadow/snow mask, creates a median composite over the latest two years through the latest completed day (subject to scene availability), and samples up to 500 pixels. For processing reliability and a single-city view, live analysis requires zoom 11 or closer; zooming farther out displays a prompt instead of requesting an oversized regional computation. The sampling grid changes with zoom: 500 m from zoom 11 to below 13, 250 m below zoom 15, and 120 m when zoomed in further. Coarser grids aggregate Landsat pixels; zooming in does not increase Landsat's native thermal resolution. Summary statistics describe the current viewport, and its 12 highest-priority sampled pixels are shown on the map.

To enable it locally on Windows:

   ```powershell
   $env:EARTHENGINE_PROJECT = "your-registered-google-cloud-project-id"
   earthengine authenticate
   streamlit run app.py
   ```

The Google Cloud project must be registered for Earth Engine. Instead of the environment variable, the project ID can be configured in `.streamlit/secrets.toml`:

   ```toml
   [earth_engine]
   project_id = "your-registered-google-cloud-project-id"
   ```

On hosted deployments, configure the project ID as a secret and provide valid Earth Engine credentials through the host's supported authentication mechanism. After setup, select **Real satellite data** and pan or zoom to an area. If project configuration, authentication, or imagery sampling fails, the app reports the problem and explicitly labels the visible synthetic demo fallback.

## Data integrity and caveats

- Demo mode uses synthetic values and is clearly labeled as sample data.
- Real satellite analysis uses Landsat 8/9 Collection 2 Level-2 surface temperature and surface reflectance when available.
- The selected city is a map starting point, not a city-wide boundary. Real-mode analysis uses the map viewport bounds, not every city in a region or a fixed radius.
- Real-mode statistics estimate conditions from up to 500 sampled pixels at a zoom-dependent scale. The displayed warmest pixels and relative risk bands are screening signals, not health or regulatory thresholds.
- Land surface temperature is different from air temperature and varies with acquisition date, cloud cover, and spatial resolution.
- Recommendations are qualitative and should be used as general design guidance rather than exact cooling forecasts.
- Relative priority scores change with the viewport, sampled pixels, observation period, and selected weights; do not compare them as absolute scores between different map views.

## Potential next improvements

- Add a user-selectable observation date range and map-layer controls
- Incorporate local impervious-surface and parcel data for more precise planning guidance
- Add exportable hotspot summaries and PDF-style reports
- Add a site-level intervention simulator after defensible infrastructure and site-area data are available

## AI assistance record

An AI coding assistant helped implement viewport-driven Landsat sampling, the relative-priority scoring module, and the hypothetical intervention scenario calculations, UI controls, tests, and documentation. The project maintainer should review the code, independently explain the percentile formula and scenario assumptions, and verify data interpretation before presenting results.
