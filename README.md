# bucharest-ilfov-education-poc

> **POC** for gathering, scoring, and comparing schools, extra-curricular activities, and parent reviews for the **Bucharest-Ilfov** region using open data and Python.

---

## Overview

This proof-of-concept pulls school data from Romanian open-data sources, normalises it into a unified `School` model, applies a configurable scoring formula, and outputs a ranked comparison table. The goal is to help parents in Bucharest-Ilfov make informed school choices based on academic performance, parent satisfaction, and extra-curricular richness.

---

## Repository Structure

```
bucharest-ilfov-education-poc/
├── configs/
│   └── bucharest_ilfov.json   # Data sources, filters & scoring weights
├── loaders/
│   └── insse_loader.py        # Loads & normalises INSSE education CSV
├── models/
│   └── school.py              # School dataclass + scoring helpers
├── orchestrator.py            # Main entry point – wires everything together
├── requirements.txt           # Python dependencies
├── .gitignore
├── LICENSE
└── README.md
```

---

## Data Sources

| Name | Type | Description |
|---|---|---|
| `insse_education_stats` | open_data_csv | INSSE pre-university education statistics (enrolment by year) |
| `international_schools_directory` | open_data_html | International schools directory with fees, ECAs, reviews |
| `google_places` | api | Google Places ratings & reviews |
| `siiir_open_data` | open_data_csv | Official SIIIR school registry (codes, addresses, types) |

All sources are configured in `configs/bucharest_ilfov.json`.

---

## Scoring Formula

Each school receives a **match score (0–100)** computed as:

```
match_score = (academic_index × 0.40)
            + (parent_satisfaction × 0.35)
            + (eca_richness × 0.25)
```

Weights are fully configurable in `configs/bucharest_ilfov.json` under `scoring_weights`.

---

## Quickstart

### 1. Clone & install

```bash
git clone https://github.com/thebabydatascientist/bucharest-ilfov-education-poc.git
cd bucharest-ilfov-education-poc
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run

```bash
python orchestrator.py
```

This will:
1. Load `configs/bucharest_ilfov.json`
2. Fetch & parse the INSSE education CSV
3. Filter to Bucharest + Ilfov county schools
4. Score and rank all schools
5. Print a top-20 ranked table to stdout

### 3. Expected output

```
========================================================================
  Bucharest-Ilfov Schools - Top 20 by Match Score
========================================================================
#    School                                         City               Score
------------------------------------------------------------------------
1    Scoala Gimnaziala Nr. 1                        Sector 1            72.5
2    Liceul Teoretic Ion Barbu                      Sector 2            68.3
...
========================================================================
Total schools loaded: 842
```

---

## Configuration

Edit `configs/bucharest_ilfov.json` to:
- Add or remove **data sources**
- Adjust **scoring weights** (`academic_performance`, `parent_satisfaction`, `eca_richness`)
- Change **filters** (counties, school types, age ranges)

---

## Roadmap

- [ ] `loaders/siiir_loader.py` — official SIIIR school registry
- [ ] `loaders/google_places_loader.py` — Google Places ratings
- [ ] `loaders/international_schools_loader.py` — international schools scraper
- [ ] Export results to CSV / JSON
- [ ] Jupyter notebook for exploratory analysis
- [ ] Interactive map (Folium / Leaflet)

---

## License

MIT — see [LICENSE](LICENSE).
