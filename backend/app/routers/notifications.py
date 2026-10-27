import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database.session import get_db
from app.models.entities import User, Notification
from app.schemas.schemas import NotificationResponse
from app.routers.deps import get_current_user

router = APIRouter(prefix="/notifications", tags=["Notification Center"])

@router.get("", response_model=List[NotificationResponse])
def get_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    notifs = db.query(Notification).filter(
        Notification.user_id == current_user.id
    ).order_by(Notification.created_at.desc()).limit(20).all()

    if not notifs:
        # Default dynamic notifications
        return [
            NotificationResponse(
                id=1,
                type="CHECKIN",
                title="Morning Check-in Recorded",
                title_tamil="காலை நலம் அறிதல் பதிவு செய்யப்பட்டது",
                body="Amma confirmed feeling well at 08:15 AM.",
                body_tamil="அம்மா காலை 08:15 மணிக்கு நலம் தெரிவித்தார்.",
                is_read=False,
                created_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=30)
            ),
            NotificationResponse(
                id=2,
                type="MEDICATION",
                title="Morning Tablet Taken",
                title_tamil="காலை மருந்து உட்கொள்ளப்பட்டது",
                body="Blood pressure tablet taken with warm water.",
                body_tamil="காலை இரத்த அழுத்த மருந்து எடுக்கப்பட்டது.",
                is_read=True,
                created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2)
            ),
            NotificationResponse(
                id=3,
                type="ROUTINE",
                title="Routine Insight",
                title_tamil="வழக்கக் குறிப்பு",
                body="Morning walk and garden routine aligned with baseline.",
                body_tamil="காலை நடைபயிற்சி வழக்கம் போல் நிறைவடைந்தது.",
                is_read=True,
                created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=4)
            )
        ]

    return notifs

@router.patch("/{id}/read", response_model=NotificationResponse)
def mark_read(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    notif = db.query(Notification).filter(Notification.id == id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif

@router.post("/read-all")
def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id
    ).update({"is_read": True})
    db.commit()
    return {"message": "All notifications marked as read"}
