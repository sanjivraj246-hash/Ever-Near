from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List
from app.db.session import get_db
from app.models.entities import User, ParentProfile, SOSAlert
from app.schemas.schemas import SOSAlertCreate, SOSAlertResponse, SOSAcknowledgeRequest
from app.api.deps import get_current_user
from app.services.alert_service import AlertService
from app.services.relationship_service import RelationshipService

router = APIRouter(prefix="/alerts", tags=["Emergency Alerts & SOS"])

@router.post("", response_model=SOSAlertResponse)
def trigger_alert(
    req: SOSAlertCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Triggers an emergency SOS alert for the parent."""
    profile = current_user.parent_profile or db.query(ParentProfile).filter(ParentProfile.user_id == current_user.id).first()
    if not profile:
        profile = ParentProfile(
            user_id=current_user.id,
            preferred_name=current_user.full_name,
            age=70,
            language_pref="ta"
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

    profile_id = profile.id
    alert = AlertService.create_alert(db, profile_id, req.notes)
    return alert

@router.get("/active", response_model=Optional[SOSAlertResponse])
def get_active_alert(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns active emergency alert for current parent or linked parent only."""
    if current_user.role.upper() == "PARENT":
        profile = current_user.parent_profile or db.query(ParentProfile).filter(ParentProfile.user_id == current_user.id).first()
        if not profile:
            return None
        return AlertService.get_active_alert(db, profile.id)
    elif current_user.role.upper() == "FAMILY":
        parent = RelationshipService.get_parent_for_family(db, current_user.id)
        if not parent:
            return None
        profile = parent.parent_profile or db.query(ParentProfile).filter(ParentProfile.user_id == parent.id).first()
        if not profile:
            return None
        return AlertService.get_active_alert(db, profile.id)
    return None

@router.post("/{alert_id}/acknowledge", response_model=SOSAlertResponse)
def acknowledge_alert(
    alert_id: int,
    req: SOSAcknowledgeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Allows family member to acknowledge emergency SOS."""
    responder = req.responder_name or current_user.full_name
    alert = AlertService.acknowledge_alert(db, alert_id, responder)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found.")
    return alert

@router.post("/{alert_id}/resolve")
def resolve_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Resolves and closes an emergency alert."""
    alert = AlertService.resolve_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found.")
    return {"status": "RESOLVED", "message": "Emergency alert marked resolved."}
