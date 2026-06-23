# loaders/insse_loader.py
# Loads school data from INSSE (Romanian National Statistics Institute) open data
# and data.gov.ro SIIIR registry for Bucharest-Ilfov region.

import logging
from pathlib import Path
from typing import List, Optional

import pandas as pd
import requests

from models.school import Historical, Location, School, make_school_id

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BUCHAREST_ILFOV_COUNTIES = {"bucuresti", "ilfov", "b"}

# Known INSSE/data.gov.ro open data endpoints for education stats
INSSE_CSV_URLS = [
    # Pre-university education statistics (update URL when INSSE publishes new data)
    "https://insse.ro/cms/files/statistici/comunicate/com_anuale/invatamant/invatamant_r.htm",
]

SIIIR_DATA_GOV_URL = "https://data.gov.ro/dataset/siiir"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_county(raw: str) -> str:
    return str(raw).lower().strip()


def _is_bucharest_ilfov(county: str) -> bool:
    return _normalise_county(county) in BUCHAREST_ILFOV_COUNTIES


def _safe_int(val) -> Optional[int]:
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Core loaders
# ---------------------------------------------------------------------------

def load_from_csv(filepath: str, fields_mapping: dict) -> pd.DataFrame:
    """
    Load a local or remote CSV file and apply field mapping.
    Returns a normalised DataFrame with standard column names.

    Args:
        filepath: local path or HTTP URL to the CSV file.
        fields_mapping: dict mapping standard names -> raw CSV column names.

    Returns:
        pd.DataFrame with normalised columns.
    """
    logger.info(f"Loading CSV from: {filepath}")

    if filepath.startswith("http"):
        resp = requests.get(filepath, timeout=30)
        resp.raise_for_status()
        from io import StringIO
        df_raw = pd.read_csv(StringIO(resp.text), sep=";", encoding="utf-8", low_memory=False)
    else:
        df_raw = pd.read_csv(filepath, sep=";", encoding="utf-8", low_memory=False)

    logger.info(f"Loaded {len(df_raw)} rows, columns: {list(df_raw.columns)}")

    df = pd.DataFrame()
    for standard_name, raw_col in fields_mapping.items():
        if raw_col in df_raw.columns:
            df[standard_name] = df_raw[raw_col]
        else:
            logger.warning(f"Column '{raw_col}' not found in CSV; skipping '{standard_name}'")
            df[standard_name] = None

    return df


def filter_bucharest_ilfov(df: pd.DataFrame, county_col: str = "county") -> pd.DataFrame:
    """
    Filter DataFrame to only Bucharest-Ilfov rows.
    Handles both 'Bucuresti' and 'Ilfov' county spellings.
    """
    if county_col not in df.columns:
        logger.warning(f"County column '{county_col}' not found; returning unfiltered.")
        return df
    mask = df[county_col].apply(lambda x: _is_bucharest_ilfov(str(x)))
    filtered = df[mask].copy()
    logger.info(f"Filtered to {len(filtered)} Bucharest-Ilfov rows from {len(df)} total")
    return filtered


def build_schools_from_insse(df: pd.DataFrame) -> List[School]:
    """
    Convert a normalised INSSE/SIIIR DataFrame into a list of School objects.

    Expected columns after field mapping:
        school_name, school_code, city, sector_or_locality,
        enrolment_2021, enrolment_2022, enrolment_2023 (optional)
    """
    schools: List[School] = []

    for _, row in df.iterrows():
        name = str(row.get("school_name", "")).strip()
        if not name:
            continue

        city = str(row.get("city", "Bucharest")).strip()
        sector = str(row.get("sector_or_locality", "")).strip()

        location = Location(
            city=city,
            sector_or_locality=sector,
            address=str(row.get("address", "")).strip() or None,
        )

        # Build enrolment history from available year columns
        enrolment_by_year = {}
        for year in [2021, 2022, 2023]:
            col = f"enrolment_{year}"
            val = _safe_int(row.get(col))
            if val is not None:
                enrolment_by_year[year] = val

        historical = Historical(enrolment_by_year=enrolment_by_year)

        school_type = str(row.get("school_type", "public")).lower()
        if "privat" in school_type or "particular" in school_type:
            school_type = "private"
        elif "international" in school_type:
            school_type = "international"
        else:
            school_type = "public"

        school = School(
            school_id=make_school_id(name, city),
            name=name,
            type=school_type,
            location=location,
            age_ranges=["6-11"],
            programmes=["Romanian curriculum"],
            historical=historical,
            data_sources=["insse_open_data"],
        )
        schools.append(school)

    logger.info(f"Built {len(schools)} School objects from INSSE data")
    return schools


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def load_insse_schools(ds_config: dict) -> List[School]:
    """
    Main entry point called by the orchestrator.

    Args:
        ds_config: DataSourceConfig dict with 'url' and 'fields_mapping' keys.

    Returns:
        List[School] for Bucharest-Ilfov.
    """
    url = ds_config.get("url", "")
    fields_mapping = ds_config.get("fields_mapping", {})

    df = load_from_csv(url, fields_mapping)
    df = filter_bucharest_ilfov(df, county_col="county")
    return build_schools_from_insse(df)


# ---------------------------------------------------------------------------
# CLI for quick testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import json

    config_path = Path(__file__).parent.parent / "configs" / "bucharest_ilfov.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    insse_cfg = next(
        ds for ds in config["data_sources"] if ds["name"] == "insse_education_stats"
    )

    schools = load_insse_schools(insse_cfg)
    print(f"Loaded {len(schools)} schools")
    if schools:
        s = schools[0]
        print(f"Sample: {s.name} | {s.type} | {s.location.city} | enrolment: {s.historical.latest_enrolment}")
