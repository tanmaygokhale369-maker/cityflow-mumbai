# CityFlow Mumbai

CityFlow Mumbai is a local-first analytics dashboard for Mumbai public-transport data. It combines static GTFS schedules and stop geography with a live Open-Meteo weather request. The dashboard does not claim access to live vehicles, road traffic, passenger counts, or measured air quality.

## Dashboard pages

- **Overview** — route, stop, agency, scheduled-trip, coordinate-quality KPIs, route distributions, and explicit static-data context.
- **Interactive Map** — OpenStreetMap tiles, up to 3,000 clustered GTFS stop markers for responsive rendering, stop search and selection/details, agency/route filters, a stop-density heatmap for all filtered stops, and a representative scheduled-stop sequence when GTFS stop-time data supports it.
- **Route Analytics** — agency-filtered route comparisons, scheduled-trip analysis, per-route details, busiest stops, searchable route/stop tables, and CSV exports.
- **Geographic Analysis** — coordinate coverage, adjustable latitude/longitude bounds, a stop-density grid, and regional concentration insight.
- **Weather & Environment** — current Open-Meteo conditions, a refresh action, API fetch timestamps, and an hourly forecast. Mobility forecasts are omitted because this project has no historical observed outcomes.
- **Big Data Benchmark** — an on-demand Pandas and local PySpark comparison for route trip counts from the same actual `trips.txt`, with three alternating runs, median workload times, matching input/output row counts, and Spark startup reported separately.
- **Data Sources** — source provenance, availability, local refresh timestamps, coordinate quality, and explicit live-feed readiness.

The dashboard opens in a dark command-center theme; use the sidebar toggle to switch between dark and light appearances. The theme applies to both the dashboard surfaces and Plotly charts.

GTFS route lines are inferred from ordered scheduled stops; they are not road-following geometry. The current feed has no `shapes.txt`. OpenStreetMap tiles need browser network access. Up to the first 3,000 currently filtered stops are added to a chunk-loaded marker cluster for browser responsiveness; the heat layer represents the full filtered set. Search by stop name/ID or narrow agency/route filters to render other stops. Stop selection is enabled for up to 500 current matches.

## Windows setup (Python 3.11 and Java 17)

Open PowerShell in the `cityflow-mumbai` project folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
java -version
```

The responsive dashboard requires Streamlit 1.51 or newer. Use a Java 17 JDK if `java -version` does not report Java 17. The Windows GTFS processor uses a private Spark temporary directory and PyArrow for Parquet output; a separate `winutils.exe` download is not required.

## Use existing GTFS data

The dashboard reads the existing files in:

- `data/reference/gtfs_extracted/`
- `data/processed/routes_summary.parquet/`
- `data/processed/stops_summary.parquet/`

From the `cityflow-mumbai` project root (the directory containing `dashboard/`, `ingestion/`, and `data/`), start the dashboard without re-extracting or rewriting those files:

```powershell
python -m streamlit run dashboard\app.py
```

Open the local URL printed by Streamlit. Use **Refresh cached data** in the sidebar after changing source files. Dashboard reads are cached for ten minutes.

If you intentionally need to create or refresh the processed summaries, first ensure the extracted GTFS files are present, then run:

```powershell
python -m processing.process_gtfs
```

To extract a new ZIP, the existing loader command is:

```powershell
python -m ingestion.load_gtfs --zip data/raw/mumbai_gtfs.zip
```

**Caution:** that loader replaces `data/reference/gtfs_extracted/`. Do not run it if you want to preserve the current extracted GTFS files.

## Validate and benchmark

Check Python syntax:

```powershell
python -m compileall -q dashboard
```

The benchmark is intentionally opt-in: open **Big Data Benchmark** and click **Run Pandas vs PySpark benchmark**. It reads the same real `trips.txt` with both engines and compares the input row counts and per-route trip counts. It reports the median of three alternating workload runs (CSV read, aggregation, and result collection); PySpark session/JVM startup is measured and reported separately. The results can be exported as CSV. Small local workloads may be faster in Pandas; this benchmark is not a general performance claim.

## Data interpretation and sources

- **Mumbai GTFS** is a static schedule/network snapshot. Check the feed dates and license before publishing results.
- **Open-Meteo** supplies current API conditions and a weather-model forecast; its data is not a street-level observation archive.
- **OpenStreetMap** supplies interactive map tiles; attribution is displayed on the map.
- No historical mobility observations are present, so CityFlow does not generate demand or ridership forecasts.
- OpenAQ is not connected. The dashboard does not present fabricated air-quality readings.
- No live transport vehicle, traffic, or passenger-count source is connected.

Data folders: `data/raw/` holds source archives, `data/reference/` holds extracted/reference inputs, and `data/processed/` holds derived Parquet summaries. Avoid committing large source or derived data files.
