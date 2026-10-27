import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.entities import (
    User, ParentProfile, CommunicationRequest, CommunicationAttempt,
    CommunicationResponse, AutomatedResponseTemplate, ScheduledCallback,
    EscalationRule, CommunicationAuditLog, TrustedContact
)
from app.schemas.schemas import (
    CommunicationRequestCreate, CommunicationResponseCreate,
    ScheduleCallbackRequest, VoiceResponseInput,
    VoiceEnquiryClassifyRequest, VoiceEnquiryClassifyResponse,
    VoiceResponseClassificationResult, ResponseTemplateCreate,
    ResponseTemplateResponse, ScheduledCallbackResponse,
    EscalationRuleUpdate, EscalationRuleResponse,
    CommunicationAuditLogResponse, CommunicationItemResponse
)
from app.services.communication_service import CommunicationService

router = APIRouter(prefix="/communication", tags=["Parent Enquiry & Call Attention"])

def serialize_communication_item(req: CommunicationRequest, db: Session) -> dict:
    # Resolve parent name
    parent_prof = db.query(ParentProfile).filter(ParentProfile.user_id == req.parent_id).first()
    parent_user = db.query(User).filter(User.id == req.parent_id).first()
    parent_name = parent_prof.preferred_name if parent_prof else (parent_user.full_name if parent_user else "Amma")

    # Resolve latest response message
    latest_resp = db.query(CommunicationResponse).filter(
        CommunicationResponse.request_id == req.id
    ).order_by(CommunicationResponse.created_at.desc()).first()

    # Resolve scheduled callback
    latest_cb = db.query(ScheduledCallback).filter(
        ScheduledCallback.request_id == req.id,
        ScheduledCallback.status == "PENDING"
    ).order_by(ScheduledCallback.created_at.desc()).first()

    attempts_count, is_unusual = CommunicationService.check_recent_attempts(db, req.parent_id)

    return {
        "id": req.id,
        "parent_id": req.parent_id,
        "parent_name": parent_name,
        "family_member_id": req.family_member_id,
        "family_member_name": req.family_member_name or "Family Member",
        "intent": req.intent,
        "reason_category": req.reason_category,
        "reason_text": req.reason_text,
        "reason_tamil": req.reason_tamil,
        "voice_input": req.voice_input,
        "voice_transcript": req.voice_transcript,
        "ai_summary": req.ai_summary,
        "ai_summary_tamil": req.ai_summary_tamil,
        "priority": req.priority,
        "status": req.status,
        "automation_status": req.automation_status,
        "parent_response": req.parent_response,
        "guidance_count": req.guidance_count,
        "max_guidance_retries": req.max_guidance_retries,
        "created_at": req.created_at,
        "updated_at": req.updated_at,
        "responded_at": req.responded_at,
        "resolved_at": req.resolved_at,
        "recent_attempts_count": attempts_count,
        "unusual_activity_detected": is_unusual,
        "latest_response_message": latest_resp.message if latest_resp else None,
        "latest_response_message_tamil": latest_resp.message_tamil if latest_resp else None,
        "scheduled_callback_time": latest_cb.scheduled_for if latest_cb else None
    }


@router.post("/requests", response_model=CommunicationItemResponse)
async def create_request(
    data: CommunicationRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Creates an intelligent communication request from parent or on behalf of parent.
    Dispatches alerts, evaluates priority, triggers attention alarm if important/urgent.
    """
    req = await CommunicationService.create_communication_request(db, current_user, data)
    return serialize_communication_item(req, db)


@router.get("/requests", response_model=List[CommunicationItemResponse])
def get_requests(
    status_filter: Optional[str] = Query(None, description="Optional status filter"),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns communication requests relevant to the authenticated user.
    """
    parent_id, _, _, _ = CommunicationService.get_parent_and_family_context(db, current_user)
    if not parent_id:
        return []
    query = db.query(CommunicationRequest).filter(CommunicationRequest.parent_id == parent_id)
    if status_filter:
        query = query.filter(CommunicationRequest.status == status_filter.upper())
    requests = query.order_by(CommunicationRequest.created_at.desc()).limit(limit).all()
    return [serialize_communication_item(r, db) for r in requests]


@router.get("/requests/active", response_model=Optional[CommunicationItemResponse])
def get_active_request(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the currently active communication request if one is pending/notified.
    """
    parent_id, _, _, _ = CommunicationService.get_parent_and_family_context(db, current_user)
    if not parent_id:
        return None
    req = db.query(CommunicationRequest).filter(
        CommunicationRequest.parent_id == parent_id,
        CommunicationRequest.status.in_(["PENDING", "NOTIFIED", "CALL_REQUESTED", "RESPONDING", "CALLBACK_SCHEDULED"])
    ).order_by(CommunicationRequest.created_at.desc()).first()

    if not req:
        return None
    return serialize_communication_item(req, db)


@router.get("/requests/{request_id}", response_model=CommunicationItemResponse)
def get_request_by_id(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    req = db.query(CommunicationRequest).filter(CommunicationRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Communication request not found.")
    return serialize_communication_item(req, db)


@router.post("/requests/{request_id}/acknowledge", response_model=CommunicationItemResponse)
async def acknowledge_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Family member acknowledges request. Halts voice guidance automation and updates parent.
    """
    req = await CommunicationService.acknowledge_request(db, request_id, current_user)
    return serialize_communication_item(req, db)


@router.post("/requests/{request_id}/respond", response_model=CommunicationItemResponse)
async def respond_to_request(
    request_id: int,
    data: CommunicationResponseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Family member sends real response (Call Now, Call Later, Automated Template Message).
    """
    req, _ = await CommunicationService.respond_to_request(db, request_id, current_user, data)
    return serialize_communication_item(req, db)


@router.post("/requests/{request_id}/schedule-callback", response_model=ScheduledCallbackResponse)
async def schedule_callback(
    request_id: int,
    data: ScheduleCallbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Family member schedules a callback for parent (15m, 30m, 60m).
    """
    cb = await CommunicationService.schedule_callback(db, request_id, current_user, data)
    return cb


@router.post("/requests/{request_id}/stop-automation", response_model=CommunicationItemResponse)
async def stop_automation(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Stops automated voice guidance for this communication request.
    """
    req = await CommunicationService.stop_automation(db, request_id, current_user)
    return serialize_communication_item(req, db)


@router.post("/voice-response", response_model=VoiceResponseClassificationResult)
async def handle_voice_response(
    data: VoiceResponseInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Processes parent voice feedback after voice guidance.
    If parent acknowledges ('Okay', 'I'm here', 'சரி'), automated voice reminder is stopped.
    CRITICAL: Does NOT cancel any active SOSAlert.
    """
    result, _ = await CommunicationService.handle_parent_voice_response(
        db=db,
        parent_user=current_user,
        spoken_text=data.spoken_text,
        language=data.language,
        request_id=data.request_id
    )
    return result


@router.post("/voice-enquiry/classify", response_model=VoiceEnquiryClassifyResponse)
def classify_enquiry(
    data: VoiceEnquiryClassifyRequest
):
    """
    Analyzes spoken text from parent in Tamil or English and maps to safe intent categories.
    Careful AI language without medical diagnoses.
    """
    return CommunicationService.classify_voice_enquiry(data.spoken_text, data.language)


@router.get("/templates", response_model=List[ResponseTemplateResponse])
def get_templates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns automated response templates for family members.
    """
    CommunicationService.seed_default_templates(db, current_user.id)
    templates = db.query(AutomatedResponseTemplate).all()
    return templates


@router.post("/templates", response_model=ResponseTemplateResponse)
def create_template(
    data: ResponseTemplateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tmpl = AutomatedResponseTemplate(
        user_id=current_user.id,
        template_type=data.template_type,
        title=data.title,
        text=data.text,
        text_tamil=data.text_tamil,
        is_default=False
    )
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return tmpl


@router.put("/templates/{template_id}", response_model=ResponseTemplateResponse)
def update_template(
    template_id: int,
    data: ResponseTemplateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tmpl = db.query(AutomatedResponseTemplate).filter(AutomatedResponseTemplate.id == template_id).first()
    if not tmpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
    tmpl.title = data.title
    tmpl.text = data.text
    tmpl.text_tamil = data.text_tamil
    tmpl.template_type = data.template_type
    db.commit()
    db.refresh(tmpl)
    return tmpl


@router.get("/escalation-rules", response_model=EscalationRuleResponse)
def get_escalation_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id, _, _, _ = CommunicationService.get_parent_and_family_context(db, current_user)
    rule = db.query(EscalationRule).filter(EscalationRule.parent_id == parent_id).first()
    if not rule:
        # Default rule
        rule = EscalationRule(
            parent_id=parent_id,
            primary_user_id=None,
            secondary_user_id=None,
            trusted_contact_id=None,
            escalation_delay_minutes=15,
            is_enabled=True
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)

    primary_name = None
    secondary_name = None
    trusted_name = None
    if rule.primary_user_id:
        u = db.query(User).filter(User.id == rule.primary_user_id).first()
        if u: primary_name = u.full_name
    if rule.secondary_user_id:
        u = db.query(User).filter(User.id == rule.secondary_user_id).first()
        if u: secondary_name = u.full_name
    if rule.trusted_contact_id:
        tc = db.query(TrustedContact).filter(TrustedContact.id == rule.trusted_contact_id).first()
        if tc: trusted_name = tc.name

    return EscalationRuleResponse(
        id=rule.id,
        parent_id=rule.parent_id,
        primary_user_id=rule.primary_user_id,
        secondary_user_id=rule.secondary_user_id,
        trusted_contact_id=rule.trusted_contact_id,
        escalation_delay_minutes=rule.escalation_delay_minutes,
        is_enabled=rule.is_enabled,
        primary_name=primary_name,
        secondary_name=secondary_name,
        trusted_contact_name=trusted_name
    )


@router.post("/escalation-rules", response_model=EscalationRuleResponse)
def update_escalation_rules(
    data: EscalationRuleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id, _, _, _ = CommunicationService.get_parent_and_family_context(db, current_user)
    rule = db.query(EscalationRule).filter(EscalationRule.parent_id == parent_id).first()
    if not rule:
        rule = EscalationRule(parent_id=parent_id)
        db.add(rule)

    rule.primary_user_id = data.primary_user_id
    rule.secondary_user_id = data.secondary_user_id
    rule.trusted_contact_id = data.trusted_contact_id
    rule.escalation_delay_minutes = data.escalation_delay_minutes
    rule.is_enabled = data.is_enabled
    rule.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(rule)

    return get_escalation_rules(current_user=current_user, db=db)


@router.get("/recent-attempts")
def get_recent_attempts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id, _, _, _ = CommunicationService.get_parent_and_family_context(db, current_user)
    count, is_unusual = CommunicationService.check_recent_attempts(db, parent_id)
    return {
        "parent_id": parent_id,
        "attempts_count_last_2h": count,
        "unusual_activity_detected": is_unusual,
        "message": "Unusual communication activity detected: multiple call attempts recorded today." if is_unusual else "Normal communication frequency.",
        "message_tamil": "வழக்கத்திற்கு மாறான தொடர் அழைப்பு முயற்சிகள் பதிவாகியுள்ளன." if is_unusual else "வழக்கமான தொடர்பு நிலை."
    }


@router.get("/audit-logs", response_model=List[CommunicationAuditLogResponse])
def get_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id, _, _, _ = CommunicationService.get_parent_and_family_context(db, current_user)
    logs = db.query(CommunicationAuditLog).filter(
        CommunicationAuditLog.parent_id == parent_id
    ).order_by(CommunicationAuditLog.timestamp.desc()).limit(limit).all()
    return logs
