import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.entities import SOSAlert, ParentProfile

class AlertService:
    @staticmethod
    def create_alert(db: Session, parent_profile_id: int, notes: Optional[str] = None) -> SOSAlert:
        alert = SOSAlert(
            parent_id=parent_profile_id,
            status="ACTIVE",
            notes=notes or "Emergency SOS requested from mobile app",
            triggered_at=datetime.datetime.utcnow()
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert

    @staticmethod
    def get_active_alert(db: Session, parent_profile_id: int) -> Optional[SOSAlert]:
        return db.query(SOSAlert).filter(
            SOSAlert.parent_id == parent_profile_id,
            SOSAlert.status.in_(["ACTIVE", "TRIGGERED", "ACKNOWLEDGED"])
        ).order_by(SOSAlert.triggered_at.desc()).first()

    @staticmethod
    def acknowledge_alert(db: Session, alert_id: int, responder_name: str = "Family Member") -> Optional[SOSAlert]:
        alert = db.query(SOSAlert).filter(SOSAlert.id == alert_id).first()
        if alert:
            alert.status = "ACKNOWLEDGED"
            alert.acknowledged_by = responder_name
            alert.acknowledged_at = datetime.datetime.utcnow()
            db.commit()
            db.refresh(alert)
        return alert

    @staticmethod
    def resolve_alert(db: Session, alert_id: int) -> Optional[SOSAlert]:
        alert = db.query(SOSAlert).filter(SOSAlert.id == alert_id).first()
        if alert:
            alert.status = "RESOLVED"
            alert.resolved_at = datetime.datetime.utcnow()
            db.commit()
            db.refresh(alert)
        return alert
