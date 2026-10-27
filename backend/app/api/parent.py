from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from app.db.session import get_db
from app.models.entities import User, ParentProfile, Medication, DailyCheckIn, SOSAlert
from app.api.deps import get_current_parent_user, get_current_user
from app.services.relationship_service import RelationshipService
from app.services.care_service import CareService
from app.services.alert_service import AlertService
from app.schemas.schemas import TrustedContactCreate, TrustedContactResponse


router = APIRouter(prefix="/parent", tags=["Parent Application"])

@router.get("/profile")
def get_parent_profile(
    current_user: User = Depends(get_current_parent_user),
    db: Session = Depends(get_db)
):
    """Retrieves parent profile for authenticated parent user."""
    profile = current_user.parent_profile
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent profile not found.")
    return {
        "user_id": current_user.id,
        "phone": current_user.phone,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "preferred_name": profile.preferred_name,
        "age": profile.age,
        "language_pref": profile.language_pref,
        "emergency_notes": profile.emergency_notes
    }

@router.get("/relationships")
def get_parent_relationships(
    current_user: User = Depends(get_current_parent_user),
    db: Session = Depends(get_db)
):
    """Lists all family members connected to this parent."""
    context = RelationshipService.identify_user_context(db, current_user)
    return context.get("relationships", [])

@router.get("/context")
def get_parent_context(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Identifies user, role, and parent/family relationships."""
    return RelationshipService.identify_user_context(db, current_user)

@router.get("/care-overview")
def get_care_overview(
    current_user: User = Depends(get_current_parent_user),
    db: Session = Depends(get_db)
):
    """Summarizes today's care, medication, and alert status for the parent."""
    profile = current_user.parent_profile
    profile_id = profile.id if profile else current_user.id

    today_checkin = CareService.get_today_checkin(db, current_user.id)
    meds = CareService.get_medications(db, profile_id)
    active_alert = AlertService.get_active_alert(db, profile_id)

    return {
        "parent_name": profile.preferred_name if profile else current_user.full_name,
        "has_checked_in_today": today_checkin is not None,
        "today_checkin": {
            "feeling": today_checkin.feeling,
            "feeling_tamil": today_checkin.feeling_tamil,
            "created_at": today_checkin.created_at
        } if today_checkin else None,
        "medications_count": len(meds),
        "has_active_emergency": active_alert is not None,
        "active_emergency_status": active_alert.status if active_alert else None
    }

@router.get("/trusted-contacts", response_model=List[TrustedContactResponse])
def get_trusted_contacts(
    current_user: User = Depends(get_current_parent_user),
    db: Session = Depends(get_db)
):
    """Lists all trusted emergency contacts registered for this parent."""
    if not current_user.parent_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent profile not found.")
    return RelationshipService.get_trusted_contacts(db, current_user.parent_profile.id)

@router.post("/trusted-contacts", response_model=TrustedContactResponse, status_code=status.HTTP_201_CREATED)
def create_trusted_contact(
    req: TrustedContactCreate,
    current_user: User = Depends(get_current_parent_user),
    db: Session = Depends(get_db)
):
    """Registers a new trusted contact for emergency escalation."""
    if not current_user.parent_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent profile not found.")
    return RelationshipService.add_trusted_contact(
        db=db,
        parent_profile_id=current_user.parent_profile.id,
        name=req.name,
        phone=req.phone,
        relationship_type=req.relationship_type,
        priority_order=req.priority_order,
        can_receive_sos=req.can_receive_sos,
        notes=req.notes
    )

@router.delete("/trusted-contacts/{contact_id}")
def delete_trusted_contact(
    contact_id: int,
    current_user: User = Depends(get_current_parent_user),
    db: Session = Depends(get_db)
):
    """Deletes a trusted contact owned by the authenticated parent."""
    if not current_user.parent_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent profile not found.")
    success = RelationshipService.delete_trusted_contact(
        db=db,
        parent_profile_id=current_user.parent_profile.id,
        contact_id=contact_id
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trusted contact not found.")
    return {"status": "success", "message": "Trusted contact removed successfully."}

