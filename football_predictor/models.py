"""
Models module.
Contains the Dixon-Coles Poisson model and XGBoost ensemble wrapper.
"""

class DixonColesModel:
    def __init__(self):
        pass

    def fit(self, matches):
        pass

    def predict(self, home_team, away_team):
        """Returns Win/Draw/Loss probabilities and expected goals."""
        pass

class XGBoostPredictor:
    def __init__(self):
        pass

    def train(self, features, targets):
        pass

    def predict_match(self, home_team_features, away_team_features):
        """Returns Win/Draw/Loss probabilities based on engineered features."""
        pass
