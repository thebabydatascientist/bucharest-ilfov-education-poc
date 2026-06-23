# orchestrator.py
# Main entry point for the Bucharest-Ilfov Education POC.
# Loads config, runs all data loaders, scores schools, and prints a ranked report.

import json
import logging
from pathlib import Path
from typing import List

from loaders.insse_loader import load_insse_schools
from models.school import School

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).parent / "configs" / "bucharest_ilfov.json"


def load_config(path: Path = CONFIG_PATH) -> dict:
    logger.info(f"Loading config from {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def get_ds_config(config: dict, name: str) -> dict:
    """Return a single data-source block by name."""
    return next(
        ds for ds in config["data_sources"] if ds["name"] == name
    )


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_schools(
    schools: List[School],
    weights: dict,
) -> List[School]:
    """
    Compute match_score for every school using config scoring_weights.
    Weights keys: academic_performance, parent_satisfaction, eca_richness.
    """
    w_acad = weights.get("academic_performance", 0.40)
    w_sat  = weights.get("parent_satisfaction",  0.35)
    w_eca  = weights.get("eca_richness",          0.25)

    for school in schools:
        acad = school.academic_index()                          # 0-100
        sat  = (school.average_rating() / 5.0) * 100 if school.ratings else 0.0
        eca  = min(len(school.extra_curricular) * 10, 100)

        school.computed_match_score = round(
            acad * w_acad + sat * w_sat + eca * w_eca, 2
        )

    return sorted(schools, key=lambda s: s.computed_match_score, reverse=True)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(schools: List[School], top_n: int = 20) -> None:
    print("\n" + "=" * 72)
    print(f"  Bucharest-Ilfov Schools - Top {top_n} by Match Score")
    print("=" * 72)
    print(f"{'#':<4} {'School':<45} {'City':<18} {'Score':>6}")
    print("-" * 72)
    for rank, school in enumerate(schools[:top_n], start=1):
        score = getattr(school, "computed_match_score", 0.0)
        print(
            f"{rank:<4} {school.name[:44]:<45} "
            f"{school.location.city[:17]:<18} {score:>6.1f}"
        )
    print("=" * 72)
    print(f"Total schools loaded: {len(schools)}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> List[School]:
    config = load_config()
    scoring_weights = config.get("scoring_weights", {})

    all_schools: List[School] = []

    # --- INSSE open-data CSV ---
    try:
        insse_cfg = get_ds_config(config, "insse_education_stats")
        insse_schools = load_insse_schools(insse_cfg)
        logger.info(f"INSSE loader: {len(insse_schools)} schools")
        all_schools.extend(insse_schools)
    except Exception as exc:
        logger.warning(f"INSSE loader failed: {exc}")

    if not all_schools:
        logger.error("No schools loaded. Check data sources and config.")
        return []

    ranked = score_schools(all_schools, scoring_weights)
    print_report(ranked)
    return ranked


if __name__ == "__main__":
    run()
