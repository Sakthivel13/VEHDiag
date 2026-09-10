"""Machine Learning System."""
from core.core import SignalCandidate


class DatasetBuilder:
    @staticmethod
    def build_training_data(frames):
        return []


class DBCDataLoader:
    @staticmethod
    def load_dbc(path: str):
        print(f"Loading DBC from {path} (scaffold)")
        return {}


class SignalClassifier:
    def predict(self, features):
        return []


class SemanticModel:
    def infer(self, features):
        return []


class ScalingPredictor:
    def predict_scale(self, values):
        return 1.0


class DBSCANClusterer:
    def cluster(self, vectors, **kwargs):
        return []


class SpectralClusterer:
    def cluster(self, vectors, **kwargs):
        return []


class ModelTrainer:
    def train(self, model, data):
        print("Training model (scaffold)")


class SemanticInference:
    def infer(self, model, data):
        return []


class SignalTypePredictor:
    def predict_type(self, candidate: SignalCandidate):
        return "unknown"


class MLEngine:
    def __init__(self, config):
        self.config = config
        self.classifier = SignalClassifier()
        self.semantic_model = SemanticModel()
        self.scaling_predictor = ScalingPredictor()