"""Cached loaders and measured workloads for the CityFlow dashboard."""
from pathlib import Path
from dataclasses import dataclass
from statistics import median
import tempfile
import time

import pandas as pd
import streamlit as st


@dataclass(frozen=True)
class TripCountBenchmark:
    spark_startup_seconds: float
    pandas_seconds: float
    spark_seconds: float
    pandas_input_rows: int
    spark_input_rows: int
    pandas_output_rows: int
    spark_output_rows: int
    pandas_counts: pd.DataFrame
    spark_counts: pd.DataFrame


@st.cache_data(ttl=600, show_spinner=False)
def read_parquet(path: str) -> pd.DataFrame:
    return pd.read_parquet(path)


def _read_optional_csv(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False, **kwargs)


@st.cache_data(ttl=600, show_spinner=False)
def load_gtfs_reference(root: str) -> dict[str, pd.DataFrame]:
    root_path = Path(root)
    feeds = sorted({
        routes.parent for routes in root_path.rglob("routes.txt")
        if (routes.parent / "stops.txt").exists()
    })
    result = {
        "feeds": pd.DataFrame({"feed_path": [str(path) for path in feeds]}),
        "agencies": [],
        "routes": [],
        "trips": [],
        "calendars": [],
    }
    for feed in feeds:
        for key, filename, columns in (
            ("agencies", "agency.txt", None),
            ("routes", "routes.txt", None),
            ("trips", "trips.txt", ["route_id", "trip_id"]),
            ("calendars", "calendar.txt", None),
        ):
            frame = _read_optional_csv(feed / filename, usecols=columns)
            if not frame.empty:
                frame["feed_folder"] = feed.name
                frame["feed_path"] = str(feed)
                result[key].append(frame)
    for key in ("agencies", "routes", "trips", "calendars"):
        frames = result[key]
        result[key] = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return result


@st.cache_data(ttl=600, show_spinner=False)
def load_route_stop_details(
    feed_paths: tuple[str, ...],
    route_ids: tuple[str, ...],
    path_route_id: str | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    selected_routes = set(route_ids)
    selected_stop_ids: set[str] = set()
    representative_path: list[str] = []
    candidate_trip: str | None = None

    for feed_path in feed_paths:
        feed = Path(feed_path)
        trips_path = feed / "trips.txt"
        stop_times_path = feed / "stop_times.txt"
        if not trips_path.exists() or not stop_times_path.exists():
            continue
        trips = pd.read_csv(
            trips_path,
            usecols=["route_id", "trip_id"],
            dtype={"route_id": "string", "trip_id": "string"},
            low_memory=False,
        )
        trips = trips[trips["route_id"].isin(selected_routes)]
        if trips.empty:
            continue
        trip_routes = trips.set_index("trip_id")["route_id"].to_dict()
        for chunk in pd.read_csv(
            stop_times_path,
            usecols=["trip_id", "stop_id", "stop_sequence"],
            dtype={"trip_id": "string", "stop_id": "string"},
            chunksize=250_000,
            low_memory=False,
        ):
            matched = chunk[chunk["trip_id"].isin(trip_routes)].copy()
            if matched.empty:
                continue
            matched["route_id"] = matched["trip_id"].map(trip_routes)
            selected_stop_ids.update(matched["stop_id"].dropna().astype(str))
            if path_route_id:
                path_rows = matched[matched["route_id"] == path_route_id]
                if not path_rows.empty:
                    if candidate_trip is None:
                        candidate_trip = str(path_rows.iloc[0]["trip_id"])
                    candidate_rows = path_rows[path_rows["trip_id"] == candidate_trip]
                    representative_path.extend(
                        candidate_rows.sort_values("stop_sequence")["stop_id"]
                        .dropna().astype(str).tolist()
                    )

    return tuple(sorted(selected_stop_ids)), tuple(representative_path)


@st.cache_data(ttl=600, show_spinner=False)
def load_route_stop_counts(
    feed_paths: tuple[str, ...],
) -> pd.DataFrame:
    pairs: set[tuple[str, str]] = set()
    for feed_path in feed_paths:
        feed = Path(feed_path)
        trips_path = feed / "trips.txt"
        stop_times_path = feed / "stop_times.txt"
        if not trips_path.exists() or not stop_times_path.exists():
            continue
        trips = pd.read_csv(
            trips_path,
            usecols=["route_id", "trip_id"],
            dtype={"route_id": "string", "trip_id": "string"},
            low_memory=False,
        )
        trip_routes = trips.set_index("trip_id")["route_id"].to_dict()
        for chunk in pd.read_csv(
            stop_times_path,
            usecols=["trip_id", "stop_id"],
            dtype={"trip_id": "string", "stop_id": "string"},
            chunksize=250_000,
            low_memory=False,
        ):
            chunk["route_id"] = chunk["trip_id"].map(trip_routes)
            matched = chunk.dropna(subset=["route_id", "stop_id"])
            pairs.update(zip(matched["route_id"], matched["stop_id"]))
    if not pairs:
        return pd.DataFrame(columns=["route_id", "stops_on_route"])
    counts = pd.Series([route_id for route_id, _ in pairs]).value_counts()
    return counts.rename_axis("route_id").reset_index(name="stops_on_route")


def benchmark_trip_counts(
    trips_path: str,
) -> TripCountBenchmark:
    """Compare repeated, equivalent CSV route-count workloads in Pandas and Spark."""
    path = Path(trips_path)
    if not path.is_file():
        raise FileNotFoundError(f"GTFS trips file does not exist: {path}")

    def run_pandas():
        started = time.perf_counter()
        trips = pd.read_csv(
            path, usecols=["route_id"], dtype={"route_id": "string"}, low_memory=False
        )
        counts = trips.groupby("route_id", dropna=False).size()
        result = counts.rename("scheduled_trips").reset_index()
        result["route_id"] = result["route_id"].fillna("<MISSING_ROUTE_ID>")
        return time.perf_counter() - started, len(trips), result

    with tempfile.TemporaryDirectory(prefix="cityflow-benchmark-") as scratch:
        from pyspark.sql import SparkSession
        from pyspark.sql.types import StringType, StructField, StructType

        schema = StructType([StructField("route_id", StringType(), True)])
        startup_started = time.perf_counter()
        spark = (
            SparkSession.builder
            .appName("CityFlow-GTFS-Benchmark")
            .master("local[*]")
            .config("spark.local.dir", scratch)
            .config("spark.sql.shuffle.partitions", "4")
            .getOrCreate()
        )
        spark_startup_seconds = time.perf_counter() - startup_started
        spark.sparkContext.setLogLevel("ERROR")
        pandas_times = []
        spark_times = []
        pandas_input_rows = 0
        spark_input_rows = 0
        pandas_counts = pd.DataFrame()
        spark_counts = pd.DataFrame()

        def run_spark():
            started = time.perf_counter()
            rows = (
                spark.read.option("header", True).schema(schema).csv(str(path))
                .groupBy("route_id").count()
                .withColumnRenamed("count", "scheduled_trips")
                .collect()
            )
            result = pd.DataFrame([row.asDict() for row in rows])
            if result.empty:
                result = pd.DataFrame(columns=["route_id", "scheduled_trips"])
            result["route_id"] = result["route_id"].fillna("<MISSING_ROUTE_ID>")
            input_rows = int(result["scheduled_trips"].sum())
            return time.perf_counter() - started, input_rows, result

        try:
            for iteration in range(3):
                if iteration % 2 == 0:
                    pandas_elapsed, pandas_input_rows, pandas_counts = run_pandas()
                    spark_elapsed, spark_input_rows, spark_counts = run_spark()
                else:
                    spark_elapsed, spark_input_rows, spark_counts = run_spark()
                    pandas_elapsed, pandas_input_rows, pandas_counts = run_pandas()
                pandas_times.append(pandas_elapsed)
                spark_times.append(spark_elapsed)
        finally:
            spark.stop()

    pandas_counts = pandas_counts.sort_values("route_id").reset_index(drop=True)
    spark_counts = spark_counts.sort_values("route_id").reset_index(drop=True)
    for counts in (pandas_counts, spark_counts):
        counts["route_id"] = counts["route_id"].astype("string")
        counts["scheduled_trips"] = pd.to_numeric(
            counts["scheduled_trips"], errors="raise"
        ).astype("int64")
    return TripCountBenchmark(
        spark_startup_seconds=spark_startup_seconds,
        pandas_seconds=median(pandas_times),
        spark_seconds=median(spark_times),
        pandas_input_rows=pandas_input_rows,
        spark_input_rows=spark_input_rows,
        pandas_output_rows=len(pandas_counts),
        spark_output_rows=len(spark_counts),
        pandas_counts=pandas_counts,
        spark_counts=spark_counts,
    )
