import datetime
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from app.models.entities import (
    User, ParentProfile, PrivacySetting, PrivacyPause,
    PrivacyPermission, FamilyRelationship, AuditLog
)

class PrivacyService:
    """
    Core Privacy, Dignity & Permission Engine (Phase 18).
    Enforces privacy-first boundaries at the API level so sensitive data
    is never leaked to family members without parental consent or during a Privacy Pause.
    """

    @staticmethod
    def get_parent_privacy_state(db: Session, parent_user_id: int) -> Dict[str, Any]:
        """
        Determines current effective privacy boundaries for the specified parent.
        Privacy Pause overrides individual toggles for the duration of the pause,
        while strictly keeping Emergency SOS active.
        """
        now = datetime.datetime.utcnow()
        pause = db.query(PrivacyPause).filter(
            PrivacyPause.parent_id == parent_user_id,
            PrivacyPause.is_paused == True
        ).first()

        is_paused = False
        paused_until = None
        if pause and pause.paused_until and pause.paused_until > now:
            is_paused = True
            paused_until = pause.paused_until

        setting = db.query(PrivacySetting).filter(
            PrivacySetting.parent_id == parent_user_id
        ).first()

        health_pref = setting.health_info if setting else True
        activity_pref = setting.daily_activity if setting else True
        location_pref = setting.location_sharing if setting else False
        cctv_pref = setting.cctv_access if setting else False
        memories_pref = setting.memories_sharing if setting else True

        return {
            "parent_id": parent_user_id,
            "is_paused": is_paused,
            "paused_until": paused_until,
            "emergency_active": True,  # Non-negotiable safety invariant
            "health_info": False if is_paused else health_pref,
            "daily_activity": False if is_paused else activity_pref,
            "location_sharing": False if is_paused else location_pref,
            "cctv_access": False if is_paused else cctv_pref,
            "memories_sharing": memories_pref
        }

    @staticmethod
    def check_cctv_access(db: Session, parent_user_id: int, family_user_id: int) -> Tuple[bool, str]:
        """Validates if family user can access parent CCTV stream."""
        state = PrivacyService.get_parent_privacy_state(db, parent_user_id)
        if state["is_paused"]:
            return False, "Parent has activated Privacy Pause. Camera streams are shielded."
        if not state["cctv_access"]:
            return False, "CCTV camera sharing is currently turned OFF by parent privacy settings."

        rel = db.query(FamilyRelationship).filter(
            FamilyRelationship.parent_id == parent_user_id,
            FamilyRelationship.family_user_id == family_user_id
        ).first()
        if rel and not rel.can_view_cctv:
            return False, "Access denied: Specific relationship does not allow CCTV viewing."

        return True, "Authorized"

    @staticmethod
    def check_health_access(db: Session, parent_user_id: int, family_user_id: int) -> Tuple[bool, str]:
        """Validates if family user can view detailed health metrics."""
        state = PrivacyService.get_parent_privacy_state(db, parent_user_id)
        if state["is_paused"]:
            return False, "Parent has activated Privacy Pause. Detailed health metrics are paused."
        if not state["health_info"]:
            return False, "Parent has chosen to keep detailed health information private."

        rel = db.query(FamilyRelationship).filter(
            FamilyRelationship.parent_id == parent_user_id,
            FamilyRelationship.family_user_id == family_user_id
        ).first()
        if rel and not rel.can_view_health:
            return False, "Access denied: Specific relationship does not allow health viewing."

        return True, "Authorized"

    @staticmethod
    def check_location_access(db: Session, parent_user_id: int, family_user_id: int) -> Tuple[bool, str]:
        """Validates if family user can view real-time location telemetry."""
        state = PrivacyService.get_parent_privacy_state(db, parent_user_id)
        if state["is_paused"]:
            return False, "Parent has activated Privacy Pause. Location tracking is disabled."
        if not state["location_sharing"]:
            return False, "Parent has disabled location sharing."

        return True, "Authorized"

    @staticmethod
    def log_privacy_event(
        db: Session,
        user_id: int,
        action: str,
        target_resource: str,
        details: str
    ) -> AuditLog:
        """Records an immutable audit log entry for privacy enforcement."""
        audit = AuditLog(
            user_id=user_id,
            action=action,
            target_resource=target_resource,
            details=details,
            timestamp=datetime.datetime.utcnow()
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)
        return audit
