import secrets
import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.session import get_db
from app.models.entities import (
    User, ParentProfile, FamilyRelationship, Notification,
    CommunicationRequest, CommunicationResponse, ScheduledCallback,
    CareTimelineItem, AuditLog, FamilyInvitation
)
from app.schemas.schemas import (
    FamilyInviteCreate, FamilyMemberResponse,
    FamilyEnquiryCreateRequest, FamilyEnquiryPatchRequest, FamilyEnquiryItemResponse,
    FamilyRelationshipCreate, FamilyRelationshipResponse,
    FamilyInvitationCreate, FamilyInvitationResponse,
    FamilyInvitationVerifyResponse, FamilyInvitationAccept
)
from app.routers.deps import get_current_user, require_role
from app.services.relationship_service import RelationshipService
from app.services.care_service import CareService
from app.services.alert_service import AlertService
from app.services.privacy_service import PrivacyService
from app.core.websocket import ws_manager

router = APIRouter(prefix="/family", tags=["Family Coordination & Enquiries"])

def generate_invite_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    part1 = "".join(secrets.choice(alphabet) for _ in range(4))
    part2 = "".join(secrets.choice(alphabet) for _ in range(2))
    return f"EN-{part1}-{part2}"

@router.get("", response_model=List[FamilyMemberResponse])
def get_family_contacts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role.upper() == "PARENT":
        parent_id = current_user.id
    else:
        linked_parent = RelationshipService.get_parent_for_family(db, current_user.id)
        if not linked_parent:
            return []
        parent_id = linked_parent.id

    relationships = db.query(FamilyRelationship).filter(
        FamilyRelationship.parent_id == parent_id
    ).all()

    results = []
    for rel in relationships:
        fam_user = db.query(User).filter(User.id == rel.family_user_id).first()
        name = fam_user.full_name if fam_user else "Family Member"
        phone = rel.phone or (fam_user.phone if fam_user else "+91 98765 43211")
        results.append(FamilyMemberResponse(
            id=rel.id,
            name=name,
            relationship_type=rel.relationship_type,
            phone=phone,
            status=rel.status,
            can_view_health=rel.can_view_health,
            can_view_cctv=rel.can_view_cctv
        ))

    return results

@router.post("/invitations", response_model=FamilyInvitationResponse, status_code=status.HTTP_201_CREATED)
def create_family_invitation(
    req: FamilyInvitationCreate,
    current_user: User = Depends(require_role("PARENT")),
    db: Session = Depends(get_db)
):
    """Parent creates a secure, expiring, single-use invitation code to connect family members."""
    code = generate_invite_code()
    for _ in range(10):
        if not db.query(FamilyInvitation).filter(FamilyInvitation.invite_code == code).first():
            break
        code = generate_invite_code()

    expires = datetime.datetime.utcnow() + datetime.timedelta(hours=max(1, req.expires_hours))
    inv = FamilyInvitation(
        parent_id=current_user.id,
        invite_code=code,
        relationship_type=req.relationship_type,
        invited_phone=req.invited_phone,
        can_view_health=req.can_view_health,
        can_view_cctv=req.can_view_cctv,
        can_receive_sos=req.can_receive_sos,
        is_used=False,
        expires_at=expires
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)

    return FamilyInvitationResponse(
        id=inv.id,
        parent_id=inv.parent_id,
        invite_code=inv.invite_code,
        relationship_type=inv.relationship_type,
        invited_phone=inv.invited_phone,
        can_view_health=inv.can_view_health,
        can_view_cctv=inv.can_view_cctv,
        can_receive_sos=inv.can_receive_sos,
        is_used=inv.is_used,
        used_by_user_id=inv.used_by_user_id,
        expires_at=inv.expires_at,
        created_at=inv.created_at,
        invite_link=f"/join?code={inv.invite_code}"
    )

@router.get("/invitations", response_model=List[FamilyInvitationResponse])
def list_family_invitations(
    current_user: User = Depends(require_role("PARENT")),
    db: Session = Depends(get_db)
):
    """Parent retrieves all pending and past invitation codes created by them."""
    invs = db.query(FamilyInvitation).filter(
        FamilyInvitation.parent_id == current_user.id
    ).order_by(FamilyInvitation.created_at.desc()).all()
    return invs

def is_invitation_expired(dt: datetime.datetime) -> bool:
    if dt.tzinfo is not None:
        return datetime.datetime.now(datetime.timezone.utc) > dt
    return datetime.datetime.utcnow() > dt

@router.get("/invitations/verify", response_model=FamilyInvitationVerifyResponse)
def verify_family_invitation(
    code: str,
    db: Session = Depends(get_db)
):
    """Verifies that an invitation code is valid, unused, and not expired."""
    clean_code = code.strip().upper()
    inv = db.query(FamilyInvitation).filter(FamilyInvitation.invite_code == clean_code).first()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation code not found.")
    
    if inv.is_used:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation code has already been used.")

    if is_invitation_expired(inv.expires_at):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation code has expired.")

    parent = db.query(User).filter(User.id == inv.parent_id).first()
    if not parent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inviting parent account not found.")

    preferred = parent.parent_profile.preferred_name if parent.parent_profile else parent.full_name

    return FamilyInvitationVerifyResponse(
        valid=True,
        invite_code=inv.invite_code,
        parent_id=inv.parent_id,
        parent_name=parent.full_name,
        parent_preferred_name=preferred,
        relationship_type=inv.relationship_type,
        can_view_health=inv.can_view_health,
        can_view_cctv=inv.can_view_cctv,
        can_receive_sos=inv.can_receive_sos,
        expires_at=inv.expires_at
    )

@router.post("/invitations/accept")
def accept_family_invitation(
    req: FamilyInvitationAccept,
    current_user: User = Depends(require_role("FAMILY")),
    db: Session = Depends(get_db)
):
    """Family member inputs invitation code to link with parent."""
    clean_code = req.invite_code.strip().upper()
    inv = db.query(FamilyInvitation).filter(FamilyInvitation.invite_code == clean_code).first()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invitation code.")

    if inv.is_used:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation code has already been used.")

    if is_invitation_expired(inv.expires_at):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation code has expired.")

    if inv.parent_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot connect to yourself.")

    # Check if target relationship already exists
    existing = db.query(FamilyRelationship).filter(
        FamilyRelationship.parent_id == inv.parent_id,
        FamilyRelationship.family_user_id == current_user.id
    ).first()

    if existing:
        existing.status = "APPROVED"
        existing.relationship_type = inv.relationship_type
        existing.can_view_health = inv.can_view_health
        existing.can_view_cctv = inv.can_view_cctv
        existing.can_receive_sos = inv.can_receive_sos
        rel = existing
    else:
        rel = FamilyRelationship(
            parent_id=inv.parent_id,
            family_user_id=current_user.id,
            relationship_type=inv.relationship_type,
            phone=current_user.phone,
            status="APPROVED",
            can_view_health=inv.can_view_health,
            can_view_cctv=inv.can_view_cctv,
            can_receive_sos=inv.can_receive_sos
        )
        db.add(rel)

    # Consume single-use invitation
    inv.is_used = True
    inv.used_by_user_id = current_user.id
    inv.used_at = datetime.datetime.utcnow()

    # Log audit record
    audit = AuditLog(
        user_id=current_user.id,
        action="FAMILY_INVITATION_ACCEPTED",
        target_resource=f"parent:{inv.parent_id}",
        details=f"Connected to parent {inv.parent_id} via invite code {inv.invite_code} as {inv.relationship_type}"
    )
    db.add(audit)

    db.commit()
    db.refresh(rel)

    # Real-time WebSocket notification to parent
    ws_manager.send_to_user(inv.parent_id, {
        "type": "FAMILY_CONNECTED",
        "message": f"{current_user.full_name} joined your Care Circle as {inv.relationship_type}!",
        "family_user_id": current_user.id
    })

    return {
        "message": "Family member connected successfully",
        "relationship_id": rel.id,
        "parent_id": inv.parent_id,
        "relationship_type": inv.relationship_type
    }

@router.post("/invite")
def invite_family_member(
    req: FamilyInviteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.core.security import hash_password
    from app.services.auth_service import normalize_phone
    clean_phone = normalize_phone(req.phone)
    target_user = db.query(User).filter((User.phone == clean_phone) | (User.phone == req.phone)).first()
    if not target_user:
        target_user = User(
            phone=clean_phone if clean_phone else req.phone,
            full_name=req.name or f"Family ({req.relationship_type})",
            role="FAMILY",
            password_hash=hash_password("invited_pending"),
            is_active=False
        )
        db.add(target_user)
        db.flush()
    target_id = target_user.id

    rel = db.query(FamilyRelationship).filter(
        FamilyRelationship.parent_id == current_user.id,
        FamilyRelationship.family_user_id == target_id
    ).first()

    if not rel:
        rel = FamilyRelationship(
            parent_id=current_user.id,
            family_user_id=target_id,
            relationship_type=req.relationship_type,
            phone=clean_phone if clean_phone else req.phone,
            status="APPROVED",
            can_view_health=True,
            can_view_cctv=True
        )
        db.add(rel)
    else:
        rel.relationship_type = req.relationship_type
        rel.phone = clean_phone if clean_phone else req.phone
        rel.status = "APPROVED"

    db.commit()
    db.refresh(rel)
    return {"message": "Family member connected successfully", "id": rel.id}

@router.post("/call-sim")
def simulate_call(
    contact_name: str,
    current_user: User = Depends(get_current_user)
):
    return {
        "status": "CONNECTING",
        "message": f"Calling {contact_name} via cellular network / VoIP bridge...",
        "tel_uri": "tel:+919876543211"
    }


# ============================================================================
# STEP 9: REAL FAMILY ENQUIRY WORKFLOW (Parent Talk to Family -> Family Response)
# ============================================================================

def _serialize_enquiry(req: CommunicationRequest, db: Session) -> FamilyEnquiryItemResponse:
    parent_prof = db.query(ParentProfile).filter(ParentProfile.user_id == req.parent_id).first()
    parent_user = db.query(User).filter(User.id == req.parent_id).first()
    parent_name = parent_prof.preferred_name if parent_prof else (parent_user.full_name if parent_user else "Amma")

    latest_resp = db.query(CommunicationResponse).filter(
        CommunicationResponse.request_id == req.id
    ).order_by(CommunicationResponse.created_at.desc()).first()

    return FamilyEnquiryItemResponse(
        id=req.id,
        parent_id=req.parent_id,
        parent_name=parent_name,
        family_member_id=req.family_member_id,
        family_member_name=req.family_member_name or "Family Member",
        reason_category=req.reason_category or "want_to_talk",
        reason_text=req.reason_text or "Want to talk",
        reason_tamil=req.reason_tamil,
        status=req.status,
        priority=req.priority,
        family_response_message=latest_resp.message if latest_resp else None,
        responding_caregiver=latest_resp.responder_name if latest_resp else None,
        created_at=req.created_at,
        updated_at=req.updated_at
    )


@router.post("/enquiries", response_model=FamilyEnquiryItemResponse)
async def create_family_enquiry(
    req: FamilyEnquiryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 9 — Parent: Talk to Family.
    Persists enquiry into PostgreSQL and broadcasts alert to family.
    Reasons:
    - Need medicine
    - Not feeling well
    - Want to talk
    - Need help
    - Please call me
    - Something happened
    - Other
    """
    parent = db.query(User).filter(User.role == "PARENT").first()
    parent_id = parent.id if parent else current_user.id
    parent_name = parent.full_name if parent else "Amma"

    # Resolve family member name
    fam_member_name = req.family_member_name or "Karthik"
    if req.family_member_id:
        fam_user = db.query(User).filter(User.id == req.family_member_id).first()
        if fam_user:
            fam_member_name = fam_user.full_name

    now = datetime.datetime.utcnow()
    time_str = now.strftime("%I:%M %p")

    tamil_reasons = {
        "medicine": "மருந்து தேவைப்படுகிறது",
        "not_well": "உடல்நலம் சரியில்லை",
        "want_to_talk": "பேச வேண்டும்",
        "need_help": "உதவி தேவை",
        "call_me": "தயவுசெய்து அழைக்கவும்",
        "incident": "ஏதோ நடந்தது",
        "other": "மற்றவை"
    }
    reason_tamil = req.reason_tamil or tamil_reasons.get(req.reason_category, "பேச வேண்டும்")

    enquiry = CommunicationRequest(
        parent_id=parent_id,
        family_member_id=req.family_member_id or 2,
        family_member_name=fam_member_name,
        intent="CALL_FAMILY",
        reason_category=req.reason_category,
        reason_text=req.reason_text,
        reason_tamil=reason_tamil,
        priority=req.priority,
        status="PENDING",
        created_at=now,
        updated_at=now
    )
    db.add(enquiry)
    db.flush()

    # Add Care Timeline Event
    timeline_item = CareTimelineItem(
        parent_id=parent_id,
        event_time=time_str,
        event_category="FAMILY",
        title=f"Talk request to {fam_member_name}",
        title_tamil=f"{fam_member_name}-டம் பேச அழைப்பு",
        description=f"Amma requested to talk: {req.reason_text}",
        description_tamil=f"அம்மா பேச விரும்புகிறார்: {reason_tamil}",
        icon="📞",
        severity="NOTICE" if req.priority == "NORMAL" else "ATTENTION",
        source="PARENT_ENQUIRY",
        created_at=now
    )
    db.add(timeline_item)

    # Add Audit Log
    audit = AuditLog(
        user_id=current_user.id,
        action="FAMILY_ENQUIRY_CREATED",
        target_resource=f"CommunicationRequest:{enquiry.id}",
        details=f"Parent initiated talk enquiry with {fam_member_name}: {req.reason_text}"
    )
    db.add(audit)
    db.commit()
    db.refresh(enquiry)

    # Directed WebSocket delivery to family of this parent
    await ws_manager.send_to_family_of_parent(db, enquiry.parent_id, {
        "type": "FAMILY_ENQUIRY",
        "enquiry_id": enquiry.id,
        "parent_id": enquiry.parent_id,
        "title": f"{parent_name.upper()} WANTS TO TALK TO YOU",
        "title_tamil": f"{parent_name} உங்களுடன் பேச விரும்புகிறார்",
        "parent_name": parent_name,
        "family_member_name": fam_member_name,
        "reason_category": enquiry.reason_category,
        "reason_text": enquiry.reason_text,
        "reason_tamil": enquiry.reason_tamil,
        "priority": enquiry.priority,
        "time": time_str,
        "actions": ["Call Now", "Reply", "I'm Responding", "Later"]
    })

    return _serialize_enquiry(enquiry, db)


@router.get("/enquiries", response_model=List[FamilyEnquiryItemResponse])
def get_family_enquiries(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns family communication enquiries.
    """
    parent = db.query(User).filter(User.role == "PARENT").first()
    parent_id = parent.id if parent else current_user.id

    enquiries = db.query(CommunicationRequest).filter(
        CommunicationRequest.parent_id == parent_id
    ).order_by(CommunicationRequest.created_at.desc()).limit(20).all()

    return [_serialize_enquiry(e, db) for e in enquiries]


@router.patch("/enquiries/{enquiry_id}", response_model=FamilyEnquiryItemResponse)
async def update_family_enquiry(
    enquiry_id: int,
    patch: FamilyEnquiryPatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 9 — Family Response Actions:
    - 'I'm Responding' -> Parent sees '{Caregiver} is responding.'
    - 'Call Now'       -> Initiates direct phone/call bridge
    - 'Reply'          -> Sends text/voice response to Parent
    - 'Later'          -> Schedules callback (e.g. in 15 mins)
    Persists all state changes to PostgreSQL and notifies Parent via WebSocket.
    """
    enquiry = db.query(CommunicationRequest).filter(CommunicationRequest.id == enquiry_id).first()
    if not enquiry:
        raise HTTPException(status_code=404, detail="Enquiry not found.")

    caregiver_name = current_user.full_name or "Karthik"
    now = datetime.datetime.utcnow()
    time_str = now.strftime("%I:%M %p")

    action_upper = patch.action.upper().replace(" ", "_")

    if action_upper in ["RESPONDING", "I'M_RESPONDING", "IM_RESPONDING"]:
        enquiry.status = "RESPONDING"
        enquiry.responded_at = now
        msg = patch.message or f"{caregiver_name} is responding."
        msg_tamil = patch.message_tamil or f"{caregiver_name} பதிலளிக்கிறார்."

        resp = CommunicationResponse(
            request_id=enquiry.id,
            responder_id=current_user.id,
            responder_name=caregiver_name,
            response_type="RESPONDING",
            message=msg,
            message_tamil=msg_tamil,
            created_at=now
        )
        db.add(resp)

        resp_msg = {
            "type": "FAMILY_RESPONDING",
            "enquiry_id": enquiry.id,
            "caregiver": caregiver_name,
            "message": f"{caregiver_name} is responding.",
            "message_tamil": f"{caregiver_name} பதிலளிக்கிறார்.",
            "time": time_str
        }
        await ws_manager.send_personal_message(resp_msg, user_id=enquiry.parent_id)
        await ws_manager.send_to_family_of_parent(db, enquiry.parent_id, resp_msg)

    elif action_upper in ["CALL_NOW", "CALL"]:
        enquiry.status = "CALL_REQUESTED"
        enquiry.responded_at = now
        msg = f"{caregiver_name} is calling you now."
        msg_tamil = f"{caregiver_name} இப்போது அழைக்கிறார்."

        resp = CommunicationResponse(
            request_id=enquiry.id,
            responder_id=current_user.id,
            responder_name=caregiver_name,
            response_type="CALL_NOW",
            message=msg,
            message_tamil=msg_tamil,
            created_at=now
        )
        db.add(resp)

        call_msg = {
            "type": "FAMILY_CALLING",
            "enquiry_id": enquiry.id,
            "caregiver": caregiver_name,
            "message": msg,
            "message_tamil": msg_tamil,
            "time": time_str
        }
        await ws_manager.send_personal_message(call_msg, user_id=enquiry.parent_id)
        await ws_manager.send_to_family_of_parent(db, enquiry.parent_id, call_msg)

    elif action_upper in ["LATER", "CALL_LATER"]:
        enquiry.status = "CALLBACK_SCHEDULED"
        enquiry.responded_at = now
        mins = patch.scheduled_minutes or 15
        msg = f"{caregiver_name} will call you back in {mins} minutes."
        msg_tamil = f"{caregiver_name} இன்னும் {mins} நிமிடங்களில் அழைப்பார்."

        cb = ScheduledCallback(
            request_id=enquiry.id,
            family_user_id=current_user.id,
            parent_id=enquiry.parent_id,
            scheduled_for=now + datetime.timedelta(minutes=mins),
            reminder_minutes=mins,
            status="PENDING",
            created_at=now
        )
        db.add(cb)

        resp = CommunicationResponse(
            request_id=enquiry.id,
            responder_id=current_user.id,
            responder_name=caregiver_name,
            response_type="CALL_LATER",
            message=msg,
            message_tamil=msg_tamil,
            created_at=now
        )
        db.add(resp)

        cb_msg = {
            "type": "FAMILY_CALLBACK",
            "enquiry_id": enquiry.id,
            "caregiver": caregiver_name,
            "scheduled_minutes": mins,
            "message": msg,
            "message_tamil": msg_tamil,
            "time": time_str
        }
        await ws_manager.send_personal_message(cb_msg, user_id=enquiry.parent_id)
        await ws_manager.send_to_family_of_parent(db, enquiry.parent_id, cb_msg)

    elif action_upper in ["REPLY", "MESSAGE"]:
        enquiry.status = "RESPONDED"
        enquiry.responded_at = now
        msg = patch.message or f"Message from {caregiver_name}"
        msg_tamil = patch.message_tamil or f"{caregiver_name}-டமிருந்து செய்தி"

        resp = CommunicationResponse(
            request_id=enquiry.id,
            responder_id=current_user.id,
            responder_name=caregiver_name,
            response_type="REPLY",
            message=msg,
            message_tamil=msg_tamil,
            created_at=now
        )
        db.add(resp)

        fmsg = {
            "type": "FAMILY_MESSAGE",
            "enquiry_id": enquiry.id,
            "caregiver": caregiver_name,
            "message": msg,
            "message_tamil": msg_tamil,
            "time": time_str
        }
        await ws_manager.send_personal_message(fmsg, user_id=enquiry.parent_id)
        await ws_manager.send_to_family_of_parent(db, enquiry.parent_id, fmsg)

    elif action_upper in ["RESOLVED", "RESOLVE"]:
        enquiry.status = "RESOLVED"
        enquiry.resolved_at = now
        msg = "Enquiry completed."

    enquiry.updated_at = now

    # Add Care Timeline Event
    timeline_item = CareTimelineItem(
        parent_id=enquiry.parent_id,
        event_time=time_str,
        event_category="FAMILY",
        title=f"Family response: {caregiver_name}",
        title_tamil=f"குடும்பத்தினர் பதில்: {caregiver_name}",
        description=f"{caregiver_name} responded to enquiry: {patch.action}",
        description_tamil=f"{caregiver_name} பதிலளித்தார்.",
        icon="💬",
        severity="INFO",
        source="FAMILY_RESPONSE",
        created_at=now
    )
    db.add(timeline_item)

    # Add Audit Log
    audit = AuditLog(
        user_id=current_user.id,
        action="FAMILY_ENQUIRY_RESPONDED",
        target_resource=f"CommunicationRequest:{enquiry.id}",
        details=f"{caregiver_name} executed action '{patch.action}' on enquiry {enquiry_id}"
    )
    db.add(audit)
    db.commit()
    db.refresh(enquiry)

    return _serialize_enquiry(enquiry, db)


@router.get("/parent-status")
def get_linked_parent_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Allows family member to view status of their linked parent."""
    parent = RelationshipService.get_parent_for_family(db, current_user.id)
    if not parent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No linked parent found.")

    profile = parent.parent_profile
    today_checkin = CareService.get_today_checkin(db, parent.id)
    profile_id = profile.id if profile else parent.id
    active_alert = AlertService.get_active_alert(db, profile_id)

    # Enforce parent privacy state for family access
    privacy = PrivacyService.get_parent_privacy_state(db, parent.id)
    today_checkin_data = None
    if today_checkin:
        if privacy["health_info"]:
            today_checkin_data = {
                "feeling": today_checkin.feeling,
                "feeling_tamil": today_checkin.feeling_tamil,
                "created_at": today_checkin.created_at
            }
        else:
            today_checkin_data = {
                "feeling": "Protected (Privacy ON)",
                "feeling_tamil": "தனியுரிமை பாதுகாக்கப்பட்டது",
                "created_at": today_checkin.created_at
            }

    return {
        "parent_id": parent.id,
        "parent_name": parent.full_name,
        "preferred_name": profile.preferred_name if profile else "Amma",
        "age": profile.age if profile else 72,
        "language_pref": profile.language_pref if profile else "ta",
        "has_checked_in_today": today_checkin is not None,
        "today_checkin": today_checkin_data,
        "has_active_emergency": active_alert is not None,
        "active_emergency_status": active_alert.status if active_alert else None
    }



@router.get("/context")
def get_family_context(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Identifies user, role, and parent/family relationships."""
    return RelationshipService.identify_user_context(db, current_user)


@router.post("/relationships", response_model=FamilyRelationshipResponse, status_code=status.HTTP_201_CREATED)
def create_family_relationship(
    req: FamilyRelationshipCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role.upper() != "PARENT":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only parent accounts can manage family relationships.")
    parent_id = current_user.id
    fam_user = db.query(User).filter(User.id == req.family_user_id).first()
    if not fam_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target family user not found.")

    rel = RelationshipService.link_parent_and_family(
        db=db,
        parent_id=parent_id,
        family_user_id=fam_user.id,
        relationship_type=req.relationship_type,
        phone=req.phone or fam_user.phone
    )
    rel.can_view_health = req.can_view_health
    rel.can_view_cctv = req.can_view_cctv
    rel.can_receive_sos = req.can_receive_sos
    db.commit()
    db.refresh(rel)
    return rel


@router.get("/profile")
def get_family_profile(
    current_user: User = Depends(require_role("FAMILY")),
    db: Session = Depends(get_db)
):
    """Retrieves family member profile for authenticated family user."""
    profile = current_user.family_profile
    return {
        "user_id": current_user.id,
        "phone": current_user.phone,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "preferred_name": profile.preferred_name if profile else current_user.full_name,
        "relationship_type": profile.relationship_type if profile else "Family Member",
        "language_pref": profile.language_pref if profile else "en"
    }

