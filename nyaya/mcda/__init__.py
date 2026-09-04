"""Multi-criteria decision analysis for SDLC selection.

The mathematics decides; the language model only explains. A recommendation an
architect cannot re-derive is one they cannot challenge, and a recommendation
nobody can challenge should not be acted on.
"""

from nyaya.mcda.ahp import AHPResult, InconsistentJudgementsError, derive_weights
from nyaya.mcda.sdlc import FACTORS, PROFILES, SDLCRecommendation, default_factors, recommend
from nyaya.mcda.topsis import Alternative, Ranking, TOPSISResult, rank

__all__ = [
    "FACTORS",
    "PROFILES",
    "AHPResult",
    "Alternative",
    "InconsistentJudgementsError",
    "Ranking",
    "SDLCRecommendation",
    "TOPSISResult",
    "default_factors",
    "derive_weights",
    "rank",
    "recommend",
]
