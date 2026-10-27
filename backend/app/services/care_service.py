import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.entities import DailyCheckIn, Medication, MedicationLog, ParentProfile, CareTimelineItem, AuditLog
from app.schemas.schemas import CheckInCreate
from app.ai.baseline_engine import baseline_engine

class CareService:
    @staticmethod
    def get_today_checkin(db: Session, user_id: int) -> Optional[DailyCheckIn]:
        today_str = datetime.date.today().isoformat()
        return db.query(DailyCheckIn).filter(
            DailyCheckIn.user_id == user_id,
            DailyCheckIn.check_in_date == today_str
        ).first()

    @staticmethod
    def record_checkin(db: Session, user_id: int, req: CheckInCreate) -> DailyCheckIn:
        today_str = datetime.date.today().isoformat()
        now = datetime.datetime.utcnow()
        time_str = now.strftime("%I:%M %p")

        existing = db.query(DailyCheckIn).filter(
            DailyCheckIn.user_id == user_id,
            DailyCheckIn.check_in_date == today_str
        ).first()

        if existing:
            existing.feeling = req.feeling
            existing.feeling_tamil = req.feeling_tamil or existing.feeling_tamil
            existing.voice_input = req.voice_input
            existing.voice_transcript = req.voice_transcript
            existing.note = req.note
            existing.created_at = now
            checkin = existing
        else:
            checkin = DailyCheckIn(
                user_id=user_id,
                feeling=req.feeling,
                feeling_tamil=req.feeling_tamil,
                voice_input=req.voice_input,
                voice_transcript=req.voice_transcript,
                note=req.note,
                check_in_date=today_str,
                created_at=now
            )
            db.add(checkin)

        # Timeline event for checkin (Idempotent update for today's checkin event)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_timeline = db.query(CareTimelineItem).filter(
            CareTimelineItem.parent_id == user_id,
            CareTimelineItem.event_category == "CHECKIN",
            CareTimelineItem.created_at >= today_start
        ).first()

        if today_timeline:
            today_timeline.event_time = time_str
            today_timeline.description = f"Check-in updated feeling '{req.feeling}'. {req.note or ''}".strip()
            today_timeline.description_tamil = f"நலம் புதுப்பிக்கப்பட்டது: {req.feeling_tamil or req.feeling}"
            today_timeline.created_at = now
        else:
            timeline_item = CareTimelineItem(
                parent_id=user_id,
                event_time=time_str,
                event_category="CHECKIN",
                title="Daily check-in completed",
                title_tamil="தினசரி நலம் தெரிவித்தல் முடிந்தது",
                description=f"Check-in recorded feeling '{req.feeling}'. {req.note or ''}".strip(),
                description_tamil=f"நலம் தெரிவிக்கப்பட்டது: {req.feeling_tamil or req.feeling}",
                icon="❤️",
                severity="INFO",
                source="PARENT_ACTION",
                created_at=now
            )
            db.add(timeline_item)

        # Audit Log (Step 14)
        audit = AuditLog(
            user_id=user_id,
            action="PARENT_CHECKIN_SUBMITTED",
            target_resource="DAILY_CHECKIN",
            details=f"Parent check-in registered feeling: {req.feeling}"
        )
        db.add(audit)
        db.commit()
        db.refresh(checkin)

        # Update personal care baseline (Step 4)
        try:
            baseline_engine.calculate_personal_baseline(db, user_id)
        except Exception:
            pass

        return checkin

    @staticmethod
    def get_medications(db: Session, parent_profile_id: int) -> List[Medication]:
        return db.query(Medication).filter(Medication.parent_id == parent_profile_id).all()

    @staticmethod
    def log_medication(db: Session, medication_id: int, parent_id: int, status: str = "TAKEN") -> MedicationLog:
        today_str = datetime.date.today().isoformat()
        log = MedicationLog(
            medication_id=medication_id,
            parent_id=parent_id,
            scheduled_for="08:00 AM",
            taken_at=datetime.datetime.utcnow(),
            status=status.upper(),
            log_date=today_str
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log
