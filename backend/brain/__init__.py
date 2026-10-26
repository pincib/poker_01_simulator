"""Poker analysis, opponent decision, and coaching modules."""

from backend.brain.draws import DrawAnalysis, DrawDetector, StraightDrawType, analyze_draws
from backend.brain.ai_agent import AIDecision, OpponentAI, OpponentProfile
from backend.brain.board_texture import BoardTexture, BoardTextureClassifier, SuitPattern, classify_board
from backend.brain.bet_sizing import BetSizer, SizingOption, SizingRecommendation, recommend_bet_size
from backend.brain.coach import (
    BetPurpose,
    BetPurposeResult,
    CallAssessment,
    CoachService,
    CoachSnapshot,
    DecisionNote,
    HandReview,
    LeakFlag,
    SessionTracker,
    WeeklyLeakReport,
)
from backend.brain.equity import EquityCalculator, EquityResult, calculate_equity
from backend.brain.plo_draws import OmahaWrapAnalysis, OmahaWrapDetector, detect_omaha_wrap
from backend.brain.pot_odds import PotOdds, PotOddsCalculator, calculate_pot_odds
from backend.brain.ranges import OPENING_RANGES, PreflopRange, get_opening_range, starting_hand_class
from backend.brain.spr import SPRCalculator, StackToPotRatio, calculate_spr

__all__ = [
    "DrawAnalysis",
    "DrawDetector",
    "StraightDrawType",
    "analyze_draws",
    "AIDecision",
    "OpponentAI",
    "OpponentProfile",
    "BoardTexture",
    "BoardTextureClassifier",
    "SuitPattern",
    "classify_board",
    "BetSizer",
    "SizingOption",
    "SizingRecommendation",
    "recommend_bet_size",
    "BetPurpose",
    "BetPurposeResult",
    "CallAssessment",
    "CoachService",
    "CoachSnapshot",
    "DecisionNote",
    "HandReview",
    "LeakFlag",
    "SessionTracker",
    "WeeklyLeakReport",
    "EquityCalculator",
    "EquityResult",
    "calculate_equity",
    "OmahaWrapAnalysis",
    "OmahaWrapDetector",
    "detect_omaha_wrap",
    "PotOdds",
    "PotOddsCalculator",
    "calculate_pot_odds",
    "SPRCalculator",
    "StackToPotRatio",
    "calculate_spr",
    "OPENING_RANGES",
    "PreflopRange",
    "get_opening_range",
    "starting_hand_class",
]
