# FlareMap

FlareMap is a Streamlit application for exploring urban heat hotspots in Texas. It focuses on surface temperature patterns, vegetation, and infrastructure conditions.

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

