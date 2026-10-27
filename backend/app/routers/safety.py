import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database.session import get_db
from app.models.entities import User, ParentProfile, SafetyEvent, DailyCheckIn, Medication, MedicationLog, FamilyRelationship
from app.schemas.schemas import SafetyEventResponse
from app.routers.deps import get_current_user

router = APIRouter(prefix="/safety", tags=["Safety & Unusual Moments"])

@router.get("/events", response_model=List[SafetyEventResponse])
def get_safety_events(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role.upper() == "PARENT":
        profile = current_user.parent_profile or db.query(ParentProfile).filter(ParentProfile.user_id == current_user.id).first()
        parent_id = profile.id if profile else current_user.id
    else:
        from app.services.relationship_service import RelationshipService
        parent = RelationshipService.get_parent_for_family(db, current_user.id)
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You do not have an approved family relationship to view safety events."
            )
        rel = db.query(FamilyRelationship).filter(
            FamilyRelationship.family_user_id == current_user.id,
            FamilyRelationship.parent_id == parent.id,
            FamilyRelationship.status == "APPROVED"
        ).first()
        if not rel:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You do not have an approved family relationship to view safety events."
            )
        profile = parent.parent_profile or db.query(ParentProfile).filter(ParentProfile.user_id == parent.id).first()
        parent_id = profile.id if profile else parent.id

    events = db.query(SafetyEvent).filter(
        SafetyEvent.parent_id == parent_id
    ).order_by(SafetyEvent.created_at.desc()).all()

    return events

@router.post("/events/{id}/acknowledge", response_model=SafetyEventResponse)
def acknowledge_safety_event(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    event = db.query(SafetyEvent).filter(SafetyEvent.id == id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Safety event not found")

    event.acknowledged = True
    event.acknowledged_by = current_user.full_name
    db.commit()
    db.refresh(event)
    return event
