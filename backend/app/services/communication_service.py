import datetime
import logging
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.entities import (
    User, ParentProfile, FamilyProfile, FamilyRelationship,
    CommunicationRequest, CommunicationAttempt, CommunicationResponse,
    AutomatedResponseTemplate, ScheduledCallback, EscalationRule,
    CommunicationAuditLog, Notification, TrustedContact, SOSAlert
)
from app.schemas.schemas import (
    CommunicationRequestCreate, CommunicationResponseCreate,
    ScheduleCallbackRequest, VoiceResponseClassificationResult,
    VoiceEnquiryClassifyResponse, ResponseTemplateCreate, EscalationRuleUpdate
)
from app.core.websocket import ws_manager

logger = logging.getLogger("ever_near.communication")

DEFAULT_TEMPLATES = [
    {
        "template_type": "CALL_MISSED",
        "title": "Call Missed — Call Soon",
        "text": "I couldn't answer your call. I'll call you soon.",
        "text_tamil": "என்னால் அழைப்பை எடுக்க முடியவில்லை. விரைவில் அழைக்கிறேன்.",
    },
    {
        "template_type": "BUSY",
        "title": "Busy Right Now",
        "text": "I'm busy right now. I'll call you shortly.",
        "text_tamil": "நான் இப்போது வேலையில் உள்ளேன். சற்று நேரத்தில் அழைக்கிறேன்.",
    },
    {
        "template_type": "ACKNOWLEDGEMENT",
        "title": "Saw Request — Stay Near Phone",
        "text": "I saw your request. Please stay near your phone.",
        "text_tamil": "உங்கள் கோரிக்கையைப் பார்த்தேன். தயவுசெய்து உங்கள் போன் அருகிலேயே இருங்கள்.",
    },
    {
        "template_type": "CALLBACK",
        "title": "Scheduled Callback",
        "text": "I'll call you at the scheduled time.",
        "text_tamil": "குறிப்பிட்ட நேரத்தில் உங்களை அழைக்கிறேன்.",
    },
]

class CommunicationService:

    @staticmethod
    def seed_default_templates(db: Session, user_id: Optional[int] = None):
        """Ensures default response templates exist in the database."""
        existing_count = db.query(AutomatedResponseTemplate).filter(
            AutomatedResponseTemplate.is_default == True
        ).count()
        if existing_count == 0:
            for item in DEFAULT_TEMPLATES:
                tmpl = AutomatedResponseTemplate(
                    user_id=user_id,
                    template_type=item["template_type"],
                    title=item["title"],
                    text=item["text"],
                    text_tamil=item["text_tamil"],
                    is_default=True,
                )
                db.add(tmpl)
            db.commit()

    @staticmethod
    def log_audit(db: Session, parent_id: int, event_type: str, request_id: Optional[int] = None, user_id: Optional[int] = None, details: Optional[str] = None):
        try:
            log_entry = CommunicationAuditLog(
                request_id=request_id,
                parent_id=parent_id,
                user_id=user_id,
                event_type=event_type,
                details=details,
                timestamp=datetime.datetime.utcnow()
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to record communication audit log: {e}")

    @staticmethod
    def classify_voice_enquiry(spoken_text: str, language: str = "ta") -> VoiceEnquiryClassifyResponse:
        text = spoken_text.strip().lower()
        
        # Rule-based natural speech classifier for English & Tamil
        # Strict rule: NEVER diagnose diseases. Use safe intent tags.
        intent = "CALL_FAMILY"
        category = "want_to_talk"
        priority = "NORMAL"
        confidence = 0.90
        safe_summary = "Parent wishes to connect with family."
        safe_summary_tamil = "பெற்றோர் குடும்பத்தினருடன் பேச விரும்புகிறார்."
        reason_text = "I want to talk to family"
        reason_tamil = "குடும்பத்தினருடன் பேச விரும்புகிறேன்"

        # Check for health concerns
        health_keywords = [
            "not well", "don't feel well", "unwell", "pain", "fever", "sick", "headache", "dizzy", "tired",
            "udambu", "vali", "sari illa", "kasta", "உடம்பு", "வலி", "சோர்வு",
            "சரியில்லை", "மயக்கம்", "காய்ச்சல்", "தலைவலி", "நெஞ்சு"
        ]
        if any(k in text for k in health_keywords):
            intent = "HEALTH_CONCERN"
            category = "not_well"
            priority = "IMPORTANT"
            confidence = 0.92
            safe_summary = "Possible health concern detected. Parent requested family conversation."
            safe_summary_tamil = "உடல் நலம் குறித்த தகவல். பெற்றோர் குடும்பத்தினருடன் பேச விரும்புகிறார்."
            reason_text = "I don't feel well"
            reason_tamil = "உடல் நலம் சரியில்லை"

        # Check for medication help
        med_keywords = ["medicine", "tablet", "pill", "dose", "marunthu", "marundu", "மருந்து", "மாத்திரை"]
        if any(k in text for k in med_keywords):
            intent = "MEDICATION_HELP"
            category = "medicine"
            priority = "IMPORTANT"
            confidence = 0.94
            safe_summary = "Parent requested assistance regarding medication."
            safe_summary_tamil = "மருந்து சம்பந்தமான உதவி கேட்கப்பட்டுள்ளது."
            reason_text = "I need help with medicine"
            reason_tamil = "மருந்து உதவி தேவை"

        # Check for food / water
        food_keywords = ["food", "water", "lunch", "dinner", "breakfast", "eat", "thanni", "saapadu", "பசி", "தண்ணீர்", "சாப்பாடு", "உணவு"]
        if any(k in text for k in food_keywords):
            intent = "FOOD_WATER"
            category = "food_water"
            priority = "NORMAL"
            confidence = 0.91
            safe_summary = "Parent requested food or water assistance."
            safe_summary_tamil = "உணவு அல்லது தண்ணீர் உதவி கேட்கப்பட்டுள்ளது."
            reason_text = "I need food or water"
            reason_tamil = "உணவு அல்லது தண்ணீர் தேவை"

        # Check for doctor / clinic
        doc_keywords = ["doctor", "hospital", "clinic", "appointment", "டாக்டர்", "மருத்துவர்", "மருத்துவமனை", "ஆஸ்பத்திரி"]
        if any(k in text for k in doc_keywords):
            intent = "DOCTOR_HELP"
            category = "doctor"
            priority = "IMPORTANT"
            confidence = 0.93
            safe_summary = "Parent requested doctor or hospital assistance."
            safe_summary_tamil = "மருத்துவர் அல்லது மருத்துவமனை உதவி கேட்கப்பட்டுள்ளது."
            reason_text = "I need help with doctor/hospital"
            reason_tamil = "மருத்துவர் / மருத்துவமனை உதவி"

        # Check for home incident
        home_keywords = ["home", "door", "lock", "sound", "light", "fall", "slip", "வீட்டில்", "சத்தம்", "விழுந்து", "உடைந்தது"]
        if any(k in text for k in home_keywords):
            intent = "HOME_INCIDENT"
            category = "home_incident"
            priority = "IMPORTANT"
            confidence = 0.88
            safe_summary = "Possible event at home reported by parent."
            safe_summary_tamil = "வீட்டில் நடந்த நிகழ்வு பற்றிய தகவல்."
            reason_text = "Something happened at home"
            reason_tamil = "வீட்டில் ஏதோ நடந்தது"

        # Check for emergency / SOS
        emergency_keywords = ["emergency", "urgent", "save", "danger", "காப்பாத்துங்க", "அவசரம்", "உடனே வாங்க"]
        if any(k in text for k in emergency_keywords):
            intent = "EMERGENCY"
            category = "other"
            priority = "URGENT"
            confidence = 0.95
            safe_summary = "Urgent parent attention request triggered."
            safe_summary_tamil = "உடனடி அவசர உதவி கோரிக்கை பதிவானது."
            reason_text = "Urgent help needed"
            reason_tamil = "உடனடி உதவி தேவை"

        # Call family direct request
        call_keywords = ["call me", "ask to call", "phone me", "pesanum", "ponna", "magan", "மகன்", "மகள்", "அழைக்கவும்", "பேச வேண்டும்"]
        if any(k in text for k in call_keywords) and intent == "CALL_FAMILY":
            category = "call_me"
            reason_text = "Please call me"
            reason_tamil = "என்னை அழைக்கவும்"

        return VoiceEnquiryClassifyResponse(
            spoken_text=spoken_text,
            detected_language=language,
            intent=intent,
            category=category,
            reason_text=reason_text,
            reason_tamil=reason_tamil,
            priority=priority,
            confidence=confidence,
            safe_summary=safe_summary,
            safe_summary_tamil=safe_summary_tamil,
        )

    @staticmethod
    def classify_voice_response(spoken_text: str, language: str = "ta") -> VoiceResponseClassificationResult:
        text = spoken_text.strip().lower()

        # 1. ACKNOWLEDGED
        ack_phrases = [
            "okay", "ok", "i'm here", "im here", "i'm ok", "im ok", "i'm okay", "im okay",
            "i am okay", "i understand", "yes", "yeah", "yep",
            "all right", "fine", "sari", "seri", "இருக்கேன்", "சரி", "பரவாயில்லை",
            "parava illai", "paravalla", "புரிந்தது", "கேட்டது", "நல்லது",
            "நான் நலமாக இருக்கிறேன்", "நான் நலம்", "நலமாக இருக்கிறேன்", "நான் இங்கு இருக்கிறேன்", "நலம்"
        ]
        if any(p in text for p in ack_phrases):
            return VoiceResponseClassificationResult(
                classification="ACKNOWLEDGED",
                automation_action="STOP",
                guidance_message="Okay ❤️ Your family has been notified. Please stay near your phone.",
                guidance_message_tamil="சரி அம்மா ❤️ உங்கள் குடும்பத்தினருக்கு தகவல் தெரிவிக்கப்பட்டது. தயவுசெய்து உங்கள் தொலைபேசியின் அருகில் இருங்கள்.",
                should_stop_reminder=True,
                is_emergency=False
            )

        # 2. REQUEST_CALL
        call_phrases = [
            "please call me", "call me", "ask them to call", "tell them to call",
            "phone pannunga", "கூப்பிடுங்க", "அழைக்கவும்", "போன் பண்ண சொல்லுங்க",
            "pesa sollu", "அழைக்கச் சொல்லுங்கள்", "குடும்பத்தினருடன் பேச", "குடும்பத்தினரிடம் பேச"
        ]
        if any(p in text for p in call_phrases):
            return VoiceResponseClassificationResult(
                classification="REQUEST_CALL",
                automation_action="STOP",
                guidance_message="I have asked your family to call you.",
                guidance_message_tamil="உங்களை அழைக்குமாறு குடும்பத்தினரிடம் தெரிவித்துள்ளேன்.",
                should_stop_reminder=True,
                is_emergency=False
            )

        # 3. NEEDS_HELP
        help_phrases = [
            "i need help", "need help", "something happened", "please come",
            "help", "உதவி வேணும்", "உதவி தேவை", "எனக்கு உதவி வேண்டும்", "வாங்க", "ஏதோ ஆச்சு"
        ]
        if any(p in text for p in help_phrases):
            return VoiceResponseClassificationResult(
                classification="NEEDS_HELP",
                automation_action="ESCALATE",
                guidance_message="Amma, your family has been notified. Please stay near your phone.",
                guidance_message_tamil="அம்மா, உங்கள் குடும்பத்தினருக்கு தகவல் தெரிவிக்கப்பட்டது. தயவுசெய்து உங்கள் தொலைபேசியின் அருகில் இருங்கள்.",
                should_stop_reminder=True,
                is_emergency=False
            )

        # 4. EMERGENCY
        emergency_phrases = ["emergency", "save me", "danger", "காப்பாத்துங்க", "அவசரம்", "உயிருக்கு ஆபத்து"]
        if any(p in text for p in emergency_phrases):
            return VoiceResponseClassificationResult(
                classification="EMERGENCY",
                automation_action="ESCALATE",
                guidance_message="Emergency alert escalated. Please keep calm and stay where you are.",
                guidance_message_tamil="அவசர எச்சரிக்கை குடும்பத்திற்கு அனுப்பப்பட்டுள்ளது. அமைதியாக பாதுகாப்பாக இருங்கள்.",
                should_stop_reminder=True,
                is_emergency=True
            )

        # 5. UNCLEAR
        return VoiceResponseClassificationResult(
            classification="UNCLEAR",
            automation_action="RETRY",
            guidance_message="Amma, I didn't understand. Please say it again.",
            guidance_message_tamil="அம்மா, சரியாகப் புரியவில்லை. தயவுசெய்து மீண்டும் சொல்லுங்கள்.",
            should_stop_reminder=False,
            is_emergency=False
        )

    @staticmethod
    def get_parent_and_family_context(db: Session, current_user: User) -> Tuple[int, str, Optional[int], Optional[str]]:
        """
        Resolves parent_id, parent_name, and primary linked family member.
        """
        if current_user.role.upper() == "PARENT":
            parent_id = current_user.id
            profile = db.query(ParentProfile).filter(ParentProfile.user_id == current_user.id).first()
            parent_name = profile.preferred_name if profile else current_user.full_name
            # Find primary linked family member
            rel = db.query(FamilyRelationship).filter(
                FamilyRelationship.parent_id == current_user.id,
                FamilyRelationship.status == "APPROVED"
            ).first()
            family_id = rel.family_user_id if rel else None
            family_name = None
            if family_id:
                fam_user = db.query(User).filter(User.id == family_id).first()
                family_name = fam_user.full_name if fam_user else None
            return parent_id, parent_name, family_id, family_name
        else:
            # Current user is family
            rel = db.query(FamilyRelationship).filter(
                FamilyRelationship.family_user_id == current_user.id,
                FamilyRelationship.status == "APPROVED"
            ).first()
            if rel:
                parent_id = rel.parent_id
                parent_user = db.query(User).filter(User.id == parent_id).first()
                profile = db.query(ParentProfile).filter(ParentProfile.user_id == parent_id).first()
                parent_name = profile.preferred_name if profile else (parent_user.full_name if parent_user else "Amma")
            else:
                return None, None, current_user.id, current_user.full_name
            return parent_id, parent_name, current_user.id, current_user.full_name

    @staticmethod
    def check_recent_attempts(db: Session, parent_id: int, window_hours: int = 2) -> Tuple[int, bool]:
        """
        Counts communication attempts in past window_hours.
        Threshold: 3 or more attempts within window triggers unusual communication activity alert.
        """
        since_time = datetime.datetime.utcnow() - datetime.timedelta(hours=window_hours)
        count = db.query(CommunicationAttempt).filter(
            CommunicationAttempt.parent_id == parent_id,
            CommunicationAttempt.attempt_time >= since_time
        ).count()
        is_unusual = count >= 3
        return count, is_unusual

    @staticmethod
    async def create_communication_request(
        db: Session,
        current_user: User,
        data: CommunicationRequestCreate
    ) -> CommunicationRequest:
        CommunicationService.seed_default_templates(db, current_user.id)
        parent_id, parent_name, default_fam_id, default_fam_name = CommunicationService.get_parent_and_family_context(db, current_user)

        target_family_id = data.family_member_id or default_fam_id
        target_family_name = data.family_member_name or default_fam_name

        if target_family_id and not target_family_name:
            fam_user = db.query(User).filter(User.id == target_family_id).first()
            if fam_user:
                target_family_name = fam_user.full_name

        # Resolve reason texts if missing
        reason_map = {
            "not_well": ("I don't feel well", "உடல் நலம் சரியில்லை"),
            "medicine": ("I need help with medicine", "மருந்து உதவி தேவை"),
            "food_water": ("I need food or water", "உணவு அல்லது தண்ணீர் தேவை"),
            "doctor": ("I need help with doctor/hospital", "மருத்துவர் / மருத்துவமனை உதவி"),
            "want_to_talk": ("I want to talk", "பேச வேண்டும்"),
            "call_me": ("Please call me", "என்னை அழைக்கவும்"),
            "home_incident": ("Something happened at home", "வீட்டில் ஏதோ நடந்தது"),
            "other": ("Parent requests attention", "தொடர்பு கொள்ள விரும்புகிறேன்"),
        }
        fallback_en, fallback_ta = reason_map.get(data.reason_category or "want_to_talk", ("I want to talk", "பேச வேண்டும்"))
        reason_text = data.reason_text or fallback_en
        reason_tamil = data.reason_tamil or fallback_ta

        # Build careful, safe AI summary (NO medical diagnoses)
        if data.intent == "HEALTH_CONCERN" or data.reason_category == "not_well":
            ai_summary = "Possible health concern noted. Consider checking on Amma."
            ai_summary_tamil = "உடல் நலம் குறித்த தகவல் பதிவானது. அம்மாவைத் தொடர்பு கொள்ளவும்."
        elif data.intent == "EMERGENCY":
            ai_summary = "Urgent communication request created by parent."
            ai_summary_tamil = "பெற்றோரிடமிருந்து அவசர அழைப்பு கோரிக்கை வந்துள்ளது."
        elif data.intent == "HOME_INCIDENT" or data.reason_category == "home_incident":
            ai_summary = "Possible unusual event at home reported by parent."
            ai_summary_tamil = "வீட்டில் ஏதோ நிகழ்ந்ததாக பெற்றோர் தெரிவித்துள்ளார்."
        else:
            ai_summary = f"{parent_name} requests a call: '{reason_text}'"
            ai_summary_tamil = f"{parent_name} பேச விரும்புகிறார்: '{reason_tamil}'"

        # Determine priority: if URGENT or IMPORTANT requested or reason warrants it
        priority = data.priority.upper()
        if data.reason_category in ["not_well", "home_incident"] and priority == "NORMAL":
            priority = "IMPORTANT"
        if data.intent == "EMERGENCY":
            priority = "URGENT"

        # Create record
        req = CommunicationRequest(
            parent_id=parent_id,
            family_member_id=target_family_id,
            family_member_name=target_family_name,
            intent=data.intent,
            reason_category=data.reason_category,
            reason_text=reason_text,
            reason_tamil=reason_tamil,
            voice_input=data.voice_input,
            voice_transcript=data.voice_transcript,
            ai_summary=ai_summary,
            ai_summary_tamil=ai_summary_tamil,
            priority=priority,
            status="NOTIFIED",
            automation_status="ACTIVE",
            guidance_count=0,
            max_guidance_retries=3,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow()
        )
        db.add(req)
        db.commit()
        db.refresh(req)

        # Log communication attempt
        attempt = CommunicationAttempt(
            parent_id=parent_id,
            request_id=req.id,
            channel="VOICE" if data.voice_input else "CALL_REQUEST",
            attempt_time=datetime.datetime.utcnow()
        )
        db.add(attempt)
        db.commit()

        # Check for repeated attempt patterns
        attempts_count, is_unusual = CommunicationService.check_recent_attempts(db, parent_id)
        if is_unusual:
            CommunicationService.log_audit(
                db, parent_id=parent_id,
                event_type="UNUSUAL_COMMUNICATION_ACTIVITY",
                request_id=req.id,
                details=f"Unusual communication activity: {attempts_count} contact attempts in past 2 hours."
            )

        CommunicationService.log_audit(
            db, parent_id=parent_id,
            event_type="REQUEST_CREATED",
            request_id=req.id,
            user_id=current_user.id,
            details=f"Intent: {req.intent}, Priority: {req.priority}, Reason: {req.reason_text}"
        )

        # Create system notification for family
        if target_family_id:
            notif = Notification(
                user_id=target_family_id,
                type="SAFETY" if req.priority != "NORMAL" else "ROUTINE",
                title=f"{parent_name.upper()} WANTS TO TALK TO YOU",
                title_tamil=f"{parent_name} உங்களிடம் பேச விரும்புகிறார்",
                body=f"Reason: {req.reason_text} ({req.priority} attention)",
                body_tamil=f"காரணம்: {req.reason_tamil}",
                data_json=f'{{"request_id": {req.id}, "priority": "{req.priority}"}}'
            )
            db.add(notif)
            db.commit()

        # Broadcast via WebSocket
        ws_payload = {
            "type": "COMMUNICATION_REQUEST",
            "request_id": req.id,
            "parent_id": parent_id,
            "parent_name": parent_name,
            "family_member_id": target_family_id,
            "family_member_name": target_family_name,
            "intent": req.intent,
            "reason_text": req.reason_text,
            "reason_tamil": req.reason_tamil,
            "priority": req.priority,
            "attention_required": req.priority in ["IMPORTANT", "URGENT"],
            "ai_summary": req.ai_summary,
            "ai_summary_tamil": req.ai_summary_tamil,
            "created_at": req.created_at.isoformat(),
            "unusual_activity_detected": is_unusual,
            "recent_attempts_count": attempts_count
        }

        # Send to specific family user or send to family of parent
        if target_family_id:
            await ws_manager.send_personal_message(ws_payload, target_family_id)
        await ws_manager.send_to_family_of_parent(db, req.parent_id, ws_payload)

        return req

    @staticmethod
    async def acknowledge_request(db: Session, request_id: int, responder: User) -> CommunicationRequest:
        req = db.query(CommunicationRequest).filter(CommunicationRequest.id == request_id).first()
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Communication request not found.")

        req.status = "ACKNOWLEDGED"
        req.automation_status = "STOPPED"
        req.responded_at = datetime.datetime.utcnow()
        req.updated_at = datetime.datetime.utcnow()

        resp = CommunicationResponse(
            request_id=req.id,
            responder_id=responder.id,
            responder_name=responder.full_name,
            response_type="ACKNOWLEDGE",
            message="Request acknowledged by family member",
            message_tamil="குடும்பத்தினர் கோரிக்கையைக் கவனித்தார்",
            created_at=datetime.datetime.utcnow()
        )
        db.add(resp)
        db.commit()
        db.refresh(req)

        CommunicationService.log_audit(
            db, parent_id=req.parent_id,
            event_type="FAMILY_ACKNOWLEDGED",
            request_id=req.id,
            user_id=responder.id,
            details=f"Acknowledged by {responder.full_name}"
        )

        # Notify parent via WebSocket
        ws_msg = {
            "type": "COMMUNICATION_ACKNOWLEDGED",
            "request_id": req.id,
            "status": req.status,
            "responder_name": responder.full_name,
            "message": f"{responder.full_name} has acknowledged your request ❤️",
            "message_tamil": f"{responder.full_name} உங்கள் கோரிக்கையைக் கவனித்தார் ❤️"
        }
        await ws_manager.send_personal_message(ws_msg, req.parent_id)
        await ws_manager.send_to_family_of_parent(db, req.parent_id, ws_msg)

        return req

    @staticmethod
    async def respond_to_request(
        db: Session,
        request_id: int,
        responder: User,
        data: CommunicationResponseCreate
    ) -> Tuple[CommunicationRequest, CommunicationResponse]:
        req = db.query(CommunicationRequest).filter(CommunicationRequest.id == request_id).first()
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Communication request not found.")

        msg = data.message
        msg_tamil = data.message_tamil
        scheduled_time = None

        if data.response_type == "CALL_NOW":
            req.status = "RESPONDING"
            msg = msg or f"{responder.full_name} is calling you now."
            msg_tamil = msg_tamil or f"{responder.full_name} இப்போது அழைக்கிறார்."
        elif data.response_type == "CALL_LATER":
            req.status = "CALLBACK_SCHEDULED"
            mins = data.scheduled_minutes or 30
            scheduled_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=mins)
            msg = msg or f"{responder.full_name} will call you in {mins} minutes."
            msg_tamil = msg_tamil or f"{responder.full_name} {mins} நிமிடங்களில் அழைப்பார்."

            # Save scheduled callback
            cb = ScheduledCallback(
                request_id=req.id,
                family_user_id=responder.id,
                parent_id=req.parent_id,
                scheduled_for=scheduled_time,
                reminder_minutes=mins,
                status="PENDING",
                created_at=datetime.datetime.utcnow()
            )
            db.add(cb)
        elif data.response_type == "TEMPLATE_MSG":
            req.status = "RESPONDING"
            if not msg:
                # Find template
                tmpl = db.query(AutomatedResponseTemplate).filter(
                    AutomatedResponseTemplate.template_type == (data.template_key or "CALL_MISSED")
                ).first()
                if tmpl:
                    msg = tmpl.text
                    msg_tamil = tmpl.text_tamil
                else:
                    msg = "I'll call you shortly."
                    msg_tamil = "சற்று நேரத்தில் அழைக்கிறேன்."

        # Automation stops as human responded
        req.automation_status = "STOPPED"
        req.responded_at = datetime.datetime.utcnow()
        req.updated_at = datetime.datetime.utcnow()

        resp = CommunicationResponse(
            request_id=req.id,
            responder_id=responder.id,
            responder_name=responder.full_name,
            response_type=data.response_type,
            template_key=data.template_key,
            message=msg,
            message_tamil=msg_tamil,
            scheduled_time=scheduled_time,
            created_at=datetime.datetime.utcnow()
        )
        db.add(resp)
        db.commit()
        db.refresh(req)
        db.refresh(resp)

        CommunicationService.log_audit(
            db, parent_id=req.parent_id,
            event_type="FAMILY_RESPONDED",
            request_id=req.id,
            user_id=responder.id,
            details=f"Type: {data.response_type}, Message: {msg}"
        )

        ws_msg = {
            "type": "COMMUNICATION_RESPONSE",
            "request_id": req.id,
            "status": req.status,
            "response_type": data.response_type,
            "responder_name": responder.full_name,
            "message": msg,
            "message_tamil": msg_tamil,
            "scheduled_time": scheduled_time.isoformat() if scheduled_time else None
        }
        await ws_manager.send_personal_message(ws_msg, req.parent_id)
        await ws_manager.send_to_family_of_parent(db, req.parent_id, ws_msg)

        return req, resp

    @staticmethod
    async def schedule_callback(
        db: Session,
        request_id: int,
        responder: User,
        data: ScheduleCallbackRequest
    ) -> ScheduledCallback:
        req = db.query(CommunicationRequest).filter(CommunicationRequest.id == request_id).first()
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Communication request not found.")

        scheduled_for = datetime.datetime.utcnow() + datetime.timedelta(minutes=data.minutes)
        cb = ScheduledCallback(
            request_id=req.id,
            family_user_id=responder.id,
            parent_id=req.parent_id,
            scheduled_for=scheduled_for,
            reminder_minutes=data.minutes,
            status="PENDING",
            created_at=datetime.datetime.utcnow()
        )
        db.add(cb)

        req.status = "CALLBACK_SCHEDULED"
        req.automation_status = "STOPPED"
        req.updated_at = datetime.datetime.utcnow()
        db.commit()
        db.refresh(cb)

        CommunicationService.log_audit(
            db, parent_id=req.parent_id,
            event_type="CALLBACK_SCHEDULED",
            request_id=req.id,
            user_id=responder.id,
            details=f"Scheduled for {data.minutes} minutes ({scheduled_for.isoformat()})"
        )

        ws_msg = {
            "type": "CALLBACK_SCHEDULED",
            "request_id": req.id,
            "scheduled_for": scheduled_for.isoformat(),
            "minutes": data.minutes,
            "responder_name": responder.full_name,
            "message": f"{responder.full_name} will call in {data.minutes} minutes.",
            "message_tamil": f"{responder.full_name} {data.minutes} நிமிடங்களில் அழைப்பார்."
        }
        await ws_manager.send_personal_message(ws_msg, req.parent_id)
        await ws_manager.send_to_family_of_parent(db, req.parent_id, ws_msg)

        return cb

    @staticmethod
    async def handle_parent_voice_response(
        db: Session,
        parent_user: User,
        spoken_text: str,
        language: str = "ta",
        request_id: Optional[int] = None
    ) -> Tuple[VoiceResponseClassificationResult, Optional[CommunicationRequest]]:
        classification = CommunicationService.classify_voice_response(spoken_text, language)

        # Retrieve active request if any
        req = None
        if request_id:
            req = db.query(CommunicationRequest).filter(CommunicationRequest.id == request_id).first()
        if not req:
            req = db.query(CommunicationRequest).filter(
                CommunicationRequest.parent_id == parent_user.id,
                CommunicationRequest.status.in_(["PENDING", "NOTIFIED", "CALL_REQUESTED"])
            ).order_by(CommunicationRequest.created_at.desc()).first()

        if req:
            req.parent_response = classification.classification.lower()
            if classification.should_stop_reminder:
                req.automation_status = "STOPPED"
                if classification.classification == "ACKNOWLEDGED":
                    req.status = "ACKNOWLEDGED"
                elif classification.classification == "REQUEST_CALL":
                    req.status = "CALL_REQUESTED"
                elif classification.classification == "NEEDS_HELP":
                    req.status = "ESCALATED"
                elif classification.classification == "EMERGENCY":
                    req.status = "ESCALATED"
            else:
                req.guidance_count += 1
                if req.guidance_count >= req.max_guidance_retries:
                    # Cooldown stop to prevent infinite speech loops
                    req.automation_status = "STOPPED"

            req.updated_at = datetime.datetime.utcnow()
            db.commit()
            db.refresh(req)

            CommunicationService.log_audit(
                db, parent_id=parent_user.id,
                event_type="VOICE_RESPONSE_RECEIVED",
                request_id=req.id,
                user_id=parent_user.id,
                details=f"Classification: {classification.classification}, Spoken: {spoken_text}"
            )

            # CRITICAL SAFETY RULE (Section 14):
            # A voice response of ACKNOWLEDGED stops the communication reminder,
            # but NEVER cancels or resolves an active SOSAlert!
            # Active SOS workflow remains strictly untouched here.

            # Broadcast update to family
            ws_msg = {
                "type": "PARENT_VOICE_RESPONSE",
                "request_id": req.id,
                "classification": classification.classification,
                "spoken_text": spoken_text,
                "automation_status": req.automation_status,
                "status": req.status,
                "parent_name": parent_user.full_name
            }
            await ws_manager.send_to_family_of_parent(db, parent_user.id, ws_msg)

        return classification, req

    @staticmethod
    async def stop_automation(db: Session, request_id: int, user: User) -> CommunicationRequest:
        req = db.query(CommunicationRequest).filter(CommunicationRequest.id == request_id).first()
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Communication request not found.")

        req.automation_status = "STOPPED"
        req.updated_at = datetime.datetime.utcnow()
        db.commit()
        db.refresh(req)

        CommunicationService.log_audit(
            db, parent_id=req.parent_id,
            event_type="AUTOMATION_STOPPED",
            request_id=req.id,
            user_id=user.id,
            details="Automated voice guidance stopped manually or via condition."
        )

        return req
