import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.entities import SafetyEvent, AuditLog

class CCTVSafetyPipeline:
    """
    CCTV Safety Pipeline:
    Prototype Computer Vision event analyzer for elderly living areas.
    Distinguishes computer vision event detection from medical diagnosis.
    Clearly marks simulation/demo mode when running on demo streams.
    """

    SUPPORTED_EVENT_TYPES = [
        "FALL_LIKE_MOVEMENT",
        "PROLONGED_INACTIVITY",
        "UNEXPECTED_MOVEMENT",
        "RESTRICTED_AREA_MOVEMENT"
    ]

    def process_telemetry_event(
        self,
        db: Session,
        parent_id: int,
        event_type: str,
        location_name: str = "Living Room",
        confidence: float = 0.86,
        is_simulation: bool = True
    ) -> Dict[str, Any]:
        """
        Processes and stores a prototype safety event.
        """
        if event_type not in self.SUPPORTED_EVENT_TYPES:
            event_type = "PROLONGED_INACTIVITY"

        title_map = {
            "FALL_LIKE_MOVEMENT": ("Possible fall-like movement detected", "திடீர் வீழ்ச்சி போன்ற இயக்கம் கவனிக்கப்பட்டது"),
            "PROLONGED_INACTIVITY": ("Unusual prolonged stillness in living area", "வரவேற்பறையில் நீண்ட நேரம் அமைதி அல்லது இயக்கம் குறைவு"),
            "UNEXPECTED_MOVEMENT": ("Unexpected night-time movement noticed", "இரவு நேரத்தில் எதிர்பாராத இயக்கம் கவனிக்கப்பட்டது"),
            "RESTRICTED_AREA_MOVEMENT": ("Movement near restricted entrance or exit", "வாயில் அல்லது தடைசெய்யப்பட்ட பகுதியில் இயக்கம்")
        }

        title_en, title_ta = title_map.get(event_type, ("Unusual safety signal noticed", "அசாதாரண நிகழ்வு கவனிக்கப்பட்டது"))
        desc_en = f"Camera optical flow analysis flagged {title_en.lower()} at {location_name}."
        desc_ta = f"{location_name} பகுதியில் பாதுகாப்பு கேமரா மூலம் இயக்கம் கவனிக்கப்பட்டது."

        # Persist event in PostgreSQL
        safety_event = SafetyEvent(
            parent_id=parent_id,
            source="CCTV",
            severity="ATTENTION" if event_type in ["FALL_LIKE_MOVEMENT", "PROLONGED_INACTIVITY"] else "INFO",
            title=title_en,
            title_tamil=title_ta,
            description=desc_en,
            description_tamil=desc_ta,
            confidence=confidence,
            acknowledged=False,
            created_at=datetime.datetime.utcnow()
        )
        db.add(safety_event)
        db.commit()
        db.refresh(safety_event)

        return {
            "id": safety_event.id,
            "event_type": event_type,
            "title": title_en,
            "title_tamil": title_ta,
            "location": location_name,
            "confidence": confidence,
            "is_simulation_mode": is_simulation,
            "mode_label": "Controlled Simulation Mode" if is_simulation else "Live Camera Stream",
            "medical_disclaimer": "This is a computer vision signal detection, not a medical or clinical diagnosis.",
            "timestamp": safety_event.created_at.isoformat()
        }

cctv_pipeline = CCTVSafetyPipeline()
