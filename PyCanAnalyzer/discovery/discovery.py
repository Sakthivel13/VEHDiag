"""Automatic Signal Discovery."""
from typing import List
from core.core import CANFrame, SignalCandidate


class DiscoveryEngine:
    def __init__(self, config):
        self.config = config

    def run(self, frames: List[CANFrame]) -> List[SignalCandidate]:
        # scaffold: return empty list
        return []


class FrameGrouping:
    @staticmethod
    def group_by_id(frames):
        groups = {}
        for f in frames:
            groups.setdefault(f.can_id, []).append(f)
        return groups


class BitExtractor:
    @staticmethod
    def extract_bits(frames):
        return []


class EntropyCalculator:
    @staticmethod
    def entropy(bit_series):
        return 0.0


class VarianceCalculator:
    @staticmethod
    def variance(values):
        return 0.0


class ToggleRateCalculator:
    @staticmethod
    def toggle_rate(bit_series):
        return 0.0


class CorrelationMatrix:
    @staticmethod
    def compute(vectors):
        return []


class BitClusterer:
    @staticmethod
    def cluster(feature_matrix):
        return []


class SignalBoundaryDetector:
    @staticmethod
    def detect_boundaries(bit_series):
        return []


class EndiannessDetector:
    @staticmethod
    def detect_endianness(bit_series):
        return "little"


class SignalDecoder:
    @staticmethod
    def decode_signal(bit_series, start_bit, length, endianness):
        return 0


class ScalingEstimator:
    @staticmethod
    def estimate_scale(values):
        return 1.0


class SignalScoring:
    @staticmethod
    def score(candidate):
        return getattr(candidate, "score", 0.0)


class CandidateRanker:
    @staticmethod
    def rank(candidates):
        return sorted(candidates, key=lambda c: c.score, reverse=True)