from datetime import datetime
from html import escape
from math import cos, radians
from pathlib import Path

import folium
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
from folium.plugins import Fullscreen, HeatMap, MarkerCluster
from streamlit_folium import st_folium

from dashboard.analytics import (
    benchmark_trip_counts,
    load_gtfs_reference,
    load_route_stop_counts,
    load_route_stop_details,
    read_parquet,
)
from ingestion.weather_api import fetch_weather


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
GTFS_ROOT = ROOT / "data" / "reference" / "gtfs_extracted"
ROUTES_PATH = PROCESSED / "routes_summary.parquet"
STOPS_PATH = PROCESSED / "stops_summary.parquet"
MAP_MARKER_LIMIT = 3_000
STOP_SELECT_LIMIT = 500

st.set_page_config(
    page_title="CityFlow Mumbai | Mobility Analytics",
    page_icon="🚍",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.session_state.setdefault("cityflow_dark_mode", False)
dark_theme = st.session_state["cityflow_dark_mode"]
if dark_theme:
    page_background = "#101827"
    sidebar_background = "#111d2e"
    surface = "#19263a"
    surface_border = "#35465e"
    text_color = "#f1f5f9"
    muted_color = "#c2cfdd"
    accent = "#67e8f9"
    secondary_accent = "#93c5fd"
    grid_color = "#34445a"
else:
    page_background = "#f3f6fa"
    sidebar_background = "#ffffff"
    surface = "#ffffff"
    surface_border = "#d9e2ec"
    text_color = "#14243a"
    muted_color = "#475569"
    accent = "#0e7490"
    secondary_accent = "#1d4ed8"
    grid_color = "#dbe4ee"
chart_template = go.layout.Template(
    pio.templates["plotly_dark" if dark_theme else "plotly_white"].to_plotly_json()
)
chart_template.layout.update(
    paper_bgcolor=page_background,
    plot_bgcolor=page_background,
    font={"color": text_color, "family": "Inter, Segoe UI, sans-serif", "size": 13},
    colorway=[accent, secondary_accent, "#059669", "#d97706", "#7c3aed"],
    xaxis={
        "color": text_color,
        "gridcolor": grid_color,
        "linecolor": grid_color,
        "zerolinecolor": grid_color,
        "title": {"font": {"color": text_color}},
        "tickfont": {"color": muted_color},
    },
    yaxis={
        "color": text_color,
        "gridcolor": grid_color,
        "linecolor": grid_color,
        "zerolinecolor": grid_color,
        "title": {"font": {"color": text_color}},
        "tickfont": {"color": muted_color},
    },
    legend={
        "font": {"color": text_color},
        "bgcolor": page_background,
    },
    hoverlabel={
        "bgcolor": surface,
        "bordercolor": surface_border,
        "font": {"color": text_color, "size": 13},
    },
)
pio.templates["cityflow_theme"] = chart_template
px.defaults.template = "cityflow_theme"
px.defaults.color_discrete_sequence = [accent, secondary_accent, "#059669", "#d97706", "#7c3aed"]
st.markdown(
    f"""
    <style>
    :root {{
        --cf-bg: {page_background};
        --cf-sidebar: {sidebar_background};
        --cf-surface: {surface};
        --cf-border: {surface_border};
        --cf-text: {text_color};
        --cf-muted: {muted_color};
        --cf-accent: {accent};
        --cf-accent-soft: {"rgba(103, 232, 249, 0.14)" if dark_theme else "rgba(14, 116, 144, 0.09)"};
        --cf-control-bg: {"#19263a" if dark_theme else "#ffffff"};
        --cf-hover: {"#24344b" if dark_theme else "#edf5fa"};
        --primary-color: {accent};
    }}
    .stApp {{
        background: var(--cf-bg);
        color: var(--cf-text);
    }}
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{background: transparent;}}
    .block-container {{padding: 1.5rem 2rem 3rem; max-width: 1680px;}}
    .stApp, .stApp p, .stApp label, .stApp li, .stApp small,
    [data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"],
    [data-testid="stText"], [data-testid="stHeader"] {{
        color: var(--cf-text);
    }}
    [data-testid="stCaptionContainer"], .cityflow-muted {{color: var(--cf-muted) !important;}}
    [data-testid="stSidebar"] {{
        background: var(--cf-sidebar);
        border-right: 1px solid var(--cf-border);
    }}
    [data-testid="stSidebar"] > div:first-child {{background: transparent;}}
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
        color: var(--cf-text);
    }}
    [data-testid="stMetric"] {{
        background: var(--cf-surface);
        border: 1px solid var(--cf-border);
        border-radius: 16px;
        padding: 1rem 1.1rem;
        box-shadow: 0 5px 16px rgba(15, 23, 42, 0.08);
        min-height: 112px;
    }}
    [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p {{
        color: var(--cf-muted) !important; font-size: 0.84rem;
    }}
    [data-testid="stMetricValue"], [data-testid="stMetricValue"] div {{
        color: var(--cf-text) !important; font-weight: 700;
    }}
    [data-testid="stMetricDelta"] {{color: var(--cf-muted) !important;}}
    [data-testid="stPlotlyChart"], [data-testid="stDataFrame"], [data-testid="stMap"] {{
        border-radius: 14px;
    }}
    [data-testid="stPlotlyChart"] {{
        border: 1px solid var(--cf-border); overflow: hidden;
        background: var(--cf-surface);
    }}
    [data-testid="stDataFrame"] {{border: 1px solid var(--cf-border); overflow: hidden;}}
    [data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p {{
        color: var(--cf-text) !important; font-weight: 600;
    }}
    [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
    [data-testid="stDateInput"] input, [data-testid="stTimeInput"] input,
    [data-testid="stSelectbox"] [role="combobox"],
    [data-testid="stMultiSelect"] [role="combobox"],
    [data-testid="stTextArea"] textarea {{
        color: var(--cf-text) !important;
        background: var(--cf-control-bg) !important;
        border-color: var(--cf-border) !important;
    }}
    [data-testid="stTextInput"] input::placeholder,
    [data-testid="stTextArea"] textarea::placeholder {{
        color: var(--cf-muted) !important; opacity: 1;
    }}
    [role="listbox"] {{
        color: var(--cf-text) !important;
        background: var(--cf-control-bg) !important;
        border: 1px solid var(--cf-border) !important;
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.18);
    }}
    [role="listbox"] [role="option"] {{
        color: var(--cf-text) !important; background: var(--cf-control-bg) !important;
    }}
    [role="listbox"] [role="option"]:hover,
    [role="listbox"] [role="option"][aria-selected="true"] {{
        background: var(--cf-hover) !important;
    }}
    [data-testid="stAlert"] {{
        background: var(--cf-surface); border: 1px solid var(--cf-border);
        color: var(--cf-text);
    }}
    [data-testid="stAlert"] p, [data-testid="stAlert"] [data-testid="stMarkdownContainer"] {{
        color: var(--cf-text) !important;
    }}
    div[data-testid="stButton"] > button, div[data-testid="stDownloadButton"] > button {{
        border-radius: 10px;
        border: 1px solid var(--cf-border);
        transition: border-color 140ms ease, transform 140ms ease;
        color: var(--cf-text);
    }}
    div[data-testid="stButton"] > button:hover, div[data-testid="stDownloadButton"] > button:hover {{
        border-color: var(--cf-accent);
        transform: translateY(-1px);
    }}
    [data-testid="stSidebar"] [role="radiogroup"] {{
        display: flex; flex-direction: column; gap: 0.35rem;
    }}
    [data-testid="stSidebar"] input[type="radio"],
    [data-testid="stSidebar"] input[type="checkbox"] {{accent-color: var(--cf-accent);}}
    [data-testid="stSidebar"] [data-testid="stRadioOption"] {{
        border: 1px solid transparent; border-radius: 10px;
        padding: 0.45rem 0.55rem; transition: background 140ms ease, border-color 140ms ease;
    }}
    [data-testid="stSidebar"] [data-testid="stRadioOption"]:hover {{
        background: var(--cf-hover);
    }}
    [data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] {{
        background: var(--cf-accent-soft) !important;
        border-color: var(--cf-accent) !important;
        box-shadow: inset 3px 0 var(--cf-accent);
    }}
    [data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] p {{
        color: var(--cf-text) !important; font-weight: 700;
    }}
    .cityflow-brand {{
        font-size: 1.35rem; font-weight: 750; letter-spacing: -0.04em;
        color: var(--cf-text) !important; margin: 0;
    }}
    .cityflow-brand span {{color: var(--cf-accent);}}
    .cityflow-eyebrow {{
        color: var(--cf-accent); font-size: 0.76rem; font-weight: 700;
        letter-spacing: 0.13em; text-transform: uppercase; margin-bottom: 0.35rem;
    }}
    .cityflow-hero {{
        border: 1px solid var(--cf-border); border-radius: 18px;
        background: var(--cf-surface);
        padding: 1.2rem 1.4rem; margin-bottom: 1.25rem;
        box-shadow: 0 5px 18px rgba(15, 23, 42, 0.06);
    }}
    .cityflow-hero h1 {{color: var(--cf-text); font-size: 2rem; margin: 0; letter-spacing: -0.04em;}}
    .cityflow-hero p {{color: var(--cf-muted); margin: 0.4rem 0 0;}}
    .cityflow-pill {{
        display: inline-block; border: 1px solid var(--cf-border); border-radius: 999px;
        padding: 0.25rem 0.6rem; color: var(--cf-muted); font-size: 0.66rem;
        letter-spacing: 0.06em; margin-left: 0.65rem; vertical-align: middle;
    }}
    .cityflow-muted {{color: var(--cf-muted); font-size: 0.9rem;}}
    @media (max-width: 760px) {{
        .block-container {{padding: 1rem 1rem 2rem;}}
        [data-testid="stMetric"] {{padding: 0.8rem; min-height: 96px;}}
        .cityflow-hero h1 {{font-size: 1.55rem;}}
        .cityflow-pill {{margin-left: 0; margin-top: 0.4rem;}}
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


def _plotly_chart(figure, **kwargs):
    figure.update_layout(
        paper_bgcolor=page_background,
        plot_bgcolor=page_background,
        font={"color": text_color, "family": "Inter, Segoe UI, sans-serif", "size": 13},
        title_font_color=text_color,
        legend={"font": {"color": text_color}, "bgcolor": page_background},
        hoverlabel={
            "bgcolor": surface,
            "bordercolor": surface_border,
            "font": {"color": text_color, "size": 13},
        },
    )
    for axes in (figure.layout.xaxis, figure.layout.yaxis):
        axes.update(
            color=text_color,
            gridcolor=grid_color,
            linecolor=grid_color,
            zerolinecolor=grid_color,
            tickfont={"color": muted_color},
            title_font={"color": text_color},
        )
    st.plotly_chart(figure, **kwargs)


@st.cache_data(ttl=600, show_spinner=False)
def get_weather():
    return fetch_weather()


def _safe_read(path: Path, label: str):
    if not path.exists():
        return None, f"{label} has not been processed yet."
    try:
        frame = read_parquet(str(path))
    except Exception as exc:
        return None, f"Could not read {label}: {exc}"
    if frame.empty:
        return None, f"{label} is empty; regenerate it from the extracted GTFS data."
    required_columns = {
        "Processed route summary": {"route_id"},
        "Processed stop summary": {"stop_id", "stop_lat", "stop_lon"},
    }.get(label, set())
    missing = required_columns.difference(frame.columns)
    if missing:
        return None, (
            f"{label} is missing required column(s): "
            f"{', '.join(sorted(missing))}."
        )
    return frame, None


def _route_type_name(value):
    try:
        code = int(value)
    except (TypeError, ValueError):
        return "Unknown"
    return {
        0: "Tram / light rail",
        1: "Metro / subway",
        2: "Rail",
        3: "Bus",
        4: "Ferry",
        5: "Cable tram",
        6: "Gondola",
        7: "Funicular",
    }.get(code, f"Other ({code})")


def _valid_stops(stops):
    if stops is None or not {"stop_lat", "stop_lon"}.issubset(stops.columns):
        return pd.DataFrame()
    result = stops.copy()
    result["stop_lat"] = pd.to_numeric(result["stop_lat"], errors="coerce")
    result["stop_lon"] = pd.to_numeric(result["stop_lon"], errors="coerce")
    result = result.dropna(subset=["stop_lat", "stop_lon"])
    return result[
        result["stop_lat"].between(-90, 90)
        & result["stop_lon"].between(-180, 180)
    ].copy()


def _latest_modified(paths):
    existing = [path for path in paths if path.exists()]
    if not existing:
        return "Not available"
    latest = max(path.stat().st_mtime for path in existing)
    return datetime.fromtimestamp(latest).astimezone().strftime("%Y-%m-%d %H:%M %Z")


def _agency_name_map(reference):
    agencies = reference["agencies"]
    if agencies.empty or "agency_id" not in agencies.columns:
        return {}
    name_column = "agency_name" if "agency_name" in agencies.columns else "agency_id"
    return (
        agencies.dropna(subset=["agency_id"])
        .drop_duplicates("agency_id")
        .set_index("agency_id")[name_column]
        .astype(str)
        .to_dict()
    )


def _enrich_routes(reference):
    routes = reference["routes"].copy()
    if routes.empty:
        return routes
    if "route_type" in routes.columns:
        routes["mode"] = routes["route_type"].map(_route_type_name)
    else:
        routes["mode"] = "Unknown"
    agencies = reference["agencies"]
    if (
        not agencies.empty
        and {"agency_id", "agency_name"}.issubset(agencies.columns)
        and "agency_id" in routes.columns
    ):
        names = agencies.drop_duplicates("agency_id")[["agency_id", "agency_name"]]
        routes = routes.merge(names, on="agency_id", how="left")
    return routes


def _render_map(stops, reference, agency_names):
    st.markdown(
        "OpenStreetMap tiles · scheduled GTFS stops · click a marker for details. "
        "Stop-sequence lines are inferred from schedules, not road geometry."
    )
    routes = _enrich_routes(reference)
    agencies = sorted(routes["agency_id"].dropna().astype(str).unique()) if "agency_id" in routes else []
    agency_labels = {"All agencies": None}
    agency_labels.update({
        f"{agency_names.get(agency_id, agency_id)} ({agency_id})": agency_id
        for agency_id in agencies
    })
    agency_label = st.selectbox("Agency filter", list(agency_labels), key="map_agency")
    selected_agency = agency_labels[agency_label]
    route_options = routes.copy()
    if selected_agency is not None and "agency_id" in route_options.columns:
        route_options = route_options[
            route_options["agency_id"].astype(str) == selected_agency
        ]
    route_options = route_options.drop_duplicates("route_id") if "route_id" in route_options else route_options
    route_choices = {"All routes": None}
    if "route_id" in route_options.columns:
        for _, route in route_options.iterrows():
            route_id = str(route["route_id"])
            short_name = route.get("route_short_name")
            long_name = route.get("route_long_name")
            label = " · ".join(
                str(value) for value in (short_name, long_name, route_id)
                if pd.notna(value) and str(value).strip()
            )
            route_choices[label] = route_id
    route_label = st.selectbox("Route filter", list(route_choices), key="map_route")
    selected_route = route_choices[route_label]

    displayed_stops = _valid_stops(stops)
    if selected_agency is not None or selected_route is not None:
        selected_routes = route_options
        if selected_route is not None:
            selected_routes = selected_routes[
                selected_routes["route_id"].astype(str) == selected_route
            ]
        route_ids = tuple(selected_routes["route_id"].dropna().astype(str).unique())
        feeds = tuple(selected_routes["feed_path"].dropna().astype(str).unique())
        if not route_ids or not feeds:
            displayed_stops = displayed_stops.iloc[0:0]
        else:
            with st.spinner("Finding scheduled stops for the selected routes…"):
                stop_ids, route_path = load_route_stop_details(
                    feeds, route_ids, path_route_id=selected_route
                )
            displayed_stops = displayed_stops[
                displayed_stops["stop_id"].astype(str).isin(stop_ids)
            ]
    else:
        route_path = ()

    search = st.text_input("Search stop name or ID", key="map_stop_search").strip().casefold()
    if search:
        names = displayed_stops.get("stop_name", pd.Series("", index=displayed_stops.index))
        ids = displayed_stops.get("stop_id", pd.Series("", index=displayed_stops.index))
        matches = names.fillna("").astype(str).str.casefold().str.contains(search, regex=False)
        matches |= ids.fillna("").astype(str).str.casefold().str.contains(search, regex=False)
        displayed_stops = displayed_stops[matches]

    if displayed_stops.empty:
        st.info("No stops match these filters. Adjust the agency, route, or search.")
        return

    st.metric("Stops matching filters", f"{len(displayed_stops):,}")
    marker_stops = displayed_stops.head(MAP_MARKER_LIMIT)
    if len(displayed_stops) > MAP_MARKER_LIMIT:
        st.info(
            f"Clustering the first {MAP_MARKER_LIMIT:,} matching stop markers for map "
            f"responsiveness. The density layer includes all {len(displayed_stops):,} "
            "matches; search by stop name/ID or narrow the agency/route filters to map "
            "other stops."
        )
    stop_ids = displayed_stops.get("stop_id", pd.Series(displayed_stops.index, index=displayed_stops.index))
    labels = displayed_stops.get("stop_name", pd.Series("Unnamed stop", index=displayed_stops.index))
    options = {
        str(stop_id): str(name) if pd.notna(name) else "Unnamed stop"
        for stop_id, name in zip(stop_ids, labels)
    }
    selected_stop_id = None
    if len(displayed_stops) <= STOP_SELECT_LIMIT:
        option_ids = [None] + list(options)
        selected_stop_id = st.selectbox(
            "Select a stop",
            option_ids,
            format_func=lambda value: (
                "No stop selected" if value is None
                else f"{options[value]} · {value}"
            ),
            key="map_selected_stop",
        )
    else:
        st.caption(
            f"Search for a stop name or ID to enable selection "
            f"(showing a selector for up to {STOP_SELECT_LIMIT:,} matches)."
        )

    center = [
        float(displayed_stops["stop_lat"].median()),
        float(displayed_stops["stop_lon"].median()),
    ]
    zoom = 10
    if selected_stop_id is not None:
        selected_rows = displayed_stops[
            displayed_stops["stop_id"].astype(str) == selected_stop_id
        ]
        if not selected_rows.empty:
            center = [
                float(selected_rows.iloc[0]["stop_lat"]),
                float(selected_rows.iloc[0]["stop_lon"]),
            ]
            zoom = 14
    map_view = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles="OpenStreetMap",
        control_scale=True,
        prefer_canvas=True,
    )
    Fullscreen(position="topright", title="Full screen", title_cancel="Exit full screen").add_to(map_view)

    stop_layer = folium.FeatureGroup(name="Stops (clustered)", show=True)
    cluster = MarkerCluster(
        name="Stops",
        options={"chunkedLoading": True, "maxClusterRadius": 55},
    ).add_to(stop_layer)
    for _, row in marker_stops.iterrows():
        stop_id = str(row.get("stop_id", "Unknown ID"))
        stop_name = str(row.get("stop_name", "Unnamed stop"))
        if stop_name == "nan":
            stop_name = "Unnamed stop"
        details = [
            f"<b>{escape(stop_name)}</b>",
            f"Stop ID: {escape(stop_id)}",
            f"Coordinates: {row['stop_lat']:.5f}, {row['stop_lon']:.5f}",
        ]
        if pd.notna(row.get("scheduled_stop_time_records")):
            details.append(
                f"Scheduled stop-time records: {int(row['scheduled_stop_time_records']):,}"
            )
        if pd.notna(row.get("routes_serving_stop")):
            details.append(f"Routes serving stop: {int(row['routes_serving_stop']):,}")
        folium.CircleMarker(
            location=[float(row["stop_lat"]), float(row["stop_lon"])],
            radius=5,
            color="#075985",
            fill=True,
            fill_color="#0ea5e9",
            fill_opacity=0.8,
            tooltip=f"{escape(stop_name)} · {escape(stop_id)}",
            popup=folium.Popup("<br>".join(details), max_width=320),
        ).add_to(cluster)
    stop_layer.add_to(map_view)

    heat_layer = folium.FeatureGroup(name="Stop density", show=False)
    HeatMap(
        displayed_stops[["stop_lat", "stop_lon"]].values.tolist(),
        radius=13,
        blur=16,
        min_opacity=0.2,
    ).add_to(heat_layer)
    heat_layer.add_to(map_view)

    if selected_route is not None and route_path:
        coordinates = (
            displayed_stops.assign(stop_id=displayed_stops["stop_id"].astype(str))
            .drop_duplicates("stop_id")
            .set_index("stop_id")[["stop_lat", "stop_lon"]]
        )
        route_points = [
            [float(coordinates.loc[stop_id, "stop_lat"]), float(coordinates.loc[stop_id, "stop_lon"])]
            for stop_id in route_path if stop_id in coordinates.index
        ]
        if len(route_points) > 1:
            line_layer = folium.FeatureGroup(name="Inferred scheduled stop sequence", show=True)
            folium.PolyLine(
                route_points,
                color="#e11d48",
                weight=4,
                opacity=0.8,
                tooltip="One scheduled trip's ordered stops; not a road/GPS track",
            ).add_to(line_layer)
            line_layer.add_to(map_view)

    if selected_stop_id is not None:
        selected_rows = displayed_stops[
            displayed_stops["stop_id"].astype(str) == selected_stop_id
        ]
        if not selected_rows.empty:
            row = selected_rows.iloc[0]
            folium.Marker(
                [float(row["stop_lat"]), float(row["stop_lon"])],
                icon=folium.Icon(color="red", icon="bus", prefix="fa"),
                tooltip=f"Selected: {escape(options[selected_stop_id])}",
            ).add_to(map_view)

    folium.LayerControl(collapsed=False).add_to(map_view)
    map_state = st_folium(
        map_view,
        height=650,
        use_container_width=True,
        returned_objects=["last_object_clicked"],
        key="cityflow_folium_map",
    )
    clicked = map_state.get("last_object_clicked") if map_state else None
    clicked_stop_id = None
    if clicked and {"lat", "lng"}.issubset(clicked):
        clicked_latitude = float(clicked["lat"])
        longitude_scale = cos(radians(clicked_latitude))
        latitude_delta = displayed_stops["stop_lat"] - clicked_latitude
        longitude_delta = (
            displayed_stops["stop_lon"] - float(clicked["lng"])
        ) * longitude_scale
        nearest_index = (latitude_delta.pow(2) + longitude_delta.pow(2)).idxmin()
        nearest = displayed_stops.loc[nearest_index]
        if (abs(float(nearest["stop_lat"]) - float(clicked["lat"])) < 0.0003
                and abs(float(nearest["stop_lon"]) - float(clicked["lng"])) < 0.0003):
            clicked_stop_id = str(nearest.get("stop_id", ""))
    detail_stop_id = clicked_stop_id or selected_stop_id
    if detail_stop_id:
        selected_rows = displayed_stops[
            displayed_stops["stop_id"].astype(str) == detail_stop_id
        ] if "stop_id" in displayed_stops.columns else pd.DataFrame()
        if not selected_rows.empty:
            selected = selected_rows.iloc[0]
            st.subheader("Selected stop")
            detail_columns = st.columns(4)
            detail_columns[0].metric("Stop", str(selected.get("stop_name", "Unnamed")))
            detail_columns[1].metric("Stop ID", detail_stop_id)
            detail_columns[2].metric(
                "Scheduled stop-time records",
                f"{int(selected['scheduled_stop_time_records']):,}"
                if pd.notna(selected.get("scheduled_stop_time_records")) else "Not available",
            )
            detail_columns[3].metric(
                "Routes serving stop",
                f"{int(selected['routes_serving_stop']):,}"
                if pd.notna(selected.get("routes_serving_stop")) else "Not available",
            )
            st.caption(
                f"Coordinates: {float(selected['stop_lat']):.6f}, "
                f"{float(selected['stop_lon']):.6f} · "
                f"Feed: {selected.get('feed_folder', 'unknown')}"
            )
    st.caption(
        f"OpenStreetMap © contributors · {len(marker_stops):,} clustered markers shown; "
        f"heat layer covers {len(displayed_stops):,} filtered stops."
    )
    if selected_route is not None and route_path:
        st.caption(
            "Route overlay uses a representative ordered trip from GTFS stop_times. "
            "No GTFS shapes.txt is present, so this is not a street-following route."
        )


def _overview(routes, stops, reference):
    agencies = reference["agencies"]
    trips = reference["trips"]
    valid = _valid_stops(stops)
    total_stops = len(stops) if stops is not None else 0
    valid_count = len(valid)
    valid_route_count = (
        routes["route_id"].nunique() if routes is not None and "route_id" in routes else 0
    )
    agency_count = (
        agencies["agency_id"].nunique() if "agency_id" in agencies else 0
    )
    trip_count = len(trips)
    coverage = (valid_count / total_stops * 100) if total_stops else 0
    kpis = st.columns(5)
    for column, label, value, help_text in zip(
        kpis,
        ("Routes", "Stops", "Agencies", "Scheduled trips", "Data quality"),
        (
            f"{valid_route_count:,}" if routes is not None else "Not available",
            f"{total_stops:,}" if stops is not None else "Not available",
            f"{agency_count:,}" if not agencies.empty else "Not available",
            f"{trip_count:,}" if not trips.empty else "Not available",
            f"{coverage:.1f}%" if total_stops else "Not available",
        ),
        (
            "Unique route IDs in the processed summary",
            "Processed stop rows",
            "Unique IDs in source agency.txt",
            "Rows in source trips.txt; scheduled, not observed",
            f"{valid_count:,} of {total_stops:,} processed stops have valid coordinates",
        ),
    ):
        column.metric(label, value, help=help_text)

    st.info(
        "Data status: GTFS is a static schedule and network snapshot. It does not contain "
        "live vehicle positions, traffic, or passenger counts."
    )
    if total_stops and valid_count:
        st.markdown(
            f'<p class="cityflow-muted">Coordinate validation: <b>{valid_count:,}</b> of '
            f'<b>{total_stops:,}</b> processed stops are within valid latitude/longitude '
            f'ranges ({coverage:.1f}% coverage).</p>',
            unsafe_allow_html=True,
        )
    if routes is None or stops is None:
        st.warning("Some processed summaries are unavailable; follow the Data Sources page to process GTFS.")
        return
    left, right = st.columns(2)
    with left:
        if "route_type" in routes.columns:
            modes = routes.assign(
                Mode=routes["route_type"].map(_route_type_name)
            )["Mode"].value_counts().rename_axis("Mode").reset_index(name="Routes")
            _plotly_chart(
                px.bar(modes, x="Mode", y="Routes", title="Routes by GTFS mode"),
                width="stretch",
            )
    with right:
        route_detail = _enrich_routes(reference)
        if "agency_id" in route_detail.columns:
            route_detail["Agency"] = route_detail.get(
                "agency_name", route_detail["agency_id"]
            ).fillna(route_detail["agency_id"])
            distribution = route_detail["Agency"].value_counts().rename_axis("Agency").reset_index(name="Routes")
            _plotly_chart(
                px.bar(distribution.head(12), x="Routes", y="Agency", orientation="h",
                       title="Routes by agency"),
                width="stretch",
            )
    with st.expander("Data quality checks"):
        route_duplicates = (
            int(routes["route_id"].duplicated().sum())
            if "route_id" in routes.columns else None
        )
        stop_duplicates = (
            int(stops["stop_id"].duplicated().sum())
            if "stop_id" in stops.columns else None
        )
        quality = pd.DataFrame([
            {"Check": "Stops with valid latitude and longitude", "Result": f"{valid_count:,} / {total_stops:,}"},
            {"Check": "Stops with missing/invalid coordinates", "Result": f"{total_stops - valid_count:,}"},
            {"Check": "Duplicate route IDs", "Result": f"{route_duplicates:,}" if route_duplicates is not None else "Column unavailable"},
            {"Check": "Duplicate stop IDs", "Result": f"{stop_duplicates:,}" if stop_duplicates is not None else "Column unavailable"},
        ])
        st.dataframe(quality, hide_index=True, width="stretch")


def _route_analytics(routes, stops, reference, agency_names):
    if routes is None or routes.empty:
        st.warning("Route summary is not available.")
        return
    if "route_id" not in routes.columns:
        st.error("Route summary is missing the required route_id column.")
        return
    enriched = _enrich_routes(reference)
    if enriched.empty:
        enriched = routes.copy()
        enriched["mode"] = (
            enriched["route_type"].map(_route_type_name)
            if "route_type" in enriched else "Unknown"
        )
    trips = reference["trips"]
    if not trips.empty and {"route_id", "trip_id"}.issubset(trips.columns):
        group_columns = ["route_id"]
        if "feed_folder" in trips.columns and "feed_folder" in enriched.columns:
            group_columns.insert(0, "feed_folder")
        trip_counts = (
            trips.dropna(subset=["route_id"])
            .groupby(group_columns, dropna=True)
            .size()
            .rename("scheduled_trips")
            .reset_index()
        )
        for column in group_columns:
            enriched[column] = enriched[column].astype("string")
            trip_counts[column] = trip_counts[column].astype("string")
        enriched = enriched.merge(trip_counts, on=group_columns, how="left")
    else:
        enriched["scheduled_trips"] = pd.NA
        st.warning("GTFS trips.txt is unavailable; scheduled trip counts cannot be calculated.")
    agency_column = "agency_name" if "agency_name" in enriched else "agency_id"
    if agency_column in enriched:
        agency_options = ["All agencies"] + sorted(
            enriched[agency_column].dropna().astype(str).unique().tolist()
        )
        selected_agency = st.selectbox(
            "Agency filter",
            agency_options,
            key="route_analytics_agency",
        )
        analysis_routes = enriched
        if selected_agency != "All agencies":
            analysis_routes = enriched[
                enriched[agency_column].fillna("").astype(str) == selected_agency
            ]
    else:
        analysis_routes = enriched
        st.info("Agency IDs are not available in the route feed; showing all routes.")
    if analysis_routes.empty:
        st.info("No routes match this agency.")
        return
    mode_counts = analysis_routes["mode"].value_counts().rename_axis("Mode").reset_index(name="Routes")
    left, right = st.columns(2)
    with left:
        _plotly_chart(
            px.bar(mode_counts, x="Mode", y="Routes", title="Routes by GTFS route type"),
            width="stretch",
        )
    with right:
        if "agency_id" in analysis_routes:
            agency_distribution = analysis_routes.copy()
            agency_distribution["Agency"] = agency_distribution.get(
                "agency_name", analysis_routes["agency_id"]
            ).fillna(analysis_routes["agency_id"])
            by_agency = agency_distribution["Agency"].value_counts().rename_axis("Agency").reset_index(name="Routes")
            _plotly_chart(
                px.bar(by_agency.head(15), x="Routes", y="Agency", orientation="h",
                       title="Route distribution by agency"),
                width="stretch",
            )
    feed_paths = tuple(reference["feeds"].get("feed_path", pd.Series(dtype=str)).astype(str))
    stops_per_route = pd.DataFrame(columns=["route_id", "stops_on_route"])
    if feed_paths:
        with st.spinner("Calculating unique scheduled stops per route from GTFS stop_times…"):
            stops_per_route = load_route_stop_counts(feed_paths)
        if not stops_per_route.empty:
            joined = stops_per_route.merge(
                analysis_routes[["route_id"] + (["route_short_name"] if "route_short_name" in analysis_routes else [])],
                on="route_id",
                how="left",
            )
            joined["Route"] = joined.apply(
                lambda row: f"{row.get('route_short_name', '')} ({row['route_id']})",
                axis=1,
            )
            chart_data = joined.nlargest(25, "stops_on_route")
            _plotly_chart(
                px.bar(chart_data, x="stops_on_route", y="Route", orientation="h",
                       title="Routes with the most unique scheduled stops"),
                width="stretch",
            )
        else:
            st.warning("GTFS stop_times did not yield route-to-stop relationships.")
    st.subheader("Route comparison")
    route_labels = {}
    for _, route in analysis_routes.iterrows():
        route_id = str(route["route_id"])
        short_name = route.get("route_short_name")
        long_name = route.get("route_long_name")
        label = " · ".join(
            str(value) for value in (short_name, long_name, route_id)
            if pd.notna(value) and str(value).strip()
        )
        route_labels[label] = route_id
    compared_labels = st.multiselect(
        "Choose routes to compare by scheduled trips",
        list(route_labels),
        max_selections=6,
        key="route_comparison_selection",
        help="Counts are scheduled GTFS trips, not observed or live service.",
    )
    if compared_labels:
        comparison = analysis_routes[
            analysis_routes["route_id"].astype(str).isin(
                [route_labels[label] for label in compared_labels]
            )
        ].copy()
        comparison["scheduled_trips"] = pd.to_numeric(
            comparison["scheduled_trips"], errors="coerce"
        )
        comparison = comparison.dropna(subset=["scheduled_trips"])
        if comparison.empty:
            st.info("Scheduled trip counts are unavailable for the selected routes.")
        else:
            comparison["Route"] = comparison.apply(
                lambda row: (
                    f"{row.get('route_short_name', '')} ({row['route_id']})"
                    if pd.notna(row.get("route_short_name"))
                    else str(row["route_id"])
                ),
                axis=1,
            )
            _plotly_chart(
                px.bar(
                    comparison.sort_values("scheduled_trips"),
                    x="scheduled_trips",
                    y="Route",
                    orientation="h",
                    title="Scheduled trips by selected route",
                    labels={"scheduled_trips": "Scheduled trips"},
                ),
                width="stretch",
            )
    route_detail_options = [None] + list(route_labels.values())
    route_detail_id = st.selectbox(
        "Inspect route details",
        route_detail_options,
        format_func=lambda value: (
            "Select a route" if value is None
            else next(label for label, route_id in route_labels.items() if route_id == value)
        ),
        key="route_detail_selection",
    )
    if route_detail_id is not None:
        detail = analysis_routes[
            analysis_routes["route_id"].astype(str) == route_detail_id
        ].iloc[0]
        detail_columns = st.columns(4)
        detail_columns[0].metric("Route ID", route_detail_id)
        detail_columns[1].metric("Mode", str(detail.get("mode", "Unknown")))
        detail_columns[2].metric(
            "Scheduled trips",
            f"{int(detail['scheduled_trips']):,}"
            if pd.notna(detail.get("scheduled_trips")) else "Not available",
        )
        route_stop_rows = stops_per_route[
            stops_per_route["route_id"].astype(str) == route_detail_id
        ]
        detail_columns[3].metric(
            "Unique scheduled stops",
            f"{int(route_stop_rows.iloc[0]['stops_on_route']):,}"
            if not route_stop_rows.empty else "Not available",
        )
        st.caption(
            f"{detail.get('route_long_name', 'Route details unavailable')} · "
            f"Agency: {detail.get('agency_name', detail.get('agency_id', 'Not available'))}"
        )
    if stops is not None and "scheduled_stop_time_records" in stops.columns:
        busiest = stops.copy()
        busiest["scheduled_stop_time_records"] = pd.to_numeric(
            busiest["scheduled_stop_time_records"], errors="coerce"
        )
        busiest = busiest.nlargest(20, "scheduled_stop_time_records")
        if not busiest.empty:
            busiest["Stop"] = busiest.apply(
                lambda row: f"{row.get('stop_name', 'Unnamed')} ({row.get('stop_id', '')})",
                axis=1,
            )
            _plotly_chart(
                px.bar(busiest, x="scheduled_stop_time_records", y="Stop", orientation="h",
                       title="Stops with the most scheduled stop-time records"),
                width="stretch",
            )
    st.subheader("Searchable route table")
    route_search = st.text_input(
        "Search route name or ID",
        key="route_table_search",
        placeholder="Route short name, long name, or ID",
    ).strip().casefold()
    route_table = analysis_routes.copy()
    if route_search:
        route_match = pd.Series(False, index=route_table.index)
        for column in ("route_short_name", "route_long_name", "route_id"):
            if column in route_table:
                route_match |= route_table[column].fillna("").astype(str).str.casefold().str.contains(
                    route_search, regex=False
                )
        route_table = route_table[route_match]
    route_table = route_table.sort_values(
        "scheduled_trips", ascending=False, na_position="last"
    )
    route_columns = [
        column for column in (
            "route_id", "route_short_name", "route_long_name", "mode",
            "agency_name", "agency_id", "scheduled_trips",
        ) if column in route_table
    ]
    st.caption(f"{len(route_table):,} routes match the current search and agency filter.")
    st.dataframe(route_table[route_columns], hide_index=True, width="stretch")
    st.download_button(
        "Download filtered routes as CSV",
        route_table[route_columns].to_csv(index=False).encode("utf-8-sig"),
        file_name="cityflow_routes.csv",
        mime="text/csv",
        key="download_routes_csv",
    )

    st.subheader("Searchable stop table")
    if stops is None or stops.empty:
        st.warning("Processed stop summary is unavailable.")
    else:
        stop_search = st.text_input(
            "Search stop name or ID",
            key="route_analytics_stop_search",
            placeholder="Stop name or ID",
        ).strip().casefold()
        stop_table = stops.copy()
        if stop_search:
            stop_match = pd.Series(False, index=stop_table.index)
            for column in ("stop_name", "stop_id"):
                if column in stop_table:
                    stop_match |= stop_table[column].fillna("").astype(str).str.casefold().str.contains(
                        stop_search, regex=False
                    )
            stop_table = stop_table[stop_match]
        service_column = "scheduled_stop_time_records"
        if service_column in stop_table:
            stop_table[service_column] = pd.to_numeric(
                stop_table[service_column], errors="coerce"
            )
            stop_table = stop_table.sort_values(
                service_column, ascending=False, na_position="last"
            )
        stop_columns = [
            column for column in (
                "stop_id", "stop_name", "stop_lat", "stop_lon",
                "scheduled_stop_time_records", "routes_serving_stop",
            ) if column in stop_table
        ]
        st.caption(
            f"{len(stop_table):,} stops match. The table displays the first "
            f"{min(500, len(stop_table)):,}; CSV contains every matching row."
        )
        st.dataframe(
            stop_table[stop_columns].head(500),
            hide_index=True,
            width="stretch",
        )
        st.download_button(
            "Download filtered stops as CSV",
            stop_table[stop_columns].to_csv(index=False).encode("utf-8-sig"),
            file_name="cityflow_stops.csv",
            mime="text/csv",
            key="download_stops_csv",
        )
    st.caption(
        f"Agency labels are sourced from agency.txt ({len(agency_names):,} agency IDs). "
        "Scheduled trip/stop counts describe the timetable, not observed service."
    )


def _geographic_analysis(stops):
    valid = _valid_stops(stops)
    if valid.empty:
        st.warning("No valid stop coordinates are available.")
        return
    col1, col2, col3 = st.columns(3)
    col1.metric("Geocoded stops", f"{len(valid):,}")
    col2.metric(
        "Latitude span",
        f"{valid['stop_lat'].min():.3f}° to {valid['stop_lat'].max():.3f}°",
    )
    col3.metric(
        "Longitude span",
        f"{valid['stop_lon'].min():.3f}° to {valid['stop_lon'].max():.3f}°",
    )
    st.caption(
        "Coverage reflects the coordinates supplied in static GTFS. It is not a measure "
        "of service frequency, demand, or live operating conditions."
    )
    filter_columns = st.columns(2)
    latitude_limits = filter_columns[0].slider(
        "Latitude bounds",
        min_value=float(valid["stop_lat"].min()),
        max_value=float(valid["stop_lat"].max()),
        value=(float(valid["stop_lat"].min()), float(valid["stop_lat"].max())),
        format="%.4f°",
        key="geo_latitude_bounds",
    )
    longitude_limits = filter_columns[1].slider(
        "Longitude bounds",
        min_value=float(valid["stop_lon"].min()),
        max_value=float(valid["stop_lon"].max()),
        value=(float(valid["stop_lon"].min()), float(valid["stop_lon"].max())),
        format="%.4f°",
        key="geo_longitude_bounds",
    )
    filtered = valid[
        valid["stop_lat"].between(*latitude_limits)
        & valid["stop_lon"].between(*longitude_limits)
    ]
    if filtered.empty:
        st.info("No stops fall inside this geographic window. Expand the coordinate bounds.")
        return
    st.caption(f"{len(filtered):,} of {len(valid):,} geocoded GTFS stops fall inside the selected bounds.")
    latitude_bins = pd.cut(filtered["stop_lat"], bins=min(20, max(1, filtered["stop_lat"].nunique())))
    longitude_bins = pd.cut(filtered["stop_lon"], bins=min(20, max(1, filtered["stop_lon"].nunique())))
    densest_cell_count = int(
        filtered.groupby([latitude_bins, longitude_bins], observed=True).size().max()
    )
    st.info(
        f"Regional insight: the densest coordinate grid cell in this view contains "
        f"{densest_cell_count:,} GTFS stops. This measures stop concentration, not ridership."
    )
    chart_data = filtered.rename(columns={"stop_lat": "Latitude", "stop_lon": "Longitude"})
    _plotly_chart(
        px.density_heatmap(
            chart_data, x="Longitude", y="Latitude", nbinsx=50, nbinsy=50,
            title="GTFS stop coordinate density",
            color_continuous_scale="Tealgrn",
        ),
        width="stretch",
    )
    left, right = st.columns(2)
    with left:
        _plotly_chart(
            px.histogram(chart_data, x="Longitude", nbins=50, title="Longitude coverage"),
            width="stretch",
        )
    with right:
        _plotly_chart(
            px.histogram(chart_data, x="Latitude", nbins=50, title="Latitude coverage"),
            width="stretch",
        )


def _weather_page():
    st.info(
        "Weather is fetched from Open-Meteo: current API conditions and model-based forecast. "
        "This project has no verified historical street-level air-quality dataset."
    )
    if st.button("Refresh Open-Meteo weather", type="primary", key="refresh_weather"):
        get_weather.clear()
        st.rerun()
    try:
        with st.spinner("Fetching Mumbai weather from Open-Meteo…"):
            weather = get_weather()
    except Exception as exc:
        st.error(f"Open-Meteo is unavailable: {exc}")
        st.caption("The transport analytics are independent of the weather API.")
        return
    current = weather.get("current", {})
    units = weather.get("current_units", {})
    fetched = weather.get("_cityflow_fetched_at_utc", "unknown")
    metrics = st.columns(4)
    for column, label, key, unit_key, default_unit in (
        (metrics[0], "Temperature", "temperature_2m", "temperature_2m", "°C"),
        (metrics[1], "Feels like", "apparent_temperature", "apparent_temperature", "°C"),
        (metrics[2], "Precipitation", "precipitation", "precipitation", "mm"),
        (metrics[3], "Wind speed", "wind_speed_10m", "wind_speed_10m", "km/h"),
    ):
        value = current.get(key, "—")
        column.metric(label, f"{value} {units.get(unit_key, default_unit)}")
    st.success("Open-Meteo API connected · current conditions and forecast returned.")
    st.caption(f"API response fetched at {fetched} · forecast timezone: Asia/Kolkata")
    hourly = weather.get("hourly", {})
    times = hourly.get("time", [])
    if times:
        forecast = pd.DataFrame({"time": pd.to_datetime(times)})
        forecast_series = []
        for key, label in (
            ("precipitation", "Precipitation (mm)"),
            ("temperature_2m", "Temperature (°C)"),
            ("precipitation_probability", "Precipitation probability (%)"),
            ("wind_speed_10m", "Wind speed"),
        ):
            values = hourly.get(key)
            if values is not None and len(values) == len(forecast):
                forecast[label] = values
                forecast_series.append(label)
        if not forecast_series:
            st.warning("The weather API returned timestamps but no supported hourly forecast values.")
            return
        selected = st.multiselect(
            "Forecast series",
            forecast_series,
            default=[column for column in ("Precipitation (mm)", "Temperature (°C)") if column in forecast_series],
        )
        if selected:
            _plotly_chart(
                px.line(
                    forecast,
                    x="time",
                    y=selected,
                    title="Open-Meteo hourly forecast",
                    labels={"time": "Local time", "value": "Forecast"},
                ),
                width="stretch",
            )
        else:
            st.caption("Choose at least one forecast series to display the chart.")
    else:
        st.warning("No hourly forecast timestamps were returned by Open-Meteo.")
    st.warning(
        "No traffic, passenger, or observed air-quality measurements are connected. "
        "No mobility forecast is shown because this project has no time-stamped historical outcomes."
    )


def _benchmark(reference):
    st.markdown(
        "This is a measured group-by of the **same GTFS trips.txt** by route. "
        "Both engines include CSV reading, aggregation, and result collection; Spark startup "
        "is reported separately. Three alternating runs reduce order bias."
    )
    feed_paths = tuple(reference["feeds"].get("feed_path", pd.Series(dtype=str)).astype(str))
    trip_paths = [Path(path) / "trips.txt" for path in feed_paths if (Path(path) / "trips.txt").exists()]
    if not trip_paths:
        st.warning("No GTFS trips.txt file is available for benchmarking.")
        return
    if not st.button("Run Pandas vs PySpark benchmark", type="primary"):
        st.caption("The benchmark reads the actual trip table when requested; it is not run automatically.")
        return
    total = len(trip_paths)
    if total != 1:
        st.warning("Run each feed separately for a like-for-like benchmark; multiple feeds are not yet combined here.")
        return
    try:
        with st.spinner("Reading GTFS trips and comparing equivalent route-count aggregations…"):
            result = benchmark_trip_counts(str(trip_paths[0]))
    except Exception as exc:
        st.error(f"Benchmark failed: {exc}")
        return
    pandas_counts = result.pandas_counts
    spark_counts = result.spark_counts
    comparison = pandas_counts.merge(
        spark_counts, on="route_id", suffixes=("_pandas", "_spark"), how="outer"
    ).fillna(0)
    equivalent = (
        result.pandas_input_rows == result.spark_input_rows
        and result.pandas_output_rows == result.spark_output_rows
        and len(comparison) == result.pandas_output_rows
        and (
            comparison["scheduled_trips_pandas"]
            == comparison["scheduled_trips_spark"]
        ).all()
    )
    metrics = st.columns(5)
    metrics[0].metric("Input rows (Pandas)", f"{result.pandas_input_rows:,}")
    metrics[1].metric("Input rows (PySpark)", f"{result.spark_input_rows:,}")
    metrics[2].metric("Output route groups", f"{result.pandas_output_rows:,}")
    metrics[3].metric("Pandas median workload", f"{result.pandas_seconds:.3f} s")
    metrics[4].metric("PySpark median workload", f"{result.spark_seconds:.3f} s")
    st.metric("PySpark startup (separate)", f"{result.spark_startup_seconds:.3f} s")
    if equivalent:
        st.success(
            f"Both workloads processed {result.pandas_input_rows:,} input rows and "
            f"produced matching counts for {result.pandas_output_rows:,} route groups. "
            "Timings are medians of three alternating runs; Spark startup is excluded "
            "from workload time and shown separately."
        )
    else:
        st.error(
            "Pandas and Spark input/output row counts or per-route results differ; "
            "inspect the source feed before interpreting timings."
        )
    _plotly_chart(
        px.bar(
            pd.DataFrame({
                "Engine": ["Pandas", "PySpark"],
                "Median workload seconds": [result.pandas_seconds, result.spark_seconds],
            }),
            x="Engine", y="Median workload seconds",
            title="Median workload time (CSV read + group-by + collection)",
        ),
        width="stretch",
    )
    st.dataframe(comparison.head(100), hide_index=True, width="stretch")
    st.download_button(
        "Download route-count comparison as CSV",
        comparison.to_csv(index=False).encode("utf-8-sig"),
        file_name="cityflow_benchmark_route_counts.csv",
        mime="text/csv",
        key="download_benchmark_csv",
    )


def _data_sources(routes, stops, reference, errors):
    st.markdown(
        "CityFlow separates static schedules, live API conditions, and forecasts. "
        "There are no connected live vehicle, traffic, passenger, or air-quality feeds."
    )
    source_rows = [
        {
            "Source": "Mumbai GTFS",
            "Type": "Static scheduled network",
            "Status": "Available" if not reference["routes"].empty else "Missing",
            "Detail": f"{len(reference['routes']):,} routes; {len(reference['trips']):,} trips; "
                      f"{len(reference['feeds']):,} feed folders",
            "Provenance": "Local extracted GTFS feed; static schedule snapshot",
            "Latest local file": _latest_modified(list(GTFS_ROOT.rglob("*.txt"))) if GTFS_ROOT.exists() else "Not available",
        },
        {
            "Source": "Processed route summary",
            "Type": "Derived Parquet",
            "Status": "Available" if routes is not None else "Missing / unreadable",
            "Detail": f"{len(routes):,} rows" if routes is not None else errors.get("routes", "Not available"),
            "Provenance": "Generated from GTFS by processing/process_gtfs.py",
            "Latest local file": _latest_modified([ROUTES_PATH]),
        },
        {
            "Source": "Processed stop summary",
            "Type": "Derived Parquet",
            "Status": "Available" if stops is not None else "Missing / unreadable",
            "Detail": f"{len(stops):,} rows" if stops is not None else errors.get("stops", "Not available"),
            "Provenance": "Generated from GTFS by processing/process_gtfs.py",
            "Latest local file": _latest_modified([STOPS_PATH]),
        },
        {
            "Source": "Open-Meteo",
            "Type": "Live API conditions + forecast model",
            "Status": "Fetched when Weather page is opened",
            "Detail": "Current conditions and hourly forecast; no historical archive stored",
            "Provenance": "Open-Meteo forecast API · api.open-meteo.com",
            "Latest local file": "API fetch time shown on Weather & Environment page",
        },
        {
            "Source": "OpenStreetMap",
            "Type": "Interactive map tiles",
            "Status": "Loaded by the browser when the map is opened",
            "Detail": "OpenStreetMap © contributors; requires network access for tiles",
            "Provenance": "OpenStreetMap contributors · openstreetmap.org",
            "Latest local file": "Not applicable",
        },
        {
            "Source": "Live vehicle positions",
            "Type": "Real-time transport feed",
            "Status": "Not connected",
            "Detail": "No GTFS-Realtime, GPS, or vehicle-position source is configured",
            "Provenance": "No source configured",
            "Latest local file": "Not available",
        },
        {
            "Source": "Traffic / passenger counts",
            "Type": "Live or observed mobility data",
            "Status": "Not connected",
            "Detail": "The project has no connected traffic, ridership, or passenger-count source",
            "Provenance": "No source configured",
            "Latest local file": "Not available",
        },
        {
            "Source": "Air quality (OpenAQ)",
            "Type": "Environmental observations",
            "Status": "Not connected",
            "Detail": "No OpenAQ credentials or verified Mumbai station data are configured",
            "Provenance": "Optional source listed in config/sources.yaml",
            "Latest local file": "Not available",
        },
    ]
    st.dataframe(
        pd.DataFrame(source_rows).rename(columns={"Latest local file": "Last refreshed / observed"}),
        hide_index=True,
        width="stretch",
    )
    if errors:
        for message in errors.values():
            st.warning(message)
    st.subheader("GTFS validation and coverage")
    if stops is not None:
        valid = _valid_stops(stops)
        total = len(stops)
        st.write(
            f"Valid stop coordinates: **{len(valid):,} / {total:,}** "
            f"({(len(valid) / total * 100) if total else 0:.1f}%); "
            f"missing/invalid: **{total - len(valid):,}**."
        )
        duplicate_stops = (
            int(stops["stop_id"].duplicated().sum()) if "stop_id" in stops.columns else None
        )
        st.caption(
            f"Duplicate stop IDs: {duplicate_stops:,}"
            if duplicate_stops is not None else "Duplicate stop IDs: column unavailable"
        )
    st.subheader("Live-feed readiness")
    st.info(
        "Static GTFS schedules are available for network and timetable analytics. "
        "Live vehicle tracking, traffic, passenger volumes, and measured air quality "
        "are not connected; the dashboard does not simulate these feeds."
    )
    shapes_available = (
        any(path.name.lower() == "shapes.txt" for path in GTFS_ROOT.rglob("shapes.txt"))
        if GTFS_ROOT.exists() else False
    )
    if not shapes_available:
        st.info(
            "No GTFS shapes.txt is available. Map route lines, when selected, are representative "
            "ordered stop sequences inferred from stop_times—not road geometry."
        )
    st.caption(
        f"GTFS reference files last changed: {_latest_modified(list(GTFS_ROOT.rglob('*.txt'))) if GTFS_ROOT.exists() else 'Not available'}"
    )


navigation = {
    "Overview": "◈",
    "Interactive Map": "⌖",
    "Route Analytics": "↗",
    "Geographic Analysis": "▦",
    "Weather & Environment": "☼",
    "Big Data Benchmark": "⏱",
    "Data Sources": "◇",
}
page_descriptions = {
    "Overview": ("Network pulse", "A live view of Mumbai’s static transit network, schedule coverage, and data quality."),
    "Interactive Map": ("Spatial operations", "Explore real GTFS stop locations, route coverage, and stop density."),
    "Route Analytics": ("Service intelligence", "Compare scheduled route supply and inspect route-level GTFS details."),
    "Geographic Analysis": ("Geographic coverage", "Inspect coordinate quality and how stops are distributed across the city."),
    "Weather & Environment": ("Weather conditions", "Current Open-Meteo conditions and the latest forecast for Mumbai."),
    "Big Data Benchmark": ("Processing benchmark", "Compare measured Pandas and PySpark workloads on the same GTFS data."),
    "Data Sources": ("Data observability", "Review provenance, refresh times, source availability, and feed readiness."),
}

with st.sidebar:
    st.markdown(
        '<p class="cityflow-brand"><span>◈</span> CITYFLOW</p>',
        unsafe_allow_html=True,
    )
    st.caption("MUMBAI · URBAN MOBILITY INTELLIGENCE")
    page = st.radio(
        "Navigate",
        tuple(navigation),
        format_func=lambda item: f"{navigation[item]}   {item}",
        label_visibility="collapsed",
        key="cityflow_page",
    )
    st.divider()
    st.toggle("Dark command-center theme", key="cityflow_dark_mode")
    st.divider()
    st.caption("GTFS is a static schedule, not live vehicle tracking.")
    if st.button("Refresh cached data", width="stretch"):
        st.cache_data.clear()
        st.rerun()

eyebrow, page_description = page_descriptions[page]
st.markdown(
    f'<div class="cityflow-hero">'
    f'<div class="cityflow-eyebrow">CITYFLOW / MUMBAI · {eyebrow}</div>'
    f'<h1>{page}<span class="cityflow-pill">STATIC GTFS · LIVE WEATHER</span></h1>'
    f'<p>{page_description}</p></div>',
    unsafe_allow_html=True,
)

load_errors = {}
with st.spinner("Loading processed summaries and GTFS reference data…"):
    routes, route_error = _safe_read(ROUTES_PATH, "Processed route summary")
    stops, stop_error = _safe_read(STOPS_PATH, "Processed stop summary")
    if route_error:
        load_errors["routes"] = route_error
    if stop_error:
        load_errors["stops"] = stop_error
    try:
        reference = load_gtfs_reference(str(GTFS_ROOT))
    except Exception as exc:
        load_errors["reference"] = f"Could not read GTFS reference tables: {exc}"
        reference = {
            "feeds": pd.DataFrame(),
            "agencies": pd.DataFrame(),
            "routes": pd.DataFrame(),
            "trips": pd.DataFrame(),
            "calendars": pd.DataFrame(),
        }
agency_names = _agency_name_map(reference)

if page == "Overview":
    _overview(routes, stops, reference)
elif page == "Interactive Map":
    if stops is None:
        st.warning(load_errors.get("stops", "Processed stops are not available."))
    else:
        _render_map(stops, reference, agency_names)
elif page == "Route Analytics":
    _route_analytics(routes, stops, reference, agency_names)
elif page == "Geographic Analysis":
    _geographic_analysis(stops)
elif page == "Weather & Environment":
    _weather_page()
elif page == "Big Data Benchmark":
    _benchmark(reference)
elif page == "Data Sources":
    _data_sources(routes, stops, reference, load_errors)

st.divider()
st.caption(
    "Static schedules and geographic coverage are not observed ridership, live traffic, "
    "or current vehicle positions. Verify source licensing and feed dates before publication."
)
