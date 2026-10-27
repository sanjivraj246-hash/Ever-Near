import json
import datetime
from sqlalchemy.orm import Session
from app.database.session import engine, Base, SessionLocal
from app.models.entities import (
    User, ParentProfile, FamilyProfile, FamilyRelationship, DailyCheckIn,
    Medication, MedicationLog, HealthDocument, CareEvent,
    RoutineEvent, SafetyEvent, CCTVDevice, CCTVPermission,
    SOSAlert, Notification, PrivacyPermission, AuditLog,
    FamilyMemory, LifeStory, FamilyPresenceEvent, ConnectionGapInsight,
    FamilyAvailability, PersonalPreference, MeaningfulMoment, FamilySurprise,
    CareCircleMember, TemporaryPermission, OneTapFamilyUpdate, FamiliarPlace,
    CareHandover, IndependenceModeConfig, ElderlyInterfaceConfig,
    PrivacySetting, DailyActivity, SleepRecord, MealRecord, HydrationRecord,
    CareTimelineItem, RoutineFeatureRecord
)
from app.core.security import hash_password

def init_db(db: Session):
    # Create all tables in database
    Base.metadata.create_all(bind=engine)

    # 1. Ensure Parent User exists
    parent_user = db.query(User).filter(User.phone == "9876543210").first()
    if not parent_user:
        parent_user = User(
            phone="9876543210",
            full_name="Lakshmi Amma",
            role="PARENT",
            password_hash=hash_password("1234"),
            is_active=True
        )
        db.add(parent_user)
        db.commit()
        db.refresh(parent_user)

    # 2. Ensure Family User exists
    family_user = db.query(User).filter(User.phone == "9876543211").first()
    if not family_user:
        family_user = User(
            phone="9876543211",
            full_name="Karthik (Son)",
            role="FAMILY",
            password_hash=hash_password("1234"),
            is_active=True
        )
        db.add(family_user)
        db.commit()
        db.refresh(family_user)

        family_profile = FamilyProfile(
            user_id=family_user.id,
            preferred_name="Karthik",
            relationship_type="Son",
            language_pref="en"
        )
        db.add(family_profile)
        db.commit()

    # 3. Ensure Parent Profile exists
    profile = db.query(ParentProfile).filter(ParentProfile.user_id == parent_user.id).first()
    if not profile:
        profile = ParentProfile(
            user_id=parent_user.id,
            preferred_name="Amma",
            age=72,
            emergency_notes="Mild hypertension, regular morning BP tablet. Preferred language Tamil.",
            language_pref="ta"
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

    # 4. Ensure Family Relationship exists
    rel = db.query(FamilyRelationship).filter(FamilyRelationship.parent_id == parent_user.id).first()
    if not rel:
        rel = FamilyRelationship(
            parent_id=parent_user.id,
            family_user_id=family_user.id,
            relationship_type="Son",
            phone="+91 98765 43211",
            status="APPROVED",
            can_view_health=True,
            can_view_cctv=True,
            can_receive_sos=True
        )
        db.add(rel)
        db.commit()

    # 5. Medications
    if db.query(Medication).filter(Medication.parent_id == profile.id).count() == 0:
        med1 = Medication(
            parent_id=profile.id,
            name="Morning BP (Amlodipine 5mg)",
            dosage="1 tablet",
            schedule_time="08:00 AM",
            period="Morning",
            instructions="Take with warm water after light breakfast",
            icon="pill"
        )
        med2 = Medication(
            parent_id=profile.id,
            name="Calcium & Vitamin D3",
            dosage="1 capsule",
            schedule_time="01:30 PM",
            period="Afternoon",
            instructions="After lunch",
            icon="pill"
        )
        med3 = Medication(
            parent_id=profile.id,
            name="Omega-3 & Joint Support",
            dosage="1 tablet",
            schedule_time="08:30 PM",
            period="Night",
            instructions="After dinner",
            icon="pill"
        )
        db.add_all([med1, med2, med3])
        db.commit()

    # 6. Check-in
    today_str = datetime.date.today().isoformat()
    if db.query(DailyCheckIn).filter(DailyCheckIn.user_id == parent_user.id).count() == 0:
        prev_checkin = DailyCheckIn(
            user_id=parent_user.id,
            feeling="good",
            feeling_tamil="நன்றாக இருக்கிறேன்",
            voice_input=False,
            note="Morning walk in garden completed",
            check_in_date=today_str,
            created_at=datetime.datetime.utcnow()
        )
        db.add(prev_checkin)
        db.commit()

    # 7. CCTV Device
    if db.query(CCTVDevice).filter(CCTVDevice.owner_id == profile.id).count() == 0:
        camera = CCTVDevice(
            owner_id=profile.id,
            name="Living Room Safety Camera",
            name_tamil="வரவேற்பறை கேமரா",
            location="Living Room",
            stream_url="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260427_054418_a6d194f0-ac86-4df9-abe5-ded73e596d7c.mp4",
            status="LIVE",
            enabled=True
        )
        db.add(camera)
        db.commit()
        db.refresh(camera)

        cctv_perm = CCTVPermission(
            device_id=camera.id,
            family_user_id=family_user.id,
            can_view_live=True,
            can_view_events=True
        )
        db.add(cctv_perm)
        db.commit()

    # 8. Privacy Permission
    if db.query(PrivacyPermission).filter(PrivacyPermission.parent_id == parent_user.id).count() == 0:
        priv = PrivacyPermission(
            parent_id=parent_user.id,
            family_user_id=family_user.id,
            share_health=True,
            share_activity=True,
            share_location=True,
            share_cctv=True,
            share_medication=True
        )
        db.add(priv)
        db.commit()

    # 9. Health Document
    if db.query(HealthDocument).filter(HealthDocument.parent_id == profile.id).count() == 0:
        doc = HealthDocument(
            parent_id=profile.id,
            filename="Annual_Health_Panel_Report.pdf",
            document_type="Vitals & Routine Blood Test",
            ai_summary="All parameters steady. Blood pressure well-controlled on prescribed morning regimen.",
            is_shared_with_family=True
        )
        db.add(doc)
        db.commit()

    # ========================================================================
    # SEED NEW UPGRADE FEATURES (Features 1 to 20)
    # ========================================================================

    # Feature 1: Family Memories
    if db.query(FamilyMemory).filter(FamilyMemory.parent_id == parent_user.id).count() == 0:
        memories = [
            FamilyMemory(
                parent_id=parent_user.id,
                author_id=parent_user.id,
                author_name="Amma",
                category="Family",
                title="Karthik's 10th Birthday in Madurai",
                content="We celebrated Karthik's 10th birthday with all 18 cousins in our ancestral home. Appa brought traditional Mysore Pak and everyone sang Tamil birthday songs.",
                voice_url=None,
                image_url=None,
                is_private=False,
                shared_with_family=True
            ),
            FamilyMemory(
                parent_id=parent_user.id,
                author_id=parent_user.id,
                author_name="Amma",
                category="Childhood",
                title="Grandmother's Courtyard Tales",
                content="Every summer vacation, we would sleep under the starlit sky in the central courtyard (Muttram). Paati would tell stories from Ramayana and distribute warm milk.",
                voice_url=None,
                image_url=None,
                is_private=False,
                shared_with_family=True
            ),
            FamilyMemory(
                parent_id=parent_user.id,
                author_id=parent_user.id,
                author_name="Amma",
                category="Recipes",
                title="Amma's Secret Rasam Recipe",
                content="Always crush cumin seeds, black peppercorns and 4 garlic cloves coarsely with stone mortar. Add ripe country tomatoes and fresh curry leaves picked from our garden before boiling.",
                voice_url=None,
                image_url=None,
                is_private=False,
                shared_with_family=True
            ),
            FamilyMemory(
                parent_id=parent_user.id,
                author_id=parent_user.id,
                author_name="Amma",
                category="Places",
                title="Meenakshi Temple Lotus Tank",
                content="My favorite peaceful place in the world is sitting on the stone steps of the Golden Lotus Tank (Porthamarai Kulam) after evening 6 PM Deeparadhana.",
                voice_url=None,
                image_url=None,
                is_private=False,
                shared_with_family=True
            ),
            FamilyMemory(
                parent_id=parent_user.id,
                author_id=parent_user.id,
                author_name="Amma",
                category="Traditions",
                title="Karthigai Deepam 27 Clay Lamps",
                content="Our family tradition is lighting exactly 27 agal vilakkugal (earthen lamps) with pure sesame oil. One lamp must always be placed at the threshold.",
                voice_url=None,
                image_url=None,
                is_private=False,
                shared_with_family=True
            ),
            FamilyMemory(
                parent_id=parent_user.id,
                author_id=parent_user.id,
                author_name="Amma",
                category="Personal Preferences",
                title="My Morning Rhythm",
                content="I prefer waking up naturally before 6:30 AM, having one cup of hot filter coffee while listening to M.S. Subbulakshmi's Suprabhatam.",
                voice_url=None,
                image_url=None,
                is_private=True,  # Private note by Amma
                shared_with_family=False
            )
        ]
        db.add_all(memories)
        db.commit()

    # Feature 2: Life Stories
    if db.query(LifeStory).filter(LifeStory.parent_id == parent_user.id).count() == 0:
        stories = [
            LifeStory(
                parent_id=parent_user.id,
                title="How I Met Appa in 1974",
                category="Life Stories",
                transcript="It was in September 1974 when our families met near Thiruparankundram temple. Appa was shy and quietly brought a box of fresh jasmine flowers. He promised my father that he would always encourage my passion for singing.",
                audio_url="https://actions.google.com/sounds/v1/ambiences/garden.ogg",
                recorded_date_text="September 2026",
                is_shared_with_family=True
            ),
            LifeStory(
                parent_id=parent_user.id,
                title="My School Days & Saraswathi Teacher",
                category="Childhood",
                transcript="I studied in Government Girls High School. I walked three kilometers every morning with my sisters. Saraswathi teacher gave me my first notebook when I won the district essay competition.",
                audio_url="https://actions.google.com/sounds/v1/ambiences/garden.ogg",
                recorded_date_text="September 2026",
                is_shared_with_family=True
            )
        ]
        db.add_all(stories)
        db.commit()

    # Feature 3: Family Presence Events
    if db.query(FamilyPresenceEvent).filter(FamilyPresenceEvent.parent_id == parent_user.id).count() == 0:
        today_d = datetime.date.today()
        presence_events = [
            FamilyPresenceEvent(
                parent_id=parent_user.id,
                family_user_id=family_user.id,
                family_member_name="Priya (Daughter)",
                relationship_type="Daughter",
                interaction_type="call",
                interaction_date=today_d.isoformat(),
                notes="Evening phone call from London (15 minutes)"
            ),
            FamilyPresenceEvent(
                parent_id=parent_user.id,
                family_user_id=family_user.id,
                family_member_name="Priya (Daughter)",
                relationship_type="Daughter",
                interaction_type="video_call",
                interaction_date=(today_d - datetime.timedelta(days=1)).isoformat(),
                notes="Sunday family video call"
            ),
            FamilyPresenceEvent(
                parent_id=parent_user.id,
                family_user_id=family_user.id,
                family_member_name="Priya (Daughter)",
                relationship_type="Daughter",
                interaction_type="approved_message",
                interaction_date=(today_d - datetime.timedelta(days=2)).isoformat(),
                notes="Morning greeting & garden photo"
            ),
            FamilyPresenceEvent(
                parent_id=parent_user.id,
                family_user_id=family_user.id,
                family_member_name="Priya (Daughter)",
                relationship_type="Daughter",
                interaction_type="call",
                interaction_date=(today_d - datetime.timedelta(days=3)).isoformat(),
                notes="Regular check-in call"
            ),
            FamilyPresenceEvent(
                parent_id=parent_user.id,
                family_user_id=family_user.id,
                family_member_name="Priya (Daughter)",
                relationship_type="Daughter",
                interaction_type="shared_memory",
                interaction_date=(today_d - datetime.timedelta(days=4)).isoformat(),
                notes="Looked at old festival photos together"
            ),
            FamilyPresenceEvent(
                parent_id=parent_user.id,
                family_user_id=family_user.id,
                family_member_name="Karthik (Son)",
                relationship_type="Son",
                interaction_type="call",
                interaction_date=today_d.isoformat(),
                notes="Morning call regarding doctor visit"
            ),
            FamilyPresenceEvent(
                parent_id=parent_user.id,
                family_user_id=family_user.id,
                family_member_name="Karthik (Son)",
                relationship_type="Son",
                interaction_type="approved_message",
                interaction_date=(today_d - datetime.timedelta(days=2)).isoformat(),
                notes="Sent temple festival video"
            ),
            FamilyPresenceEvent(
                parent_id=parent_user.id,
                family_user_id=family_user.id,
                family_member_name="Karthik (Son)",
                relationship_type="Son",
                interaction_type="family_check_in",
                interaction_date=(today_d - datetime.timedelta(days=4)).isoformat(),
                notes="Confirmed weekly grocery delivery"
            ),
            FamilyPresenceEvent(
                parent_id=parent_user.id,
                family_user_id=None,
                family_member_name="Ananya (Granddaughter)",
                relationship_type="Granddaughter",
                interaction_type="video_call",
                interaction_date=(today_d - datetime.timedelta(days=1)).isoformat(),
                notes="Showed Amma her school dance trophy"
            ),
            FamilyPresenceEvent(
                parent_id=parent_user.id,
                family_user_id=None,
                family_member_name="Ananya (Granddaughter)",
                relationship_type="Granddaughter",
                interaction_type="approved_message",
                interaction_date=(today_d - datetime.timedelta(days=3)).isoformat(),
                notes="Voice note singing Tamil rhyme"
            )
        ]
        db.add_all(presence_events)
        db.commit()

    # Feature 4: Connection Gap Insight
    if db.query(ConnectionGapInsight).filter(ConnectionGapInsight.parent_id == parent_user.id).count() == 0:
        gap = ConnectionGapInsight(
            parent_id=parent_user.id,
            title="Connection Pattern Notice",
            message="Your usual connection with Amma has reduced recently.",
            message_tamil="அம்மாவுடனான உங்கள் வழக்கமான தொடர்பு சமீபத்தில் குறைந்துள்ளது.",
            why_text="Family interaction has decreased compared with the recent 7-day pattern.",
            why_text_tamil="கடந்த 7 நாள் வழக்கத்துடன் ஒப்பிடும்போது குடும்பத் தொடர்பு எண்ணிக்கை குறைந்துள்ளது.",
            status="ACTIVE"
        )
        db.add(gap)
        db.commit()

    # Feature 5: Family Availability & Timezone Coordinator
    if db.query(FamilyAvailability).filter(FamilyAvailability.family_user_id == family_user.id).count() == 0:
        av1 = FamilyAvailability(
            family_user_id=family_user.id,
            family_member_name="Karthik (Son)",
            relationship_type="Son",
            country="USA",
            timezone="America/New_York",
            normal_availability="Available",
            preferred_call_hours="07:00 PM — 10:00 PM EST",
            notes="Works during day. Best time to call is evening or weekend mornings."
        )
        av2 = FamilyAvailability(
            family_user_id=family_user.id,
            family_member_name="Priya (Daughter)",
            relationship_type="Daughter",
            country="UK",
            timezone="Europe/London",
            normal_availability="Available",
            preferred_call_hours="06:00 PM — 09:00 PM GMT",
            notes="Usually available right after her office hours."
        )
        db.add_all([av1, av2])
        db.commit()

    # Feature 6: Personal Preference Memory
    if db.query(PersonalPreference).filter(PersonalPreference.parent_id == parent_user.id).count() == 0:
        pref = PersonalPreference(
            parent_id=parent_user.id,
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

    # Feature 7: Meaningful Moments
    if db.query(MeaningfulMoment).filter(MeaningfulMoment.parent_id == parent_user.id).count() == 0:
        moments = [
            MeaningfulMoment(
                parent_id=parent_user.id,
                author_name="Amma",
                title="Granddaughter Ananya called on video",
                description="Today my granddaughter called me and showed her new school drawing of our Madurai garden with mango trees.",
                photo_url="https://images.unsplash.com/photo-1544717305-2782549b5136?w=600&auto=format&fit=crop&q=80",
                voice_url=None,
                moment_date=datetime.date.today().isoformat()
            ),
            MeaningfulMoment(
                parent_id=parent_user.id,
                author_name="Amma",
                title="Sunday Family Video Dinner",
                description="Both Karthik from New York and Priya from London joined on video while I was having dinner. Felt very warm.",
                photo_url=None,
                voice_url=None,
                moment_date=(datetime.date.today() - datetime.timedelta(days=2)).isoformat()
            )
        ]
        db.add_all(moments)
        db.commit()

    # Feature 8: Family Surprise Coordinator
    if db.query(FamilySurprise).filter(FamilySurprise.parent_id == parent_user.id).count() == 0:
        surprise = FamilySurprise(
            parent_id=parent_user.id,
            created_by_id=family_user.id,
            created_by_name="Priya (Daughter)",
            title="Surprise 75th Birthday Gathering for Amma",
            surprise_type="Birthday",
            event_date=datetime.datetime.utcnow() + datetime.timedelta(days=12),
            notes="Quiet celebration coordinated among children. Do not reveal in parent view.",
            status="PLANNING",
            participants_json=json.dumps([
                {"name": "Priya (Daughter)", "task": "Send fresh jasmine garlands & sweet box", "completed": False},
                {"name": "Karthik (Son)", "task": "Record video greeting montage from cousins", "completed": True},
                {"name": "Ananya (Granddaughter)", "task": "Handmade birthday card with audio message", "completed": False}
            ])
        )
        db.add(surprise)
        db.commit()

    # Feature 9: Care Circle Members
    if db.query(CareCircleMember).filter(CareCircleMember.parent_id == parent_user.id).count() == 0:
        care_members = [
            CareCircleMember(
                parent_id=parent_user.id,
                name="Priya (Daughter)",
                relationship="Daughter",
                role_title="Primary Care Coordinator",
                phone="+44 7700 900123",
                can_communication=True,
                can_health_docs=True,
                can_appointments=True,
                can_emergency_only=False,
                can_memories=True,
                can_cctv=True,
                is_active=True
            ),
            CareCircleMember(
                parent_id=parent_user.id,
                name="Karthik (Son)",
                relationship="Son",
                role_title="Family Communication & Check-ins",
                phone="+1 212 555 0192",
                can_communication=True,
                can_health_docs=False,
                can_appointments=False,
                can_emergency_only=False,
                can_memories=True,
                can_cctv=True,
                is_active=True
            ),
            CareCircleMember(
                parent_id=parent_user.id,
                name="Sundaram (Brother)",
                relationship="Brother",
                role_title="Local Support & Appointments",
                phone="+91 98401 23456",
                can_communication=True,
                can_health_docs=False,
                can_appointments=True,
                can_emergency_only=False,
                can_memories=True,
                can_cctv=False,
                is_active=True
            ),
            CareCircleMember(
                parent_id=parent_user.id,
                name="Murugan (Trusted Neighbor)",
                relationship="Neighbor",
                role_title="Emergency First Responder Only",
                phone="+91 94440 98765",
                can_communication=False,
                can_health_docs=False,
                can_appointments=False,
                can_emergency_only=True,
                can_memories=False,
                can_cctv=False,
                is_active=True
            )
        ]
        db.add_all(care_members)
        db.commit()

    # Feature 10: Temporary Permissions
    if db.query(TemporaryPermission).filter(TemporaryPermission.parent_id == parent_user.id).count() == 0:
        temp_perm = TemporaryPermission(
            parent_id=parent_user.id,
            grantee_name="Priya (Daughter)",
            resource_type="HEALTH_DOC",
            resource_name="Annual Health Panel Report (PDF)",
            duration_hours=24,
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=23, minutes=42),
            status="ACTIVE"
        )
        db.add(temp_perm)
        db.commit()

    # Feature 11: One-Tap Family Update
    if db.query(OneTapFamilyUpdate).filter(OneTapFamilyUpdate.parent_id == parent_user.id).count() == 0:
        upd = OneTapFamilyUpdate(
            parent_id=parent_user.id,
            message="Amma is okay today ❤️",
            message_tamil="அம்மா இன்று நலமாக இருக்கிறார் ❤️",
            sent_by="Amma"
        )
        db.add(upd)
        db.commit()

    # Feature 14: Familiar Places
    if db.query(FamiliarPlace).filter(FamiliarPlace.parent_id == parent_user.id).count() == 0:
        places = [
            FamiliarPlace(
                parent_id=parent_user.id,
                name="Thirunagar Residence",
                name_tamil="திருநகர் இல்லம்",
                place_type="HOME",
                address_or_landmark="14, 3rd Cross Street, Thirunagar, Madurai",
                notes="Primary home where Amma lives independently",
                is_enabled=True
            ),
            FamiliarPlace(
                parent_id=parent_user.id,
                name="Meenakshi Amman Temple",
                name_tamil="மீனாட்சி அம்மன் திருக்கோயில்",
                place_type="TEMPLE",
                address_or_landmark="East Chithirai Street, Madurai",
                notes="Amma walks here regularly for evening prayers",
                is_enabled=True
            ),
            FamiliarPlace(
                parent_id=parent_user.id,
                name="Apollo Specialty Clinic",
                name_tamil="அப்போலோ சிறப்பு மருத்துவமனை",
                place_type="HOSPITAL",
                address_or_landmark="Lake View Road, K.K. Nagar",
                notes="Regular quarterly doctor check-up clinic",
                is_enabled=True
            ),
            FamiliarPlace(
                parent_id=parent_user.id,
                name="Nilgiris Departmental Store",
                name_tamil="நீலகிரிஸ் சிறப்பங்காடி",
                place_type="GROCERY",
                address_or_landmark="Main Road, Thirunagar",
                notes="Nearby trusted grocery store",
                is_enabled=True
            ),
            FamiliarPlace(
                parent_id=parent_user.id,
                name="Brother Sundaram's Home",
                name_tamil="சுந்தரம் அண்ணன் இல்லம்",
                place_type="RELATIVE_HOME",
                address_or_landmark="Near Perumal Temple, Madurai",
                notes="Elder brother's residence",
                is_enabled=True
            )
        ]
        db.add_all(places)
        db.commit()

    # Feature 19: Care Handover
    if db.query(CareHandover).filter(CareHandover.parent_id == parent_user.id).count() == 0:
        start_d = datetime.datetime.utcnow() - datetime.timedelta(days=1)
        end_d = start_d + datetime.timedelta(days=3)
        handover = CareHandover(
            parent_id=parent_user.id,
            primary_caregiver_name="Priya (Daughter)",
            temporary_caregiver_name="Karthik (Son)",
            start_date=start_d,
            end_date=end_d,
            duration_days=3,
            notes="Daughter is on flight & conferences for 3 days. Son receives all care reminders.",
            status="ACTIVE"
        )
        db.add(handover)
        db.commit()

    # Feature 13: Independence Mode Config
    if db.query(IndependenceModeConfig).filter(IndependenceModeConfig.parent_id == parent_user.id).count() == 0:
        indep_cfg = IndependenceModeConfig(
            parent_id=parent_user.id,
            mode_enabled=True,
            current_escalation="NORMAL",
            suppress_routine_alerts=True
        )
        db.add(indep_cfg)
        db.commit()

    # Feature 15: Elderly Interface Config
    if db.query(ElderlyInterfaceConfig).filter(ElderlyInterfaceConfig.parent_id == parent_user.id).count() == 0:
        ui_cfg = ElderlyInterfaceConfig(
            parent_id=parent_user.id,
            mode="STANDARD",
            language="ta",
            voice_guidance_active=True
        )
        db.add(ui_cfg)
        db.commit()

    # Feature 16: Privacy Settings (Step 13 - Privacy Control)
    if db.query(PrivacySetting).filter(PrivacySetting.parent_id == parent_user.id).count() == 0:
        priv_setting = PrivacySetting(
            parent_id=parent_user.id,
            health_info=True,
            daily_activity=True,
            location_sharing=False,   # Privacy-first default OFF
            cctv_access=False,        # Privacy-first default OFF
            memories_sharing=True
        )
        db.add(priv_setting)
        db.commit()

    # Feature 17: 7-Day Historical Data for Personal Care Baseline Engine (Step 4)
    if db.query(DailyActivity).filter(DailyActivity.parent_id == parent_user.id).count() < 7:
        today = datetime.date.today()
        for i in range(1, 8):
            d = today - datetime.timedelta(days=i)
            d_str = d.isoformat()
            
            # Daily Activity
            if not db.query(DailyActivity).filter(DailyActivity.parent_id == parent_user.id, DailyActivity.record_date == d_str).first():
                db.add(DailyActivity(
                    parent_id=parent_user.id,
                    record_date=d_str,
                    steps_count=3200 + (i * 120 % 500),
                    active_minutes=int(48 - (i % 3) * 4),
                    activity_score=0.92,
                    summary="Garden walk and light movement",
                    recorded_at=datetime.datetime.combine(d, datetime.time(11, 30))
                ))
            
            # Sleep Record
            if not db.query(SleepRecord).filter(SleepRecord.parent_id == parent_user.id, SleepRecord.sleep_date == d_str).first():
                db.add(SleepRecord(
                    parent_id=parent_user.id,
                    sleep_date=d_str,
                    bed_time="10:15 PM",
                    wake_time="06:30 AM",
                    duration_hours=7.5 + (0.2 if i % 2 == 0 else -0.3),
                    quality_rating="RESTFUL",
                    recorded_at=datetime.datetime.combine(d, datetime.time(7, 0))
                ))
            
            # Meal Records
            if not db.query(MealRecord).filter(MealRecord.parent_id == parent_user.id, MealRecord.meal_date == d_str).first():
                db.add(MealRecord(
                    parent_id=parent_user.id,
                    meal_date=d_str,
                    meal_type="Breakfast",
                    description="Idli with sambar and warm tea",
                    was_on_time=True,
                    recorded_at=datetime.datetime.combine(d, datetime.time(8, 45))
                ))
                db.add(MealRecord(
                    parent_id=parent_user.id,
                    meal_date=d_str,
                    meal_type="Lunch",
                    description="Rice, rasam, and cooked greens",
                    was_on_time=True,
                    recorded_at=datetime.datetime.combine(d, datetime.time(13, 0))
                ))

            # Hydration Record
            if not db.query(HydrationRecord).filter(HydrationRecord.parent_id == parent_user.id, HydrationRecord.record_date == d_str).first():
                db.add(HydrationRecord(
                    parent_id=parent_user.id,
                    record_date=d_str,
                    amount_liters=1.65,
                    glasses_count=7,
                    recorded_at=datetime.datetime.combine(d, datetime.time(17, 0))
                ))
        db.commit()

    # Feature 18: Care Timeline Items (Step 11)
    if db.query(CareTimelineItem).filter(CareTimelineItem.parent_id == parent_user.id).count() == 0:
        timeline_items = [
            CareTimelineItem(
                parent_id=parent_user.id,
                event_time="08:35 AM",
                event_category="CHECKIN",
                title="Morning check-in completed",
                title_tamil="காலை நலம் தெரிவித்தல் முடிந்தது",
                description="Amma checked in feeling peaceful and well.",
                description_tamil="அம்மா நலமாக இருப்பதாக தெரிவித்தார்.",
                icon="❤️",
                severity="INFO",
                source="DATABASE"
            ),
            CareTimelineItem(
                parent_id=parent_user.id,
                event_time="09:02 AM",
                event_category="MEAL",
                title="Breakfast recorded",
                title_tamil="காலை உணவு உட்கொள்ளப்பட்டது",
                description="Wholesome idli and warm herbal tea recorded.",
                description_tamil="இட்லி மற்றும் மூலிகை தேநீர் உட்கொள்ளப்பட்டது.",
                icon="🍲",
                severity="INFO",
                source="DATABASE"
            ),
            CareTimelineItem(
                parent_id=parent_user.id,
                event_time="09:30 AM",
                event_category="MEDICATION",
                title="Morning medication confirmed",
                title_tamil="காலை மருந்து உட்கொள்ளப்பட்டது",
                description="BP and daily multivitamin acknowledged on time.",
                description_tamil="ரத்த அழுத்த மாத்திரை உட்கொள்ளப்பட்டது.",
                icon="💊",
                severity="INFO",
                source="DATABASE"
            ),
            CareTimelineItem(
                parent_id=parent_user.id,
                event_time="10:15 AM",
                event_category="ACTIVITY",
                title="Activity aligned with personal baseline",
                title_tamil="நடைபயிற்சி வழக்கமான அளவில் உள்ளது",
                description="Gentle garden stroll and veranda seating completed.",
                description_tamil="தோட்ட நடைபயிற்சி மற்றும் ஓய்வு முடிந்தது.",
                icon="🚶‍♀️",
                severity="INFO",
                source="DATABASE"
            ),
        ]
        db.add_all(timeline_items)
        db.commit()

    db.commit()
    print("[EVER NEAR SEED] Full-Platform & Family Connection Upgrade database seed verified successfully!")

if __name__ == "__main__":
    db = SessionLocal()
    init_db(db)
    db.close()

