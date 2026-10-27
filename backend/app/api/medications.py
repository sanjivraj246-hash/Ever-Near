import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.models.entities import User, ParentProfile, Medication, MedicationLog
from app.schemas.schemas import MedicationCreate, MedicationResponse, MedicationLogCreate
from app.api.deps import get_current_user
from app.services.care_service import CareService
from app.services.relationship_service import RelationshipService

router = APIRouter(prefix="/medications", tags=["Medications"])

@router.get("", response_model=List[MedicationResponse])
def get_medications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves all prescribed medications and checks if taken today."""
    if current_user.role.upper() == "PARENT":
        profile = current_user.parent_profile
    else:
        parent = RelationshipService.get_parent_for_family(db, current_user.id)
        profile = parent.parent_profile if parent else None

    if not profile:
        return []

    meds = db.query(Medication).filter(Medication.parent_id == profile.id).all()
    today_str = datetime.date.today().isoformat()

    results = []
    for med in meds:
        log = db.query(MedicationLog).filter(
            MedicationLog.medication_id == med.id,
            MedicationLog.log_date == today_str
        ).first()

        results.append(MedicationResponse(
            id=med.id,
            parent_id=med.parent_id,
            name=med.name,
            dosage=med.dosage,
            schedule_time=med.schedule_time,
            period=med.period,
            instructions=med.instructions,
            icon=med.icon,
            today_taken=log.status == "TAKEN" if log else False,
            taken_at=log.taken_at if log else None
        ))

    return results

@router.post("", response_model=MedicationResponse, status_code=status.HTTP_201_CREATED)
def create_medication(
    req: MedicationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Creates a new prescribed medication for the parent.
    Accessible to the parent or authorized family member.
    """
    if current_user.role.upper() == "PARENT":
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
        parent_id = profile.id
    else:
        parent = RelationshipService.get_parent_for_family(db, current_user.id)
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You do not have an approved relationship with this parent."
            )
        profile = parent.parent_profile or db.query(ParentProfile).filter(ParentProfile.user_id == parent.id).first()
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent profile not found.")
        parent_id = profile.id

    new_med = Medication(
        parent_id=parent_id,
        name=req.name.strip(),
        dosage=req.dosage.strip(),
        schedule_time=req.schedule_time.strip(),
        period=req.period.strip() if req.period else "Morning",
        instructions=req.instructions.strip() if req.instructions else "After food",
        icon=req.icon or "pill"
    )
    db.add(new_med)
    db.commit()
    db.refresh(new_med)

    return MedicationResponse(
        id=new_med.id,
        parent_id=new_med.parent_id,
        name=new_med.name,
        dosage=new_med.dosage,
        schedule_time=new_med.schedule_time,
        period=new_med.period,
        instructions=new_med.instructions,
        icon=new_med.icon,
        today_taken=False,
        taken_at=None
    )

@router.post("/{medication_id}/log")
def log_medication(
    medication_id: int,
    req: MedicationLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Logs medication taken or missed for today."""
    med = db.query(Medication).filter(Medication.id == medication_id).first()
    if not med:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found.")

    log = CareService.log_medication(db, medication_id, med.parent_id, req.status)
    return {
        "status": "success",
        "medication_id": medication_id,
        "action": log.status,
        "logged_at": log.taken_at
    }


@router.post("/acknowledge")
def acknowledge_medication(
    medication_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 2: POST /medications/acknowledge
    Acknowledges medication intake. If medication_id is not specified,
    acknowledges the first pending medication for today.
    Persists to PostgreSQL, records Care Timeline, and writes Audit Log.
    """
    from app.models.entities import CareTimelineItem, AuditLog

    if current_user.role.upper() == "PARENT":
        parent_id = current_user.id
        parent_prof = current_user.parent_profile
    else:
        parent = RelationshipService.get_parent_for_family(db, current_user.id)
        if not parent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No linked parent found.")
        parent_id = parent.id
        parent_prof = parent.parent_profile

    prof_id = parent_prof.id if parent_prof else parent_id

    if medication_id:
        med = db.query(Medication).filter(Medication.id == medication_id).first()
    else:
        # Pick first med
        med = db.query(Medication).filter(Medication.parent_id == prof_id).first()

    if not med:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No medication found to acknowledge.")

    log = CareService.log_medication(db, med.id, prof_id, "TAKEN")

    # Care Timeline Item
    now = datetime.datetime.utcnow()
    timeline_item = CareTimelineItem(
        parent_id=parent_id,
        event_time=now.strftime("%I:%M %p"),
        event_category="MEDICATION",
        title=f"Medication confirmed: {med.name}",
        title_tamil=f"மருந்து உட்கொள்ளப்பட்டது: {med.name}",
        description=f"{med.name} ({med.dosage}) taken on schedule.",
        description_tamil=f"{med.name} வழக்கமான நேரத்தில் உட்கொள்ளப்பட்டது.",
        icon="💊",
        severity="INFO",
        source="PARENT_ACTION",
        created_at=now
    )
    db.add(timeline_item)

    # Audit Log
    audit = AuditLog(
        user_id=current_user.id,
        action="MEDICATION_ACKNOWLEDGED",
        target_resource=f"Medication:{med.id}",
        details=f"Parent acknowledged taking {med.name} ({med.dosage})"
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "message": f"{med.name} acknowledged successfully",
        "medication_id": med.id,
        "medication_name": med.name,
        "action": "TAKEN",
        "taken_at": log.taken_at
    }

