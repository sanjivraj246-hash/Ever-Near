import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List
from app.database.session import get_db
from app.models.entities import User, ParentProfile, SOSAlert, Notification, CareTimelineItem, AuditLog
from app.schemas.schemas import SOSCreate, SOSAcknowledge, SOSResponse
from app.routers.deps import get_current_user
from app.core.websocket import ws_manager

router = APIRouter(prefix="/sos", tags=["SOS Emergency Workflow"])

@router.get("", response_model=List[SOSResponse])
def get_sos_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 2: GET /sos
    Returns recent SOS emergency history scoped to current user or linked family.
    """
    if current_user.role.upper() == "PARENT":
        profile = current_user.parent_profile
        prof_id = profile.id if profile else current_user.id
    else:
        from app.services.relationship_service import RelationshipService
        parent = RelationshipService.get_parent_for_family(db, current_user.id)
        if not parent:
            return []
        prof_id = parent.parent_profile.id if parent.parent_profile else parent.id

    alerts = db.query(SOSAlert).filter(
        SOSAlert.parent_id == prof_id
    ).order_by(SOSAlert.triggered_at.desc()).limit(20).all()

    results = []
    for a in alerts:
        profile = db.query(ParentProfile).filter(ParentProfile.id == a.parent_id).first()
        pname = profile.preferred_name if profile else "Amma"
        results.append(SOSResponse(
            id=a.id,
            parent_id=a.parent_id,
            parent_name=pname,
            status=a.status,
            triggered_at=a.triggered_at,
            acknowledged_by=a.acknowledged_by,
            acknowledged_at=a.acknowledged_at,
            escalation_level=a.escalation_level,
            notes=a.notes
        ))
    return results

@router.post("", response_model=SOSResponse)
async def create_sos(
    req: SOSCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = current_user.parent_profile or db.query(ParentProfile).filter(ParentProfile.user_id == current_user.id).first()
    parent_id = profile.id if profile else current_user.id
    parent_name = profile.preferred_name if profile else current_user.full_name
    parent_user_id = profile.user_id if profile else current_user.id

    now = datetime.datetime.utcnow()
    time_str = now.strftime("%I:%M %p")

    alert = SOSAlert(
        parent_id=parent_id,
        status="ACTIVE",
        triggered_at=now,
        escalation_level=1,
        notes=req.notes or "Immediate assistance requested by parent"
    )
    db.add(alert)
    db.flush()

    # Step 11: Care Timeline
    timeline_item = CareTimelineItem(
        parent_id=parent_user_id,
        event_time=time_str,
        event_category="SOS",
        title="EMERGENCY SOS TRIGGERED",
        title_tamil="அவசர உதவி கோரிக்கை விடுக்கப்பட்டது",
        description=f"Emergency SOS triggered by {parent_name}: {alert.notes}",
        description_tamil=f"அவசர உதவி கோரிக்கை: {alert.notes}",
        icon="🆘",
        severity="URGENT",
        source="PARENT_SOS",
        created_at=now
    )
    db.add(timeline_item)

    # Step 14: Audit Log
    audit = AuditLog(
        user_id=current_user.id,
        action="SOS_TRIGGERED",
        target_resource=f"SOSAlert:{alert.id}",
        details=f"Parent triggered emergency SOS: {alert.notes}"
    )
    db.add(audit)
    db.commit()
    db.refresh(alert)

    # Broadcast real-time SOS Alert strictly to connected family members over WebSocket
    await ws_manager.send_to_family_of_parent(db, parent_user_id, {
        "type": "SOS_ALERT",
        "sos_id": alert.id,
        "parent_name": parent_name,
        "status": "ACTIVE",
        "time": time_str,
        "notes": alert.notes
    })

    return SOSResponse(
        id=alert.id,
        parent_id=parent_id,
        parent_name=parent_name,
        status=alert.status,
        triggered_at=alert.triggered_at,
        acknowledged_by=alert.acknowledged_by,
        acknowledged_at=alert.acknowledged_at,
        escalation_level=alert.escalation_level,
        notes=alert.notes
    )

@router.get("/active", response_model=Optional[SOSResponse])
def get_active_sos(
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
            return None
        profile = parent.parent_profile or db.query(ParentProfile).filter(ParentProfile.user_id == parent.id).first()
        parent_id = profile.id if profile else parent.id

    alert = db.query(SOSAlert).filter(
        SOSAlert.parent_id == parent_id,
        SOSAlert.status.in_(["ACTIVE", "ACKNOWLEDGED"])
    ).order_by(SOSAlert.triggered_at.desc()).first()

    if not alert:
        return None

    profile = db.query(ParentProfile).filter(ParentProfile.id == alert.parent_id).first()
    parent_name = profile.preferred_name if profile else "Amma"

    return SOSResponse(
        id=alert.id,
        parent_id=alert.parent_id,
        parent_name=parent_name,
        status=alert.status,
        triggered_at=alert.triggered_at,
        acknowledged_by=alert.acknowledged_by,
        acknowledged_at=alert.acknowledged_at,
        escalation_level=alert.escalation_level,
        notes=alert.notes
    )

@router.post("/{id}/acknowledge", response_model=SOSResponse)
async def acknowledge_sos(
    id: int,
    req: Optional[SOSAcknowledge] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    alert = db.query(SOSAlert).filter(SOSAlert.id == id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="SOS Alert not found")

    now = datetime.datetime.utcnow()
    responder = (req.responder_name if req and req.responder_name else None) or current_user.full_name or "Family Member"
    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_by = responder
    alert.acknowledged_at = now
    db.commit()
    db.refresh(alert)

    # Resolve parent user id
    prof = db.query(ParentProfile).filter(ParentProfile.id == alert.parent_id).first()
    parent_user_id = prof.user_id if prof else alert.parent_id

    # Broadcast acknowledgment back to specific parent and their care circle
    ack_msg = {
        "type": "SOS_ACKNOWLEDGED",
        "sos_id": alert.id,
        "acknowledged_by": responder,
        "time": now.strftime("%I:%M %p")
    }
    await ws_manager.send_personal_message(ack_msg, user_id=parent_user_id)
    await ws_manager.send_to_family_of_parent(db, parent_user_id, ack_msg)

    profile = db.query(ParentProfile).filter(ParentProfile.id == alert.parent_id).first()
    parent_name = profile.preferred_name if profile else "Amma"

    return SOSResponse(
        id=alert.id,
        parent_id=alert.parent_id,
        parent_name=parent_name,
        status=alert.status,
        triggered_at=alert.triggered_at,
        acknowledged_by=alert.acknowledged_by,
        acknowledged_at=alert.acknowledged_at,
        escalation_level=alert.escalation_level,
        notes=alert.notes
    )

@router.post("/{id}/resolve")
async def resolve_sos(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    alert = db.query(SOSAlert).filter(SOSAlert.id == id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="SOS Alert not found")

    alert.status = "RESOLVED"
    db.commit()

    prof = db.query(ParentProfile).filter(ParentProfile.id == alert.parent_id).first()
    parent_user_id = prof.user_id if prof else alert.parent_id
    resolved_msg = {
        "type": "SOS_RESOLVED",
        "sos_id": alert.id,
        "parent_id": alert.parent_id
    }
    await ws_manager.send_personal_message(resolved_msg, user_id=parent_user_id)
    await ws_manager.send_to_family_of_parent(db, parent_user_id, resolved_msg)

    return {"message": "SOS alert resolved successfully", "status": "RESOLVED"}
