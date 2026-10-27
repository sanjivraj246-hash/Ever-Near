
import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.session import get_db
from app.models.entities import (
    User, ParentProfile, HelpRequest, SafeReturnTrip, FamilyMessage,
    PrivacyPause, PrivacySetting, TemporaryPermission, FamilyRelationship
)
from app.schemas.schemas import (
    HelpRequestCreate, HelpRequestResponse,
    SafeReturnStartRequest, SafeReturnResponse,
    FamilyMessageCreate, FamilyMessageResponse
)
from app.routers.deps import get_current_user
from app.core.websocket import ws_manager

router = APIRouter(prefix="", tags=["Everyday Help & Family Messages"])

# ----------------- I NEED HELP (Everyday Requests) -----------------
@router.post("/help-requests", response_model=HelpRequestResponse)
async def create_help_request(
    req: HelpRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tamil_map = {
        "groceries": "மளிகை / வீட்டுத் தேவைகள்",
        "medicine": "மருந்து தீர்ந்துவிட்டது",
        "chat": "அன்பாக பேச வேண்டும்",
        "home": "வீட்டு பழுது / உதவி",
        "transport": "வாகன உதவி தேவை",
        "discomfort": "உடல் அசௌகரியம் (அவசரம் அல்ல)"
    }
    tamil_label = req.category_tamil or tamil_map.get(req.category.lower(), req.category)

    help_req = HelpRequest(
        parent_id=current_user.id,
        category=req.category,
        category_tamil=tamil_label,
        note=req.note or f"Assistance needed for {req.category}",
        status="OPEN"
    )
    db.add(help_req)
    db.commit()
    db.refresh(help_req)

    # Real-time WebSocket announcement strictly to this parent's authorized family circle
    await ws_manager.send_to_family_of_parent(db, current_user.id, {
        "type": "HELP_REQUEST",
        "help_request_id": help_req.id,
        "category": req.category,
        "category_tamil": tamil_label,
        "note": help_req.note,
        "parent_name": current_user.full_name
    })

    return help_req

from app.services.relationship_service import RelationshipService

def resolve_support_parent_id(current_user: User, db: Session) -> Optional[int]:
    if current_user.role.upper() == "PARENT":
        return current_user.id
    parent = RelationshipService.get_parent_for_family(db, current_user.id)
    return parent.id if parent else None

@router.get("/help-requests", response_model=List[HelpRequestResponse])
def get_help_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = resolve_support_parent_id(current_user, db)
    if not parent_id:
        return []

    requests = db.query(HelpRequest).filter(
        HelpRequest.parent_id == parent_id
    ).order_by(HelpRequest.created_at.desc()).limit(10).all()

    return requests

@router.post("/help-requests/{id}/acknowledge", response_model=HelpRequestResponse)
async def acknowledge_help_request(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    help_req = db.query(HelpRequest).filter(HelpRequest.id == id).first()
    if not help_req:
        raise HTTPException(status_code=404, detail="Help request not found")

    if current_user.role.upper() == "FAMILY":
        parent = RelationshipService.get_parent_for_family(db, current_user.id)
        if not parent or parent.id != help_req.parent_id:
            raise HTTPException(status_code=403, detail="Not authorized to acknowledge this help request")

    help_req.status = "ACKNOWLEDGED"
    help_req.handled_by = current_user.full_name
    db.commit()
    db.refresh(help_req)

    update_msg = {
        "type": "HELP_REQUEST_UPDATED",
        "help_request_id": help_req.id,
        "status": "ACKNOWLEDGED",
        "handled_by": current_user.full_name,
        "category": help_req.category
    }
    await ws_manager.send_personal_message(update_msg, user_id=help_req.parent_id)
    await ws_manager.send_to_family_of_parent(db, help_req.parent_id, update_msg)
    return help_req

@router.post("/help-requests/{id}/resolve", response_model=HelpRequestResponse)
async def resolve_help_request(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    help_req = db.query(HelpRequest).filter(HelpRequest.id == id).first()
    if not help_req:
        raise HTTPException(status_code=404, detail="Help request not found")

    if current_user.role.upper() == "FAMILY":
        parent = RelationshipService.get_parent_for_family(db, current_user.id)
        if not parent or parent.id != help_req.parent_id:
            raise HTTPException(status_code=403, detail="Not authorized to resolve this help request")
    elif current_user.id != help_req.parent_id:
        raise HTTPException(status_code=403, detail="Not authorized to resolve this help request")

    help_req.status = "COMPLETED"
    if not help_req.handled_by:
        help_req.handled_by = current_user.full_name
    db.commit()
    db.refresh(help_req)

    update_msg = {
        "type": "HELP_REQUEST_UPDATED",
        "help_request_id": help_req.id,
        "status": "COMPLETED",
        "handled_by": help_req.handled_by,
        "category": help_req.category
    }
    await ws_manager.send_personal_message(update_msg, user_id=help_req.parent_id)
    await ws_manager.send_to_family_of_parent(db, help_req.parent_id, update_msg)
    return help_req

# ----------------- SAFE RETURN (Shop, Temple, Hospital) -----------------
@router.post("/safe-return/start", response_model=SafeReturnResponse)
async def start_safe_return(
    req: SafeReturnStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    now = datetime.datetime.utcnow()
    expected = now + datetime.timedelta(minutes=req.duration_minutes)

    trip = SafeReturnTrip(
        parent_id=current_user.id,
        destination=req.destination,
        destination_tamil=req.destination_tamil or "கடை",
        duration_minutes=req.duration_minutes,
        expected_return_at=expected,
        status="OUT"
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)

    await ws_manager.send_to_family_of_parent(db, current_user.id, {
        "type": "SAFE_RETURN_STARTED",
        "destination": trip.destination,
        "destination_tamil": trip.destination_tamil,
        "duration_minutes": trip.duration_minutes,
        "parent_name": current_user.full_name
    })

    return trip

@router.post("/safe-return/confirm-home", response_model=SafeReturnResponse)
@router.post("/safe-return/{id}/return", response_model=SafeReturnResponse)
async def confirm_safe_return(
    id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(SafeReturnTrip).filter(SafeReturnTrip.parent_id == current_user.id)
    if id:
        trip = query.filter(SafeReturnTrip.id == id).first()
    else:
        trip = query.filter(SafeReturnTrip.status == "OUT").order_by(SafeReturnTrip.created_at.desc()).first()

    if not trip:
        raise HTTPException(status_code=404, detail="No active outing found")

    trip.status = "RETURNED"
    trip.returned_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(trip)

    await ws_manager.send_to_family_of_parent(db, current_user.id, {
        "type": "SAFE_RETURN_CONFIRMED",
        "destination": trip.destination,
        "parent_name": current_user.full_name
    })

    return trip

@router.get("/safe-return/active", response_model=Optional[SafeReturnResponse])
def get_safe_return_active(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = resolve_support_parent_id(current_user, db)
    if not parent_id:
        if current_user.role.upper() in ["FAMILY", "GUARDIAN", "CAREGIVER"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You do not have an approved family relationship to view location."
            )
        return None

    # If family/guardian/caregiver, check location privacy boundaries
    if current_user.role.upper() in ["FAMILY", "GUARDIAN", "CAREGIVER"]:
        # 0. Approved Relationship Check
        rel = db.query(FamilyRelationship).filter(
            FamilyRelationship.family_user_id == current_user.id,
            FamilyRelationship.parent_id == parent_id,
            FamilyRelationship.status == "APPROVED"
        ).first()
        if not rel:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You do not have an approved family relationship to view location."
            )

        now = datetime.datetime.utcnow()
        pause = db.query(PrivacyPause).filter(
            PrivacyPause.parent_id == parent_id,
            PrivacyPause.is_paused == True
        ).first()
        if pause and pause.paused_until and pause.paused_until > now:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Location sharing is temporarily paused by Amma's Privacy Pause."
            )

        priv = db.query(PrivacySetting).filter(PrivacySetting.parent_id == parent_id).first()
        has_temp = db.query(TemporaryPermission).filter(
            TemporaryPermission.parent_id == parent_id,
            TemporaryPermission.resource_type == "LOCATION",
            TemporaryPermission.status == "ACTIVE",
            TemporaryPermission.expires_at > now,
            (TemporaryPermission.grantee_name.like(f"%{current_user.full_name}%")) |
            (TemporaryPermission.grantee_name == current_user.phone)
        ).first()
        if priv and not priv.location_sharing and not has_temp:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Parent has chosen to keep location sharing private."
            )

    trip = db.query(SafeReturnTrip).filter(
        SafeReturnTrip.parent_id == parent_id,
        SafeReturnTrip.status == "OUT"
    ).order_by(SafeReturnTrip.created_at.desc()).first()

    if trip and trip.expected_return_at < datetime.datetime.utcnow():
        trip.status = "OVERDUE"
        db.commit()

    return trip

@router.get("/safe-return/status", response_model=SafeReturnResponse)
def get_safe_return_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = resolve_support_parent_id(current_user, db)
    if not parent_id:
        if current_user.role.upper() in ["FAMILY", "GUARDIAN", "CAREGIVER"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You do not have an approved family relationship to view location."
            )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active outing found")

    if current_user.role.upper() in ["FAMILY", "GUARDIAN", "CAREGIVER"]:
        rel = db.query(FamilyRelationship).filter(
            FamilyRelationship.family_user_id == current_user.id,
            FamilyRelationship.parent_id == parent_id,
            FamilyRelationship.status == "APPROVED"
        ).first()
        if not rel:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You do not have an approved family relationship to view location."
            )

    trip = db.query(SafeReturnTrip).filter(
        SafeReturnTrip.parent_id == parent_id
    ).order_by(SafeReturnTrip.created_at.desc()).first()

    if not trip:
        return SafeReturnResponse(
            id=0,
            destination="Home",
            destination_tamil="வீடு",
            duration_minutes=0,
            expected_return_at=datetime.datetime.utcnow(),
            returned_at=datetime.datetime.utcnow(),
            status="RETURNED",
            created_at=datetime.datetime.utcnow()
        )

    # Check if overdue
    if trip.status == "OUT" and trip.expected_return_at < datetime.datetime.utcnow():
        trip.status = "OVERDUE"
        db.commit()

    return trip

# ----------------- FAMILY MESSAGES (Warm Prompts, Greetings) -----------------
@router.post("/messages", response_model=FamilyMessageResponse)
async def send_family_message(
    req: FamilyMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    msg = FamilyMessage(
        sender_name=current_user.full_name,
        sender_role=current_user.role,
        receiver_name=req.receiver_name,
        message_type=req.message_type,
        content=req.content,
        content_tamil=req.content_tamil or req.content
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # WebSocket event strictly directed
    event_payload = {
        "type": "NEW_FAMILY_MESSAGE",
        "sender_name": msg.sender_name,
        "content": msg.content,
        "content_tamil": msg.content_tamil
    }
    if current_user.role.upper() == "PARENT":
        await ws_manager.send_to_family_of_parent(db, current_user.id, event_payload)
    else:
        parent = RelationshipService.get_parent_for_family(db, current_user.id)
        if parent:
            await ws_manager.send_personal_message(event_payload, user_id=parent.id)

    return msg

@router.get("/messages", response_model=List[FamilyMessageResponse])
def get_family_messages(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    msgs = db.query(FamilyMessage).order_by(FamilyMessage.created_at.desc()).limit(15).all()
    return msgs
