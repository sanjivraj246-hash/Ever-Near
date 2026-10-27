from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

# Auth
class UserRegister(BaseModel):
    phone: str
    full_name: str
    role: str = "PARENT"  # 'PARENT' or 'FAMILY'
    password: str
    password_confirm: Optional[str] = None
    preferred_name: Optional[str] = None
    relationship_type: Optional[str] = "Child"
    language_pref: Optional[str] = "ta"

class UserLogin(BaseModel):
    phone: str
    password: Optional[str] = None
    pin: Optional[str] = None
    otp: Optional[str] = None

class GoogleAuthRequest(BaseModel):
    id_token: str
    role: Optional[str] = "PARENT"
    relationship_type: Optional[str] = "Child"
    phone: Optional[str] = None
    pin: Optional[str] = None
    full_name: Optional[str] = None
    language_pref: Optional[str] = "ta"

class GoogleAccountLinkRequest(BaseModel):
    phone: str
    pin: str
    id_token: str

class ForgotPinRequest(BaseModel):
    phone: str

class ForgotPinResetRequest(BaseModel):
    phone: str
    recovery_token: str
    new_pin: str
    new_pin_confirm: Optional[str] = None

class ForgotPinResponse(BaseModel):
    message: str
    phone: str
    dev_recovery_token: Optional[str] = None
    sms_dispatched: bool = False

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    full_name: str

class UserProfileResponse(BaseModel):
    id: int
    phone: str
    full_name: str
    role: str
    preferred_name: Optional[str] = None
    language_pref: Optional[str] = "ta"
    relationship_type: Optional[str] = None

# CheckIn
class CheckInCreate(BaseModel):
    feeling: str  # 'good', 'okay', 'not_well'
    feeling_tamil: Optional[str] = None
    voice_input: bool = False
    voice_transcript: Optional[str] = None
    note: Optional[str] = None

class CheckInResponse(BaseModel):
    id: int
    user_id: int
    feeling: str
    feeling_tamil: Optional[str]
    voice_input: bool
    voice_transcript: Optional[str]
    note: Optional[str]
    check_in_date: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

# Medication
class MedicationCreate(BaseModel):
    name: str
    dosage: str = "1 tablet"
    schedule_time: str = "08:00 AM"
    period: str = "Morning"
    instructions: Optional[str] = "After food with warm water"
    icon: Optional[str] = "pill"

class MedicationLogCreate(BaseModel):
    status: str = "TAKEN"
    notes: Optional[str] = None

class MedicationItemResponse(BaseModel):
    id: int
    parent_id: Optional[int] = None
    name: str
    dosage: str
    schedule_time: str
    period: str
    instructions: Optional[str] = None
    icon: str = "pill"
    today_taken: bool = False
    taken_at: Optional[datetime] = None

MedicationResponse = MedicationItemResponse

# Care
class CareLogCreate(BaseModel):
    event_type: str  # WATER, FOOD, SLEEP, ACTIVITY
    value: str
    notes: Optional[str] = None

class CareSummaryResponse(BaseModel):
    wellbeing: str
    water_liters: str
    food_status: str
    sleep_hours: str
    activity_level: str
    medications_taken: int
    medications_total: int

# Family
class FamilyInviteCreate(BaseModel):
    phone: str
    relationship_type: str = "Child"
    name: str

class FamilyMemberResponse(BaseModel):
    id: int
    name: str
    relationship_type: str
    phone: str
    status: str
    can_view_health: bool
    can_view_cctv: bool

class FamilyRelationshipCreate(BaseModel):
    family_user_id: int
    relationship_type: str = "Child"
    phone: Optional[str] = None
    can_view_health: bool = True
    can_view_cctv: bool = True
    can_receive_sos: bool = True

class FamilyRelationshipResponse(BaseModel):
    id: int
    parent_id: int
    family_user_id: int
    relationship_type: str
    status: str
    can_view_health: bool
    can_view_cctv: bool
    can_receive_sos: bool
    phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Family Invitations
class FamilyInvitationCreate(BaseModel):
    relationship_type: str = "Child"
    invited_phone: Optional[str] = None
    can_view_health: bool = True
    can_view_cctv: bool = True
    can_receive_sos: bool = True
    expires_hours: int = 48

class FamilyInvitationResponse(BaseModel):
    id: int
    parent_id: int
    invite_code: str
    relationship_type: str
    invited_phone: Optional[str] = None
    can_view_health: bool
    can_view_cctv: bool
    can_receive_sos: bool
    is_used: bool
    used_by_user_id: Optional[int] = None
    expires_at: datetime
    created_at: datetime
    invite_link: Optional[str] = None

    class Config:
        from_attributes = True

class FamilyInvitationVerifyResponse(BaseModel):
    valid: bool
    invite_code: str
    parent_id: int
    parent_name: str
    parent_preferred_name: str
    relationship_type: str
    can_view_health: bool
    can_view_cctv: bool
    can_receive_sos: bool
    expires_at: datetime

class FamilyInvitationAccept(BaseModel):
    invite_code: str

# Trusted Contacts
class TrustedContactCreate(BaseModel):
    name: str
    relationship_type: str = "Neighbor"
    phone: str
    priority_order: int = 1
    can_receive_sos: bool = True
    notes: Optional[str] = None

class TrustedContactResponse(BaseModel):
    id: int
    parent_id: int
    name: str
    relationship_type: str
    phone: str
    priority_order: int
    can_receive_sos: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# SOS
class SOSCreate(BaseModel):
    notes: Optional[str] = "Urgent assistance requested"

class SOSAcknowledge(BaseModel):
    responder_name: Optional[str] = "Family Member"

class SOSResponse(BaseModel):
    id: int
    parent_id: int
    parent_name: Optional[str] = "Parent"
    status: str
    triggered_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    escalation_level: int = 1
    notes: Optional[str] = None

SOSAlertCreate = SOSCreate
SOSAcknowledgeRequest = SOSAcknowledge
SOSAlertResponse = SOSResponse

# AI Routine & Briefing
class AIRoutineStatusResponse(BaseModel):
    status: str  # 'normal', 'attention', 'deviation'
    reason: str
    reason_tamil: str
    confidence: float
    average_checkin_time: str
    today_checkin_time: Optional[str]
    activity_score: float
    recommendation: str

class AIFamilyBriefingResponse(BaseModel):
    parent_name: str
    status_indicator: str  # 'Stable', 'Attention', 'Urgent'
    summary_text: str
    summary_text_tamil: str
    checkin_status: str
    medication_status: str
    activity_window: str
    cctv_status: str
    ai_recommendation: str

# Safety
class SafetyEventResponse(BaseModel):
    id: int
    source: str
    severity: str
    title: str
    title_tamil: Optional[str]
    description: str
    description_tamil: Optional[str]
    confidence: float
    acknowledged: bool
    created_at: datetime

    class Config:
        from_attributes = True

# CCTV
class CCTVDeviceCreate(BaseModel):
    name: str
    location: str
    stream_url: Optional[str] = None

class CCTVDeviceResponse(BaseModel):
    id: int
    name: str
    name_tamil: Optional[str]
    location: str
    stream_url: Optional[str]
    status: str
    enabled: bool
    is_simulation: bool = True
    source_type: str = "DEMO / SIMULATED CAMERA"

    class Config:
        from_attributes = True

# Privacy
class PrivacyUpdateRequest(BaseModel):
    family_user_id: Optional[int] = 2
    share_health: Optional[bool] = None
    share_activity: Optional[bool] = None
    share_location: Optional[bool] = None
    share_cctv: Optional[bool] = None
    share_medication: Optional[bool] = None

class PrivacyStatusResponse(BaseModel):
    share_health: bool
    share_activity: bool
    share_location: bool
    share_cctv: bool
    share_medication: bool

class AuditLogResponse(BaseModel):
    id: int
    action: str
    target_resource: Optional[str]
    timestamp: datetime
    details: Optional[str]

# Health Documents
class HealthDocumentResponse(BaseModel):
    id: int
    filename: str
    document_type: str
    ai_summary: Optional[str]
    is_shared_with_family: bool
    uploaded_at: datetime

    class Config:
        from_attributes = True

class HealthExplanationRequest(BaseModel):
    term: str
    context: Optional[str] = None

class HealthExplanationResponse(BaseModel):
    term: str
    explanation: str
    explanation_tamil: str
    disclaimer: str

# Notifications
class NotificationResponse(BaseModel):
    id: int
    type: str
    title: str
    title_tamil: Optional[str]
    body: str
    body_tamil: Optional[str]
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

# AI Ask EVER NEAR
class AIAskRequest(BaseModel):
    question: str
    lang: Optional[str] = "en"

class AIAskResponse(BaseModel):
    question: str
    answer: str
    answer_tamil: str
    sources_used: List[str]
    timestamp: datetime

# Explainable AI Breakdown ("See Why")
class ExplainableSignal(BaseModel):
    name: str
    name_tamil: str
    status: str  # 'NORMAL', 'NOTICE', 'ATTENTION'
    detail: str
    detail_tamil: str

class ExplainableStatusResponse(BaseModel):
    overall_status: str  # 'NORMAL', 'NOTICE', 'ATTENTION', 'URGENT'
    headline: str
    headline_tamil: str
    what_changed: str
    what_changed_tamil: str
    when_noticed: str
    why_noticed: str
    why_noticed_tamil: str
    signals: List[ExplainableSignal]
    suggested_action: str
    suggested_action_tamil: str
    disclaimer: str

# My Normal Day Baseline
class NormalDayBaselineResponse(BaseModel):
    typical_wake_window: str
    typical_morning_med: str
    typical_checkin_window: str
    typical_morning_activity: str
    typical_night_rest: str
    confidence_score: float

# Privacy Pause
class PrivacyPauseRequest(BaseModel):
    duration_minutes: int = 30

class PrivacyPauseResponse(BaseModel):
    is_paused: bool
    paused_until: Optional[datetime]
    duration_minutes: int
    emergency_remains_active: bool = True

# Help Requests ("I Need Help")
class HelpRequestCreate(BaseModel):
    category: str
    category_tamil: Optional[str] = None
    note: Optional[str] = None

class HelpRequestResponse(BaseModel):
    id: int
    category: str
    category_tamil: Optional[str]
    note: Optional[str]
    status: str
    handled_by: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

# Safe Return
class SafeReturnStartRequest(BaseModel):
    destination: str = "Nearby Store"
    destination_tamil: Optional[str] = "அருகிலுள்ள கடை"
    duration_minutes: int = 60

class SafeReturnResponse(BaseModel):
    id: int
    destination: str
    destination_tamil: Optional[str]
    duration_minutes: int
    expected_return_at: datetime
    returned_at: Optional[datetime]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# AI Feedback
class AIFeedbackRequest(BaseModel):
    event_type: str
    event_id: Optional[int] = None
    feedback: str = "NOT_A_CONCERN"
    notes: Optional[str] = None

# Family Messages
class FamilyMessageCreate(BaseModel):
    content: str
    content_tamil: Optional[str] = None
    message_type: str = "warm_prompt"
    receiver_name: str = "Amma"

class FamilyMessageResponse(BaseModel):
    id: int
    sender_name: str
    sender_role: str
    receiver_name: str
    message_type: str
    content: str
    content_tamil: Optional[str]
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Independence View
class RoutineTaskItem(BaseModel):
    id: str
    title: str
    title_tamil: str
    completed: bool
    completed_time: Optional[str]

class IndependenceViewResponse(BaseModel):
    completed_count: int
    total_count: int
    positive_message: str
    positive_message_tamil: str
    tasks: List[RoutineTaskItem]

# Communication System Schemas
class CommunicationRequestCreate(BaseModel):
    family_member_id: Optional[int] = None
    family_member_name: Optional[str] = None
    intent: str = "CALL_FAMILY"
    reason_category: Optional[str] = "want_to_talk"
    reason_text: Optional[str] = None
    reason_tamil: Optional[str] = None
    voice_input: bool = False
    voice_transcript: Optional[str] = None
    priority: str = "NORMAL"  # NORMAL, IMPORTANT, URGENT

class CommunicationResponseCreate(BaseModel):
    response_type: str = "ACKNOWLEDGE"  # CALL_NOW, CALL_LATER, TEMPLATE_MSG, ACKNOWLEDGE
    template_key: Optional[str] = None
    message: Optional[str] = None
    message_tamil: Optional[str] = None
    scheduled_minutes: Optional[int] = None

class ScheduleCallbackRequest(BaseModel):
    minutes: int = 30
    custom_time: Optional[str] = None

class VoiceResponseInput(BaseModel):
    request_id: Optional[int] = None
    spoken_text: str
    language: str = "ta"

class VoiceEnquiryClassifyRequest(BaseModel):
    spoken_text: str
    language: str = "ta"

class VoiceEnquiryClassifyResponse(BaseModel):
    spoken_text: str
    detected_language: str
    intent: str
    category: str
    reason_text: str
    reason_tamil: str
    priority: str
    confidence: float
    safe_summary: str
    safe_summary_tamil: str

class VoiceResponseClassificationResult(BaseModel):
    classification: str  # ACKNOWLEDGED, REQUEST_CALL, NEEDS_HELP, EMERGENCY, UNCLEAR
    automation_action: str  # STOP, CONTINUE, ESCALATE, RETRY
    guidance_message: str
    guidance_message_tamil: str
    should_stop_reminder: bool
    is_emergency: bool = False

class ResponseTemplateCreate(BaseModel):
    template_type: str = "CALL_MISSED"  # CALL_MISSED, BUSY, ACKNOWLEDGEMENT, CALLBACK
    title: str
    text: str
    text_tamil: Optional[str] = None
    is_default: bool = True

class ResponseTemplateResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    template_type: str
    title: str
    text: str
    text_tamil: Optional[str]
    is_default: bool
    created_at: datetime

    class Config:
        from_attributes = True

class ScheduledCallbackResponse(BaseModel):
    id: int
    request_id: int
    family_user_id: int
    parent_id: int
    scheduled_for: datetime
    reminder_minutes: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class EscalationRuleUpdate(BaseModel):
    primary_user_id: Optional[int] = None
    secondary_user_id: Optional[int] = None
    trusted_contact_id: Optional[int] = None
    escalation_delay_minutes: int = 15
    is_enabled: bool = True

class EscalationRuleResponse(BaseModel):
    id: int
    parent_id: int
    primary_user_id: Optional[int]
    secondary_user_id: Optional[int]
    trusted_contact_id: Optional[int]
    escalation_delay_minutes: int
    is_enabled: bool
    primary_name: Optional[str] = None
    secondary_name: Optional[str] = None
    trusted_contact_name: Optional[str] = None

class CommunicationAuditLogResponse(BaseModel):
    id: int
    request_id: Optional[int]
    parent_id: int
    user_id: Optional[int]
    event_type: str
    details: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True

class CommunicationItemResponse(BaseModel):
    id: int
    parent_id: int
    parent_name: str
    family_member_id: Optional[int]
    family_member_name: Optional[str]
    intent: str
    reason_category: Optional[str]
    reason_text: Optional[str]
    reason_tamil: Optional[str]
    voice_input: bool
    voice_transcript: Optional[str]
    ai_summary: Optional[str]
    ai_summary_tamil: Optional[str]
    priority: str
    status: str
    automation_status: str
    parent_response: Optional[str]
    guidance_count: int
    max_guidance_retries: int
    created_at: datetime
    updated_at: datetime
    responded_at: Optional[datetime]
    resolved_at: Optional[datetime]
    recent_attempts_count: int = 0
    unusual_activity_detected: bool = False
    latest_response_message: Optional[str] = None
    latest_response_message_tamil: Optional[str] = None
    scheduled_callback_time: Optional[datetime] = None


# ============================================================================
# NEW UPGRADE SCHEMAS — FAMILY CONNECTION & INDEPENDENCE PLATFORM
# ============================================================================

class FamilyMemoryCreate(BaseModel):
    category: str = "Family"
    title: str
    content: str
    voice_url: Optional[str] = None
    image_url: Optional[str] = None
    is_private: bool = False
    shared_with_family: bool = True

class FamilyMemoryResponse(BaseModel):
    id: int
    parent_id: int
    author_name: str
    category: str
    title: str
    content: str
    voice_url: Optional[str] = None
    image_url: Optional[str] = None
    is_private: bool
    shared_with_family: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class LifeStoryCreate(BaseModel):
    title: str
    category: str = "Childhood"
    transcript: str
    audio_url: Optional[str] = None
    recorded_date_text: Optional[str] = "September 2026"
    is_shared_with_family: bool = True

class LifeStoryResponse(BaseModel):
    id: int
    parent_id: int
    title: str
    category: str
    transcript: str
    audio_url: Optional[str] = None
    recorded_date_text: str
    is_shared_with_family: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class FamilyPresenceEventCreate(BaseModel):
    family_member_name: str
    relationship_type: str = "Child"
    interaction_type: str  # call, approved_message, video_call, family_check_in, shared_memory
    notes: Optional[str] = None

class FamilyPresenceMemberStat(BaseModel):
    family_member_name: str
    relationship_type: str
    total_interactions: int
    interaction_breakdown: dict  # {"call": 2, "approved_message": 2, ...}

class FamilyPresenceSummaryResponse(BaseModel):
    period: str = "This Week"
    members: List[FamilyPresenceMemberStat]
    recent_events: List[dict]

class ConnectionGapInsightResponse(BaseModel):
    id: int
    title: str
    message: str
    message_tamil: Optional[str] = None
    why_text: str
    why_text_tamil: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class FamilyAvailabilityUpdate(BaseModel):
    family_member_name: Optional[str] = None
    relationship_type: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    normal_availability: Optional[str] = None
    preferred_call_hours: Optional[str] = None
    notes: Optional[str] = None

class FamilyAvailabilityResponse(BaseModel):
    id: int
    family_user_id: int
    family_member_name: str
    relationship_type: str
    country: str
    timezone: str
    normal_availability: str
    preferred_call_hours: str
    status_summary: str
    local_time_display: str
    notes: Optional[str] = None
    updated_at: datetime

    class Config:
        from_attributes = True

class PersonalPreferenceUpdate(BaseModel):
    preferred_language: Optional[str] = None
    preferred_call_time: Optional[str] = None
    favorite_food: Optional[str] = None
    favorite_activities: Optional[str] = None
    preferred_family_contact: Optional[str] = None
    preferred_communication_style: Optional[str] = None
    important_routines: Optional[str] = None
    preferred_voice_guidance_style: Optional[str] = None

class PersonalPreferenceResponse(BaseModel):
    id: int
    parent_id: int
    preferred_language: str
    preferred_call_time: str
    favorite_food: str
    favorite_activities: str
    preferred_family_contact: str
    preferred_communication_style: str
    important_routines: str
    preferred_voice_guidance_style: str
    updated_at: datetime

    class Config:
        from_attributes = True

class MeaningfulMomentCreate(BaseModel):
    title: str
    description: Optional[str] = None
    photo_url: Optional[str] = None
    voice_url: Optional[str] = None
    moment_date: Optional[str] = None

class MeaningfulMomentResponse(BaseModel):
    id: int
    parent_id: int
    author_name: str
    title: str
    description: Optional[str] = None
    photo_url: Optional[str] = None
    voice_url: Optional[str] = None
    moment_date: str
    created_at: datetime

    class Config:
        from_attributes = True

class SurpriseParticipant(BaseModel):
    name: str
    task: str
    completed: bool = False

class FamilySurpriseCreate(BaseModel):
    title: str
    surprise_type: str = "Birthday"
    event_date: datetime
    notes: Optional[str] = None
    participants: List[SurpriseParticipant] = []

class FamilySurpriseResponse(BaseModel):
    id: int
    parent_id: int
    created_by_name: str
    title: str
    surprise_type: str
    event_date: datetime
    notes: Optional[str] = None
    status: str
    participants: List[SurpriseParticipant]
    is_visible_to_parent: bool = False
    created_at: datetime

class CareCircleMemberCreate(BaseModel):
    name: str
    relationship: str
    role_title: str = "Family Member"
    phone: Optional[str] = None
    can_communication: bool = True
    can_health_docs: bool = False
    can_appointments: bool = False
    can_emergency_only: bool = False
    can_memories: bool = True
    can_cctv: bool = False

class CareCircleMemberUpdate(BaseModel):
    role_title: Optional[str] = None
    can_communication: Optional[bool] = None
    can_health_docs: Optional[bool] = None
    can_appointments: Optional[bool] = None
    can_emergency_only: Optional[bool] = None
    can_memories: Optional[bool] = None
    can_cctv: Optional[bool] = None
    is_active: Optional[bool] = None

class CareCircleMemberResponse(BaseModel):
    id: int
    parent_id: int
    name: str
    relationship: str
    role_title: str
    phone: Optional[str]
    can_communication: bool
    can_health_docs: bool
    can_appointments: bool
    can_emergency_only: bool
    can_memories: bool
    can_cctv: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class TemporaryPermissionCreate(BaseModel):
    grantee_name: str
    resource_type: str  # HEALTH_DOC, CCTV, LOCATION, FAMILY_MEMORY
    resource_name: Optional[str] = None
    duration_hours: int = 24

class TemporaryPermissionResponse(BaseModel):
    id: int
    parent_id: int
    grantee_name: str
    resource_type: str
    resource_name: Optional[str]
    duration_hours: int
    expires_at: datetime
    status: str  # ACTIVE, EXPIRED, REVOKED
    time_remaining_str: str
    is_expired: bool
    created_at: datetime

class OneTapFamilyUpdateCreate(BaseModel):
    message: Optional[str] = "Amma is okay today ❤️"
    message_tamil: Optional[str] = "அம்மா இன்று நலமாக இருக்கிறார் ❤️"

class OneTapFamilyUpdateResponse(BaseModel):
    id: int
    parent_id: int
    message: str
    message_tamil: Optional[str]
    sent_by: str
    created_at: datetime

    class Config:
        from_attributes = True

class FamiliarPlaceCreate(BaseModel):
    name: str
    name_tamil: Optional[str] = None
    place_type: str = "TEMPLE"
    address_or_landmark: Optional[str] = None
    notes: Optional[str] = None

class FamiliarPlaceResponse(BaseModel):
    id: int
    parent_id: int
    name: str
    name_tamil: Optional[str]
    place_type: str
    address_or_landmark: Optional[str]
    notes: Optional[str]
    is_enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True

class CareHandoverCreate(BaseModel):
    primary_caregiver_name: str = "Daughter (Priya)"
    temporary_caregiver_name: str = "Son (Karthik)"
    start_date: datetime
    end_date: datetime
    duration_days: int = 3
    notes: Optional[str] = None

class CareHandoverResponse(BaseModel):
    id: int
    parent_id: int
    primary_caregiver_name: str
    temporary_caregiver_name: str
    start_date: datetime
    end_date: datetime
    duration_days: int
    notes: Optional[str]
    status: str
    is_currently_active: bool
    date_range_display: str
    created_at: datetime

class IndependenceModeUpdate(BaseModel):
    mode_enabled: Optional[bool] = None
    current_escalation: Optional[str] = None
    suppress_routine_alerts: Optional[bool] = None

class IndependenceModeResponse(BaseModel):
    id: int
    parent_id: int
    mode_enabled: bool
    current_escalation: str
    suppress_routine_alerts: bool
    escalation_flow: List[dict]
    explanation: str
    updated_at: datetime

class ElderlyInterfaceConfigUpdate(BaseModel):
    mode: Optional[str] = None  # STANDARD, VOICE_FIRST, LARGE_TEXT, MINIMAL
    language: Optional[str] = None  # ta, en
    voice_guidance_active: Optional[bool] = None

class ElderlyInterfaceConfigResponse(BaseModel):
    id: int
    parent_id: int
    mode: str
    language: str
    voice_guidance_active: bool
    updated_at: datetime

    class Config:
        from_attributes = True

class MemoryAssistantRequest(BaseModel):
    question: str
    lang: str = "en"

class MemoryAssistantResponse(BaseModel):
    question: str
    answer: str
    answer_tamil: str
    status: str  # KNOWN or UNKNOWN
    sources_used: List[str]
    timestamp: datetime

class FamilyBriefingItem(BaseModel):
    icon: str
    text: str
    text_tamil: str
    category: str

class FamilyBriefingNewResponse(BaseModel):
    headline: str
    headline_tamil: str
    items: List[FamilyBriefingItem]
    generated_at: str

class FamilyTimelineEvent(BaseModel):
    id: str
    date_display: str
    event_type: str  # call, message, memory, moment, story, update, celebration
    icon: str
    title: str
    description: Optional[str] = None
    author: Optional[str] = None
    media_url: Optional[str] = None
    audio_url: Optional[str] = None
    created_at: datetime

class FamilyContinuityItem(BaseModel):
    category: str
    title: str
    snippet: str
    date_text: str
    has_audio: bool
    has_photo: bool
    id: int
    item_type: str  # MEMORY or STORY


# ============================================================================
# MASTER FUNCTIONAL SCHEMAS — AI ALERTS, TIMELINE, PRIVACY, DEMO SIMULATION
# ============================================================================

class AIAlertEvidenceResponse(BaseModel):
    id: int
    signal_name: str
    signal_name_tamil: Optional[str] = None
    baseline_value: str
    current_value: str
    deviation_description: str
    deviation_description_tamil: Optional[str] = None
    signal_status: str

    class Config:
        from_attributes = True


class AIAlertResponse(BaseModel):
    id: int
    parent_id: int
    alert_type: str
    severity: str
    title: str
    title_tamil: Optional[str] = None
    message: str
    message_tamil: Optional[str] = None
    change_score: float
    anomaly_score: float
    is_anomaly: bool
    status: str
    family_action_taken: Optional[str] = None
    parent_response_text: Optional[str] = None
    suggested_action: str
    suggested_action_tamil: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
    evidences: List[AIAlertEvidenceResponse] = []

    class Config:
        from_attributes = True


class AIAlertExplanationResponse(BaseModel):
    alert_id: int
    title: str
    title_tamil: Optional[str] = None
    detected_change: str
    detected_change_tamil: Optional[str] = None
    baseline_comparison: str
    baseline_comparison_tamil: Optional[str] = None
    change_score: float
    anomaly_score: float
    severity: str
    system_interpretation: str
    system_interpretation_tamil: Optional[str] = None
    suggested_action: str
    suggested_action_tamil: Optional[str] = None
    supporting_signals: List[AIAlertEvidenceResponse]
    disclaimer: str


class CareTimelineItemResponse(BaseModel):
    id: int
    parent_id: int
    event_time: str
    event_category: str
    title: str
    title_tamil: Optional[str] = None
    description: Optional[str] = None
    description_tamil: Optional[str] = None
    icon: str
    severity: str
    source: str
    created_at: datetime

    class Config:
        from_attributes = True


class PrivacySettingsUpdateRequest(BaseModel):
    health_info: Optional[bool] = None
    daily_activity: Optional[bool] = None
    location_sharing: Optional[bool] = None
    cctv_access: Optional[bool] = None
    memories_sharing: Optional[bool] = None


class PrivacySettingsResponse(BaseModel):
    id: int
    parent_id: int
    health_info: bool
    daily_activity: bool
    location_sharing: bool
    cctv_access: bool
    memories_sharing: bool
    updated_at: datetime

    class Config:
        from_attributes = True


class FamilyEnquiryCreateRequest(BaseModel):
    family_member_id: Optional[int] = None
    family_member_name: Optional[str] = None
    reason_category: str = "want_to_talk"  # medicine, not_well, want_to_talk, need_help, call_me, incident, other
    reason_text: str = "Want to talk"
    reason_tamil: Optional[str] = None
    priority: str = "NORMAL"


class FamilyEnquiryPatchRequest(BaseModel):
    action: str  # RESPONDING, CALL_NOW, REPLY, LATER, RESOLVED
    message: Optional[str] = None
    message_tamil: Optional[str] = None
    scheduled_minutes: Optional[int] = None


class FamilyEnquiryItemResponse(BaseModel):
    id: int
    parent_id: int
    parent_name: str
    family_member_id: Optional[int] = None
    family_member_name: str
    reason_category: str
    reason_text: str
    reason_tamil: Optional[str] = None
    status: str
    priority: str
    family_response_message: Optional[str] = None
    responding_caregiver: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DemoSimulationRequest(BaseModel):
    scenario: str = "abnormal_day"  # "abnormal_day", "normal_day", "cctv_fall_simulation"
    parent_id: Optional[int] = None


class DemoSimulationResponse(BaseModel):
    scenario: str
    status: str
    headline: str
    headline_tamil: str
    change_score: float
    is_anomaly: bool
    anomaly_score: float
    alert_created: bool
    alert_id: Optional[int] = None
    explanation: str
    suggested_action: str
    timeline_event_id: Optional[int] = None
    simulation_disclaimer: str


class VoiceRouteRequest(BaseModel):
    spoken_text: str
    language: str = "ta"


class VoiceRouteResponse(BaseModel):
    spoken_text: str
    language: str
    intent: str
    category: str
    priority: str
    target_flow: str
    target_route: str
    suggested_action: str
    suggested_action_tamil: str
    explanation: str
    explanation_tamil: str




