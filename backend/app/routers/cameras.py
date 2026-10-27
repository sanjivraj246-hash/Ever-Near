import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database.session import get_db
from app.models.entities import (
    User, ParentProfile, CCTVDevice, CCTVPermission, AuditLog, SafetyEvent,
    PrivacySetting, PrivacyPause, TemporaryPermission, CareCircleMember,
    FamilyRelationship
)
from app.schemas.schemas import CCTVDeviceCreate, CCTVDeviceResponse, SafetyEventResponse
from app.routers.deps import get_current_user

router = APIRouter(prefix="/cameras", tags=["CCTV Cameras"])

@router.get("", response_model=List[CCTVDeviceResponse])
def get_cameras(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role.upper() == "PARENT":
        profile = current_user.parent_profile
        owner_id = profile.id if profile else current_user.id
        parent_user_id = current_user.id
    else:
        from app.services.relationship_service import RelationshipService
        parent = RelationshipService.get_parent_for_family(db, current_user.id)
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You do not have an approved relationship with this parent."
            )
        profile = parent.parent_profile
        owner_id = profile.id if profile else parent.id
        parent_user_id = parent.id

    # Check privacy permissions if user is family / guardian / caregiver
    if current_user.role.upper() in ["FAMILY", "GUARDIAN", "CAREGIVER"]:
        now = datetime.datetime.utcnow()

        # 0. Approved Relationship Check
        rel = db.query(FamilyRelationship).filter(
            FamilyRelationship.family_user_id == current_user.id,
            FamilyRelationship.parent_id == parent_user_id,
            FamilyRelationship.status == "APPROVED"
        ).first()
        if not rel:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You do not have an approved relationship with this parent."
            )

        # 1. Sovereign Privacy Pause Check
        pause = db.query(PrivacyPause).filter(
            PrivacyPause.parent_id == parent_user_id,
            PrivacyPause.is_paused == True
        ).first()
        if pause and pause.paused_until and pause.paused_until > now:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CCTV camera sharing is temporarily paused by Amma's Privacy Pause."
            )

        # 2. Temporary Permission Check
        has_temp_cctv = db.query(TemporaryPermission).filter(
            TemporaryPermission.parent_id == parent_user_id,
            TemporaryPermission.resource_type == "CCTV",
            TemporaryPermission.status == "ACTIVE",
            TemporaryPermission.expires_at > now,
            (TemporaryPermission.grantee_name.like(f"%{current_user.full_name}%")) |
            (TemporaryPermission.grantee_name == current_user.phone)
        ).first()

        # 3. Care Circle Role Permissions
        circle_member = db.query(CareCircleMember).filter(
            CareCircleMember.parent_id == parent_user_id,
            (CareCircleMember.phone == current_user.phone) | (CareCircleMember.name.like(f"%{current_user.full_name}%"))
        ).first()

        if circle_member and circle_member.can_emergency_only and not has_temp_cctv:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Emergency first-responder role cannot access cameras during routine non-emergency periods."
            )

        if circle_member and not circle_member.can_cctv and not has_temp_cctv:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your Care Circle role does not have authorization to view CCTV cameras."
            )

        # 4. Parent Privacy Setting Check
        priv = db.query(PrivacySetting).filter(PrivacySetting.parent_id == parent_user_id).first()
        if priv and not priv.cctv_access and not has_temp_cctv:
            audit = AuditLog(
                user_id=current_user.id,
                action="VIEW_CAMERAS_BLOCKED_BY_PRIVACY",
                target_resource="CCTV_LIST",
                details="Member request for CCTV blocked by Parent Privacy Setting (CCTV: OFF)"
            )
            db.add(audit)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CCTV camera sharing is currently turned OFF by Amma's privacy settings."
            )

        # Log authorized audit entry
        audit = AuditLog(
            user_id=current_user.id,
            action="VIEW_CAMERAS_LIST",
            target_resource="CCTV_LIST",
            details="Care circle member requested active CCTV device overview"
        )
        db.add(audit)
        db.commit()

    devices = db.query(CCTVDevice).filter(
        CCTVDevice.owner_id == owner_id,
        CCTVDevice.enabled == True
    ).all()

    results = []
    for d in devices:
        is_sim = d.stream_url is not None and ("cloudfront.net" in d.stream_url or "sample" in d.stream_url.lower())
        results.append(CCTVDeviceResponse(
            id=d.id,
            name=d.name,
            name_tamil=d.name_tamil,
            location=d.location,
            stream_url=d.stream_url,
            status=d.status,
            enabled=d.enabled,
            is_simulation=is_sim,
            source_type="DEMO / SIMULATED CAMERA" if is_sim else "REAL CAMERA"
        ))
    return results

@router.post("", response_model=CCTVDeviceResponse)
def add_camera(
    req: CCTVDeviceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = current_user.parent_profile
    owner_id = profile.id if profile else 1

    device = CCTVDevice(
        owner_id=owner_id,
        name=req.name,
        location=req.location,
        stream_url=req.stream_url,
        status="LIVE",
        enabled=True
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    is_sim = device.stream_url is not None and ("cloudfront.net" in device.stream_url or "sample" in device.stream_url.lower())
    return CCTVDeviceResponse(
        id=device.id,
        name=device.name,
        name_tamil=device.name_tamil,
        location=device.location,
        stream_url=device.stream_url,
        status=device.status,
        enabled=device.enabled,
        is_simulation=is_sim,
        source_type="DEMO / SIMULATED CAMERA" if is_sim else "REAL CAMERA"
    )

@router.delete("/{id}")
def delete_camera(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    device = db.query(CCTVDevice).filter(CCTVDevice.id == id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Camera not found")

    db.delete(device)
    db.commit()
    return {"message": "Camera removed successfully"}

@router.get("/{id}/events", response_model=List[SafetyEventResponse])
def get_camera_events(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    device = db.query(CCTVDevice).filter(CCTVDevice.id == id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    if current_user.role.upper() == "PARENT":
        profile = current_user.parent_profile or db.query(ParentProfile).filter(ParentProfile.user_id == current_user.id).first()
        owner_id = profile.id if profile else current_user.id
        if device.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden: You do not own this camera.")
    else:
        from app.services.relationship_service import RelationshipService
        parent = RelationshipService.get_parent_for_family(db, current_user.id)
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You do not have an approved relationship with this parent."
            )
        parent_user_id = parent.id
        rel = db.query(FamilyRelationship).filter(
            FamilyRelationship.family_user_id == current_user.id,
            FamilyRelationship.parent_id == parent_user_id,
            FamilyRelationship.status == "APPROVED"
        ).first()
        if not rel:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You do not have an approved relationship with this parent."
            )
        parent_prof = parent.parent_profile or db.query(ParentProfile).filter(ParentProfile.user_id == parent.id).first()
        owner_id = parent_prof.id if parent_prof else parent.id
        if device.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden: Camera does not belong to your linked parent.")

    events = db.query(SafetyEvent).filter(
        SafetyEvent.parent_id == device.owner_id,
        SafetyEvent.source == "CCTV"
    ).order_by(SafetyEvent.created_at.desc()).limit(10).all()
    return events


@router.get("/setup-guide")
def get_camera_setup_guide():
    """
    Verified setup instructions for real IP / RTSP / ONVIF safety cameras.
    Never presents simulated video or fabricated events as live surveillance.
    """
    return {
        "status": "ready",
        "supported_protocols": ["RTSP", "ONVIF", "WebRTC", "HTTP Live Streaming (HLS)"],
        "supported_hardware": [
            "Hikvision / Ezviz (rtsp://admin:password@ip:554/Streaming/Channels/101)",
            "CP Plus (rtsp://admin:password@ip:554/cam/realmonitor?channel=1&subtype=0)",
            "TP-Link Tapo (rtsp://username:password@ip:554/stream1)",
            "Dahua / IMOU (rtsp://admin:password@ip:554/cam/realmonitor?channel=1&subtype=0)"
        ],
        "setup_steps": [
            {
                "step": 1,
                "title": "Enable RTSP on Home IP Camera",
                "title_tamil": "உங்கள் வீட்டு IP கேமராவில் RTSP வசதியை இயக்கவும்",
                "instructions": "In your camera mobile app (Tapo / CP Plus / Hikvision), navigate to Advanced Settings -> Device Account / RTSP and create a local streaming username and password."
            },
            {
                "step": 2,
                "title": "Assign Static IP Address",
                "title_tamil": "கேமராவின் உள்ளூர் IP முகவரியைக் குறித்துக்கொள்ளவும்",
                "instructions": "Assign a static local IP address to the camera in your home Wi-Fi router (e.g. 192.168.1.150)."
            },
            {
                "step": 3,
                "title": "Add Stream in EVER NEAR",
                "title_tamil": "EVER NEAR தளத்தில் கேமரா இணைப்பை சேர்க்கவும்",
                "instructions": "Enter the RTSP stream URL and name the location (e.g., Living Room, Main Entrance)."
            },
            {
                "step": 4,
                "title": "Verify Sovereign Privacy Controls",
                "title_tamil": "தனியுரிமை மற்றும் சுயாட்சி பாதுகாப்பு",
                "instructions": "Amma has sovereign privacy controls. When Amma activates Privacy Pause, the camera feed is immediately blocked across all family dashboards."
            }
        ],
        "privacy_notice": "EVER NEAR strictly adheres to privacy-by-design. Cameras are 100% optional, never mandatory, and sample videos will never be presented as live CCTV."
    }
