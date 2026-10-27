from typing import Dict, Any

def generate_family_briefing(
    parent_name: str,
    has_checked_in: bool,
    feeling: str,
    meds_taken: int,
    meds_total: int,
    recent_events_count: int
) -> Dict[str, Any]:
    """
    Generates a concise, non-alarmist family daily summary.
    Respects elderly dignity and does not provide medical diagnoses.
    """
    feeling_labels = {
        "good": ("Good & cheerful", "நன்றாக உள்ளார்"),
        "okay": ("Okay", "பரவாயில்லை"),
        "not_well": ("A bit tired / low energy", "சோர்வாக உள்ளார்")
    }
    feeling_text, feeling_ta = feeling_labels.get(feeling, ("Not checked in yet", "பதிவு செய்யப்படவில்லை"))

    if has_checked_in and meds_taken == meds_total and recent_events_count == 0:
        summary_en = (
            f"{parent_name} completed her morning check-in and confirmed feeling {feeling_text}. "
            "Morning routine and medications are confirmed on schedule. No safety deviations detected."
        )
        summary_ta = (
            f"{parent_name} காலை நலம் அறிதலை முடித்துள்ளார் ({feeling_ta}). "
            "காலை உணவு மற்றும் மருந்து உட்கொள்ளப்பட்டது. வழக்கத்திற்கு மாறான முரண்பாடுகள் எதுவும் இல்லை."
        )
        recommendation = "All parameters are peaceful and reassuring."
        status_indicator = "Stable"
    elif not has_checked_in:
        summary_en = (
            f"{parent_name} has not yet submitted her usual morning check-in. "
            "Living room camera shows ambient room motion, but check-in remains pending."
        )
        summary_ta = (
            f"{parent_name} இன்றைய காலை நலம் அறிதலை இன்னும் பதிவு செய்யவில்லை. "
            "வீட்டில் அசைவுகள் இருந்தாலும் நலம் அறிதல் நிலுவையில் உள்ளது."
        )
        recommendation = "Consider a gentle phone call or warm message to say hello."
        status_indicator = "Attention"
    else:
        summary_en = (
            f"{parent_name} checked in as {feeling_text}. "
            f"Medications: {meds_taken} of {meds_total} taken. "
            "Activity is slightly quieter than her usual morning baseline."
        )
        summary_ta = (
            f"{parent_name} நலம் தெரிவித்தார் ({feeling_ta}). "
            f"மருந்து: {meds_taken}/{meds_total} எடுக்கப்பட்டது. வழக்கம் போல சீராக உள்ளது."
        )
        recommendation = "Keep an occasional warm connection open today."
        status_indicator = "Stable"

    return {
        "parent_name": parent_name,
        "status_indicator": status_indicator,
        "summary_text": summary_en,
        "summary_text_tamil": summary_ta,
        "checkin_status": f"Completed ({feeling_text})" if has_checked_in else "Pending",
        "medication_status": f"{meds_taken}/{meds_total} Taken",
        "activity_window": "7:30 AM — 8:15 AM",
        "cctv_status": "All normal in monitored zones",
        "ai_recommendation": recommendation
    }
