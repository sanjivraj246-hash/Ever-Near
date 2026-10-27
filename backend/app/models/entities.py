import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey, Enum as SQLEnum, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.db.session import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(32), unique=True, index=True, nullable=False)
    full_name = Column(String(128), nullable=False)
    role = Column(String(32), default="PARENT", index=True, nullable=False)  # 'PARENT' or 'FAMILY'
    password_hash = Column(String(256), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    google_id = Column(String(128), unique=True, index=True, nullable=True)
    google_email = Column(String(256), unique=True, index=True, nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    recovery_token = Column(String(128), index=True, nullable=True)
    recovery_token_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Role & Ownership Relationships
    parent_profile = relationship("ParentProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    family_profile = relationship("FamilyProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    check_ins = relationship("DailyCheckIn", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    family_relationships_as_parent = relationship("FamilyRelationship", foreign_keys="[FamilyRelationship.parent_id]", cascade="all, delete-orphan")
    family_relationships_as_family = relationship("FamilyRelationship", foreign_keys="[FamilyRelationship.family_user_id]", cascade="all, delete-orphan")
    invitations_as_parent = relationship("FamilyInvitation", foreign_keys="[FamilyInvitation.parent_id]", cascade="all, delete-orphan")


class ParentProfile(Base):
    __tablename__ = "parent_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    preferred_name = Column(String(128), default="Amma", nullable=False)
    age = Column(Integer, default=72)
    emergency_notes = Column(Text, nullable=True)
    language_pref = Column(String(10), default="ta", nullable=False)  # 'en' or 'ta'
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="parent_profile")
    trusted_contacts = relationship("TrustedContact", back_populates="parent", cascade="all, delete-orphan")
    medications = relationship("Medication", back_populates="parent", cascade="all, delete-orphan")
    health_documents = relationship("HealthDocument", back_populates="parent", cascade="all, delete-orphan")
    care_events = relationship("CareEvent", back_populates="parent", cascade="all, delete-orphan")
    routine_events = relationship("RoutineEvent", back_populates="parent", cascade="all, delete-orphan")
    safety_events = relationship("SafetyEvent", back_populates="parent", cascade="all, delete-orphan")
    sos_alerts = relationship("SOSAlert", back_populates="parent", cascade="all, delete-orphan")
    cctv_devices = relationship("CCTVDevice", back_populates="owner", cascade="all, delete-orphan")


class FamilyProfile(Base):
    __tablename__ = "family_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    preferred_name = Column(String(128), default="Family Member", nullable=False)
    relationship_type = Column(String(64), default="Child", nullable=False)  # 'Daughter', 'Son', 'Caregiver', etc.
    language_pref = Column(String(10), default="en", nullable=False)  # 'en' or 'ta'
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="family_profile")


class FamilyRelationship(Base):
    __tablename__ = "family_relationships"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    family_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    relationship_type = Column(String(64), default="Child", nullable=False)  # 'Daughter', 'Son', etc.
    status = Column(String(32), default="APPROVED", index=True, nullable=False)  # 'APPROVED', 'PENDING'
    can_view_health = Column(Boolean, default=True, nullable=False)
    can_view_cctv = Column(Boolean, default=True, nullable=False)
    can_receive_sos = Column(Boolean, default=True, nullable=False)
    phone = Column(String(32), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("parent_id", "family_user_id", name="uq_parent_family_relationship"),
    )


class FamilyInvitation(Base):
    __tablename__ = "family_invitations"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    invite_code = Column(String(32), unique=True, index=True, nullable=False)
    relationship_type = Column(String(64), default="Child", nullable=False)
    invited_phone = Column(String(32), nullable=True, index=True)
    can_view_health = Column(Boolean, default=True, nullable=False)
    can_view_cctv = Column(Boolean, default=True, nullable=False)
    can_receive_sos = Column(Boolean, default=True, nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    used_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    parent = relationship("User", foreign_keys=[parent_id], overlaps="invitations_as_parent")
    used_by_user = relationship("User", foreign_keys=[used_by_user_id])


class TrustedContact(Base):
    __tablename__ = "trusted_contacts"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("parent_profiles.id", ondelete="CASCADE"), index=True, nullable=False)
    name = Column(String(128), nullable=False)
    relationship_type = Column(String(64), default="Neighbor", nullable=False)  # 'Son', 'Doctor', 'Neighbor', etc.
    phone = Column(String(32), nullable=False, index=True)
    priority_order = Column(Integer, default=1, nullable=False)  # 1 = primary, 2 = secondary
    can_receive_sos = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    parent = relationship("ParentProfile", back_populates="trusted_contacts")


class DailyCheckIn(Base):
    __tablename__ = "daily_check_ins"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    feeling = Column(String(32), nullable=False)  # 'good', 'okay', 'not_well'
    feeling_tamil = Column(String(64), nullable=True)
    voice_input = Column(Boolean, default=False)
    voice_transcript = Column(Text, nullable=True)
    note = Column(Text, nullable=True)
    check_in_date = Column(String(16), index=True)  # YYYY-MM-DD
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="check_ins")


class Medication(Base):
    __tablename__ = "medications"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("parent_profiles.id"), nullable=False)
    name = Column(String(128), nullable=False)
    dosage = Column(String(64), default="1 tablet")
    schedule_time = Column(String(16), default="08:00 AM")
    period = Column(String(32), default="Morning")  # 'Morning', 'Afternoon', 'Night'
    instructions = Column(String(256), default="After food with warm water")
    icon = Column(String(32), default="pill")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    parent = relationship("ParentProfile", back_populates="medications")
    logs = relationship("MedicationLog", back_populates="medication", cascade="all, delete-orphan")


class MedicationLog(Base):
    __tablename__ = "medication_logs"

    id = Column(Integer, primary_key=True, index=True)
    medication_id = Column(Integer, ForeignKey("medications.id"), nullable=False)
    parent_id = Column(Integer, nullable=False)
    scheduled_for = Column(String(16), default="08:00 AM")
    taken_at = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String(32), default="TAKEN")  # 'TAKEN', 'MISSED', 'SKIPPED'
    log_date = Column(String(16), index=True)  # YYYY-MM-DD
    notes = Column(Text, nullable=True)

    medication = relationship("Medication", back_populates="logs")


class HealthDocument(Base):
    __tablename__ = "health_documents"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("parent_profiles.id"), nullable=False)
    filename = Column(String(256), nullable=False)
    document_type = Column(String(64), default="Blood Test")
    file_path = Column(String(512), nullable=True)
    ai_summary = Column(Text, nullable=True)
    is_shared_with_family = Column(Boolean, default=False)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)

    parent = relationship("ParentProfile", back_populates="health_documents")


class CareEvent(Base):
    __tablename__ = "care_events"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("parent_profiles.id"), nullable=False)
    event_type = Column(String(32), nullable=False)  # 'WATER', 'FOOD', 'SLEEP', 'ACTIVITY'
    value = Column(String(64), nullable=False)  # e.g., '1.5 Liters', 'Breakfast', '7 hours'
    notes = Column(Text, nullable=True)
    recorded_at = Column(DateTime, default=datetime.datetime.utcnow)

    parent = relationship("ParentProfile", back_populates="care_events")


class RoutineEvent(Base):
    __tablename__ = "routine_events"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("parent_profiles.id"), nullable=False)
    event_type = Column(String(64), nullable=False)  # 'MORNING_WALK', 'BREAKFAST', 'REST'
    start_time = Column(String(16), nullable=False)
    duration_minutes = Column(Integer, default=30)
    deviation_score = Column(Float, default=0.0)  # Standard deviations from baseline
    recorded_at = Column(DateTime, default=datetime.datetime.utcnow)

    parent = relationship("ParentProfile", back_populates="routine_events")


class SafetyEvent(Base):
    __tablename__ = "safety_events"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("parent_profiles.id"), nullable=False)
    source = Column(String(32), default="CCTV")  # 'CCTV', 'ROUTINE', 'CHECKIN', 'MEDICATION'
    severity = Column(String(32), default="ATTENTION")  # 'INFO', 'ATTENTION', 'CRITICAL'
    title = Column(String(256), nullable=False)
    title_tamil = Column(String(256), nullable=True)
    description = Column(Text, nullable=False)
    description_tamil = Column(Text, nullable=True)
    confidence = Column(Float, default=0.85)
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    parent = relationship("ParentProfile", back_populates="safety_events")


class CCTVDevice(Base):
    __tablename__ = "cctv_devices"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("parent_profiles.id"), nullable=False)
    name = Column(String(128), nullable=False)  # 'Living Room', 'Entrance', 'Kitchen'
    name_tamil = Column(String(128), default="வரவேற்பறை கேமரா")
    location = Column(String(128), default="Living Room")
    stream_url = Column(String(512), nullable=True)
    status = Column(String(32), default="LIVE")  # 'LIVE', 'OFFLINE', 'CONNECTING'
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("ParentProfile", back_populates="cctv_devices")
    permissions = relationship("CCTVPermission", back_populates="device", cascade="all, delete-orphan")


class CCTVPermission(Base):
    __tablename__ = "cctv_permissions"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("cctv_devices.id"), nullable=False)
    family_user_id = Column(Integer, nullable=False)
    can_view_live = Column(Boolean, default=True)
    can_view_events = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)

    device = relationship("CCTVDevice", back_populates="permissions")


class SOSAlert(Base):
    __tablename__ = "sos_alerts"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("parent_profiles.id"), nullable=False)
    status = Column(String(32), default="ACTIVE")  # 'ACTIVE', 'ACKNOWLEDGED', 'RESOLVED'
    triggered_at = Column(DateTime, default=datetime.datetime.utcnow)
    acknowledged_by = Column(String(128), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    escalation_level = Column(Integer, default=1)
    notes = Column(Text, nullable=True)

    parent = relationship("ParentProfile", back_populates="sos_alerts")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(32), default="SOS")  # 'SOS', 'SAFETY', 'MEDICATION', 'CHECKIN', 'ROUTINE'
    title = Column(String(256), nullable=False)
    title_tamil = Column(String(256), nullable=True)
    body = Column(Text, nullable=False)
    body_tamil = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    data_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="notifications")


class PrivacyPermission(Base):
    __tablename__ = "privacy_permissions"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, nullable=False)
    family_user_id = Column(Integer, nullable=False)
    share_health = Column(Boolean, default=True)
    share_activity = Column(Boolean, default=True)
    share_location = Column(Boolean, default=True)
    share_cctv = Column(Boolean, default=True)
    share_medication = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(128), nullable=False)  # 'VIEWED_CAMERA', 'ACCESSED_HEALTH_DOC', 'REVOKED_PERMISSION'
    target_resource = Column(String(128), nullable=True)
    ip_address = Column(String(64), default="127.0.0.1")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    details = Column(Text, nullable=True)

    user = relationship("User", back_populates="audit_logs")


class PrivacyPause(Base):
    __tablename__ = "privacy_pauses"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, nullable=False, index=True)
    is_paused = Column(Boolean, default=False)
    paused_until = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, default=30)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class HelpRequest(Base):
    __tablename__ = "help_requests"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, nullable=False, index=True)
    category = Column(String(64), nullable=False)  # 'groceries', 'medicine', 'chat', 'home', 'transport', 'discomfort'
    category_tamil = Column(String(128), nullable=True)
    note = Column(Text, nullable=True)
    status = Column(String(32), default="OPEN")  # 'OPEN', 'ACKNOWLEDGED', 'COMPLETED'
    handled_by = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class SafeReturnTrip(Base):
    __tablename__ = "safe_return_trips"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, nullable=False, index=True)
    destination = Column(String(128), default="Nearby Store")
    destination_tamil = Column(String(128), default="அருகிலுள்ள கடை")
    duration_minutes = Column(Integer, default=60)
    expected_return_at = Column(DateTime, nullable=False)
    returned_at = Column(DateTime, nullable=True)
    status = Column(String(32), default="OUT")  # 'OUT', 'RETURNED', 'OVERDUE'
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class AIFeedback(Base):
    __tablename__ = "ai_feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    event_type = Column(String(64), nullable=False)  # 'ROUTINE_ANOMALY', 'CCTV_STILLNESS', 'CHECKIN_DELAY'
    event_id = Column(Integer, nullable=True)
    feedback = Column(String(32), default="NOT_A_CONCERN")  # 'NOT_A_CONCERN', 'HELPFUL', 'FALSE_ALARM'
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class FamilyMessage(Base):
    __tablename__ = "family_messages"

    id = Column(Integer, primary_key=True, index=True)
    sender_name = Column(String(128), default="Family Member")
    sender_role = Column(String(32), default="FAMILY")
    receiver_name = Column(String(128), default="Amma")
    message_type = Column(String(32), default="warm_prompt")  # 'warm_prompt', 'text', 'voice'
    content = Column(Text, nullable=False)
    content_tamil = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class RoutineBaseline(Base):
    __tablename__ = "routine_baselines"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, nullable=False, unique=True)
    typical_wake_window = Column(String(64), default="06:30 AM — 07:00 AM")
    typical_morning_med = Column(String(64), default="08:00 AM")
    typical_checkin_window = Column(String(64), default="08:15 AM — 09:00 AM")
    typical_morning_activity = Column(String(64), default="Garden walk & light movement")
    typical_night_rest = Column(String(64), default="10:00 PM")
    confidence_score = Column(Float, default=0.91)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)


class CommunicationRequest(Base):
    __tablename__ = "communication_requests"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    family_member_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    family_member_name = Column(String(128), nullable=True)
    intent = Column(String(64), default="CALL_FAMILY", nullable=False)  # CALL_FAMILY, HEALTH_CONCERN, MEDICATION_HELP, FOOD_WATER, DOCTOR_HELP, HOME_INCIDENT, GENERAL_MESSAGE, EMERGENCY
    reason_category = Column(String(64), nullable=True)  # not_well, medicine, food_water, doctor, want_to_talk, call_me, home_incident, other
    reason_text = Column(String(256), nullable=True)
    reason_tamil = Column(String(256), nullable=True)
    voice_input = Column(Boolean, default=False)
    voice_transcript = Column(Text, nullable=True)
    ai_summary = Column(String(256), nullable=True)
    ai_summary_tamil = Column(String(256), nullable=True)
    priority = Column(String(32), default="NORMAL", nullable=False)  # NORMAL, IMPORTANT, URGENT
    status = Column(String(32), default="PENDING", nullable=False)  # PENDING, NOTIFIED, ACKNOWLEDGED, CALL_REQUESTED, CALLBACK_SCHEDULED, RESPONDING, RESOLVED, ESCALATED, CANCELLED
    automation_status = Column(String(32), default="ACTIVE", nullable=False)  # ACTIVE, WAITING, STOPPED, ESCALATED, COMPLETED
    parent_response = Column(String(64), nullable=True)  # acknowledged, call_me, needs_help, emergency, unclear
    guidance_count = Column(Integer, default=0, nullable=False)
    max_guidance_retries = Column(Integer, default=3, nullable=False)
    last_guidance_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    responded_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    parent = relationship("User", foreign_keys=[parent_id])
    family_member = relationship("User", foreign_keys=[family_member_id])
    responses = relationship("CommunicationResponse", back_populates="request", cascade="all, delete-orphan")
    callbacks = relationship("ScheduledCallback", back_populates="request", cascade="all, delete-orphan")


class CommunicationAttempt(Base):
    __tablename__ = "communication_attempts"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    request_id = Column(Integer, ForeignKey("communication_requests.id", ondelete="CASCADE"), nullable=True)
    channel = Column(String(32), default="CALL_REQUEST", nullable=False)  # CALL_REQUEST, VOICE, DIRECT_CALL
    attempt_time = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)


class CommunicationResponse(Base):
    __tablename__ = "communication_responses"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("communication_requests.id", ondelete="CASCADE"), index=True, nullable=False)
    responder_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    responder_name = Column(String(128), default="Family Member")
    response_type = Column(String(64), default="ACKNOWLEDGE", nullable=False)  # CALL_NOW, CALL_LATER, TEMPLATE_MSG, ACKNOWLEDGE
    template_key = Column(String(64), nullable=True)
    message = Column(Text, nullable=True)
    message_tamil = Column(Text, nullable=True)
    scheduled_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    request = relationship("CommunicationRequest", back_populates="responses")
    responder = relationship("User", foreign_keys=[responder_id])


class AutomatedResponseTemplate(Base):
    __tablename__ = "automated_response_templates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    template_type = Column(String(64), default="CALL_MISSED", nullable=False)  # CALL_MISSED, BUSY, ACKNOWLEDGEMENT, CALLBACK
    title = Column(String(128), nullable=False)
    text = Column(Text, nullable=False)
    text_tamil = Column(Text, nullable=True)
    is_default = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class ScheduledCallback(Base):
    __tablename__ = "scheduled_callbacks"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("communication_requests.id", ondelete="CASCADE"), index=True, nullable=False)
    family_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    scheduled_for = Column(DateTime, nullable=False)
    reminder_minutes = Column(Integer, default=30)
    status = Column(String(32), default="PENDING", nullable=False)  # PENDING, DUE, COMPLETED, CANCELLED
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    request = relationship("CommunicationRequest", back_populates="callbacks")


class EscalationRule(Base):
    __tablename__ = "escalation_rules"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    primary_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    secondary_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    trusted_contact_id = Column(Integer, ForeignKey("trusted_contacts.id", ondelete="SET NULL"), nullable=True)
    escalation_delay_minutes = Column(Integer, default=15, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)


class CommunicationAuditLog(Base):
    __tablename__ = "communication_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, nullable=True, index=True)
    parent_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=True)
    event_type = Column(String(128), nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


# ============================================================================
# NEW PRODUCT UPGRADE ENTITIES — FAMILY CONNECTION & INDEPENDENCE PLATFORM
# ============================================================================

class FamilyMemory(Base):
    __tablename__ = "family_memories"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    author_name = Column(String(128), default="Amma", nullable=False)
    category = Column(String(64), default="Family", index=True, nullable=False)  # Family, Childhood, Recipes, Important People, Places, Traditions, Life Stories, Personal Preferences
    title = Column(String(256), nullable=False)
    content = Column(Text, nullable=False)
    voice_url = Column(String(512), nullable=True)
    image_url = Column(String(512), nullable=True)
    is_private = Column(Boolean, default=False, nullable=False)  # If True, only parent can see
    shared_with_family = Column(Boolean, default=True, nullable=False)
    is_archived = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)


class LifeStory(Base):
    __tablename__ = "life_stories"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title = Column(String(256), nullable=False)
    category = Column(String(64), default="Childhood", nullable=False)
    transcript = Column(Text, nullable=False)
    audio_url = Column(String(512), nullable=True)
    recorded_date_text = Column(String(64), default="September 2026", nullable=False)
    is_shared_with_family = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)


class FamilyPresenceEvent(Base):
    __tablename__ = "family_presence_events"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    family_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    family_member_name = Column(String(128), nullable=False)
    relationship_type = Column(String(64), default="Child", nullable=False)
    interaction_type = Column(String(64), nullable=False)  # call, approved_message, video_call, family_check_in, shared_memory
    interaction_date = Column(String(16), index=True, nullable=False)  # YYYY-MM-DD
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class ConnectionGapInsight(Base):
    __tablename__ = "connection_gap_insights"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title = Column(String(256), default="Connection Pattern Change", nullable=False)
    message = Column(Text, nullable=False)
    message_tamil = Column(Text, nullable=True)
    why_text = Column(Text, nullable=False)
    why_text_tamil = Column(Text, nullable=True)
    status = Column(String(32), default="ACTIVE", nullable=False)  # ACTIVE, DISMISSED
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class FamilyAvailability(Base):
    __tablename__ = "family_availabilities"

    id = Column(Integer, primary_key=True, index=True)
    family_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    family_member_name = Column(String(128), default="Family Member", nullable=False)
    relationship_type = Column(String(64), default="Child", nullable=False)
    country = Column(String(64), default="USA", nullable=False)
    timezone = Column(String(64), default="America/New_York", nullable=False)
    normal_availability = Column(String(64), default="Available", nullable=False)  # Available, Busy, Preferred Call Window, Sleeping
    preferred_call_hours = Column(String(128), default="06:00 PM — 09:00 PM", nullable=False)
    notes = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)


class PersonalPreference(Base):
    __tablename__ = "personal_preferences"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    preferred_language = Column(String(64), default="Tamil", nullable=False)
    preferred_call_time = Column(String(64), default="07:00 PM", nullable=False)
    favorite_food = Column(String(256), default="Filter coffee, Idli, Rasam vadai", nullable=False)
    favorite_activities = Column(String(256), default="Carnatic music, morning garden walk, devotional books", nullable=False)
    preferred_family_contact = Column(String(128), default="Daughter (Priya)", nullable=False)
    preferred_communication_style = Column(String(64), default="Voice", nullable=False)
    important_routines = Column(Text, default="Morning temple walk at 07:00 AM, Evening prayers at 06:30 PM", nullable=False)
    preferred_voice_guidance_style = Column(String(64), default="Gentle, Calm Tamil", nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)


class MeaningfulMoment(Base):
    __tablename__ = "meaningful_moments"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    author_name = Column(String(128), default="Amma", nullable=False)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    photo_url = Column(String(512), nullable=True)
    voice_url = Column(String(512), nullable=True)
    moment_date = Column(String(16), index=True, nullable=False)  # YYYY-MM-DD
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class FamilySurprise(Base):
    __tablename__ = "family_surprises"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by_name = Column(String(128), default="Daughter", nullable=False)
    title = Column(String(256), nullable=False)
    surprise_type = Column(String(64), default="Birthday", nullable=False)
    event_date = Column(DateTime, nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(String(32), default="PLANNING", nullable=False)  # PLANNING, COMPLETED
    participants_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class CareCircleMember(Base):
    __tablename__ = "care_circle_members"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name = Column(String(128), nullable=False)
    relationship = Column(String(64), nullable=False)
    role_title = Column(String(64), default="Family Member", nullable=False)
    phone = Column(String(32), nullable=True)
    can_communication = Column(Boolean, default=True, nullable=False)
    can_health_docs = Column(Boolean, default=False, nullable=False)
    can_appointments = Column(Boolean, default=False, nullable=False)
    can_emergency_only = Column(Boolean, default=False, nullable=False)
    can_memories = Column(Boolean, default=True, nullable=False)
    can_cctv = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class TemporaryPermission(Base):
    __tablename__ = "temporary_permissions"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    grantee_name = Column(String(128), nullable=False)
    resource_type = Column(String(64), nullable=False)  # HEALTH_DOC, CCTV, LOCATION, FAMILY_MEMORY
    resource_name = Column(String(256), nullable=True)
    duration_hours = Column(Integer, default=24, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    status = Column(String(32), default="ACTIVE", nullable=False)  # ACTIVE, EXPIRED, REVOKED
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class OneTapFamilyUpdate(Base):
    __tablename__ = "one_tap_family_updates"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    message = Column(String(256), default="Amma is okay today ❤️", nullable=False)
    message_tamil = Column(String(256), default="அம்மா இன்று நலமாக இருக்கிறார் ❤️", nullable=True)
    sent_by = Column(String(128), default="Amma", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class FamiliarPlace(Base):
    __tablename__ = "familiar_places"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name = Column(String(128), nullable=False)
    name_tamil = Column(String(128), nullable=True)
    place_type = Column(String(64), default="TEMPLE", nullable=False)  # HOME, HOSPITAL, TEMPLE, GROCERY, RELATIVE_HOME
    address_or_landmark = Column(String(256), nullable=True)
    notes = Column(Text, nullable=True)
    is_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class CareHandover(Base):
    __tablename__ = "care_handovers"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    primary_caregiver_name = Column(String(128), default="Daughter (Priya)", nullable=False)
    temporary_caregiver_name = Column(String(128), default="Son (Karthik)", nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    duration_days = Column(Integer, default=3, nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(String(32), default="ACTIVE", nullable=False)  # ACTIVE, COMPLETED, REVOKED
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class IndependenceModeConfig(Base):
    __tablename__ = "independence_mode_configs"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    mode_enabled = Column(Boolean, default=True, nullable=False)
    current_escalation = Column(String(32), default="NORMAL", nullable=False)  # NORMAL, SMALL_CHANGE, MEANINGFUL_CHANGE, SAFETY_EVENT
    suppress_routine_alerts = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)


class ElderlyInterfaceConfig(Base):
    __tablename__ = "elderly_interface_configs"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    mode = Column(String(32), default="STANDARD", nullable=False)  # STANDARD, VOICE_FIRST, LARGE_TEXT, MINIMAL
    language = Column(String(10), default="ta", nullable=False)
    voice_guidance_active = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)


# ============================================================================
# MASTER FUNCTIONAL MODELS — CARE BASELINE, TIMELINE, AI ALERTS & PRIVACY
# ============================================================================

class DailyActivity(Base):
    __tablename__ = "daily_activities"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    record_date = Column(String(16), index=True, nullable=False)  # YYYY-MM-DD
    steps_count = Column(Integer, default=2400, nullable=False)
    active_minutes = Column(Integer, default=45, nullable=False)
    activity_score = Column(Float, default=0.88, nullable=False)  # 0.0 - 1.0
    summary = Column(String(256), default="Morning garden walk and light movement")
    recorded_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class SleepRecord(Base):
    __tablename__ = "sleep_records"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    sleep_date = Column(String(16), index=True, nullable=False)  # YYYY-MM-DD
    duration_hours = Column(Float, default=7.5, nullable=False)
    bed_time = Column(String(16), default="10:00 PM", nullable=False)
    wake_time = Column(String(16), default="06:30 AM", nullable=False)
    quality_rating = Column(String(32), default="RESTFUL", nullable=False)  # RESTFUL, LIGHT, INTERRUPTED
    recorded_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class MealRecord(Base):
    __tablename__ = "meal_records"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    meal_date = Column(String(16), index=True, nullable=False)  # YYYY-MM-DD
    meal_type = Column(String(32), nullable=False)  # Breakfast, Lunch, Evening Snack, Dinner
    description = Column(String(256), nullable=False)
    was_on_time = Column(Boolean, default=True, nullable=False)
    recorded_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class HydrationRecord(Base):
    __tablename__ = "hydration_records"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    record_date = Column(String(16), index=True, nullable=False)  # YYYY-MM-DD
    amount_liters = Column(Float, default=1.6, nullable=False)
    glasses_count = Column(Integer, default=7, nullable=False)
    recorded_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class CareTimelineItem(Base):
    __tablename__ = "care_timeline_items"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    event_time = Column(String(32), nullable=False)  # "10:42 AM"
    event_category = Column(String(64), nullable=False)  # ROUTINE_CHANGE, MEDICATION, ACTIVITY, MEAL, CHECKIN, SOS, FAMILY
    title = Column(String(256), nullable=False)
    title_tamil = Column(String(256), nullable=True)
    description = Column(Text, nullable=True)
    description_tamil = Column(Text, nullable=True)
    icon = Column(String(16), default="❤️", nullable=False)
    severity = Column(String(32), default="INFO", nullable=False)  # INFO, NOTICE, ATTENTION, URGENT
    source = Column(String(64), default="DATABASE", nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)


class RoutineFeatureRecord(Base):
    __tablename__ = "routine_feature_records"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    record_date = Column(String(16), index=True, nullable=False)  # YYYY-MM-DD
    checkin_delay_mins = Column(Float, default=0.0, nullable=False)
    med_delay_mins = Column(Float, default=0.0, nullable=False)
    activity_ratio = Column(Float, default=1.0, nullable=False)  # current / baseline
    sleep_hours = Column(Float, default=7.5, nullable=False)
    meal_count = Column(Integer, default=3, nullable=False)
    hydration_liters = Column(Float, default=1.6, nullable=False)
    interaction_count = Column(Integer, default=4, nullable=False)
    change_score = Column(Float, default=0.15, nullable=False)  # 0.00 - 1.00
    is_anomaly = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class AIAlert(Base):
    __tablename__ = "ai_alerts"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    alert_type = Column(String(64), default="ROUTINE_CHANGE", nullable=False)  # ROUTINE_CHANGE, MULTI_SIGNAL_SAFETY, CCTV_STILLNESS
    severity = Column(String(32), default="ATTENTION", nullable=False)  # NORMAL, MILD, ATTENTION, HIGH_PRIORITY
    title = Column(String(256), nullable=False)
    title_tamil = Column(String(256), nullable=True)
    message = Column(Text, nullable=False)
    message_tamil = Column(Text, nullable=True)
    change_score = Column(Float, default=0.0, nullable=False)  # 0.00 - 1.00
    anomaly_score = Column(Float, default=0.0, nullable=False)  # Isolation Forest decision_function
    is_anomaly = Column(Boolean, default=False, nullable=False)
    status = Column(String(32), default="ACTIVE", nullable=False)  # ACTIVE, CHECKED_IN, RESOLVED, DISMISSED
    family_action_taken = Column(String(64), nullable=True)  # CHECKED_IN, CALLED, MESSAGED
    parent_response_text = Column(String(256), nullable=True)
    suggested_action = Column(String(256), default="Consider checking in with Amma")
    suggested_action_tamil = Column(String(256), default="அம்மாவிடம் நலம் விசாரிக்கலாம்")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    resolved_at = Column(DateTime, nullable=True)

    evidences = relationship("AIAlertEvidence", back_populates="alert", cascade="all, delete-orphan")


class AIAlertEvidence(Base):
    __tablename__ = "ai_alert_evidences"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("ai_alerts.id", ondelete="CASCADE"), index=True, nullable=False)
    signal_name = Column(String(128), nullable=False)
    signal_name_tamil = Column(String(128), nullable=True)
    baseline_value = Column(String(128), nullable=False)
    current_value = Column(String(128), nullable=False)
    deviation_description = Column(String(256), nullable=False)
    deviation_description_tamil = Column(String(256), nullable=True)
    signal_status = Column(String(32), default="ATTENTION", nullable=False)  # NORMAL, NOTICE, ATTENTION

    alert = relationship("AIAlert", back_populates="evidences")


class PrivacySetting(Base):
    __tablename__ = "privacy_settings"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    health_info = Column(Boolean, default=True, nullable=False)
    daily_activity = Column(Boolean, default=True, nullable=False)
    location_sharing = Column(Boolean, default=False, nullable=False)  # Privacy-first default OFF
    cctv_access = Column(Boolean, default=False, nullable=False)      # Privacy-first default OFF
    memories_sharing = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)


