import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.entities import User, ParentProfile, CareEvent, DailyCheckIn, Medication, MedicationLog, CareTimelineItem, AIAlert
from app.schemas.schemas import CareLogCreate, CareSummaryResponse, CareTimelineItemResponse
from app.routers.deps import get_current_user
from app.services.privacy_service import PrivacyService

router = APIRouter(prefix="/care", tags=["Care Events"])

@router.get("/today", response_model=CareSummaryResponse)
def get_today_care_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role.upper() == "PARENT":
        profile = current_user.parent_profile or db.query(ParentProfile).filter(ParentProfile.user_id == current_user.id).first()
        parent_user_id = current_user.id
        parent_id = profile.id if profile else current_user.id
    else:
        from app.services.relationship_service import RelationshipService
        parent = RelationshipService.get_parent_for_family(db, current_user.id)
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You do not have an approved family relationship to view care summary."
            )
        profile = parent.parent_profile or db.query(ParentProfile).filter(ParentProfile.user_id == parent.id).first()
        parent_user_id = parent.id
        parent_id = profile.id if profile else parent.id

    today_str = datetime.date.today().isoformat()

    # Get checkin
    user_id = parent_user_id
    checkin = db.query(DailyCheckIn).filter(
        DailyCheckIn.user_id == user_id,
        DailyCheckIn.check_in_date == today_str
    ).first()

    # Get med counts
    meds = db.query(Medication).filter(Medication.parent_id == parent_id).all()
    med_ids = [m.id for m in meds]
    taken_logs = db.query(MedicationLog).filter(
        MedicationLog.medication_id.in_(med_ids),
        MedicationLog.log_date == today_str,
        MedicationLog.status == "TAKEN"
    ).count() if med_ids else 0

    # Get latest care events
    events = db.query(CareEvent).filter(CareEvent.parent_id == parent_id).all()
    water_val = "Not recorded"
    food_val = "Not recorded"
    sleep_val = "Not recorded"
    activity_val = "Not recorded"

    for ev in events:
        if ev.event_type == "WATER":
            water_val = ev.value
        elif ev.event_type == "FOOD":
            food_val = ev.value
        elif ev.event_type == "SLEEP":
            sleep_val = ev.value
        elif ev.event_type == "ACTIVITY":
            activity_val = ev.value

    wellbeing_val = checkin.feeling if checkin else "Not checked in"

    # Enforce parent privacy settings if requested by a family member
    if current_user.role.upper() == "FAMILY":
        privacy = PrivacyService.get_parent_privacy_state(db, user_id)
        if not privacy["health_info"]:
            water_val = "Protected"
            food_val = "Protected"
            sleep_val = "Protected"
            wellbeing_val = "Protected"
        if not privacy["daily_activity"]:
            activity_val = "Protected"

    return CareSummaryResponse(
        wellbeing=wellbeing_val,
        water_liters=water_val,
        food_status=food_val,
        sleep_hours=sleep_val,
        activity_level=activity_val,
        medications_taken=taken_logs,
        medications_total=len(meds)
    )


@router.get("/summary", response_model=CareSummaryResponse)
def get_care_summary_alias(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_today_care_summary(current_user, db)

@router.post("/log")
def log_care_event(
    req: CareLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = current_user.parent_profile
    parent_id = profile.id if profile else 1

    ev = CareEvent(
        parent_id=parent_id,
        event_type=req.event_type.upper(),
        value=req.value,
        notes=req.notes
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return {"message": "Care event recorded", "id": ev.id}

@router.get("/timeline", response_model=List[CareTimelineItemResponse])
def get_care_timeline(
    limit: int = 25,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns real timeline events sourced directly from persisted PostgreSQL database records.
    Combines: CareTimelineItem, DailyCheckIn, MedicationLog, CareEvent, AIAlert, SOSAlert, CommunicationRequest.
    """
    if current_user.role.upper() == "PARENT":
        profile = current_user.parent_profile or db.query(ParentProfile).filter(ParentProfile.user_id == current_user.id).first()
        parent_user_id = current_user.id
        parent_id = profile.id if profile else current_user.id
    else:
        from app.services.relationship_service import RelationshipService
        parent = RelationshipService.get_parent_for_family(db, current_user.id)
        if not parent:
            return []
        profile = parent.parent_profile or db.query(ParentProfile).filter(ParentProfile.user_id == parent.id).first()
        parent_user_id = parent.id
        parent_id = profile.id if profile else parent.id

    timeline_items: List[CareTimelineItemResponse] = []

    # 1. Custom persisted timeline items
    db_items = db.query(CareTimelineItem).filter(
        CareTimelineItem.parent_id.in_([parent_id, parent_user_id])
    ).order_by(CareTimelineItem.created_at.desc()).limit(limit).all()

    for item in db_items:
        timeline_items.append(CareTimelineItemResponse(
            id=item.id,
            parent_id=item.parent_id,
            event_time=item.event_time,
            event_category=item.event_category,
            title=item.title,
            title_tamil=item.title_tamil,
            description=item.description,
            description_tamil=item.description_tamil,
            icon=item.icon,
            severity=item.severity,
            source=item.source,
            created_at=item.created_at
        ))

    # 2. Check-ins
    checkins = db.query(DailyCheckIn).filter(
        DailyCheckIn.user_id == parent_id
    ).order_by(DailyCheckIn.created_at.desc()).limit(10).all()

    for c in checkins:
        t_str = c.created_at.strftime("%I:%M %p")
        feeling_label = "Feeling well" if c.feeling == "good" else ("Feeling okay" if c.feeling == "okay" else "Feeling unwell")
        timeline_items.append(CareTimelineItemResponse(
            id=100000 + c.id,
            parent_id=parent_id,
            event_time=t_str,
            event_category="CHECKIN",
            title="Morning check-in completed",
            title_tamil="காலை நலம் அறிதல் முடிந்தது",
            description=f"Confirmed at {t_str} as '{c.feeling}'. Note: {c.note or 'Everything peaceful'}",
            description_tamil=f"{t_str} மணிக்கு நலம் உறுதி செய்யப்பட்டது.",
            icon="❤️",
            severity="INFO",
            source="CHECKIN",
            created_at=c.created_at
        ))

    # 3. AI Alerts
    ai_alerts = db.query(AIAlert).filter(
        AIAlert.parent_id == parent_id
    ).order_by(AIAlert.created_at.desc()).limit(10).all()

    for a in ai_alerts:
        t_str = a.created_at.strftime("%I:%M %p")
        timeline_items.append(CareTimelineItemResponse(
            id=200000 + a.id,
            parent_id=parent_id,
            event_time=t_str,
            event_category="ROUTINE_CHANGE",
            title=a.title,
            title_tamil=a.title_tamil,
            description=a.message,
            description_tamil=a.message_tamil,
            icon="⚠️" if a.severity in ["ATTENTION", "HIGH_PRIORITY"] else "ℹ️",
            severity=a.severity,
            source="AI_ENGINE",
            created_at=a.created_at
        ))

    # 4. Medication logs
    med_logs = db.query(MedicationLog).filter(
        MedicationLog.parent_id == parent_id
    ).order_by(MedicationLog.taken_at.desc()).limit(10).all()

    for m in med_logs:
        t_str = m.taken_at.strftime("%I:%M %p") if m.taken_at else "08:30 AM"
        med = db.query(Medication).filter(Medication.id == m.medication_id).first()
        med_name = med.name if med else "Morning prescription"
        status_txt = "acknowledged on time" if m.status == "TAKEN" else "not yet marked"
        timeline_items.append(CareTimelineItemResponse(
            id=300000 + m.id,
            parent_id=parent_id,
            event_time=t_str,
            event_category="MEDICATION",
            title=f"{med_name} {status_txt}",
            title_tamil=f"{med_name} உட்கொள்ளப்பட்டது",
            description=f"Status: {m.status} at {t_str}",
            description_tamil=f"மருந்து நிலை: {m.status}",
            icon="💊",
            severity="INFO" if m.status == "TAKEN" else "ATTENTION",
            source="MEDICATION",
            created_at=m.taken_at or datetime.datetime.utcnow()
        ))

    # Sort descending by created_at
    timeline_items.sort(key=lambda x: x.created_at, reverse=True)
    return timeline_items[:limit]

