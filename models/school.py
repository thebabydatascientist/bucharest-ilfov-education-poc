# models/school.py
# Data model for schools and related entities in Bucharest-Ilfov POC

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

@dataclass
class ExamResult:
    """Stores one exam result for a school, including diff vs benchmark."""
    exam_type: str              # e.g. "Cambridge Checkpoint", "IB Diploma", "Evaluare Nationala"
    year: int
    school_average: float       # numeric score (context-dependent: points, grade 1-10, etc.)
    benchmark_average: float    # international / national reference average
    pass_rate: Optional[float] = None   # 0.0 - 1.0
    score_diff: float = field(init=False)
    above_benchmark: bool = field(init=False)
    notes: Optional[str] = None

    def __post_init__(self):
        self.score_diff = round(self.school_average - self.benchmark_average, 4)
        self.above_benchmark = self.score_diff > 0


@dataclass
class ExternalRating:
    """Rating from a third-party review platform."""
    source: str                 # e.g. "international-schools-database", "desprecopii"
    rating: float
    scale_max: float = 10.0
    review_count: int = 0
    url: Optional[str] = None


@dataclass
class Reviews:
    """Aggregated review data from Google and external platforms."""
    google_rating: Optional[float] = None
    google_review_count: int = 0
    google_place_id: Optional[str] = None
    external_ratings: List[ExternalRating] = field(default_factory=list)
    sentiment_summary: Optional[str] = None    # "very positive" | "positive" | "mixed" | "negative"

    @property
    def combined_rating(self) -> Optional[float]:
        """Simple average across all available ratings."""
        scores = []
        if self.google_rating is not None:
            scores.append(self.google_rating / 5.0 * 10)  # normalise to 0-10
        for ext in self.external_ratings:
            scores.append(ext.rating / ext.scale_max * 10)
        return round(sum(scores) / len(scores), 2) if scores else None


@dataclass
class ECA:
    """Extra-curricular activity offered by a school."""
    name: str
    category: str               # "sports" | "arts" | "music" | "languages" | "stem" | "other"
    age_range: Optional[str] = None
    frequency: Optional[str] = None    # e.g. "weekly", "twice a week"
    included_in_fees: Optional[bool] = None


@dataclass
class ECAs:
    """Collection of ECAs and summary stats."""
    items: List[ECA] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.items)

    @property
    def categories(self) -> List[str]:
        return sorted(set(e.category for e in self.items))


@dataclass
class Historical:
    """Historical enrolment and founding data."""
    year_opened: Optional[int] = None
    enrolment_by_year: Dict[int, int] = field(default_factory=dict)  # {2021: 250, 2022: 270}

    @property
    def latest_enrolment(self) -> Optional[int]:
        if not self.enrolment_by_year:
            return None
        return self.enrolment_by_year[max(self.enrolment_by_year)]

    @property
    def enrolment_trend(self) -> Optional[str]:
        """Returns 'growing', 'stable', or 'declining' based on last 2 data points."""
        if len(self.enrolment_by_year) < 2:
            return None
        years = sorted(self.enrolment_by_year)
        delta = self.enrolment_by_year[years[-1]] - self.enrolment_by_year[years[-2]]
        if delta > 10:
            return "growing"
        elif delta < -10:
            return "declining"
        return "stable"


@dataclass
class Location:
    """Geographic and administrative location."""
    city: str                               # "Bucharest" or locality name
    sector_or_locality: str                 # "Sector 1" ... "Sector 6" or Ilfov commune
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    google_maps_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Main School model
# ---------------------------------------------------------------------------

@dataclass
class School:
    """Complete school record for Bucharest-Ilfov POC."""

    # Identity
    school_id: str
    name: str
    type: str                       # "public" | "private" | "international"
    location: Location

    # Curriculum
    age_ranges: List[str]           # e.g. ["6-11", "11-15"]
    programmes: List[str]           # e.g. ["Romanian curriculum", "Cambridge", "IB"]
    language_of_instruction: List[str] = field(default_factory=list)

    # Data layers
    historical: Historical = field(default_factory=Historical)
    exams: List[ExamResult] = field(default_factory=list)
    reviews: Reviews = field(default_factory=Reviews)
    ecas: ECAs = field(default_factory=ECAs)

    # Contact & trust signals
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    has_parent_guide: bool = False
    has_transparent_pricing: bool = False
    accreditations: List[str] = field(default_factory=list)

    # Metadata
    data_sources: List[str] = field(default_factory=list)   # which loaders populated this
    meta_last_updated: datetime = field(default_factory=datetime.utcnow)

    # ---------------------------------------------------------------------------
    # Scoring helpers
    # ---------------------------------------------------------------------------

    @property
    def academic_index(self) -> Optional[float]:
        """
        Normalised 0-100 academic performance index.
        Uses average score_diff across all available exam results.
        Returns None if no exam data.
        """
        if not self.exams:
            return None
        avg_diff = sum(e.score_diff for e in self.exams) / len(self.exams)
        # Scale: clamp to [-20, +20] range then map to [0, 100]
        clamped = max(-20.0, min(20.0, avg_diff))
        return round((clamped + 20) / 40 * 100, 1)

    @property
    def trust_score(self) -> float:
        """
        Simple 0-5 trust score based on verifiable signals.
        """
        score = 0.0
        if self.website:
            score += 1.0
        if self.phone or self.email:
            score += 1.0
        if self.has_parent_guide:
            score += 1.0
        if self.has_transparent_pricing:
            score += 1.0
        if self.accreditations:
            score += 1.0
        return score

    @property
    def match_score(self) -> Optional[float]:
        """
        Composite 0-100 match score using default weights from config.
        Weights: academic 40%, parent satisfaction 35%, ECA richness 25%.
        """
        weights = {"academic": 0.40, "satisfaction": 0.35, "eca": 0.25}

        academic = self.academic_index or 50.0   # neutral fallback
        satisfaction = ((self.reviews.combined_rating or 5.0) / 10.0) * 100
        eca = min(self.ecas.count / 10.0, 1.0) * 100   # cap at 10 ECAs = 100

        return round(
            academic * weights["academic"]
            + satisfaction * weights["satisfaction"]
            + eca * weights["eca"],
            1,
        )


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def make_school_id(name: str, city: str) -> str:
    """Generate a deterministic-ish school ID."""
    slug = f"{city.lower().replace(' ', '-')}-{name.lower().replace(' ', '-')}"
    return f"{slug}-{uuid4().hex[:6]}"
