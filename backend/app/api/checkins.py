from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.models.entities import User, DailyCheckIn
from app.schemas.schemas import CheckInCreate, CheckInResponse
from app.api.deps import get_current_user
from app.services.care_service import CareService
from app.services.relationship_service import RelationshipService

router = APIRouter(prefix="/checkins", tags=["Daily Check-ins"])

@router.get("/today", response_model=Optional[CheckInResponse])
def get_today_checkin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves today's completed check-in for the active parent."""
    user_id = current_user.id
    if current_user.role.upper() == "FAMILY":
        parent = RelationshipService.get_parent_for_family(db, current_user.id)
        if not parent:
            return None
        user_id = parent.id

    return CareService.get_today_checkin(db, user_id)

@router.get("", response_model=List[CheckInResponse])
@router.get("/history", response_model=List[CheckInResponse])
def get_checkin_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves check-in history sorted by latest entry."""
    user_id = current_user.id
    if current_user.role.upper() == "FAMILY":
        parent = RelationshipService.get_parent_for_family(db, current_user.id)
        if not parent:
            return []
        user_id = parent.id

    return db.query(DailyCheckIn).filter(
        DailyCheckIn.user_id == user_id
    ).order_by(DailyCheckIn.created_at.desc()).limit(30).all()

@router.get("/latest", response_model=Optional[CheckInResponse])
def get_latest_checkin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves the most recent check-in record for the active parent."""
    user_id = current_user.id
    if current_user.role.upper() == "FAMILY":
        parent = RelationshipService.get_parent_for_family(db, current_user.id)
        if not parent:
            return None
        user_id = parent.id

    return db.query(DailyCheckIn).filter(
        DailyCheckIn.user_id == user_id
    ).order_by(DailyCheckIn.created_at.desc()).first()

@router.post("", response_model=CheckInResponse)
async def submit_checkin(
    req: CheckInCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Records a daily feeling check-in for the parent and broadcasts real-time update."""
    user_id = current_user.id
    if current_user.role.upper() == "FAMILY":
        parent = RelationshipService.get_parent_for_family(db, current_user.id)
        if parent:
            user_id = parent.id

    checkin = CareService.record_checkin(db, user_id, req)

    # Real-time WebSocket event dispatch to Care Circle
    try:
        from app.core.websocket import ws_manager
        parent_name = (
            current_user.parent_profile.preferred_name
            if current_user.parent_profile and current_user.parent_profile.preferred_name
            else current_user.full_name
        )
        ws_msg = {
            "type": "CHECKIN_UPDATE",
            "parent_id": user_id,
            "parent_name": parent_name,
            "feeling": checkin.feeling,
            "feeling_tamil": checkin.feeling_tamil,
            "check_in_date": checkin.check_in_date,
            "created_at": checkin.created_at.isoformat() if checkin.created_at else None
        }
        await ws_manager.send_to_family_of_parent(db, user_id, ws_msg)
    except Exception:
        pass

    return checkin

# Alias router for /check-ins
alias_router = APIRouter(prefix="/check-ins", tags=["Daily Check-ins Alias"])
alias_router.add_api_route("/today", get_today_checkin, methods=["GET"], response_model=Optional[CheckInResponse])
alias_router.add_api_route("/latest", get_latest_checkin, methods=["GET"], response_model=Optional[CheckInResponse])
alias_router.add_api_route("", get_checkin_history, methods=["GET"], response_model=List[CheckInResponse])
alias_router.add_api_route("/history", get_checkin_history, methods=["GET"], response_model=List[CheckInResponse])
alias_router.add_api_route("", submit_checkin, methods=["POST"], response_model=CheckInResponse)

