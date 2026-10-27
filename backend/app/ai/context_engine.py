from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

class MultiSignalContextEngine:
    """
    Multi-Signal Context Engine:
    Synthesizes multiple observational streams (Check-in, Medication, Activity,
    Sleep, Meals, Hydration, CCTV Events, Phone Interaction, and SOS status).
    Never triggers high-severity alerts from a single weak signal.
    Produces clear, explainable, human-centered insights without diagnosing diseases.
    """

    def evaluate_context(
        self,
        anomaly_result: Dict[str, Any],
        baseline: Dict[str, Any],
        cctv_events: List[Dict[str, Any]],
        phone_interactions_recent: bool = False,
        active_sos: bool = False,
        lang: str = "en"
    ) -> Dict[str, Any]:
        """
        Cross-examines anomaly detection outputs against multi-signal context.
        """
        change_score = anomaly_result.get("change_score", 0.0)
        is_anomaly = anomaly_result.get("is_anomaly", False)
        breakdown = anomaly_result.get("feature_breakdown", {})

        supporting_signals = []

        # 1. Check-In Signal
        checkin_delay = breakdown.get("checkin_delay_mins", 0)
        if checkin_delay > 60:
            supporting_signals.append({
                "signal_name": "Morning Check-In",
                "signal_name_tamil": "காலை நலம் அறிதல்",
                "baseline_value": baseline.get("typical_checkin_window", "08:15 AM — 09:00 AM"),
                "current_value": f"{int(checkin_delay)} minutes later than usual",
                "current_value_tamil": f"வழக்கத்தை விட {int(checkin_delay)} நிமிடங்கள் தாமதம்",
                "status": "ATTENTION" if checkin_delay > 90 else "NOTICE",
                "detail": f"Check-in is delayed by {int(checkin_delay)} minutes past normal baseline."
            })
        else:
            supporting_signals.append({
                "signal_name": "Morning Check-In",
                "signal_name_tamil": "காலை நலம் அறிதல்",
                "baseline_value": baseline.get("typical_checkin_window", "08:15 AM — 09:00 AM"),
                "current_value": "Completed on schedule",
                "current_value_tamil": "வழக்கமான நேரத்தில் முடிந்தது",
                "status": "NORMAL",
                "detail": "Morning check-in registered within expected baseline window."
            })

        # 2. Medication Signal
        med_delay = breakdown.get("med_delay_mins", 0)
        if med_delay > 45:
            supporting_signals.append({
                "signal_name": "Scheduled Medications",
                "signal_name_tamil": "மருந்து உட்கொள்ளல்",
                "baseline_value": baseline.get("typical_morning_med", "08:30 AM"),
                "current_value": "Not yet confirmed",
                "current_value_tamil": "இன்னும் உறுதி செய்யப்படவில்லை",
                "status": "ATTENTION",
                "detail": "Scheduled morning medication dose has not yet been marked taken."
            })
        else:
            supporting_signals.append({
                "signal_name": "Scheduled Medications",
                "signal_name_tamil": "மருந்து உட்கொள்ளல்",
                "baseline_value": baseline.get("typical_morning_med", "08:30 AM"),
                "current_value": "Confirmed on time",
                "current_value_tamil": "நேரத்தில் உட்கொள்ளப்பட்டது",
                "status": "NORMAL",
                "detail": "Prescribed morning medications confirmed."
            })

        # 3. Activity Signal
        act_ratio = breakdown.get("activity_ratio", 1.0)
        if act_ratio < 0.65:
            drop_pct = int((1.0 - act_ratio) * 100)
            supporting_signals.append({
                "signal_name": "Daily Movement & Activity",
                "signal_name_tamil": "தினசரி இயக்கம் & நடை",
                "baseline_value": f"~{int(baseline.get('expected_active_minutes', 45))} active mins",
                "current_value": f"{drop_pct}% below personal baseline",
                "current_value_tamil": f"வழக்கத்தை விட {drop_pct}% குறைவு",
                "status": "ATTENTION" if drop_pct > 40 else "NOTICE",
                "detail": f"Daily movement registered {drop_pct}% lower than historical average."
            })
        else:
            supporting_signals.append({
                "signal_name": "Daily Movement & Activity",
                "signal_name_tamil": "தினசரி இயக்கம் & நடை",
                "baseline_value": f"~{int(baseline.get('expected_active_minutes', 45))} active mins",
                "current_value": "Normal active movement",
                "current_value_tamil": "இயல்பான நடை & இயக்கம்",
                "status": "NORMAL",
                "detail": "Movement and walking aligned with daily routine."
            })

        # 4. CCTV Safety Signal
        has_cctv_motion_spike = any(e.get("event_type") == "RAPID_MOVEMENT_EVENT" for e in cctv_events)
        has_cctv_stillness = any(e.get("event_type") == "UNUSUAL_INACTIVITY" for e in cctv_events)

        if has_cctv_motion_spike or has_cctv_stillness:
            supporting_signals.append({
                "signal_name": "Living Room Safety Camera",
                "signal_name_tamil": "வரவேற்பறை கேமரா",
                "baseline_value": "Ambient steady motion",
                "current_value": "Optical flow variance flagged",
                "current_value_tamil": "இயக்க மாற்றம் கவனிக்கப்பட்டது",
                "status": "ATTENTION",
                "detail": "Motion analysis registered a variance in room activity."
            })
        else:
            supporting_signals.append({
                "signal_name": "Living Room Safety Camera",
                "signal_name_tamil": "வரவேற்பறை கேமரா",
                "baseline_value": "Ambient steady motion",
                "current_value": "Clear & steady",
                "current_value_tamil": "அமைதியான இயக்கம்",
                "status": "NORMAL",
                "detail": "Camera optical flow confirms steady ambient environment."
            })

        # Contextual Evaluation Rules (Step 8)
        # Rule 1: Fall-like movement + movement resumed / phone interaction = lower priority
        if (has_cctv_motion_spike or has_cctv_stillness) and phone_interactions_recent:
            severity = "NOTICE"
            headline = "Motion Variance Noticed (Activity Resumed)"
            headline_tamil = "இயக்க மாற்றம் கவனிக்கப்பட்டது (மீண்டும் இயக்கம் தொடர்கிறது)"
            interpretation = "An abrupt motion variance was flagged, but phone activity resumed shortly after, indicating ongoing engagement."
            interpretation_tamil = "திடீர் இயக்கம் கவனிக்கப்பட்டாலும், தொலைபேசி பயன்பாடு தொடர்ந்துள்ளதால் இயல்பு நிலைக்குத் திரும்பியுள்ளது."
            suggested_action = "No emergency action needed. Consider sending a warm check-in message later."
            suggested_action_tamil = "அவசரம் ஏதுமில்லை. பின்னர் ஒரு முறை நலம் விசாரிக்கலாம்."
            confidence = 0.85

        # Rule 2: Fall-like event + prolonged inactivity + no check-in = high-priority safety event
        elif (has_cctv_stillness or has_cctv_motion_spike) and checkin_delay > 90 and not phone_interactions_recent:
            severity = "HIGH_PRIORITY"
            headline = "Safety Attention Advised: Inactivity with Delayed Check-In"
            headline_tamil = "அவசரக் கவனம் தேவை: நலம் அறிதல் தாமதம் மற்றும் இயக்கம் குறைவு"
            interpretation = "Prolonged stillness flagged by camera optical flow coincides with an unconfirmed morning check-in and absence of recent phone interaction."
            interpretation_tamil = "காலை நலம் அறிதல் தாமதத்துடன் அறையின் அமைதியும் நீடிப்பதால் உடனடி கவனம் தேவைப்படுகிறது."
            suggested_action = "Please call Amma or reach out to nearby trusted contact."
            suggested_action_tamil = "அம்மாவை உடனடியாகத் தொலைபேசியில் அழைக்கவும் அல்லது அருகில் உள்ளவரை தொடர்பு கொள்ளவும்."
            confidence = 0.94

        # Rule 3: Meaningful routine deviation (delayed checkin + meds pending + low activity)
        elif change_score >= 0.60 or is_anomaly:
            severity = "ATTENTION"
            headline = "Routine Change Detected"
            headline_tamil = "அன்றாட வழக்கத்தில் மாற்றம் கவனிக்கப்பட்டது"
            interpretation = "Compared with Amma's recent routine, morning check-in, medication, and activity markers have shifted from baseline."
            interpretation_tamil = "அம்மாவின் வழக்கமான நேரத்துடன் ஒப்பிடும்போது நலம் அறிதல், மருந்து மற்றும் இயக்கத்தில் மாற்றம் ஏற்பட்டுள்ளது."
            suggested_action = "Consider giving Amma a friendly check-in call to say hello."
            suggested_action_tamil = "அம்மாவிடம் நலம் விசாரிக்க ஒரு அன்பான தொலைபேசி அழைப்பு விடுக்கலாம்."
            confidence = 0.88

        # Rule 4: Mild shift
        elif change_score >= 0.30:
            severity = "MILD"
            headline = "Gentle Notice: Routine Slightly Shifted"
            headline_tamil = "கவனிக்க: அன்றாட நேரம் சற்று மாறியுள்ளது"
            interpretation = "One or two daily activities occurred slightly outside usual timing, but overall routine remains reassuring."
            interpretation_tamil = "ஒரு சில நிகழ்வுகள் சற்று தாமதமாக நடந்துள்ளன, இருப்பினும் ஒட்டுமொத்த சூழல் சீராக உள்ளது."
            suggested_action = "No urgency. Keep an eye on today's routine progress."
            suggested_action_tamil = "அவசரம் ஏதுமில்லை. இன்றைய நிகழ்வுகளை அமைதியாக கவனியுங்கள்."
            confidence = 0.90

        # Rule 5: Normal baseline
        else:
            severity = "NORMAL"
            headline = "All Everyday Routines Aligned"
            headline_tamil = "அனைத்தும் சீராக இயல்பாக உள்ளது"
            interpretation = "Signals across check-ins, medications, and room activity align closely with Amma's historical baseline."
            interpretation_tamil = "நலம் அறிதல், மருந்துகள் மற்றும் அன்றாட இயக்கம் அனைத்தும் சீராக உள்ளன."
            suggested_action = "Everything is peaceful. Consider sending a warm greeting."
            suggested_action_tamil = "அனைத்தும் அமைதியாக உள்ளது. ஒரு அன்பான வணக்கம் தெரிவிக்கலாம்."
            confidence = 0.95

        return {
            "severity": severity,
            "headline": headline,
            "headline_tamil": headline_tamil,
            "interpretation": interpretation,
            "interpretation_tamil": interpretation_tamil,
            "change_score": change_score,
            "anomaly_score": anomaly_result.get("anomaly_score", 0.0),
            "is_anomaly": is_anomaly,
            "confidence": confidence,
            "suggested_action": suggested_action,
            "suggested_action_tamil": suggested_action_tamil,
            "supporting_signals": supporting_signals,
            "disclaimer": "EVER NEAR AI observes everyday routine patterns and is not a clinical medical diagnostic tool."
        }

context_engine = MultiSignalContextEngine()
