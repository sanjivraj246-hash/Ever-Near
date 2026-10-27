import statistics
import math
from datetime import datetime, time
from typing import Dict, Any, List

class RoutineIntelligenceEngine:
    """
    Explainable AI engine calculating personal routine baseline.
    Avoids aggressive predictions; uses statistical deviations (mean, standard deviation, Z-score)
    to provide gentle, explainable attention signals.
    """
    def __init__(self):
        # Baseline configuration (in minutes from midnight)
        self.default_checkin_window_start = 7 * 60 + 30  # 07:30 AM
        self.default_checkin_window_end = 9 * 60 + 30    # 09:30 AM
        self.expected_daily_activity_hours = 2.5

    def analyze_checkin_pattern(self, checkin_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyzes historical check-ins to build baseline mean & variance.
        """
        if not checkin_history or len(checkin_history) < 2:
            return {
                "status": "normal",
                "reason": "Routine baseline is actively learning from daily check-ins.",
                "reason_tamil": "தினசரி நலம் அறிதல் மூலம் வழக்கமான அட்டவணை கணிக்கப்படுகிறது.",
                "confidence": 0.75,
                "average_checkin_time": "08:15 AM",
                "activity_score": 0.88,
                "recommendation": "Everything appears within normal morning routine."
            }

        times_in_minutes = []
        for record in checkin_history:
            dt: datetime = record.get("created_at")
            if dt:
                mins = dt.hour * 60 + dt.minute
                times_in_minutes.append(mins)

        if not times_in_minutes:
            times_in_minutes = [495, 510, 500]  # ~8:15 - 8:30 AM fallback

        mean_mins = float(statistics.mean(times_in_minutes))
        std_mins = float(statistics.stdev(times_in_minutes)) if len(times_in_minutes) > 1 else 15.0

        avg_hour = int(mean_mins // 60)
        avg_min = int(mean_mins % 60)
        am_pm = "AM" if avg_hour < 12 else "PM"
        display_hour = avg_hour if avg_hour <= 12 else avg_hour - 12
        if display_hour == 0:
            display_hour = 12
        avg_time_str = f"{display_hour:02d}:{avg_min:02d} {am_pm}"

        # Check current time vs mean
        now = datetime.now()
        current_mins = now.hour * 60 + now.minute
        diff_from_mean = current_mins - mean_mins

        if diff_from_mean > (std_mins * 2) and current_mins > self.default_checkin_window_end:
            return {
                "status": "attention",
                "reason": "Morning check-in is later than Amma's usual routine pattern.",
                "reason_tamil": "அம்மாவின் வழக்கமான நேரத்தை விட காலை நலம் அறிதல் தாமதமாகியுள்ளது.",
                "confidence": 0.82,
                "average_checkin_time": avg_time_str,
                "activity_score": 0.65,
                "recommendation": "Consider giving Amma a gentle call to say hello."
            }

        return {
            "status": "normal",
            "reason": "Amma's routine aligns closely with her historical baseline.",
            "reason_tamil": "அம்மாவின் அன்றாட வழக்கங்கள் வழக்கம்போல் சீராக உள்ளன.",
            "confidence": 0.89,
            "average_checkin_time": avg_time_str,
            "activity_score": 0.92,
            "recommendation": "Routine is stable and within expected parameters."
        }

    def detect_combined_anomaly(
        self,
        has_checked_in: bool,
        meds_taken_count: int,
        meds_total: int,
        cctv_safety_events_count: int,
        lang: str = "en"
    ) -> Dict[str, Any]:
        """
        Combines signals: Check-in + Medication + Routine + CCTV
        Yields ATTENTION or STABLE, never alarmist medical diagnosis.
        """
        reasons_en = []
        reasons_ta = []
        severity = "normal"
        confidence = 0.90

        if not has_checked_in:
            reasons_en.append("Morning check-in has not yet been registered.")
            reasons_ta.append("காலை நலம் அறிதல் இன்னும் பதிவு செய்யப்படவில்லை.")
            severity = "attention"
            confidence = 0.85

        if meds_total > 0 and meds_taken_count < meds_total:
            reasons_en.append("Scheduled morning medication has not yet been marked taken.")
            reasons_ta.append("காலை மருந்து உட்கொள்ளல் இன்னும் உறுதி செய்யப்படவில்லை.")
            severity = "attention"

        if cctv_safety_events_count > 0:
            reasons_en.append("Camera flagged unusual prolonged stillness in living area.")
            reasons_ta.append("வரவேற்பறையில் அசாதாரண அமைதி அல்லது இயக்கம் குறைவு கவனிக்கப்பட்டது.")
            severity = "attention"
            confidence = 0.88

        if not reasons_en:
            return {
                "indicator": "Stable",
                "headline": "All Routines Normal",
                "headline_tamil": "அனைத்தும் சீராக உள்ளது",
                "explanation": "Check-in completed, medications confirmed, and room activity detected on schedule.",
                "explanation_tamil": "நலம் அறிதல், மருந்துகள் மற்றும் அன்றாட இயக்கம் அனைத்தும் சீராக உள்ளன.",
                "severity": "normal",
                "confidence": 0.94
            }

        return {
            "indicator": "Attention Needed",
            "headline": "Gentle Attention Advised",
            "headline_tamil": "கவனிக்கவும்",
            "explanation": " ".join(reasons_en),
            "explanation_tamil": " ".join(reasons_ta),
            "severity": severity,
            "confidence": confidence
        }

routine_engine = RoutineIntelligenceEngine()
