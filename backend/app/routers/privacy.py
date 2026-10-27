import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.session import get_db
from app.models.entities import (
    User, ParentProfile, PrivacyPermission, AuditLog, PrivacyPause,
    FamilyRelationship, PrivacySetting, CareTimelineItem
)
from app.schemas.schemas import (
    PrivacyUpdateRequest, PrivacyStatusResponse, AuditLogResponse,
    PrivacyPauseRequest, PrivacyPauseResponse,
    PrivacySettingsUpdateRequest, PrivacySettingsResponse
)
from app.routers.deps import get_current_user
from app.services.relationship_service import RelationshipService

router = APIRouter(prefix="/privacy", tags=["Privacy & Sovereignty"])

def resolve_parent_id_for_user(current_user: User, db: Session) -> int:
    if current_user.role.upper() == "PARENT":
        return current_user.id
    parent = RelationshipService.get_parent_for_family(db, current_user.id)
    if parent:
        return parent.id
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No linked parent found.")

@router.get("/permissions", response_model=PrivacyStatusResponse)
def get_privacy_permissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = resolve_parent_id_for_user(current_user, db)

    # Check if privacy pause is active
    pause = db.query(PrivacyPause).filter(
        PrivacyPause.parent_id == parent_id,
        PrivacyPause.is_paused == True
    ).first()

    now = datetime.datetime.utcnow()
    is_paused_now = False
    if pause and pause.paused_until and pause.paused_until > now:
        is_paused_now = True

    perm = db.query(PrivacyPermission).filter(
        PrivacyPermission.parent_id == parent_id
    ).first()

    if not perm:
        return PrivacyStatusResponse(
            share_health=not is_paused_now,
            share_activity=not is_paused_now,
            share_location=not is_paused_now,
            share_cctv=not is_paused_now,
            share_medication=True
        )

    return PrivacyStatusResponse(
        share_health=False if is_paused_now else perm.share_health,
        share_activity=False if is_paused_now else perm.share_activity,
        share_location=False if is_paused_now else perm.share_location,
        share_cctv=False if is_paused_now else perm.share_cctv,
        share_medication=perm.share_medication  # Meds remain visible for safety
    )

@router.post("/permissions", response_model=PrivacyStatusResponse)
def update_privacy_permissions(
    req: PrivacyUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role.upper() != "PARENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the parent can modify sovereign sharing permissions."
        )
    parent_id = current_user.id
    perm = db.query(PrivacyPermission).filter(
        PrivacyPermission.parent_id == parent_id
    ).first()

    if not perm:
        perm = PrivacyPermission(
            parent_id=parent_id,
            family_user_id=req.family_user_id or 2,
            share_health=True if req.share_health is None else req.share_health,
            share_activity=True if req.share_activity is None else req.share_activity,
            share_location=True if req.share_location is None else req.share_location,
            share_cctv=True if req.share_cctv is None else req.share_cctv,
            share_medication=True if req.share_medication is None else req.share_medication
        )
        db.add(perm)
    else:
        if req.share_health is not None:
            perm.share_health = req.share_health
        if req.share_activity is not None:
            perm.share_activity = req.share_activity
        if req.share_location is not None:
            perm.share_location = req.share_location
        if req.share_cctv is not None:
            perm.share_cctv = req.share_cctv
        if req.share_medication is not None:
            perm.share_medication = req.share_medication
        perm.updated_at = datetime.datetime.utcnow()

    # Create audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="UPDATE_PRIVACY_PERMISSIONS",
        target_resource="PERMISSIONS",
        details="Parent updated granular sharing permissions"
    )
    db.add(audit)
    db.commit()
    db.refresh(perm)

    return PrivacyStatusResponse(
        share_health=perm.share_health,
        share_activity=perm.share_activity,
        share_location=perm.share_location,
        share_cctv=perm.share_cctv,
        share_medication=perm.share_medication
    )

@router.post("/pause", response_model=PrivacyPauseResponse)
def set_privacy_pause(
    req: PrivacyPauseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Privacy Pause: Parent can temporarily pause camera, activity, and location
    sharing for 15, 30, or 60 minutes while Emergency SOS remains strictly active.
    """
    if current_user.role.upper() != "PARENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the parent can activate Privacy Pause."
        )
    parent_id = current_user.id
    now = datetime.datetime.utcnow()
    until = now + datetime.timedelta(minutes=req.duration_minutes)

    pause = db.query(PrivacyPause).filter(PrivacyPause.parent_id == parent_id).first()
    if not pause:
        pause = PrivacyPause(
            parent_id=parent_id,
            is_paused=True,
            paused_until=until,
            duration_minutes=req.duration_minutes
        )
        db.add(pause)
    else:
        pause.is_paused = True
        pause.paused_until = until
        pause.duration_minutes = req.duration_minutes

    audit = AuditLog(
        user_id=current_user.id,
        action="PRIVACY_PAUSE_ACTIVATED",
        target_resource="SOVEREIGNTY",
        details=f"Parent activated Privacy Pause for {req.duration_minutes} minutes"
    )
    db.add(audit)
    db.commit()
    db.refresh(pause)

    return PrivacyPauseResponse(
        is_paused=True,
        paused_until=pause.paused_until,
        duration_minutes=pause.duration_minutes,
        emergency_remains_active=True
    )

@router.get("/pause", response_model=PrivacyPauseResponse)
def get_privacy_pause_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = resolve_parent_id_for_user(current_user, db)

    pause = db.query(PrivacyPause).filter(PrivacyPause.parent_id == parent_id).first()
    now = datetime.datetime.utcnow()
    if pause and pause.is_paused and pause.paused_until and pause.paused_until > now:
        return PrivacyPauseResponse(
            is_paused=True,
            paused_until=pause.paused_until,
            duration_minutes=pause.duration_minutes,
            emergency_remains_active=True
        )

    return PrivacyPauseResponse(
        is_paused=False,
        paused_until=None,
        duration_minutes=0,
        emergency_remains_active=True
    )

@router.post("/resume", response_model=PrivacyPauseResponse)
def resume_privacy_sharing(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role.upper() != "PARENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the parent can resume privacy sharing."
        )
    parent_id = current_user.id
    pause = db.query(PrivacyPause).filter(PrivacyPause.parent_id == parent_id).first()
    if pause:
        pause.is_paused = False
        pause.paused_until = None
        db.commit()

    audit = AuditLog(
        user_id=current_user.id,
        action="PRIVACY_PAUSE_RESUMED",
        target_resource="SOVEREIGNTY",
        details="Parent manually resumed normal sharing"
    )
    db.add(audit)
    db.commit()

    return PrivacyPauseResponse(
        is_paused=False,
        paused_until=None,
        duration_minutes=0,
        emergency_remains_active=True
    )

@router.get("/audit-logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(30).all()
    if not logs:
        sample = AuditLog(
            id=1,
            user_id=current_user.id,
            action="INITIAL_PERMISSION_SETUP",
            target_resource="SOVEREIGNTY",
            timestamp=datetime.datetime.utcnow(),
            details="Privacy boundaries established with parent sovereign encryption"
        )
        return [sample]
    return logs


# ============================================================================
# STEP 13: REAL PARENT-CONTROLLED PRIVACY SETTINGS
# ============================================================================

@router.get("/settings", response_model=PrivacySettingsResponse)
def get_privacy_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 13 — Privacy Control:
    Retrieves the Parent-controlled privacy boundaries persisted in PostgreSQL.
    Health information: ON
    Daily activity: ON
    Location: OFF
    CCTV: OFF
    Memories: ON
    """
    parent_id = resolve_parent_id_for_user(current_user, db)

    setting = db.query(PrivacySetting).filter(PrivacySetting.parent_id == parent_id).first()
    if not setting:
        setting = PrivacySetting(
            parent_id=parent_id,
            health_info=True,
            daily_activity=True,
            location_sharing=False,
            cctv_access=False,
            memories_sharing=True
        )
        db.add(setting)
        db.commit()
        db.refresh(setting)

    return setting


@router.post("/settings", response_model=PrivacySettingsResponse)
def update_privacy_settings(
    req: PrivacySettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 13 — Parent updates privacy boundaries.
    Enforced in backend: if Location is OFF, family cannot receive location;
    if CCTV is OFF, family cannot receive CCTV information.
    Creates an Audit Log and records event to Care Timeline.
    """
    if current_user.role.upper() != "PARENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the parent can modify sovereign privacy boundaries."
        )
    parent_id = current_user.id

    setting = db.query(PrivacySetting).filter(PrivacySetting.parent_id == parent_id).first()
    if not setting:
        setting = PrivacySetting(
            parent_id=parent_id,
            health_info=req.health_info if req.health_info is not None else True,
            daily_activity=req.daily_activity if req.daily_activity is not None else True,
            location_sharing=req.location_sharing if req.location_sharing is not None else False,
            cctv_access=req.cctv_access if req.cctv_access is not None else False,
            memories_sharing=req.memories_sharing if req.memories_sharing is not None else True
        )
        db.add(setting)
    else:
        if req.health_info is not None:
            setting.health_info = req.health_info
        if req.daily_activity is not None:
            setting.daily_activity = req.daily_activity
        if req.location_sharing is not None:
            setting.location_sharing = req.location_sharing
        if req.cctv_access is not None:
            setting.cctv_access = req.cctv_access
        if req.memories_sharing is not None:
            setting.memories_sharing = req.memories_sharing
        setting.updated_at = datetime.datetime.utcnow()

    # Also sync legacy PrivacyPermission if exists
    perm = db.query(PrivacyPermission).filter(PrivacyPermission.parent_id == parent_id).first()
    if perm:
        perm.share_health = setting.health_info
        perm.share_activity = setting.daily_activity
        perm.share_location = setting.location_sharing
        perm.share_cctv = setting.cctv_access
        perm.updated_at = datetime.datetime.utcnow()

    # Create Audit Log (Step 14)
    audit = AuditLog(
        user_id=current_user.id,
        action="UPDATE_PRIVACY_SETTINGS",
        target_resource="PRIVACY_CONTROL",
        details=f"Parent updated privacy toggles: Health={setting.health_info}, Activity={setting.daily_activity}, Location={setting.location_sharing}, CCTV={setting.cctv_access}"
    )
    db.add(audit)

    # Care Timeline
    now = datetime.datetime.utcnow()
    timeline_item = CareTimelineItem(
        parent_id=parent_id,
        event_time=now.strftime("%I:%M %p"),
        event_category="PRIVACY",
        title="Privacy boundaries updated",
        title_tamil="தனியுரிமை அமைப்புகள் மாற்றப்பட்டன",
        description=f"Parent updated privacy controls (CCTV: {'ON' if setting.cctv_access else 'OFF'}, Location: {'ON' if setting.location_sharing else 'OFF'})",
        description_tamil=f"தனியுரிமை அமைப்புகள் புதுப்பிக்கப்பட்டன.",
        icon="🔒",
        severity="INFO",
        source="PARENT_CONTROL",
        created_at=now
    )
    db.add(timeline_item)

    db.commit()
    db.refresh(setting)

    return setting

