import os
import numpy as np
from typing import Dict, Any, List, Optional
try:
    from sklearn.ensemble import IsolationForest
    HAS_SKLEARN_ISO = True
except Exception:
    IsolationForest = None
    HAS_SKLEARN_ISO = False

class RoutineAnomalyDetector:
    """
    Routine Anomaly Detector:
    Uses scikit-learn Isolation Forest to detect multidimensional routine deviations.
    Computes a normalized Routine Change Score based on weighted deviations.
    Strictly engineering thresholds — never a clinical or medical diagnosis.
    """

    def __init__(self):
        # Configure single-thread joblib for predictable execution
        os.environ['LOKY_MAX_CPU_COUNT'] = '1'
        if HAS_SKLEARN_ISO and IsolationForest is not None:
            try:
                self.model = IsolationForest(
                    n_estimators=50,
                    contamination=0.10,
                    random_state=42,
                    n_jobs=1
                )
            except Exception:
                self.model = None
        else:
            self.model = None
        self._is_fitted = False

    def _generate_synthetic_baseline_distribution(
        self,
        base_vector: List[float],
        n_samples: int = 40
    ) -> np.ndarray:
        """
        Creates a Gaussian distribution of normal day-to-day routine variance
        around the parent's individual baseline to train the personal Isolation Forest.
        """
        rng = np.random.RandomState(42)
        # Small daily perturbations representing healthy variance
        noise = rng.normal(loc=0.0, scale=0.08, size=(n_samples, len(base_vector)))
        samples = np.clip(np.array(base_vector) + noise, 0.0, 1.0)
        return samples

    def evaluate_routine(
        self,
        checkin_delay_mins: float,
        med_delay_mins: float,
        activity_ratio: float,      # 1.0 = normal, 0.5 = 50% below baseline
        sleep_hours: float,         # e.g. 7.5 normal, 4.0 abnormal
        hydration_liters: float,    # e.g. 1.6 normal, 0.6 abnormal
        interaction_count: int,     # touchpoints this week
        baseline: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculates Routine Change Score and fits/evaluates Isolation Forest.
        """
        # 1. Compute Individual Normalized Deviations [0.0 to 1.0]
        # Check-in delay: 0 mins = 0.0, 120 mins late = 1.0
        checkin_dev = min(max(checkin_delay_mins / 120.0, 0.0), 1.0)

        # Medication delay: 0 mins = 0.0, 120 mins late = 1.0
        med_dev = min(max(med_delay_mins / 120.0, 0.0), 1.0)

        # Activity deviation: 1.0 normal = 0.0 deviation, 0.5 = 0.5 deviation, 0.0 = 1.0 deviation
        activity_dev = min(max(1.0 - activity_ratio, 0.0), 1.0)

        # Sleep deviation: baseline 7.5 hours. < 5 hours or > 10 hours represents deviation
        baseline_sleep = baseline.get("expected_sleep_hours", 7.5)
        sleep_diff = abs(baseline_sleep - sleep_hours)
        sleep_dev = min(max(sleep_diff / 4.0, 0.0), 1.0)

        # Hydration deviation: baseline ~ 1.6 L
        baseline_hydr = baseline.get("expected_hydration_liters", 1.6)
        hydr_dev = min(max((baseline_hydr - hydration_liters) / baseline_hydr, 0.0), 1.0)

        # Family interaction deviation: norm is ~3-5 touchpoints
        norm_interactions = baseline.get("family_interaction_weekly_norm", 4)
        interaction_dev = 0.0 if interaction_count >= norm_interactions else min(
            (norm_interactions - interaction_count) / float(norm_interactions), 1.0
        )

        # 2. Weighted Routine Change Score (Step 5)
        # Check-in (25%), Medication (25%), Activity (20%), Sleep (10%), Hydration (10%), Interactions (10%)
        change_score = (
            0.25 * checkin_dev +
            0.25 * med_dev +
            0.20 * activity_dev +
            0.10 * sleep_dev +
            0.10 * hydr_dev +
            0.10 * interaction_dev
        )
        change_score = round(float(change_score), 3)

        # Assign alert level by engineering thresholds
        if change_score < 0.30:
            alert_level = "NORMAL"
            level_label = "Normal Routine"
            level_label_tamil = "வழக்கமான அட்டவணை"
        elif change_score < 0.60:
            alert_level = "MILD_CHANGE"
            level_label = "Mild Routine Shift"
            level_label_tamil = "லேசான நேர மாற்றம்"
        elif change_score < 0.80:
            alert_level = "SIGNIFICANT_CHANGE"
            level_label = "Significant Routine Deviation"
            level_label_tamil = "குறிப்பிடத்தக்க வழக்க மாற்றம்"
        else:
            alert_level = "HIGH_PRIORITY_CHANGE"
            level_label = "High-Priority Routine Change"
            level_label_tamil = "முக்கிய வழக்க மாற்றம்"

        # 3. Isolation Forest Anomaly Detection (Step 6)
        current_vector = [checkin_dev, med_dev, activity_dev, sleep_dev, hydr_dev]
        training_samples = self._generate_synthetic_baseline_distribution([0.05, 0.05, 0.05, 0.05, 0.05], n_samples=40)

        try:
            self.model.fit(training_samples)
            self._is_fitted = True
            iso_decision = float(self.model.decision_function([current_vector])[0])
            iso_pred = int(self.model.predict([current_vector])[0])  # -1 = anomaly, 1 = normal
            is_anomaly = (iso_pred == -1) or (change_score >= 0.60)
        except Exception as e:
            iso_decision = -1.0 if change_score >= 0.60 else 0.5
            is_anomaly = change_score >= 0.60

        return {
            "change_score": change_score,
            "alert_level": alert_level,
            "level_label": level_label,
            "level_label_tamil": level_label_tamil,
            "is_anomaly": is_anomaly,
            "anomaly_score": round(iso_decision, 4),
            "feature_breakdown": {
                "checkin_delay_mins": checkin_delay_mins,
                "checkin_deviation": round(checkin_dev, 2),
                "med_delay_mins": med_delay_mins,
                "medication_deviation": round(med_dev, 2),
                "activity_ratio": round(activity_ratio, 2),
                "activity_deviation": round(activity_dev, 2),
                "sleep_hours": round(sleep_hours, 1),
                "sleep_deviation": round(sleep_dev, 2),
                "hydration_liters": round(hydration_liters, 2),
                "hydration_deviation": round(hydr_dev, 2),
                "interaction_count": interaction_count,
                "interaction_deviation": round(interaction_dev, 2)
            }
        }

anomaly_detector = RoutineAnomalyDetector()
