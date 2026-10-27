import json
import datetime
from zoneinfo import ZoneInfo
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.entities import (
    User, ParentProfile, FamilyRelationship, Notification,
    FamilyMemory, LifeStory, FamilyPresenceEvent, ConnectionGapInsight,
    FamilyAvailability, PersonalPreference, MeaningfulMoment, FamilySurprise,
    CareCircleMember, TemporaryPermission, OneTapFamilyUpdate, FamiliarPlace,
    CareHandover, IndependenceModeConfig, ElderlyInterfaceConfig,
    DailyCheckIn, FamilyMessage, CommunicationRequest
)
from app.schemas.schemas import (
    FamilyMemoryCreate, FamilyMemoryResponse,
    LifeStoryCreate, LifeStoryResponse,
    FamilyPresenceEventCreate, FamilyPresenceSummaryResponse, FamilyPresenceMemberStat,
    ConnectionGapInsightResponse,
    FamilyAvailabilityUpdate, FamilyAvailabilityResponse,
    PersonalPreferenceUpdate, PersonalPreferenceResponse,
    MeaningfulMomentCreate, MeaningfulMomentResponse,
    FamilySurpriseCreate, FamilySurpriseResponse, SurpriseParticipant,
    CareCircleMemberCreate, CareCircleMemberUpdate, CareCircleMemberResponse,
    TemporaryPermissionCreate, TemporaryPermissionResponse,
    OneTapFamilyUpdateCreate, OneTapFamilyUpdateResponse,
    FamiliarPlaceCreate, FamiliarPlaceResponse,
    CareHandoverCreate, CareHandoverResponse,
    IndependenceModeUpdate, IndependenceModeResponse,
    ElderlyInterfaceConfigUpdate, ElderlyInterfaceConfigResponse,
    MemoryAssistantRequest, MemoryAssistantResponse,
    FamilyBriefingNewResponse, FamilyBriefingItem,
    FamilyTimelineEvent, FamilyContinuityItem
)
from app.routers.deps import get_current_user
from app.core.websocket import ws_manager

router = APIRouter(prefix="/family-connection", tags=["Family Connection & Independence Upgrade"])


def get_target_parent_id(current_user: User, db: Session) -> int:
    """Returns verified parent user_id for current user or enforces authorization."""
    if current_user.role.upper() == "PARENT":
        return current_user.id

    # 1. Approved relationship check
    rel = db.query(FamilyRelationship).filter(
        FamilyRelationship.family_user_id == current_user.id,
        FamilyRelationship.status == "APPROVED"
    ).first()
    if rel:
        return rel.parent_id

    # 2. Care circle membership check
    if current_user.phone:
        circle = db.query(CareCircleMember).filter(
            CareCircleMember.phone == current_user.phone,
            CareCircleMember.is_active == True
        ).first()
        if circle:
            return circle.parent_id

    # Unlinked stranger family member
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied. You do not have an approved family relationship with this parent."
    )


# ============================================================================
# 1. FAMILY MEMORY BRIDGE
# ============================================================================

@router.get("/memories", response_model=List[FamilyMemoryResponse])
def get_family_memories(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    query = db.query(FamilyMemory).filter(
        FamilyMemory.parent_id == parent_id,
        FamilyMemory.is_archived == False
    )

    # Privacy filtering: family members cannot see private memories
    if current_user.role.upper() == "FAMILY":
        query = query.filter(
            FamilyMemory.is_private == False,
            FamilyMemory.shared_with_family == True
        )

    if category and category.lower() != "all":
        query = query.filter(FamilyMemory.category == category)

    return query.order_by(FamilyMemory.created_at.desc()).all()


@router.post("/memories", response_model=FamilyMemoryResponse)
def create_family_memory(
    req: FamilyMemoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    author_name = current_user.full_name or ("Amma" if current_user.role.upper() == "PARENT" else "Family Member")

    mem = FamilyMemory(
        parent_id=parent_id,
        author_id=current_user.id,
        author_name=author_name,
        category=req.category,
        title=req.title,
        content=req.content,
        voice_url=req.voice_url,
        image_url=req.image_url,
        is_private=req.is_private,
        shared_with_family=req.shared_with_family
    )
    db.add(mem)
    db.commit()
    db.refresh(mem)

    # Record family presence event if shared
    if req.shared_with_family and not req.is_private:
        today_str = datetime.date.today().isoformat()
        presence = FamilyPresenceEvent(
            parent_id=parent_id,
            family_user_id=current_user.id if current_user.role.upper() == "FAMILY" else None,
            family_member_name=author_name,
            relationship_type="Parent" if current_user.role.upper() == "PARENT" else "Child",
            interaction_type="shared_memory",
            interaction_date=today_str,
            notes=f"Shared memory: {req.title}"
        )
        db.add(presence)
        db.commit()

    return mem


# ============================================================================
# 2. LIFE STORY ARCHIVE
# ============================================================================

@router.get("/stories", response_model=List[LifeStoryResponse])
def get_life_stories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    query = db.query(LifeStory).filter(LifeStory.parent_id == parent_id)
    if current_user.role.upper() == "FAMILY":
        query = query.filter(LifeStory.is_shared_with_family == True)
    return query.order_by(LifeStory.created_at.desc()).all()


@router.post("/stories", response_model=LifeStoryResponse)
def create_life_story(
    req: LifeStoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    story = LifeStory(
        parent_id=parent_id,
        title=req.title,
        category=req.category,
        transcript=req.transcript,
        audio_url=req.audio_url,
        recorded_date_text=req.recorded_date_text or datetime.datetime.utcnow().strftime("%B %Y"),
        is_shared_with_family=req.is_shared_with_family
    )
    db.add(story)
    db.commit()
    db.refresh(story)
    return story


@router.delete("/stories/{story_id}")
def delete_life_story(
    story_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    story = db.query(LifeStory).filter(
        LifeStory.id == story_id,
        LifeStory.parent_id == parent_id
    ).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    db.delete(story)
    db.commit()
    return {"message": "Life story deleted successfully"}


# ============================================================================
# 3. FAMILY PRESENCE (NOT a competitive health score)
# ============================================================================

@router.get("/presence", response_model=FamilyPresenceSummaryResponse)
def get_family_presence(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    seven_days_ago = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")

    events = db.query(FamilyPresenceEvent).filter(
        FamilyPresenceEvent.parent_id == parent_id,
        FamilyPresenceEvent.interaction_date >= seven_days_ago
    ).order_by(FamilyPresenceEvent.created_at.desc()).all()

    # Group by family member without ranking or scores
    stats_map = {}
    for ev in events:
        name = ev.family_member_name
        rel = ev.relationship_type
        if name not in stats_map:
            stats_map[name] = {
                "family_member_name": name,
                "relationship_type": rel,
                "total_interactions": 0,
                "interaction_breakdown": {
                    "call": 0,
                    "approved_message": 0,
                    "video_call": 0,
                    "family_check_in": 0,
                    "shared_memory": 0
                }
            }
        stats_map[name]["total_interactions"] += 1
        i_type = ev.interaction_type
        if i_type in stats_map[name]["interaction_breakdown"]:
            stats_map[name]["interaction_breakdown"][i_type] += 1
        else:
            stats_map[name]["interaction_breakdown"][i_type] = 1

    members = [FamilyPresenceMemberStat(**data) for data in stats_map.values()]

    recent_list = [
        {
            "id": ev.id,
            "member_name": ev.family_member_name,
            "relationship": ev.relationship_type,
            "type": ev.interaction_type,
            "date": ev.interaction_date,
            "notes": ev.notes,
            "time": ev.created_at.strftime("%I:%M %p")
        }
        for ev in events[:10]
    ]

    return FamilyPresenceSummaryResponse(
        period="This Week",
        members=members,
        recent_events=recent_list
    )


@router.post("/presence", response_model=dict)
def record_presence_event(
    req: FamilyPresenceEventCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    today_str = datetime.date.today().isoformat()
    ev = FamilyPresenceEvent(
        parent_id=parent_id,
        family_user_id=current_user.id if current_user.role.upper() == "FAMILY" else None,
        family_member_name=req.family_member_name,
        relationship_type=req.relationship_type,
        interaction_type=req.interaction_type,
        interaction_date=today_str,
        notes=req.notes
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return {"message": "Presence interaction logged", "id": ev.id}


# ============================================================================
# 4. CONNECTION GAP INSIGHT & "WHY AM I SEEING THIS?"
# ============================================================================

@router.get("/gap-insight", response_model=Optional[ConnectionGapInsightResponse])
def get_connection_gap_insight(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    insight = db.query(ConnectionGapInsight).filter(
        ConnectionGapInsight.parent_id == parent_id,
        ConnectionGapInsight.status == "ACTIVE"
    ).order_by(ConnectionGapInsight.created_at.desc()).first()

    if not insight:
        return None

    return insight


@router.post("/gap-insight/{insight_id}/dismiss")
def dismiss_connection_gap_insight(
    insight_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    insight = db.query(ConnectionGapInsight).filter(
        ConnectionGapInsight.id == insight_id,
        ConnectionGapInsight.parent_id == parent_id
    ).first()
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")
    insight.status = "DISMISSED"
    db.commit()
    return {"message": "Insight dismissed"}


# ============================================================================
# 5. TIME-ZONE FAMILY COORDINATOR
# ============================================================================

@router.get("/availability", response_model=List[FamilyAvailabilityResponse])
def get_family_availabilities(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    availabilities = db.query(FamilyAvailability).all()
    results = []

    for av in availabilities:
        # Compute real-time hour in their timezone
        try:
            tz = ZoneInfo(av.timezone)
            now_in_tz = datetime.datetime.now(tz)
            local_time_display = now_in_tz.strftime("%I:%M %p")
            hour = now_in_tz.hour

            # Status summary: "Your daughter is currently available"
            if 9 <= hour < 18:
                status_summary = f"{av.family_member_name} is in daytime hours ({av.normal_availability})"
            elif 18 <= hour < 22:
                status_summary = f"{av.family_member_name} is currently available for calls ❤️"
            else:
                status_summary = f"{av.family_member_name}'s preferred call window begins in daytime."
        except Exception:
            local_time_display = "Local Time"
            status_summary = f"{av.family_member_name} ({av.normal_availability})"

        results.append(FamilyAvailabilityResponse(
            id=av.id,
            family_user_id=av.family_user_id,
            family_member_name=av.family_member_name,
            relationship_type=av.relationship_type,
            country=av.country,
            timezone=av.timezone,
            normal_availability=av.normal_availability,
            preferred_call_hours=av.preferred_call_hours,
            status_summary=status_summary,
            local_time_display=local_time_display,
            notes=av.notes,
            updated_at=av.updated_at
        ))

    return results


@router.put("/availability/{av_id}", response_model=FamilyAvailabilityResponse)
def update_family_availability(
    av_id: int,
    req: FamilyAvailabilityUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    av = db.query(FamilyAvailability).filter(FamilyAvailability.id == av_id).first()
    if not av:
        raise HTTPException(status_code=404, detail="Availability profile not found")

    if req.family_member_name:
        av.family_member_name = req.family_member_name
    if req.relationship_type:
        av.relationship_type = req.relationship_type
    if req.country:
        av.country = req.country
    if req.timezone:
        av.timezone = req.timezone
    if req.normal_availability:
        av.normal_availability = req.normal_availability
    if req.preferred_call_hours:
        av.preferred_call_hours = req.preferred_call_hours
    if req.notes is not None:
        av.notes = req.notes
    av.updated_at = datetime.datetime.utcnow()

    db.commit()
    db.refresh(av)

    return FamilyAvailabilityResponse(
        id=av.id,
        family_user_id=av.family_user_id,
        family_member_name=av.family_member_name,
        relationship_type=av.relationship_type,
        country=av.country,
        timezone=av.timezone,
        normal_availability=av.normal_availability,
        preferred_call_hours=av.preferred_call_hours,
        status_summary=f"{av.family_member_name} availability updated",
        local_time_display="Updated",
        notes=av.notes,
        updated_at=av.updated_at
    )


# ============================================================================
# 6. PERSONAL PREFERENCE MEMORY ("ABOUT ME" PROFILE)
# ============================================================================

@router.get("/preferences", response_model=PersonalPreferenceResponse)
def get_personal_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    pref = db.query(PersonalPreference).filter(PersonalPreference.parent_id == parent_id).first()
    if not pref:
        pref = PersonalPreference(
            parent_id=parent_id,
            preferred_language="Tamil",
            preferred_call_time="07:00 PM",
            favorite_food="Filter coffee, Idli, Rasam vadai",
            favorite_activities="Carnatic music, morning garden walk, devotional books",
            preferred_family_contact="Daughter (Priya)",
            preferred_communication_style="Voice",
            important_routines="Morning temple walk at 07:00 AM, Evening prayers at 06:30 PM",
            preferred_voice_guidance_style="Gentle, Calm Tamil"
        )
        db.add(pref)
        db.commit()
        db.refresh(pref)
    return pref


@router.put("/preferences", response_model=PersonalPreferenceResponse)
def update_personal_preferences(
    req: PersonalPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    pref = db.query(PersonalPreference).filter(PersonalPreference.parent_id == parent_id).first()
    if not pref:
        pref = PersonalPreference(parent_id=parent_id)
        db.add(pref)

    if req.preferred_language is not None:
        pref.preferred_language = req.preferred_language
    if req.preferred_call_time is not None:
        pref.preferred_call_time = req.preferred_call_time
    if req.favorite_food is not None:
        pref.favorite_food = req.favorite_food
    if req.favorite_activities is not None:
        pref.favorite_activities = req.favorite_activities
    if req.preferred_family_contact is not None:
        pref.preferred_family_contact = req.preferred_family_contact
    if req.preferred_communication_style is not None:
        pref.preferred_communication_style = req.preferred_communication_style
    if req.important_routines is not None:
        pref.important_routines = req.important_routines
    if req.preferred_voice_guidance_style is not None:
        pref.preferred_voice_guidance_style = req.preferred_voice_guidance_style
    pref.updated_at = datetime.datetime.utcnow()

    db.commit()
    db.refresh(pref)
    return pref


# ============================================================================
# 7. MEANINGFUL MOMENTS ("SAVE THIS MOMENT ❤️")
# ============================================================================

@router.get("/moments", response_model=List[MeaningfulMomentResponse])
def get_meaningful_moments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    return db.query(MeaningfulMoment).filter(
        MeaningfulMoment.parent_id == parent_id
    ).order_by(MeaningfulMoment.created_at.desc()).all()


@router.post("/moments", response_model=MeaningfulMomentResponse)
def create_meaningful_moment(
    req: MeaningfulMomentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    author_name = current_user.full_name or ("Amma" if current_user.role.upper() == "PARENT" else "Family Member")
    moment_date = req.moment_date or datetime.date.today().isoformat()

    moment = MeaningfulMoment(
        parent_id=parent_id,
        author_name=author_name,
        title=req.title,
        description=req.description,
        photo_url=req.photo_url,
        voice_url=req.voice_url,
        moment_date=moment_date
    )
    db.add(moment)
    db.commit()
    db.refresh(moment)

    # Record family presence event
    presence = FamilyPresenceEvent(
        parent_id=parent_id,
        family_user_id=current_user.id if current_user.role.upper() == "FAMILY" else None,
        family_member_name=author_name,
        relationship_type="Parent" if current_user.role.upper() == "PARENT" else "Child",
        interaction_type="shared_memory",
        interaction_date=moment_date,
        notes=f"Saved moment: {req.title}"
    )
    db.add(presence)
    db.commit()

    return moment


# ============================================================================
# 8. FAMILY SURPRISE COORDINATOR (Completely hidden from parent!)
# ============================================================================

@router.get("/surprises", response_model=List[FamilySurpriseResponse])
def get_family_surprises(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Rule: Parent MUST NOT see the private surprise planning details!
    if current_user.role.upper() == "PARENT":
        return []

    parent_id = get_target_parent_id(current_user, db)
    surprises = db.query(FamilySurprise).filter(
        FamilySurprise.parent_id == parent_id,
        FamilySurprise.status == "PLANNING"
    ).order_by(FamilySurprise.event_date.asc()).all()

    results = []
    for s in surprises:
        participants = []
        if s.participants_json:
            try:
                raw = json.loads(s.participants_json)
                participants = [SurpriseParticipant(**p) for p in raw]
            except Exception:
                participants = []
        results.append(FamilySurpriseResponse(
            id=s.id,
            parent_id=s.parent_id,
            created_by_name=s.created_by_name,
            title=s.title,
            surprise_type=s.surprise_type,
            event_date=s.event_date,
            notes=s.notes,
            status=s.status,
            participants=participants,
            is_visible_to_parent=False,
            created_at=s.created_at
        ))
    return results


@router.post("/surprises", response_model=FamilySurpriseResponse)
def create_family_surprise(
    req: FamilySurpriseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role.upper() == "PARENT":
        raise HTTPException(status_code=403, detail="Surprise coordinator is only accessible to family circle.")

    parent_id = get_target_parent_id(current_user, db)
    participants_raw = [p.model_dump() for p in req.participants]

    surprise = FamilySurprise(
        parent_id=parent_id,
        created_by_id=current_user.id,
        created_by_name=current_user.full_name or "Family Member",
        title=req.title,
        surprise_type=req.surprise_type,
        event_date=req.event_date,
        notes=req.notes,
        status="PLANNING",
        participants_json=json.dumps(participants_raw)
    )
    db.add(surprise)
    db.commit()
    db.refresh(surprise)

    return FamilySurpriseResponse(
        id=surprise.id,
        parent_id=surprise.parent_id,
        created_by_name=surprise.created_by_name,
        title=surprise.title,
        surprise_type=surprise.surprise_type,
        event_date=surprise.event_date,
        notes=surprise.notes,
        status=surprise.status,
        participants=req.participants,
        is_visible_to_parent=False,
        created_at=surprise.created_at
    )


@router.post("/surprises/{surprise_id}/complete")
def complete_family_surprise(
    surprise_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    surprise = db.query(FamilySurprise).filter(FamilySurprise.id == surprise_id).first()
    if not surprise:
        raise HTTPException(status_code=404, detail="Surprise not found")
    surprise.status = "COMPLETED"
    db.commit()
    return {"message": "Surprise successfully marked completed"}


# ============================================================================
# 9. CARE CIRCLE
# ============================================================================

@router.get("/care-circle", response_model=List[CareCircleMemberResponse])
def get_care_circle(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    return db.query(CareCircleMember).filter(
        CareCircleMember.parent_id == parent_id,
        CareCircleMember.is_active == True
    ).order_by(CareCircleMember.id.asc()).all()


@router.post("/care-circle", response_model=CareCircleMemberResponse)
def add_care_circle_member(
    req: CareCircleMemberCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    member = CareCircleMember(
        parent_id=parent_id,
        name=req.name,
        relationship=req.relationship,
        role_title=req.role_title,
        phone=req.phone,
        can_communication=req.can_communication,
        can_health_docs=req.can_health_docs,
        can_appointments=req.can_appointments,
        can_emergency_only=req.can_emergency_only,
        can_memories=req.can_memories,
        can_cctv=req.can_cctv,
        is_active=True
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.put("/care-circle/{member_id}", response_model=CareCircleMemberResponse)
def update_care_circle_member(
    member_id: int,
    req: CareCircleMemberUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    member = db.query(CareCircleMember).filter(CareCircleMember.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if req.role_title is not None:
        member.role_title = req.role_title
    if req.can_communication is not None:
        member.can_communication = req.can_communication
    if req.can_health_docs is not None:
        member.can_health_docs = req.can_health_docs
    if req.can_appointments is not None:
        member.can_appointments = req.can_appointments
    if req.can_emergency_only is not None:
        member.can_emergency_only = req.can_emergency_only
    if req.can_memories is not None:
        member.can_memories = req.can_memories
    if req.can_cctv is not None:
        member.can_cctv = req.can_cctv
    if req.is_active is not None:
        member.is_active = req.is_active

    db.commit()
    db.refresh(member)
    return member


# ============================================================================
# 10. TEMPORARY ACCESS (Time-Limited Permissions with Auto-Expiration)
# ============================================================================

@router.get("/temporary-permissions", response_model=List[TemporaryPermissionResponse])
def get_temporary_permissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    now = datetime.datetime.utcnow()

    perms = db.query(TemporaryPermission).filter(
        TemporaryPermission.parent_id == parent_id
    ).order_by(TemporaryPermission.created_at.desc()).all()

    results = []
    for p in perms:
        is_expired = now >= p.expires_at or p.status == "EXPIRED"
        if is_expired and p.status != "EXPIRED":
            p.status = "EXPIRED"
            db.commit()

        if is_expired:
            time_remaining_str = "ACCESS EXPIRED 🔒"
        else:
            diff = p.expires_at - now
            hours, remainder = divmod(int(diff.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            time_remaining_str = f"ACCESS EXPIRES IN: {hours}h {minutes}m"

        results.append(TemporaryPermissionResponse(
            id=p.id,
            parent_id=p.parent_id,
            grantee_name=p.grantee_name,
            resource_type=p.resource_type,
            resource_name=p.resource_name,
            duration_hours=p.duration_hours,
            expires_at=p.expires_at,
            status="EXPIRED" if is_expired else p.status,
            time_remaining_str=time_remaining_str,
            is_expired=is_expired,
            created_at=p.created_at
        ))
    return results


@router.post("/temporary-permissions", response_model=TemporaryPermissionResponse)
def create_temporary_permission(
    req: TemporaryPermissionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    now = datetime.datetime.utcnow()
    expires_at = now + datetime.timedelta(hours=req.duration_hours)

    perm = TemporaryPermission(
        parent_id=parent_id,
        grantee_name=req.grantee_name,
        resource_type=req.resource_type,
        resource_name=req.resource_name or req.resource_type,
        duration_hours=req.duration_hours,
        expires_at=expires_at,
        status="ACTIVE"
    )
    db.add(perm)
    db.commit()
    db.refresh(perm)

    diff = expires_at - now
    hours, remainder = divmod(int(diff.total_seconds()), 3600)
    minutes, _ = divmod(remainder, 60)
    time_remaining = f"ACCESS EXPIRES IN: {hours}h {minutes}m"

    return TemporaryPermissionResponse(
        id=perm.id,
        parent_id=perm.parent_id,
        grantee_name=perm.grantee_name,
        resource_type=perm.resource_type,
        resource_name=perm.resource_name,
        duration_hours=perm.duration_hours,
        expires_at=perm.expires_at,
        status="ACTIVE",
        time_remaining_str=time_remaining,
        is_expired=False,
        created_at=perm.created_at
    )


@router.post("/temporary-permissions/{perm_id}/revoke")
def revoke_temporary_permission(
    perm_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    perm = db.query(TemporaryPermission).filter(TemporaryPermission.id == perm_id).first()
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    perm.status = "REVOKED"
    db.commit()
    return {"message": "Permission revoked"}


# ============================================================================
# 11. ONE-TAP FAMILY UPDATE (❤️ "Tell My Family I'm OK")
# ============================================================================

@router.post("/one-tap-update", response_model=OneTapFamilyUpdateResponse)
async def send_one_tap_family_update(
    req: OneTapFamilyUpdateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    msg_text = req.message or "Amma is okay today ❤️"
    msg_tamil = req.message_tamil or "அம்மா இன்று நலமாக இருக்கிறார் ❤️"

    update = OneTapFamilyUpdate(
        parent_id=parent_id,
        message=msg_text,
        message_tamil=msg_tamil,
        sent_by=current_user.full_name or "Amma"
    )
    db.add(update)

    # Log in family messages as well for visibility
    fam_msg = FamilyMessage(
        sender_name="Amma",
        sender_role="PARENT",
        receiver_name="All Family",
        message_type="warm_prompt",
        content=msg_text,
        content_tamil=msg_tamil,
        is_read=False
    )
    db.add(fam_msg)

    # Record family presence event
    today_str = datetime.date.today().isoformat()
    presence = FamilyPresenceEvent(
        parent_id=parent_id,
        family_user_id=None,
        family_member_name="Amma",
        relationship_type="Parent",
        interaction_type="family_check_in",
        interaction_date=today_str,
        notes="One-tap check-in: Amma confirmed she is OK ❤️"
    )
    db.add(presence)
    db.commit()
    db.refresh(update)

    # Broadcast notification to family of this parent via WebSocket
    await ws_manager.send_to_family_of_parent(db, parent_id, {
        "type": "FAMILY_UPDATE",
        "parent_id": parent_id,
        "title": "Amma is OK ❤️",
        "title_tamil": "அம்மா நலம் தெரிவித்தார் ❤️",
        "message": msg_text,
        "message_tamil": msg_tamil,
        "timestamp": update.created_at.isoformat()
    })

    return update


# ============================================================================
# 12. FAMILY AI BRIEFING (Respects permissions, clear and human)
# ============================================================================

@router.get("/briefing", response_model=FamilyBriefingNewResponse)
def get_family_briefing_upgraded(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    today_str = datetime.date.today().isoformat()

    # 1. Checkin
    checkin = db.query(DailyCheckIn).filter(
        DailyCheckIn.user_id == parent_id,
        DailyCheckIn.check_in_date == today_str
    ).first()

    # 2. Communications / calls
    comm_count = db.query(CommunicationRequest).filter(
        CommunicationRequest.parent_id == parent_id,
        CommunicationRequest.status.in_(["RESOLVED", "RESPONDING", "ACKNOWLEDGED"])
    ).count()

    # 3. Messages
    msg_count = db.query(FamilyMessage).count()

    # 4. New memories
    memory_count = db.query(FamilyMemory).filter(
        FamilyMemory.parent_id == parent_id,
        FamilyMemory.shared_with_family == True
    ).count()

    # 5. Unresolved requests
    unresolved_count = db.query(CommunicationRequest).filter(
        CommunicationRequest.parent_id == parent_id,
        CommunicationRequest.status.in_(["PENDING", "CALL_REQUESTED"])
    ).count()

    items = []

    # Checkin item
    if checkin:
        items.append(FamilyBriefingItem(
            icon="❤️",
            text="Check-in completed: Amma confirmed feeling well today",
            text_tamil="நலம் அறிதல் முடிந்தது: அம்மா நன்றாக இருப்பதாக உறுதிசெய்தார்",
            category="Check-in"
        ))
    else:
        items.append(FamilyBriefingItem(
            icon="⏳",
            text="Morning check-in pending normal routine window",
            text_tamil="காலை நலம் அறிதல் வழக்கமான நேரத்தில் எதிர்பார்க்கப்படுகிறது",
            category="Check-in"
        ))

    # Calls / interactions item
    items.append(FamilyBriefingItem(
        icon="📞",
        text=f"{max(comm_count, 1)} family call & voice touchpoints completed recently",
        text_tamil="குடும்பத்தினருடனான அழைப்பு மற்றும் குரல் தொடர்பு நிறைவடைந்தது",
        category="Communication"
    ))

    # Messages
    items.append(FamilyBriefingItem(
        icon="💬",
        text=f"Family warm prompts & greetings active ({max(msg_count, 1)} messages)",
        text_tamil="அன்பான குடும்பச் செய்திகள் பரிமாறப்பட்டுள்ளன",
        category="Messages"
    ))

    # Memories
    items.append(FamilyBriefingItem(
        icon="📖",
        text=f"{memory_count} family memories and stories safely preserved in archive",
        text_tamil=f"{memory_count} குடும்ப நினைவுகள் மற்றும் வாழ்க்கைக் கதைகள் பாதுகாக்கப்பட்டுள்ளன",
        category="Memories"
    ))

    # Unresolved requests
    if unresolved_count > 0:
        items.append(FamilyBriefingItem(
            icon="⚠️",
            text=f"{unresolved_count} family call request awaiting callback",
            text_tamil=f"{unresolved_count} குடும்ப அழைப்புக் கோரிக்கை நிலுவையில் உள்ளது",
            category="Attention"
        ))
    else:
        items.append(FamilyBriefingItem(
            icon="✅",
            text="No important unresolved requests or safety concerns",
            text_tamil="நிலுவையில் உள்ள அவசரக் கோரிக்கைகள் ஏதுமில்லை",
            category="Safety"
        ))

    return FamilyBriefingNewResponse(
        headline="Today with Amma",
        headline_tamil="இன்று அம்மாவுடன்",
        items=items,
        generated_at=datetime.datetime.utcnow().strftime("%I:%M %p")
    )


# ============================================================================
# 13. INDEPENDENCE MODE (Independent Living Mode)
# ============================================================================

@router.get("/independence-mode", response_model=IndependenceModeResponse)
def get_independence_mode(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    cfg = db.query(IndependenceModeConfig).filter(
        IndependenceModeConfig.parent_id == parent_id
    ).first()

    if not cfg:
        cfg = IndependenceModeConfig(
            parent_id=parent_id,
            mode_enabled=True,
            current_escalation="NORMAL",
            suppress_routine_alerts=True
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)

    flow = [
        {"stage": "NORMAL", "label": "Normal Routine", "action": "Observe calmly without sending unnecessary notifications", "status": "active" if cfg.current_escalation == "NORMAL" else "standby"},
        {"stage": "SMALL_CHANGE", "label": "Small Shift", "action": "Continue observing quietly. Do not disturb the family.", "status": "active" if cfg.current_escalation == "SMALL_CHANGE" else "standby"},
        {"stage": "MEANINGFUL_CHANGE", "label": "Repeated / Meaningful Change", "action": "Suggest checking in gently during regular calling hours.", "status": "active" if cfg.current_escalation == "MEANINGFUL_CHANGE" else "standby"},
        {"stage": "SAFETY_EVENT", "label": "High-Confidence Safety Event", "action": "Alert immediately according to configured safety rules.", "status": "active" if cfg.current_escalation == "SAFETY_EVENT" else "standby"}
    ]

    return IndependenceModeResponse(
        id=cfg.id,
        parent_id=cfg.parent_id,
        mode_enabled=cfg.mode_enabled,
        current_escalation=cfg.current_escalation,
        suppress_routine_alerts=cfg.suppress_routine_alerts,
        escalation_flow=flow,
        explanation="Protection without constant surveillance: routine activities do not trigger notifications. Amma lives independently with dignified privacy.",
        updated_at=cfg.updated_at
    )


@router.put("/independence-mode", response_model=IndependenceModeResponse)
def update_independence_mode(
    req: IndependenceModeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    cfg = db.query(IndependenceModeConfig).filter(
        IndependenceModeConfig.parent_id == parent_id
    ).first()
    if not cfg:
        cfg = IndependenceModeConfig(parent_id=parent_id)
        db.add(cfg)

    if req.mode_enabled is not None:
        cfg.mode_enabled = req.mode_enabled
    if req.current_escalation is not None:
        cfg.current_escalation = req.current_escalation
    if req.suppress_routine_alerts is not None:
        cfg.suppress_routine_alerts = req.suppress_routine_alerts
    cfg.updated_at = datetime.datetime.utcnow()

    db.commit()
    db.refresh(cfg)
    return get_independence_mode(current_user, db)


# ============================================================================
# 14. FAMILIARITY MAP (Privacy-Friendly Place Familiarity)
# ============================================================================

@router.get("/familiar-places", response_model=List[FamiliarPlaceResponse])
def get_familiar_places(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    return db.query(FamiliarPlace).filter(
        FamiliarPlace.parent_id == parent_id,
        FamiliarPlace.is_enabled == True
    ).order_by(FamiliarPlace.id.asc()).all()


@router.post("/familiar-places", response_model=FamiliarPlaceResponse)
def create_familiar_place(
    req: FamiliarPlaceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    place = FamiliarPlace(
        parent_id=parent_id,
        name=req.name,
        name_tamil=req.name_tamil,
        place_type=req.place_type,
        address_or_landmark=req.address_or_landmark,
        notes=req.notes,
        is_enabled=True
    )
    db.add(place)
    db.commit()
    db.refresh(place)
    return place


@router.delete("/familiar-places/{place_id}")
def delete_familiar_place(
    place_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    place = db.query(FamiliarPlace).filter(FamiliarPlace.id == place_id).first()
    if not place:
        raise HTTPException(status_code=404, detail="Place not found")
    db.delete(place)
    db.commit()
    return {"message": "Familiar place removed"}


# ============================================================================
# 15. ADAPTIVE ELDERLY INTERFACE SETTINGS
# ============================================================================

@router.get("/interface-mode", response_model=ElderlyInterfaceConfigResponse)
def get_elderly_interface_mode(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    cfg = db.query(ElderlyInterfaceConfig).filter(
        ElderlyInterfaceConfig.parent_id == parent_id
    ).first()

    if not cfg:
        cfg = ElderlyInterfaceConfig(
            parent_id=parent_id,
            mode="STANDARD",
            language="ta",
            voice_guidance_active=True
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


@router.put("/interface-mode", response_model=ElderlyInterfaceConfigResponse)
def update_elderly_interface_mode(
    req: ElderlyInterfaceConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    cfg = db.query(ElderlyInterfaceConfig).filter(
        ElderlyInterfaceConfig.parent_id == parent_id
    ).first()
    if not cfg:
        cfg = ElderlyInterfaceConfig(parent_id=parent_id)
        db.add(cfg)

    if req.mode is not None:
        cfg.mode = req.mode
    if req.language is not None:
        cfg.language = req.language
    if req.voice_guidance_active is not None:
        cfg.voice_guidance_active = req.voice_guidance_active
    cfg.updated_at = datetime.datetime.utcnow()

    db.commit()
    db.refresh(cfg)
    return cfg


# ============================================================================
# 16. MEMORY-BASED FAMILY ASSISTANT (Never hallucinate, Known vs Unknown)
# ============================================================================

@router.post("/memory-assistant", response_model=MemoryAssistantResponse)
def answer_from_approved_memory(
    req: MemoryAssistantRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Answers questions strictly from approved family memories, life stories,
    and personal preferences. Never invents personal memories.
    Always distinguishes KNOWN vs UNKNOWN.
    """
    parent_id = get_target_parent_id(current_user, db)
    q_lower = req.question.lower().strip()

    # Load approved memories and preferences
    pref = db.query(PersonalPreference).filter(PersonalPreference.parent_id == parent_id).first()
    memories = db.query(FamilyMemory).filter(
        FamilyMemory.parent_id == parent_id,
        FamilyMemory.shared_with_family == True,
        FamilyMemory.is_private == False
    ).all()
    stories = db.query(LifeStory).filter(
        LifeStory.parent_id == parent_id,
        LifeStory.is_shared_with_family == True
    ).all()

    matched_answer_en = None
    matched_answer_ta = None
    sources = []

    # 1. Food / Breakfast / Favorite Food
    if any(k in q_lower for k in ["breakfast", "food", "eat", "favorite food", "சாப்பாடு", "டிபன்", "உணவு"]):
        if pref and pref.favorite_food:
            matched_answer_en = f"Amma has saved in her preferences that she usually prefers: {pref.favorite_food}."
            matched_answer_ta = f"அம்மா தனது விருப்பங்களில் குறிப்பிட்டுள்ளார்: {pref.favorite_food}."
            sources.append("Amma's Personal Preferences (About Me)")
        else:
            # Check memories for recipes
            recipe_mem = next((m for m in memories if m.category.lower() in ["recipes", "food"]), None)
            if recipe_mem:
                matched_answer_en = f"From Amma's saved memories: {recipe_mem.title} — {recipe_mem.content}."
                matched_answer_ta = f"அம்மாவின் சேமிக்கப்பட்ட நினைவிலிருந்து: {recipe_mem.title}."
                sources.append(f"Family Memory: {recipe_mem.title}")

    # 2. Temple / Place / Visit
    elif any(k in q_lower for k in ["temple", "place", "walk", "கோயில்", "இடம்", "நடை"]):
        temple_mem = next((m for m in memories if "temple" in m.title.lower() or "temple" in m.content.lower() or m.category.lower() == "places"), None)
        if temple_mem:
            matched_answer_en = f"From Amma's saved places: \"{temple_mem.title}\" — {temple_mem.content}"
            matched_answer_ta = f"அம்மாவின் இடங்கள் நினைவிலிருந்து: \"{temple_mem.title}\""
            sources.append("Amma's Saved Memories (Places)")
        elif pref and "temple" in pref.important_routines.lower():
            matched_answer_en = f"According to Amma's saved routine: {pref.important_routines}."
            matched_answer_ta = f"அம்மாவின் வழக்கமான அட்டவணை: {pref.important_routines}."
            sources.append("Amma's Personal Preferences (Routines)")

    # 3. Call time / Preferred time to call
    elif any(k in q_lower for k in ["call time", "when to call", "best time", "அழைக்க", "நேரம்"]):
        if pref and pref.preferred_call_time:
            matched_answer_en = f"Amma has set her preferred evening call time to {pref.preferred_call_time}."
            matched_answer_ta = f"அம்மா தனது விருப்பமான மாலை அழைப்பு நேரமாக {pref.preferred_call_time} அமைத்துள்ளார்."
            sources.append("Amma's Personal Preferences (Call Hours)")

    # 4. Life story / Childhood / School / Appa
    elif any(k in q_lower for k in ["school", "childhood", "appa", "met", "story", "கதை", "பள்ளி", "அப்பா"]):
        story_match = next((s for s in stories if any(k in s.title.lower() or k in s.transcript.lower() for k in ["appa", "school", "childhood", "meet"])), None)
        if story_match:
            matched_answer_en = f"In Amma's life story \"{story_match.title}\": \"{story_match.transcript}\""
            matched_answer_ta = f"அம்மாவின் வாழ்க்கைக் கதை \"{story_match.title}\": \"{story_match.transcript}\""
            sources.append(f"Life Story Archive: {story_match.title}")

    # 5. Language preference
    elif any(k in q_lower for k in ["language", "speak", "மொழி"]):
        if pref:
            matched_answer_en = f"Amma's preferred language is {pref.preferred_language}, and she prefers {pref.preferred_communication_style} communication."
            matched_answer_ta = f"அம்மாவின் விருப்பமான மொழி {pref.preferred_language}, மற்றும் {pref.preferred_communication_style} தொடர்பை விரும்புகிறார்."
            sources.append("Amma's Personal Preferences (Language)")

    # 6. Activities / Music / Hobbies
    elif any(k in q_lower for k in ["activity", "music", "hobby", "hobbies", "இசை", "விருப்பம்"]):
        if pref and pref.favorite_activities:
            matched_answer_en = f"Amma's approved favorite activities are: {pref.favorite_activities}."
            matched_answer_ta = f"அம்மாவின் விருப்பமான பொழுதுபோக்குகள்: {pref.favorite_activities}."
            sources.append("Amma's Personal Preferences (Activities)")

    # Fallback to general keyword match across all memories (excluding common query stopwords)
    STOPWORDS = {
        "what", "whats", "when", "whens", "where", "wheres", "which", "who", "whos",
        "whom", "whose", "why", "how", "does", "amma", "ammas", "have", "first",
        "that", "this", "from", "with", "name", "names", "like", "usually", "tell",
        "about", "your", "their", "there", "were", "been", "will", "would", "could",
        "should", "some", "them", "then", "into", "also", "much", "many", "give",
        "wear", "wears", "sleep", "sleeps", "make", "makes", "brand", "brands",
        "take", "takes", "know", "knows", "time", "times", "good", "best", "used"
    }
    if not matched_answer_en:
        import re
        clean_q = re.sub(r'[^a-z0-9\s]', ' ', q_lower)
        meaningful_words = [w for w in clean_q.split() if len(w) >= 4 and w not in STOPWORDS]
        if meaningful_words:
            for m in memories:
                # Direct title match is highest confidence
                title_matches = [w for w in meaningful_words if re.search(r'\b' + re.escape(w) + r'\b', m.title.lower())]
                content_matches = [w for w in meaningful_words if re.search(r'\b' + re.escape(w) + r'\b', m.content.lower())]
                
                # Match if title contains keyword, or if content contains at least 2 keywords (or 1 keyword if only 1 was asked)
                if title_matches or len(content_matches) >= min(2, len(meaningful_words)):
                    matched_answer_en = f"Amma saved this in \"{m.title}\" ({m.category}): {m.content}"
                    matched_answer_ta = f"அம்மா \"{m.title}\" என்ற நினைவில் சேமித்துள்ளார்: {m.content}"
                    sources.append(f"Family Memory: {m.title}")
                    break

    # If nothing is found in memory, NEVER INVENT. Always return UNKNOWN.
    if not matched_answer_en:
        return MemoryAssistantResponse(
            question=req.question,
            answer="I don't have that information. Amma has not saved or approved this detail in her private family memories yet.",
            answer_tamil="என்னிடம் இந்த தகவல் இல்லை. அம்மா தனது குடும்ப நினைவுகளில் இந்த விவரத்தை இன்னும் சேர்க்கவில்லை.",
            status="UNKNOWN",
            sources_used=[],
            timestamp=datetime.datetime.utcnow()
        )

    return MemoryAssistantResponse(
        question=req.question,
        answer=matched_answer_en,
        answer_tamil=matched_answer_ta or matched_answer_en,
        status="KNOWN",
        sources_used=sources,
        timestamp=datetime.datetime.utcnow()
    )


# ============================================================================
# 18. FAMILY CONNECTION TIMELINE (Story of Family Connection)
# ============================================================================

@router.get("/timeline", response_model=List[FamilyTimelineEvent])
def get_family_timeline(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    events: List[FamilyTimelineEvent] = []

    # 1. Meaningful moments
    moments = db.query(MeaningfulMoment).filter(MeaningfulMoment.parent_id == parent_id).all()
    for m in moments:
        events.append(FamilyTimelineEvent(
            id=f"moment-{m.id}",
            date_display=m.moment_date,
            event_type="moment",
            icon="❤️",
            title=m.title,
            description=m.description,
            author=m.author_name,
            media_url=m.photo_url,
            audio_url=m.voice_url,
            created_at=m.created_at
        ))

    # 2. Shared memories
    memories = db.query(FamilyMemory).filter(
        FamilyMemory.parent_id == parent_id,
        FamilyMemory.shared_with_family == True
    ).all()
    for mem in memories:
        events.append(FamilyTimelineEvent(
            id=f"mem-{mem.id}",
            date_display=mem.created_at.strftime("%B %Y"),
            event_type="memory",
            icon="📖",
            title=mem.title,
            description=f"[{mem.category}] {mem.content}",
            author=mem.author_name,
            media_url=mem.image_url,
            audio_url=mem.voice_url,
            created_at=mem.created_at
        ))

    # 3. Life stories
    stories = db.query(LifeStory).filter(
        LifeStory.parent_id == parent_id,
        LifeStory.is_shared_with_family == True
    ).all()
    for s in stories:
        events.append(FamilyTimelineEvent(
            id=f"story-{s.id}",
            date_display=s.recorded_date_text,
            event_type="story",
            icon="🎙️",
            title=f"Amma's Story: {s.title}",
            description=s.transcript,
            author="Amma",
            audio_url=s.audio_url,
            created_at=s.created_at
        ))

    # 4. One-tap updates
    updates = db.query(OneTapFamilyUpdate).filter(
        OneTapFamilyUpdate.parent_id == parent_id
    ).all()
    for u in updates:
        events.append(FamilyTimelineEvent(
            id=f"update-{u.id}",
            date_display=u.created_at.strftime("%b %d, %Y"),
            event_type="update",
            icon="❤️",
            title="Amma checked in with Family",
            description=u.message,
            author=u.sent_by,
            created_at=u.created_at
        ))

    # Sort descending by created_at
    events.sort(key=lambda x: x.created_at, reverse=True)
    return events


# ============================================================================
# 19. CARE HANDOVER (Temporary Responsibility Transfer)
# ============================================================================

@router.get("/care-handover", response_model=Optional[CareHandoverResponse])
def get_active_care_handover(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    now = datetime.datetime.utcnow()

    handover = db.query(CareHandover).filter(
        CareHandover.parent_id == parent_id,
        CareHandover.status == "ACTIVE"
    ).order_by(CareHandover.created_at.desc()).first()

    if not handover:
        return None

    # Check auto return
    if now >= handover.end_date:
        handover.status = "COMPLETED"
        db.commit()
        return None

    date_range = f"{handover.start_date.strftime('%b %d')} — {handover.end_date.strftime('%b %d')}"

    return CareHandoverResponse(
        id=handover.id,
        parent_id=handover.parent_id,
        primary_caregiver_name=handover.primary_caregiver_name,
        temporary_caregiver_name=handover.temporary_caregiver_name,
        start_date=handover.start_date,
        end_date=handover.end_date,
        duration_days=handover.duration_days,
        notes=handover.notes,
        status=handover.status,
        is_currently_active=True,
        date_range_display=date_range,
        created_at=handover.created_at
    )


@router.post("/care-handover", response_model=CareHandoverResponse)
def create_care_handover(
    req: CareHandoverCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)

    # Deactivate any existing active handovers
    existing = db.query(CareHandover).filter(
        CareHandover.parent_id == parent_id,
        CareHandover.status == "ACTIVE"
    ).all()
    for e in existing:
        e.status = "COMPLETED"

    handover = CareHandover(
        parent_id=parent_id,
        primary_caregiver_name=req.primary_caregiver_name,
        temporary_caregiver_name=req.temporary_caregiver_name,
        start_date=req.start_date,
        end_date=req.end_date,
        duration_days=req.duration_days,
        notes=req.notes,
        status="ACTIVE"
    )
    db.add(handover)
    db.commit()
    db.refresh(handover)

    date_range = f"{handover.start_date.strftime('%b %d')} — {handover.end_date.strftime('%b %d')}"

    return CareHandoverResponse(
        id=handover.id,
        parent_id=handover.parent_id,
        primary_caregiver_name=handover.primary_caregiver_name,
        temporary_caregiver_name=handover.temporary_caregiver_name,
        start_date=handover.start_date,
        end_date=handover.end_date,
        duration_days=handover.duration_days,
        notes=handover.notes,
        status="ACTIVE",
        is_currently_active=True,
        date_range_display=date_range,
        created_at=handover.created_at
    )


@router.post("/care-handover/{handover_id}/return")
def return_care_handover(
    handover_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    handover = db.query(CareHandover).filter(CareHandover.id == handover_id).first()
    if not handover:
        raise HTTPException(status_code=404, detail="Handover not found")
    handover.status = "COMPLETED"
    db.commit()
    return {"message": "Care responsibility returned to primary caregiver"}


# ============================================================================
# 20. FAMILY CONTINUITY (Generational Archive)
# ============================================================================

@router.get("/continuity", response_model=List[FamilyContinuityItem])
@router.get("/continuity-archive", response_model=List[FamilyContinuityItem])
def get_family_continuity_archive(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parent_id = get_target_parent_id(current_user, db)
    archive: List[FamilyContinuityItem] = []

    # Life stories
    stories = db.query(LifeStory).filter(
        LifeStory.parent_id == parent_id,
        LifeStory.is_shared_with_family == True
    ).all()
    for s in stories:
        archive.append(FamilyContinuityItem(
            category="Life Stories",
            title=s.title,
            snippet=s.transcript[:140] + ("..." if len(s.transcript) > 140 else ""),
            date_text=s.recorded_date_text,
            has_audio=bool(s.audio_url),
            has_photo=False,
            id=s.id,
            item_type="STORY"
        ))

    # Memories across categories (Recipes, Traditions, Important People, Childhood, Places)
    memories = db.query(FamilyMemory).filter(
        FamilyMemory.parent_id == parent_id,
        FamilyMemory.shared_with_family == True,
        FamilyMemory.is_private == False
    ).all()
    for m in memories:
        archive.append(FamilyContinuityItem(
            category=m.category,
            title=m.title,
            snippet=m.content[:140] + ("..." if len(m.content) > 140 else ""),
            date_text=m.created_at.strftime("%B %Y"),
            has_audio=bool(m.voice_url),
            has_photo=bool(m.image_url),
            id=m.id,
            item_type="MEMORY"
        ))

    return archive
