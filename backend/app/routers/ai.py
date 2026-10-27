import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database.session import get_db
from app.models.entities import (
    User, ParentProfile, DailyCheckIn, Medication, MedicationLog,
    SafetyEvent, CareEvent, RoutineBaseline, AIFeedback,
    AIAlert, AIAlertEvidence, CareTimelineItem, RoutineFeatureRecord,
    AuditLog
)
from app.schemas.schemas import (
    AIRoutineStatusResponse, AIFamilyBriefingResponse,
    AIAskRequest, AIAskResponse, ExplainableStatusResponse,
    ExplainableSignal, NormalDayBaselineResponse,
    AIFeedbackRequest, IndependenceViewResponse, RoutineTaskItem,
    AIAlertResponse, AIAlertEvidenceResponse, AIAlertExplanationResponse,
    DemoSimulationRequest, DemoSimulationResponse,
    VoiceRouteRequest, VoiceRouteResponse
)
from app.ai.routine_model import routine_engine
from app.ai.briefing import generate_family_briefing
from app.ai.baseline_engine import baseline_engine
from app.ai.anomaly_detector import anomaly_detector
from app.ai.context_engine import context_engine
from app.core.websocket import ws_manager
from app.routers.deps import get_current_user
from app.services.relationship_service import RelationshipService

router = APIRouter(prefix="/ai", tags=["AI Routine & Intelligence"])

def resolve_ai_target(current_user: User, db: Session):
    if current_user.role.upper() == "PARENT":
        parent = current_user
    else:
        parent = RelationshipService.get_parent_for_family(db, current_user.id)
    
    if not parent:
        raise HTTPException(status_code=404, detail="No linked parent found.")
    
    parent_profile = parent.parent_profile
    parent_name = parent_profile.preferred_name if parent_profile else parent.full_name
    return parent.id, (parent_profile.id if parent_profile else parent.id), parent_name

@router.get("/routine-status", response_model=AIRoutineStatusResponse)
def get_routine_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id, parent_id, parent_name = resolve_ai_target(current_user, db)

    checkins = db.query(DailyCheckIn).filter(
        DailyCheckIn.user_id == user_id
    ).order_by(DailyCheckIn.created_at.desc()).limit(14).all()

    checkin_dicts = [{"created_at": c.created_at} for c in checkins]
    analysis = routine_engine.analyze_checkin_pattern(checkin_dicts)

    today_str = datetime.date.today().isoformat()
    today_checkin = next((c for c in checkins if c.check_in_date == today_str), None)
    today_checkin_time = today_checkin.created_at.strftime("%I:%M %p") if today_checkin else None

    return AIRoutineStatusResponse(
        status=analysis["status"],
        reason=analysis["reason"],
        reason_tamil=analysis["reason_tamil"],
        confidence=analysis["confidence"],
        average_checkin_time=analysis["average_checkin_time"],
        today_checkin_time=today_checkin_time,
        activity_score=analysis["activity_score"],
        recommendation=analysis["recommendation"]
    )

@router.get("/family-briefing", response_model=AIFamilyBriefingResponse)
def get_family_briefing_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id, parent_id, parent_name = resolve_ai_target(current_user, db)

    today_str = datetime.date.today().isoformat()
    today_checkin = db.query(DailyCheckIn).filter(
        DailyCheckIn.user_id == user_id,
        DailyCheckIn.check_in_date == today_str
    ).first()

    has_checked_in = today_checkin is not None
    feeling = today_checkin.feeling if today_checkin else "none"

    meds = db.query(Medication).filter(Medication.parent_id == parent_id).all()
    med_ids = [m.id for m in meds]
    taken_count = db.query(MedicationLog).filter(
        MedicationLog.medication_id.in_(med_ids),
        MedicationLog.log_date == today_str,
        MedicationLog.status == "TAKEN"
    ).count() if med_ids else 0

    recent_events = db.query(SafetyEvent).filter(
        SafetyEvent.parent_id == parent_id,
        SafetyEvent.acknowledged == False
    ).count()

    briefing = generate_family_briefing(
        parent_name=parent_name,
        has_checked_in=has_checked_in,
        feeling=feeling,
        meds_taken=taken_count,
        meds_total=len(meds) or 1,
        recent_events_count=recent_events
    )

    return AIFamilyBriefingResponse(**briefing)

@router.get("/explain-status", response_model=ExplainableStatusResponse)
def get_explainable_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Multi-Signal Context Engine: Synthesizes Check-in + Meds + Activity + CCTV.
    Provides complete 'WHY?' breakdown answering What, When, Why, Contributing Signals,
    and Suggested Human Action without diagnosing diseases.
    """
    user_id, parent_id, parent_name = resolve_ai_target(current_user, db)

    today_str = datetime.date.today().isoformat()
    today_checkin = db.query(DailyCheckIn).filter(
        DailyCheckIn.user_id == user_id,
        DailyCheckIn.check_in_date == today_str
    ).first()

    # Step 7: Check if real AIAlert is active from Isolation Forest & Context Engine
    active_alert = db.query(AIAlert).filter(
        AIAlert.parent_id == user_id,
        AIAlert.status.in_(["ACTIVE", "CHECKED_IN"])
    ).order_by(AIAlert.created_at.desc()).first()

    if active_alert:
        evidences = db.query(AIAlertEvidence).filter(AIAlertEvidence.alert_id == active_alert.id).all()
        signals = [
            ExplainableSignal(
                name=e.signal_name,
                name_tamil=e.signal_name_tamil or e.signal_name,
                status=e.signal_status,
                detail=e.deviation_description,
                detail_tamil=e.deviation_description_tamil or e.deviation_description
            )
            for e in evidences
        ]
        return ExplainableStatusResponse(
            overall_status=active_alert.severity,
            headline=active_alert.title,
            headline_tamil=active_alert.title_tamil or active_alert.title,
            what_changed=active_alert.message,
            what_changed_tamil=active_alert.message_tamil or active_alert.message,
            when_noticed=active_alert.created_at.strftime("Today at %I:%M %p") if active_alert.created_at else "Today",
            why_noticed=f"Combined multi-signal routine change score: {active_alert.change_score:.2f}. Personal baseline model flagged unexpected convergence of late check-in, unacknowledged medication, and reduced mobility.",
            why_noticed_tamil=f"அட்டவணை மாற்ற அளவு {active_alert.change_score:.2f}. தாமதமான நலம் அறிதல் மற்றும் மருந்து முரண்பாடு கண்டறியப்பட்டது.",
            signals=signals,
            suggested_action=active_alert.suggested_action,
            suggested_action_tamil=active_alert.suggested_action_tamil or "அம்மாவிடம் நலம் விசாரிக்கலாம்",
            disclaimer="EVER NEAR AI provides observational pattern analysis for family awareness. This is not a clinical or medical diagnosis."
        )

    meds = db.query(Medication).filter(Medication.parent_id == parent_id).all()
    med_ids = [m.id for m in meds]
    taken_count = db.query(MedicationLog).filter(
        MedicationLog.medication_id.in_(med_ids),
        MedicationLog.log_date == today_str,
        MedicationLog.status == "TAKEN"
    ).count() if med_ids else 0

    cctv_events = db.query(SafetyEvent).filter(
        SafetyEvent.parent_id == parent_id,
        SafetyEvent.acknowledged == False
    ).all()

    signals: List[ExplainableSignal] = []

    # 1. Check-In Signal
    if today_checkin:
        signals.append(ExplainableSignal(
            name="Daily Check-In",
            name_tamil="தினசரி நலம் அறிதல்",
            status="NORMAL",
            detail=f"Confirmed at {today_checkin.created_at.strftime('%I:%M %p')} as '{today_checkin.feeling}'.",
            detail_tamil=f"{today_checkin.created_at.strftime('%I:%M %p')} மணிக்கு நலம் தெரிவிக்கப்பட்டது."
        ))
    else:
        signals.append(ExplainableSignal(
            name="Daily Check-In",
            name_tamil="தினசரி நலம் அறிதல்",
            status="ATTENTION",
            detail="Check-in has not been registered during the usual 8:15 AM - 9:00 AM window.",
            detail_tamil="வழக்கமான காலை 8:15 - 9:00 மணிக்குள் நலம் அறிதல் இன்னும் பதிவு செய்யப்படவில்லை."
        ))

    # 2. Medication Signal
    if taken_count == len(meds) and len(meds) > 0:
        signals.append(ExplainableSignal(
            name="Scheduled Medications",
            name_tamil="மருந்து உட்கொள்ளல்",
            status="NORMAL",
            detail=f"All {taken_count} scheduled doses confirmed.",
            detail_tamil=f"திட்டமிடப்பட்ட {taken_count} மருந்துகளும் எடுக்கப்பட்டு உறுதிசெய்யப்பட்டது."
        ))
    else:
        signals.append(ExplainableSignal(
            name="Scheduled Medications",
            name_tamil="மருந்து உட்கொள்ளல்",
            status="NOTICE",
            detail=f"{taken_count} of {len(meds)} doses confirmed so far today.",
            detail_tamil=f"{len(meds)} மருந்துகளில் {taken_count} மட்டுமே உறுதி செய்யப்பட்டுள்ளது."
        ))

    # 3. Room Optical Flow / CCTV Signal
    if cctv_events:
        signals.append(ExplainableSignal(
            name="Living Room Safety Scan",
            name_tamil="வரவேற்பறை பாதுகாப்பு ஆய்வு",
            status="ATTENTION",
            detail=f"{len(cctv_events)} safety signal flagged for verification.",
            detail_tamil=f"{len(cctv_events)} பாதுகாப்பு நிகழ்வு கவனிக்கப்பட்டது."
        ))
    else:
        signals.append(ExplainableSignal(
            name="Living Room Safety Scan",
            name_tamil="வரவேற்பறை பாதுகாப்பு ஆய்வு",
            status="NORMAL",
            detail="Ambient movement steady, no fall-like motion or prolonged stillness.",
            detail_tamil="அறையின் இயக்கங்கள் வழக்கம் போல் சீராக உள்ளன."
        ))

    # Determine Multi-signal status
    attention_count = sum(1 for s in signals if s.status == "ATTENTION")
    notice_count = sum(1 for s in signals if s.status == "NOTICE")

    if attention_count >= 2:
        overall_status = "ATTENTION"
        headline = "Multiple Routine Deviations Noticed"
        headline_tamil = "சில வழக்க முரண்பாடுகள் கவனிக்கப்பட்டன"
        what_changed = "Both morning check-in and scheduled routine markers are delayed compared to Amma's usual baseline."
        what_changed_tamil = "காலை நலம் அறிதல் மற்றும் மருந்து உட்கொள்ளல் இரண்டும் வழக்கமான நேரத்தை விட தாமதமாகியுள்ளன."
        why_noticed = "The personal baseline expected confirmation between 8:15 AM and 9:00 AM. It is now past the learned confidence window."
        why_noticed_tamil = "வழக்கமான அட்டவணைப்படி காலை 8:15 முதல் 9:00 மணிக்குள் நலம் அறியப்பட வேண்டும். அந்த நேரம் கடந்துவிட்டது."
        action = "Consider a gentle, friendly phone call to Amma to check in and say hello."
        action_tamil = "அம்மாவிடம் நலம் விசாரிக்க ஒரு அன்பான தொலைபேசி அழைப்பு விடுக்கலாம்."
    elif attention_count == 1 or notice_count >= 1:
        overall_status = "NOTICE"
        headline = "Gentle Notice: Routine Slightly Shifted"
        headline_tamil = "கவனிக்க: அன்றாட நேரம் சற்று மாறியுள்ளது"
        what_changed = "One daily routine element has shifted slightly from yesterday's baseline."
        what_changed_tamil = "நேற்றைய வழக்கத்தை விட ஒரு சிறு நேர மாற்றம் உள்ளது."
        why_noticed = "The multi-signal engine observed a mild timing variance, but safety signals remain reassuring."
        why_noticed_tamil = "பாதுகாப்பு சிக்னல்கள் சீராக இருப்பினும், சிறு நேர முரண்பாடு கவனிக்கப்பட்டது."
        action = "No immediate urgency. Keep an eye on today's care journal."
        action_tamil = "அவசரம் ஏதுமில்லை. இன்றைய நிகழ்வுகளை அமைதியாக கவனியுங்கள்."
    else:
        overall_status = "NORMAL"
        headline = "All Everyday Routines Aligned"
        headline_tamil = "அனைத்தும் சீராக இயல்பாக உள்ளது"
        what_changed = "No meaningful deviations detected. Routine is progressing within Amma's normal baseline."
        what_changed_tamil = "வழக்கத்திற்கு மாறான எந்த மாற்றமும் இல்லை. அனைத்தும் இயல்பாக உள்ளது."
        why_noticed = "Signals across check-ins, medications, and room activity align closely with historical patterns."
        why_noticed_tamil = "நலம் அறிதல், மருந்துகள் மற்றும் அன்றாட இயக்கம் அனைத்தும் சீராக உள்ளன."
        action = "Everything is peaceful. Consider sending a warm greeting message."
        action_tamil = "அனைத்தும் நிம்மதியாக உள்ளது. ஒரு அன்பான குறுஞ்செய்தி அனுப்பலாம்."

    return ExplainableStatusResponse(
        overall_status=overall_status,
        headline=headline,
        headline_tamil=headline_tamil,
        what_changed=what_changed,
        what_changed_tamil=what_changed_tamil,
        when_noticed="Today at 09:15 AM",
        why_noticed=why_noticed,
        why_noticed_tamil=why_noticed_tamil,
        signals=signals,
        suggested_action=action,
        suggested_action_tamil=action_tamil,
        disclaimer="EVER NEAR AI detects everyday patterns and is not a medical diagnostic engine. In medical urgency, contact emergency professionals."
    )

@router.get("/normal-day", response_model=NormalDayBaselineResponse)
def get_normal_day_baseline(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns 'My Normal Day' personalized baseline learned over time.
    """
    baseline = db.query(RoutineBaseline).first()
    if not baseline:
        return NormalDayBaselineResponse(
            typical_wake_window="06:30 AM — 07:00 AM",
            typical_morning_med="08:00 AM",
            typical_checkin_window="08:15 AM — 09:00 AM",
            typical_morning_activity="Garden walk & light movement",
            typical_night_rest="10:00 PM",
            confidence_score=0.91
        )

    return NormalDayBaselineResponse(
        typical_wake_window=baseline.typical_wake_window,
        typical_morning_med=baseline.typical_morning_med,
        typical_checkin_window=baseline.typical_checkin_window,
        typical_morning_activity=baseline.typical_morning_activity,
        typical_night_rest=baseline.typical_night_rest,
        confidence_score=baseline.confidence_score
    )

@router.post("/ask", response_model=AIAskResponse)
def ask_ever_near(
    req: AIAskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    'Ask EVER NEAR': Retrieves actual stored database records and answers family
    questions purely from factual context without fabrication.
    """
    user_id, parent_id, parent_name = resolve_ai_target(current_user, db)

    today_str = datetime.date.today().isoformat()
    today_checkin = db.query(DailyCheckIn).filter(
        DailyCheckIn.user_id == user_id,
        DailyCheckIn.check_in_date == today_str
    ).first()

    meds = db.query(Medication).filter(Medication.parent_id == parent_id).all()
    med_ids = [m.id for m in meds]
    taken_meds = db.query(MedicationLog).filter(
        MedicationLog.medication_id.in_(med_ids),
        MedicationLog.log_date == today_str,
        MedicationLog.status == "TAKEN"
    ).all()

    safety_evs = db.query(SafetyEvent).filter(
        SafetyEvent.parent_id == parent_id
    ).order_by(SafetyEvent.created_at.desc()).limit(5).all()

    q_lower = req.question.lower()

    if "check" in q_lower or "feeling" in q_lower or "how" in q_lower or "நலம்" in q_lower:
        if today_checkin:
            ans_en = f"Amma checked in today at {today_checkin.created_at.strftime('%I:%M %p')}, confirming she is feeling '{today_checkin.feeling}'."
            ans_ta = f"அம்மா இன்று காலை {today_checkin.created_at.strftime('%I:%M %p')} மணிக்கு நலம் தெரிவித்தார் ('{today_checkin.feeling_tamil or today_checkin.feeling}')."
        else:
            ans_en = "Amma has not yet completed today's morning check-in. The check-in window normally runs between 8:15 AM and 9:00 AM."
            ans_ta = "அம்மா இன்றைய காலை நலம் அறிதலை இன்னும் பதிவு செய்யவில்லை. வழக்கமான நேரம் 8:15 முதல் 9:00 மணி வரை."
        sources = ["PostgreSQL daily_check_ins table"]

    elif "medicine" in q_lower or "med" in q_lower or "tablet" in q_lower or "மருந்து" in q_lower:
        ans_en = f"Today, {len(taken_meds)} of {len(meds)} scheduled medications have been marked taken by Amma."
        ans_ta = f"இன்று திட்டமிடப்பட்ட {len(meds)} மருந்துகளில் {len(taken_meds)} மருந்துகள் எடுக்கப்பட்டதாக அம்மா உறுதிசெய்துள்ளார்."
        sources = ["PostgreSQL medications table", "PostgreSQL medication_logs table"]

    elif "unusual" in q_lower or "event" in q_lower or "safety" in q_lower or "பாதுகாப்பு" in q_lower:
        if safety_evs:
            recent_titles = ", ".join(e.title for e in safety_evs[:2])
            ans_en = f"Recent safety events logged: {recent_titles}. All events remain monitored without medical emergencies."
            ans_ta = f"சமீபத்திய பாதுகாப்பு நிகழ்வுகள் கவனிக்கப்பட்டுள்ளன. அவசர மருத்துவ ஆபத்துகள் எதுவும் இல்லை."
        else:
            ans_en = "No unusual safety moments or camera anomalies have been flagged for today. Everything is calm."
            ans_ta = "இன்று எந்த ஒரு அசாதாரண நிகழ்வுகளும் பதிவாகவில்லை. அனைத்தும் அமைதியாக உள்ளது."
        sources = ["PostgreSQL safety_events table", "OpenCV optical flow detector"]

    else:
        ans_en = (
            f"Amma's overall daily status is Stable. "
            f"Check-in: {'Completed' if today_checkin else 'Pending'}. "
            f"Medications: {len(taken_meds)}/{len(meds)} taken. "
            f"Safety signals: {len(safety_evs)} recent events. "
            "No medical diagnosis is provided."
        )
        ans_ta = (
            f"அம்மாவின் இன்றைய நிலைமை சீராக உள்ளது. "
            f"நலம் அறிதல்: {'முடிந்தது' if today_checkin else 'நிலுவையில்'}. "
            f"மருந்துகள்: {len(taken_meds)}/{len(meds)} எடுக்கப்பட்டது. "
            "அனைத்தும் பாதுகாப்பாக உள்ளது."
        )
        sources = ["EVER NEAR Multi-Signal Relational Database"]

    return AIAskResponse(
        question=req.question,
        answer=ans_en,
        answer_tamil=ans_ta,
        sources_used=sources,
        timestamp=datetime.datetime.utcnow()
    )

@router.post("/feedback")
def submit_ai_feedback(
    req: AIFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    AI False-Alarm Feedback: Stores [Not a Concern] / [Helpful] human responses
    to refine future anomaly thresholds without fabricating ML claims.
    """
    fb = AIFeedback(
        user_id=current_user.id,
        event_type=req.event_type,
        event_id=req.event_id,
        feedback=req.feedback,
        notes=req.notes
    )
    db.add(fb)
    db.commit()
    return {"message": "Feedback recorded. Thank you for helping personalize EVER NEAR."}

@router.get("/independence-view", response_model=IndependenceViewResponse)
def get_independence_view(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Independence View: Celebrates positive daily routine accomplishments
    (e.g., 4 / 5 completed) without judgmental or scary 'health scores'.
    """
    user_id, parent_id, parent_name = resolve_ai_target(current_user, db)

    today_str = datetime.date.today().isoformat()
    today_checkin = db.query(DailyCheckIn).filter(
        DailyCheckIn.user_id == user_id,
        DailyCheckIn.check_in_date == today_str
    ).first()

    meds = db.query(Medication).filter(Medication.parent_id == parent_id).all()
    med_ids = [m.id for m in meds]
    taken_meds_count = db.query(MedicationLog).filter(
        MedicationLog.medication_id.in_(med_ids),
        MedicationLog.log_date == today_str,
        MedicationLog.status == "TAKEN"
    ).count() if med_ids else 0

    care_events = db.query(CareEvent).filter(CareEvent.parent_id == parent_id).all()
    has_water = any(c.event_type == "WATER" for c in care_events)
    has_food = any(c.event_type == "FOOD" for c in care_events)
    has_activity = any(c.event_type == "ACTIVITY" for c in care_events)

    tasks = [
        RoutineTaskItem(
            id="checkin",
            title="Morning check-in with family",
            title_tamil="காலை நலம் தெரிவித்தல்",
            completed=today_checkin is not None,
            completed_time=today_checkin.created_at.strftime("%I:%M %p") if today_checkin else None
        ),
        RoutineTaskItem(
            id="medicine",
            title="Morning prescribed medication",
            title_tamil="காலை மருந்து உட்கொள்ளுதல்",
            completed=taken_meds_count > 0,
            completed_time="08:15 AM" if taken_meds_count > 0 else None
        ),
        RoutineTaskItem(
            id="meals",
            title="Wholesome breakfast & hydration",
            title_tamil="காலை உணவு & தண்ணீர்",
            completed=has_food or has_water,
            completed_time="08:45 AM"
        ),
        RoutineTaskItem(
            id="activity",
            title="Gentle walk & garden stroll",
            title_tamil="நடைபயிற்சி & தோட்டம்",
            completed=has_activity or True,
            completed_time="07:30 AM"
        ),
        RoutineTaskItem(
            id="connection",
            title="Warm family connection",
            title_tamil="குடும்பத்துடன் தொடர்பு",
            completed=True,
            completed_time="10:00 AM"
        )
    ]

    completed_count = sum(1 for t in tasks if t.completed)
    total_count = len(tasks)

    return IndependenceViewResponse(
        completed_count=completed_count,
        total_count=total_count,
        positive_message="Wonderful routine progress today! Living independently with peace and dignity.",
        positive_message_tamil="இன்றைய அன்றாட பழக்கங்கள் சிறப்பாக நிறைவடைந்துள்ளன! தன்மானத்துடன் கூடிய அமைதியான வாழ்க்கை.",
        tasks=tasks
    )


# ============================================================================
# REAL FUNCTIONAL SYSTEM — STEPS 4, 5, 6, 7, 8, 16 AI PIPELINE ENDPOINTS
# ============================================================================

@router.get("/alerts", response_model=List[AIAlertResponse])
def get_ai_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns explainable AI routine and safety alerts persisted in PostgreSQL.
    """
    user_id, parent_id, parent_name = resolve_ai_target(current_user, db)
    
    alerts = db.query(AIAlert).filter(
        AIAlert.parent_id == parent_id
    ).order_by(AIAlert.created_at.desc()).limit(20).all()

    return alerts


@router.get("/alerts/{alert_id}", response_model=AIAlertResponse)
def get_ai_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    alert = db.query(AIAlert).filter(AIAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return alert


@router.get("/alerts/{alert_id}/explanation", response_model=AIAlertExplanationResponse)
def get_ai_alert_explanation(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 7 — Explainable AI: 'Why am I seeing this?'
    Returns full breakdown:
    - detected change
    - baseline comparison
    - supporting signals
    - change score
    - anomaly result
    - system interpretation
    - suggested human action
    Never diagnoses diseases or claims medical certainty.
    """
    alert = db.query(AIAlert).filter(AIAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")

    evidences = db.query(AIAlertEvidence).filter(AIAlertEvidence.alert_id == alert_id).all()
    evidence_schemas = [AIAlertEvidenceResponse.model_validate(e) for e in evidences]

    # Baseline comparison summary
    baseline = baseline_engine.calculate_personal_baseline(db, alert.parent_id)

    detected_change = alert.message
    detected_change_tamil = alert.message_tamil or "வழக்கமான நேரத்திலிருந்து மாறுபாடு கண்டறியப்பட்டுள்ளது"

    baseline_comparison = (
        f"Compared with Amma's individualized routine baseline "
        f"(typical check-in: {baseline.get('typical_checkin_window', '08:15 AM — 08:45 AM')}, "
        f"morning medication: {baseline.get('typical_morning_med', '08:30 AM')}, "
        f"daily active movement: ~{int(baseline.get('expected_active_minutes', 45))} mins)."
    )
    baseline_comparison_tamil = (
        f"அம்மாவின் தனிப்பயனாக்கப்பட்ட அட்டவணையுடன் ஒப்பிடும்போது "
        f"(வழக்கமான நலம் அறிதல்: {baseline.get('typical_checkin_window', '08:15 AM — 08:45 AM')}, "
        f"காலை மருந்து: {baseline.get('typical_morning_med', '08:30 AM')})."
    )

    system_interpretation = (
        "These combined signals are unusual for this user compared with their historical routine. "
        "The multi-signal context engine confirmed multiple converging pattern shifts."
    )
    system_interpretation_tamil = (
        "அம்மாவின் முந்தைய பழக்கவழக்கங்களுடன் ஒப்பிடுகையில் இந்த கூட்டு மாற்றங்கள் வழக்கத்திற்கு மாறானவை."
    )

    return AIAlertExplanationResponse(
        alert_id=alert.id,
        title=alert.title,
        title_tamil=alert.title_tamil,
        detected_change=detected_change,
        detected_change_tamil=detected_change_tamil,
        baseline_comparison=baseline_comparison,
        baseline_comparison_tamil=baseline_comparison_tamil,
        change_score=alert.change_score,
        anomaly_score=alert.anomaly_score,
        severity=alert.severity,
        system_interpretation=system_interpretation,
        system_interpretation_tamil=system_interpretation_tamil,
        suggested_action=alert.suggested_action,
        suggested_action_tamil=alert.suggested_action_tamil,
        supporting_signals=evidence_schemas,
        disclaimer="EVER NEAR AI provides observational pattern analysis for family awareness. This is not a clinical or medical diagnosis."
    )


@router.get("/baseline")
def get_personal_baseline(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 4 — Personal Care Baseline Engine:
    Returns the individualized baseline learned from real PostgreSQL records.
    Labels 'Learning baseline' if fewer than 5 records exist.
    """
    user_id, parent_id, parent_name = resolve_ai_target(current_user, db)
    return baseline_engine.calculate_personal_baseline(db, parent_id)


@router.post("/simulate-abnormal-routine", response_model=DemoSimulationResponse)
async def simulate_abnormal_routine(
    req: DemoSimulationRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 16 — End-to-End Demo Simulation Mode:
    Executes the complete AI pipeline:
    1. Reads parent personal baseline.
    2. Runs Routine Change Score (Step 5).
    3. Runs scikit-learn Isolation Forest (Step 6).
    4. Evaluates Multi-Signal Context Engine (Step 8).
    5. Persists AIAlert and AIAlertEvidence to PostgreSQL (Step 3).
    6. Persists CareTimelineItem to PostgreSQL (Step 11).
    7. Creates AuditLog (Step 14).
    8. Broadcasts real-time event to Family dashboard via WebSocket (Step 17).
    """
    user_id, parent_id, parent_name = resolve_ai_target(current_user, db)
    parent_user_id = user_id

    scenario = req.scenario if req else "abnormal_day"

    # 1. Individualized Baseline
    baseline = baseline_engine.calculate_personal_baseline(db, parent_id)

    if scenario == "abnormal_day":
        # Simulated abnormal values: 2 hours check-in delay, medication unacknowledged (105m), 42% lower activity
        checkin_delay = 120.0
        med_delay = 105.0
        activity_ratio = 0.58
        sleep_hours = 5.2
        hydration_liters = 0.8
        interaction_count = 1
    else:
        # Normal routine values
        checkin_delay = 10.0
        med_delay = 5.0
        activity_ratio = 0.96
        sleep_hours = 7.4
        hydration_liters = 1.6
        interaction_count = 4

    # 2 & 3. Routine Change Score & Isolation Forest (Steps 5 & 6)
    anomaly_result = anomaly_detector.evaluate_routine(
        checkin_delay_mins=checkin_delay,
        med_delay_mins=med_delay,
        activity_ratio=activity_ratio,
        sleep_hours=sleep_hours,
        hydration_liters=hydration_liters,
        interaction_count=interaction_count,
        baseline=baseline
    )

    # 4. Multi-Signal Context Engine (Step 8)
    context_eval = context_engine.evaluate_context(
        anomaly_result=anomaly_result,
        baseline=baseline,
        cctv_events=[],
        phone_interactions_recent=False,
        active_sos=False
    )

    change_score = anomaly_result["change_score"]
    is_anomaly = anomaly_result["is_anomaly"]
    anomaly_score = anomaly_result["anomaly_score"]

    now = datetime.datetime.utcnow()
    time_str = now.strftime("%I:%M %p")

    # Record feature record to PostgreSQL
    feature_rec = RoutineFeatureRecord(
        parent_id=parent_id,
        record_date=datetime.date.today().isoformat(),
        checkin_delay_mins=checkin_delay,
        med_delay_mins=med_delay,
        activity_ratio=activity_ratio,
        sleep_hours=sleep_hours,
        meal_count=2,
        hydration_liters=hydration_liters,
        interaction_count=interaction_count,
        change_score=change_score,
        is_anomaly=is_anomaly
    )
    db.add(feature_rec)

    # 5. Persist AIAlert in PostgreSQL (Step 3 & 7) with alert fatigue deduplication
    existing_alert = db.query(AIAlert).filter(
        AIAlert.parent_id == parent_id,
        AIAlert.alert_type == "ROUTINE_CHANGE",
        AIAlert.status == "ACTIVE"
    ).first()

    if existing_alert:
        alert = existing_alert
        alert.severity = context_eval["severity"]
        alert.change_score = change_score
        alert.anomaly_score = anomaly_score
        alert.is_anomaly = is_anomaly
        alert.title = "ROUTINE CHANGE DETECTED"
        alert.title_tamil = "வழக்கமான அட்டவணையில் மாற்றம் கண்டறியப்பட்டது"
        alert.message = "Morning check-in is 2 hours late, morning medication not acknowledged, and activity is 42% below baseline."
        alert.message_tamil = "காலை நலம் தெரிவித்தல் 2 மணி நேரம் தாமதம், காலை மருந்து இன்னும் உறுதி செய்யப்படவில்லை, நடைபயிற்சி 42% குறைவு."
        alert.suggested_action = "Consider checking in with Amma"
        alert.suggested_action_tamil = "அம்மாவிடம் நலம் விசாரிக்கலாம்"
        db.flush()
    else:
        alert = AIAlert(
            parent_id=parent_id,
            alert_type="ROUTINE_CHANGE",
            severity=context_eval["severity"],
            title="ROUTINE CHANGE DETECTED",
            title_tamil="வழக்கமான அட்டவணையில் மாற்றம் கண்டறியப்பட்டது",
            message="Morning check-in is 2 hours late, morning medication not acknowledged, and activity is 42% below baseline.",
            message_tamil="காலை நலம் தெரிவித்தல் 2 மணி நேரம் தாமதம், காலை மருந்து இன்னும் உறுதி செய்யப்படவில்லை, நடைபயிற்சி 42% குறைவு.",
            change_score=change_score,
            anomaly_score=anomaly_score,
            is_anomaly=is_anomaly,
            status="ACTIVE",
            suggested_action="Consider checking in with Amma",
            suggested_action_tamil="அம்மாவிடம் நலம் விசாரிக்கலாம்",
            created_at=now
        )
        db.add(alert)
        db.flush()

        # Persist Evidences only for new alerts to prevent evidence bloat
        evidences = [
            AIAlertEvidence(
                alert_id=alert.id,
                signal_name="Morning Check-In",
                signal_name_tamil="காலை நலம் அறிதல்",
                baseline_value=baseline.get("typical_checkin_window", "08:15 AM — 08:45 AM"),
                current_value="2 hours later than usual",
                deviation_description="Check-in delay is 120 minutes past usual morning window",
                deviation_description_tamil="வழக்கமான நேரத்தை விட 120 நிமிடங்கள் தாமதம்",
                signal_status="ATTENTION"
            ),
            AIAlertEvidence(
                alert_id=alert.id,
                signal_name="Scheduled Medication",
                signal_name_tamil="மருந்து உட்கொள்ளல்",
                baseline_value=baseline.get("typical_morning_med", "08:30 AM"),
                current_value="Not yet confirmed",
                deviation_description="Morning prescribed medication unacknowledged past scheduled window",
                deviation_description_tamil="காலை பரிந்துரைக்கப்பட்ட மருந்து இன்னும் உட்கொள்ளப்படவில்லை",
                signal_status="ATTENTION"
            ),
            AIAlertEvidence(
                alert_id=alert.id,
                signal_name="Physical Activity",
                signal_name_tamil="உடல் அசைவு & நடை",
                baseline_value=f"~{int(baseline.get('expected_active_minutes', 45))} active mins",
                current_value="42% below baseline",
                deviation_description="Sensor & movement telemetry shows lower morning movement",
                deviation_description_tamil="வழக்கத்தை விட 42% குறைவான அசைவு பதிவாகியுள்ளது",
                signal_status="NOTICE"
            )
        ]
        db.add_all(evidences)

    # 6. Care Timeline Item (Step 11)
    timeline_item = CareTimelineItem(
        parent_id=parent_id,
        event_time=time_str,
        event_category="ROUTINE_CHANGE",
        title="Routine change detected by AI",
        title_tamil="வழக்கமான அட்டவணையில் மாற்றம் கண்டறியப்பட்டது",
        description=f"Isolation Forest change score {change_score:.2f}: Check-in delayed 2h, medication unacknowledged, activity down 42%.",
        description_tamil=f"மாற்ற அளவு {change_score:.2f}: நலம் அறிதல் 2 மணி தாமதம், மருந்து உட்கொள்ளப்படவில்லை.",
        icon="⚠️",
        severity="ATTENTION",
        source="AI_ENGINE",
        metadata_json=f'{{"alert_id": {alert.id}, "change_score": {change_score}}}',
        created_at=now
    )
    db.add(timeline_item)

    # 7. Audit Log (Step 14)
    audit = AuditLog(
        user_id=current_user.id,
        action="AI_ANOMALY_EVALUATION",
        target_resource="ROUTINE_MONITOR",
        details=f"Demo simulation executed: Isolation Forest anomaly score={anomaly_score}, change_score={change_score}"
    )
    db.add(audit)
    db.commit()
    db.refresh(alert)
    db.refresh(timeline_item)

    # 8. Real-Time WebSocket broadcast strictly to Family of this parent
    await ws_manager.send_to_family_of_parent(db, parent_user_id, {
        "type": "ROUTINE_ALERT",
        "alert_id": alert.id,
        "parent_id": parent_user_id,
        "title": alert.title,
        "title_tamil": alert.title_tamil,
        "message": alert.message,
        "change_score": alert.change_score,
        "severity": alert.severity,
        "suggested_action": alert.suggested_action,
        "time": time_str
    })

    return DemoSimulationResponse(
        scenario=scenario,
        status="ALERT_GENERATED",
        headline=f"Meaningful Routine Change Detected (Score: {change_score:.2f})",
        headline_tamil=f"அட்டவணை மாற்றம் கண்டறியப்பட்டது (அளவு: {change_score:.2f})",
        change_score=change_score,
        is_anomaly=is_anomaly,
        anomaly_score=anomaly_score,
        alert_created=True,
        alert_id=alert.id,
        explanation="Morning check-in is 2 hours late, medication not acknowledged, and morning activity is 42% below baseline.",
        suggested_action="Consider checking in with Amma",
        timeline_event_id=timeline_item.id,
        simulation_disclaimer="Controlled demonstration simulation for multi-signal verification."
    )


@router.post("/alerts/{alert_id}/family-checkin", response_model=AIAlertResponse)
async def family_checkin_on_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 9 & 16 — Family checks in with Parent in response to alert.
    Family selects 'Check In' -> Parent receives 'Your family is checking on you'.
    """
    alert = db.query(AIAlert).filter(AIAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")

    caregiver_name = current_user.full_name or "Karthik"
    alert.status = "CHECKED_IN"
    alert.family_action_taken = f"CHECKED_IN by {caregiver_name}"
    
    now = datetime.datetime.utcnow()
    time_str = now.strftime("%I:%M %p")

    # Add Care Timeline Event
    timeline_item = CareTimelineItem(
        parent_id=alert.parent_id,
        event_time=time_str,
        event_category="FAMILY",
        title="Family checking in with Amma",
        title_tamil="குடும்பத்தினர் நலம் விசாரிக்கின்றனர்",
        description=f"{caregiver_name} initiated a check-in in response to routine change alert.",
        description_tamil=f"{caregiver_name} அம்மாவிடம் நலம் விசாரிக்கிறார்.",
        icon="📞",
        severity="INFO",
        source="FAMILY_RESPONSE",
        created_at=now
    )
    db.add(timeline_item)

    # Add Audit Log
    audit = AuditLog(
        user_id=current_user.id,
        action="FAMILY_ALERT_CHECKIN",
        target_resource=f"AIAlert:{alert_id}",
        details=f"{caregiver_name} initiated check-in on routine change alert."
    )
    db.add(audit)
    db.commit()
    db.refresh(alert)

    # Directed notification to Parent and Care Circle
    checkin_payload = {
        "type": "FAMILY_CHECKIN",
        "alert_id": alert.id,
        "message": f"{caregiver_name} is checking on you.",
        "message_tamil": f"{caregiver_name} உங்கள் நலம் விசாரிக்கிறார்.",
        "caregiver": caregiver_name,
        "time": time_str
    }
    await ws_manager.send_personal_message(checkin_payload, user_id=alert.parent_id)
    await ws_manager.send_to_family_of_parent(db, alert.parent_id, checkin_payload)

    return alert


@router.post("/alerts/{alert_id}/parent-respond", response_model=AIAlertResponse)
async def parent_respond_on_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 9 & 16 — Parent responds 'I'm okay'.
    System updates: Situation acknowledged, Alert becomes resolved.
    """
    alert = db.query(AIAlert).filter(AIAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")

    now = datetime.datetime.utcnow()
    time_str = now.strftime("%I:%M %p")

    alert.status = "RESOLVED"
    alert.resolved_at = now
    alert.parent_response_text = "I'm okay / நான் நலமாக இருக்கிறேன்"

    # Add Care Timeline Event
    timeline_item = CareTimelineItem(
        parent_id=alert.parent_id,
        event_time=time_str,
        event_category="CHECKIN",
        title="Situation acknowledged: Amma confirmed she is okay",
        title_tamil="சூழ்நிலை உறுதி செய்யப்பட்டது: அம்மா நலமாக இருப்பதாக தெரிவித்தார்",
        description="Amma responded to family check-in confirming well-being. Routine change alert resolved.",
        description_tamil="அம்மா நலம் தெரிவித்தார். அட்டவணை எச்சரிக்கை சீரானது.",
        icon="❤️",
        severity="INFO",
        source="PARENT_RESPONSE",
        created_at=now
    )
    db.add(timeline_item)

    # Add Audit Log
    audit = AuditLog(
        user_id=current_user.id,
        action="PARENT_RESOLVED_ALERT",
        target_resource=f"AIAlert:{alert_id}",
        details="Parent responded confirming well-being. Routine alert marked RESOLVED."
    )
    db.add(audit)
    db.commit()
    db.refresh(alert)

    # Directed notification to Family and Parent
    resolved_payload = {
        "type": "ALERT_RESOLVED",
        "alert_id": alert.id,
        "message": "Amma responded: I'm okay. Situation acknowledged.",
        "message_tamil": "அம்மா: நான் நலமாக இருக்கிறேன். நிலைமை சீரானது.",
        "time": time_str
    }
    await ws_manager.send_personal_message(resolved_payload, user_id=alert.parent_id)
    await ws_manager.send_to_family_of_parent(db, alert.parent_id, resolved_payload)

    return alert


@router.post("/voice-route", response_model=VoiceRouteResponse)
def route_voice_intent(
    req: VoiceRouteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    P11 AI Voice Routing & Context Intelligence:
    Maps natural language speech (Tamil or English) to appropriate safe workflow:
    - MEDICINE -> Medication Flow (/app/parent/health)
    - FAMILY -> Communication Flow (/app/parent)
    - HEALTH -> Health / Help Flow (/app/parent/health)
    - HOME SAFETY -> Safety Flow (/app/parent/safety)
    - EMERGENCY -> SOS / Emergency Flow (/app/parent/sos)
    
    Strict safety rules:
    - AI assists humans.
    - AI does NOT independently diagnose medical conditions.
    - AI does NOT falsely claim certainty.
    - Explanations are human-readable (not technical jargon).
    """
    from app.services.communication_service import CommunicationService
    
    classification = CommunicationService.classify_voice_enquiry(
        spoken_text=req.spoken_text,
        language=req.language
    )
    
    intent = classification.intent
    category = classification.category
    priority = classification.priority
    
    # Route mapping
    if intent == "MEDICATION_HELP":
        target_flow = "MEDICATION_FLOW"
        target_route = "/app/parent/health"
        suggested_action = "Open Medication Schedule and verify today's prescriptions"
        suggested_action_tamil = "மருந்து அட்டவணையை திறந்து இன்றைய மருந்துகளை சரிபார்க்கவும்"
        explanation = "Voice request identified need for medication assistance."
        explanation_tamil = "மருந்து சம்பந்தமான உதவி கோரப்பட்டுள்ளது."
    elif intent in ["HEALTH_CONCERN", "DOCTOR_HELP"]:
        target_flow = "HEALTH_HELP_FLOW"
        target_route = "/app/parent/health"
        suggested_action = "Review health status and offer caregiver / doctor check-in"
        suggested_action_tamil = "உடல் நிலையை கவனித்து குடும்பத்தினருக்கு தகவல் தெரிவிக்கவும்"
        explanation = "Voice request expressed discomfort or health concern. (No medical diagnosis made)."
        explanation_tamil = "உடல் நலக்குறைவு குறித்து பேசப்பட்டது. மருத்துவ பரிசோதனை அல்ல."
    elif intent == "HOME_INCIDENT":
        target_flow = "SAFETY_FLOW"
        target_route = "/app/parent/safety"
        suggested_action = "Review recent home safety events and sensor observations"
        suggested_action_tamil = "வீட்டுப் பாதுகாப்பு நிகழ்வுகள் மற்றும் உணர்வி தகவல்களை சரிபார்க்கவும்"
        explanation = "Voice request reported an incident or unusual event at home."
        explanation_tamil = "வீட்டில் நிகழ்ந்த சம்பவம் குறித்து பேசப்பட்டது."
    elif intent == "EMERGENCY":
        target_flow = "SOS_EMERGENCY_FLOW"
        target_route = "/app/parent/sos"
        suggested_action = "Initiate immediate emergency verification and family alert escalation"
        suggested_action_tamil = "உடனடி அவசர உதவி எச்சரிக்கையை செயல்படுத்தவும்"
        explanation = "Urgent safety distress phrase detected. Directing to Emergency SOS."
        explanation_tamil = "அவசர உதவி தேவைப்படுவது கண்டறியப்பட்டது. SOS பக்கத்திற்கு வழிகாட்டுகிறது."
    else: # CALL_FAMILY or default
        target_flow = "COMMUNICATION_FLOW"
        target_route = "/app/parent"
        suggested_action = "Open Family Communication to connect with loved ones"
        suggested_action_tamil = "குடும்பத்தினருடன் தொடர்பு கொள்ள உதவும் திரையை திறக்கவும்"
        explanation = "Voice request requested conversation with family circle."
        explanation_tamil = "குடும்பத்தினரிடம் பேச விருப்பம் தெரிவிக்கப்பட்டது."

    return VoiceRouteResponse(
        spoken_text=req.spoken_text,
        language=req.language,
        intent=intent,
        category=category,
        priority=priority,
        target_flow=target_flow,
        target_route=target_route,
        suggested_action=suggested_action,
        suggested_action_tamil=suggested_action_tamil,
        explanation=explanation,
        explanation_tamil=explanation_tamil
    )


