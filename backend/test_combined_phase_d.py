import sys
import io
import datetime
import json

# Ensure Windows terminal prints Tamil and Unicode safely
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from fastapi.testclient import TestClient
from app.main import app
from app.database.session import SessionLocal, engine, Base
from app.models.entities import (
    User, ParentProfile, FamilyProfile, FamilyRelationship,
    DailyCheckIn, Medication, MedicationLog, SafetyEvent,
    AIAlert, AIAlertEvidence, CCTVDevice, RoutineBaseline,
    CareTimelineItem, AuditLog, SOSAlert
)
from app.core.security import hash_password, create_access_token
from app.ai.anomaly_detector import anomaly_detector
from app.ai.baseline_engine import baseline_engine
from app.ai.context_engine import context_engine
from app.ai.briefing import generate_family_briefing

def run_combined_phase_d_suite():
    print("\n" + "="*75)
    print(">>> EVER NEAR AI — COMBINED PHASE D (P10 + P11) TEST SUITE <<<")
    print("="*75)

    Base.metadata.create_all(bind=engine)
    client = TestClient(app)
    db = SessionLocal()

    passed_count = 0
    total_tests = 11

    try:
        # =========================================================================
        # SETUP USERS AND PERMISSIONS
        # =========================================================================
        print("\n[Setup] Preparing test fixtures and identities...")
        
        # 1. Parent
        parent = db.query(User).filter(User.phone == "9876543210").first()
        if not parent:
            parent = User(
                phone="9876543210",
                full_name="Lakshmi Amma",
                role="PARENT",
                password_hash=hash_password("1234"),
                is_active=True
            )
            db.add(parent)
            db.commit()
            db.refresh(parent)
            p_prof = ParentProfile(user_id=parent.id, preferred_name="Amma", language_pref="ta")
            db.add(p_prof)
            db.commit()

        # 2. Authorized Family
        family = db.query(User).filter(User.phone == "9876543211").first()
        if not family:
            family = User(
                phone="9876543211",
                full_name="Karthik (Son)",
                role="FAMILY",
                password_hash=hash_password("1234"),
                is_active=True
            )
            db.add(family)
            db.commit()
            db.refresh(family)
            f_prof = FamilyProfile(user_id=family.id, preferred_name="Karthik", relationship_type="Son")
            db.add(f_prof)
            db.commit()

        # Ensure approved relationship
        rel = db.query(FamilyRelationship).filter(
            FamilyRelationship.parent_id == parent.id,
            FamilyRelationship.family_user_id == family.id
        ).first()
        if not rel:
            rel = FamilyRelationship(
                parent_id=parent.id,
                family_user_id=family.id,
                relationship_type="Son",
                phone=family.phone,
                status="APPROVED"
            )
            db.add(rel)
            db.commit()
        else:
            rel.status = "APPROVED"
            db.commit()

        # 3. Unauthorized Family Member (Stranger / Unapproved)
        unauth_family = db.query(User).filter(User.phone == "9876543999").first()
        if not unauth_family:
            unauth_family = User(
                phone="9876543999",
                full_name="Unapproved Outsider",
                role="FAMILY",
                password_hash=hash_password("1234"),
                is_active=True
            )
            db.add(unauth_family)
            db.commit()
            db.refresh(unauth_family)

        # 4. CCTV Device Setup
        camera = db.query(CCTVDevice).first()
        if not camera:
            camera = CCTVDevice(
                name="Living Room Camera",
                name_tamil="வரவேற்பறை கேமரா",
                location="Living Room",
                stream_url="https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4",
                status="LIVE",
                enabled=True
            )
            db.add(camera)
            db.commit()
        # Ensure Parent Privacy allows CCTV access for authorized family in setup
        profile = db.query(ParentProfile).first()
        target_uid = profile.user_id if profile else parent.id
        from app.models.entities import PrivacySetting
        p_priv = db.query(PrivacySetting).filter(PrivacySetting.parent_id == target_uid).first()
        if not p_priv:
            p_priv = PrivacySetting(parent_id=target_uid, cctv_access=True, location_sharing=True, health_records_access=True)
            db.add(p_priv)
            db.commit()
        else:
            p_priv.cctv_access = True
            p_priv.location_sharing = True
            p_priv.health_records_access = True
            db.commit()

        p_token = create_access_token(parent.id, "PARENT")
        f_token = create_access_token(family.id, "FAMILY")
        unauth_token = create_access_token(unauth_family.id, "FAMILY")

        p_headers = {"Authorization": f"Bearer {p_token}"}
        f_headers = {"Authorization": f"Bearer {f_token}"}
        unauth_headers = {"Authorization": f"Bearer {unauth_token}"}
        print("  [OK] Users, permissions, and CCTV devices initialized.")

        # =========================================================================
        # TEST 1: Normal check-in -> no unnecessary alert
        # =========================================================================
        print("\n--- TEST 1: Normal Check-In (No Unnecessary Alert) ---")
        baseline = baseline_engine.calculate_personal_baseline(db, parent.id)
        assert "typical_checkin_window" in baseline
        
        # Evaluate normal parameters
        normal_eval = anomaly_detector.evaluate_routine(
            checkin_delay_mins=10.0,
            med_delay_mins=5.0,
            activity_ratio=0.95,
            sleep_hours=7.5,
            hydration_liters=1.8,
            interaction_count=4,
            baseline=baseline
        )
        assert normal_eval["is_anomaly"] is False
        assert normal_eval["change_score"] < 0.35
        print(f"  [OK] Normal evaluation: is_anomaly={normal_eval['is_anomaly']}, change_score={normal_eval['change_score']:.2f}")

        # Live routine status endpoint
        routine_res = client.get("/api/ai/routine-status", headers=p_headers)
        assert routine_res.status_code == 200, routine_res.text
        routine_data = routine_res.json()
        assert routine_data["status"] in ["normal", "attention", "deviation"]
        print(f"  [OK] Routine status endpoint responded: {routine_data['status']} (No panic or emergency created)")
        passed_count += 1

        # =========================================================================
        # TEST 2: Slight routine variation -> does not automatically become emergency
        # =========================================================================
        print("\n--- TEST 2: Slight Routine Variation (Not An Emergency) ---")
        slight_variation = anomaly_detector.evaluate_routine(
            checkin_delay_mins=25.0,  # 25 min variation
            med_delay_mins=15.0,
            activity_ratio=0.82,
            sleep_hours=6.8,
            hydration_liters=1.4,
            interaction_count=3,
            baseline=baseline
        )
        # Context engine cross evaluation
        context_result = context_engine.evaluate_context(
            anomaly_result=slight_variation,
            baseline=baseline,
            cctv_events=[],
            phone_interactions_recent=True,
            active_sos=False
        )
        # Verify it distinguishes attention/mild from emergency, strictly NOT EMERGENCY
        assert context_result["severity"] in ["NORMAL", "NOTICE", "LOW", "MILD", "ATTENTION"], f"Expected non-emergency severity, got {context_result['severity']}"
        assert context_result["severity"] not in ["EMERGENCY", "URGENT"], "Slight routine variation must never be EMERGENCY"
        print(f"  [OK] Slight routine variation severity: {context_result['severity']}")
        passed_count += 1

        # =========================================================================
        # TEST 3: Missed check-in -> appropriate routine-change handling
        # =========================================================================
        print("\n--- TEST 3: Missed Check-In (Appropriate Routine-Change Handling) ---")
        missed_eval = anomaly_detector.evaluate_routine(
            checkin_delay_mins=120.0,  # 2 hours delayed
            med_delay_mins=10.0,
            activity_ratio=0.75,
            sleep_hours=6.5,
            hydration_liters=1.2,
            interaction_count=2,
            baseline=baseline
        )
        assert missed_eval["change_score"] > 0.40
        assert missed_eval["alert_level"] in ["MILD_CHANGE", "SIGNIFICANT_CHANGE", "HIGH_PRIORITY_CHANGE"]
        assert missed_eval["feature_breakdown"]["checkin_deviation"] > 0.5
        print(f"  [OK] Missed check-in detected: alert_level={missed_eval['alert_level']}, checkin_deviation={missed_eval['feature_breakdown']['checkin_deviation']} (change_score={missed_eval['change_score']:.2f})")
        passed_count += 1

        # =========================================================================
        # TEST 4: Unusual CCTV event -> safety event generated according to implementation
        # =========================================================================
        print("\n--- TEST 4: Unusual CCTV Event Generation & Clarity ---")
        # Check camera source clarity
        cam_res = client.get("/api/cameras", headers=f_headers)
        assert cam_res.status_code == 200, cam_res.text
        cams = cam_res.json()
        assert len(cams) > 0
        first_cam = cams[0]
        assert "is_simulation" in first_cam
        assert "source_type" in first_cam
        print(f"  [OK] Camera transparency: {first_cam['name']} -> is_simulation={first_cam['is_simulation']}, source_type='{first_cam['source_type']}'")

        # Create unusual moment safety event
        now = datetime.datetime.utcnow()
        parent_prof = parent.parent_profile or db.query(ParentProfile).filter(ParentProfile.user_id == parent.id).first()
        prof_id = parent_prof.id if parent_prof else 1
        cctv_safety_event = SafetyEvent(
            parent_id=prof_id,
            source="CCTV",
            title="Unusual movement detected in living room",
            title_tamil="வரவேற்பறையில் அசாதாரண அசைவு கவனிக்கப்பட்டது",
            description="Optical flow movement detected outside normal morning baseline window at 03:20 PM.",
            severity="ATTENTION",
            confidence=0.89,
            acknowledged=False,
            created_at=now
        )
        db.add(cctv_safety_event)
        db.commit()
        db.refresh(cctv_safety_event)

        # Family fetches events
        events_res = client.get(f"/api/cameras/{camera.id}/events", headers=f_headers)
        assert events_res.status_code == 200, events_res.text
        events_data = events_res.json()
        assert any(e["id"] == cctv_safety_event.id for e in events_data)
        print(f"  [OK] Unusual CCTV moment recorded and verified on camera event feed.")
        passed_count += 1

        # =========================================================================
        # TEST 5: Multiple meaningful signals -> context engine evaluates combined info
        # =========================================================================
        print("\n--- TEST 5: Multi-Signal Context Engine Evaluation ---")
        multi_signal_anomaly = anomaly_detector.evaluate_routine(
            checkin_delay_mins=120.0,
            med_delay_mins=90.0,
            activity_ratio=0.55,
            sleep_hours=5.0,
            hydration_liters=0.8,
            interaction_count=0,
            baseline=baseline
        )
        cctv_event_summary = [{
            "event_type": "UNUSUAL_MOVEMENT",
            "severity": "ATTENTION",
            "time": now.strftime("%I:%M %p")
        }]
        context_multi = context_engine.evaluate_context(
            anomaly_result=multi_signal_anomaly,
            baseline=baseline,
            cctv_events=cctv_event_summary,
            phone_interactions_recent=False,
            active_sos=False
        )
        assert context_multi["severity"] in ["ATTENTION", "HIGH", "HIGH_PRIORITY", "URGENT"]
        assert len(context_multi["supporting_signals"]) >= 2
        print(f"  [OK] Multi-signal combination: severity={context_multi['severity']}, signals count={len(context_multi['supporting_signals'])}")
        passed_count += 1

        # =========================================================================
        # TEST 6: Unauthorized family member -> cannot access restricted safety/camera/location data
        # =========================================================================
        print("\n--- TEST 6: Unauthorized Family Access Restriction (403 Forbidden) ---")
        # 6a. CCTV cameras
        cam_unauth = client.get("/api/cameras", headers=unauth_headers)
        assert cam_unauth.status_code == 403, f"Expected 403, got {cam_unauth.status_code}"
        print("  [OK] Unauthorized family blocked from /api/cameras (403)")

        # 6b. Camera events
        cam_evt_unauth = client.get(f"/api/cameras/{camera.id}/events", headers=unauth_headers)
        assert cam_evt_unauth.status_code == 403, f"Expected 403, got {cam_evt_unauth.status_code}"
        print("  [OK] Unauthorized family blocked from camera events (403)")

        # 6c. Safety events
        safety_unauth = client.get("/api/safety/events", headers=unauth_headers)
        assert safety_unauth.status_code == 403, f"Expected 403, got {safety_unauth.status_code}"
        print("  [OK] Unauthorized family blocked from /api/safety/events (403)")

        # 6d. Geofence / Safe Return active location
        loc_unauth = client.get("/api/support/safe-return/active", headers=unauth_headers)
        assert loc_unauth.status_code == 403, f"Expected 403, got {loc_unauth.status_code}"
        print("  [OK] Unauthorized family blocked from Safe Return location (403)")
        passed_count += 1

        # =========================================================================
        # TEST 7: Emergency / SOS -> existing emergency workflow remains independent
        # =========================================================================
        print("\n--- TEST 7: Emergency SOS Independence ---")
        sos_res = client.post("/api/sos", headers=p_headers, json={
            "notes": "Emergency assistance requested by parent test"
        })
        assert sos_res.status_code == 200, sos_res.text
        sos_data = sos_res.json()
        assert sos_data["status"] == "ACTIVE"
        sos_id = sos_data["id"]
        print(f"  [OK] SOS triggered independently (Alert ID: {sos_id})")

        # Verify active SOS in database
        sos_db = db.query(SOSAlert).filter(SOSAlert.id == sos_id).first()
        assert sos_db is not None
        assert sos_db.status == "ACTIVE"

        # Resolve SOS cleanly
        resolve_res = client.post(f"/api/sos/{sos_id}/resolve", headers=p_headers)
        assert resolve_res.status_code == 200
        print("  [OK] SOS resolved independently. AI routine monitoring remains distinct from emergency SOS.")
        passed_count += 1

        # =========================================================================
        # TEST 8: AI-generated alert -> contains human-readable explanation
        # =========================================================================
        print("\n--- TEST 8: Explainable AI Alert (Human-Readable, No Raw Risk Jargon) ---")
        # Trigger simulation to produce explainable alert
        sim_res = client.post("/api/ai/simulate-abnormal-routine", headers=f_headers, json={
            "scenario": "abnormal_day"
        })
        assert sim_res.status_code == 200, sim_res.text
        sim_data = sim_res.json()
        alert_id = sim_data["alert_id"]
        assert alert_id is not None
        
        # Fetch detailed explanation
        exp_res = client.get(f"/api/ai/alerts/{alert_id}/explanation", headers=f_headers)
        assert exp_res.status_code == 200, exp_res.text
        exp_data = exp_res.json()
        
        # Verify human-readable fields
        assert "detected_change" in exp_data
        assert "baseline_comparison" in exp_data
        assert "system_interpretation" in exp_data
        assert "suggested_action" in exp_data
        assert "disclaimer" in exp_data
        assert "IsolationForest prediction" not in exp_data["detected_change"]
        assert "diagnostic" in exp_data["disclaimer"].lower() or "medical" in exp_data["disclaimer"].lower()
        print(f"  [OK] Human explanation verified:\n       What: {exp_data['detected_change']}\n       Why: {exp_data['system_interpretation']}\n       Action: {exp_data['suggested_action']}")
        passed_count += 1

        # =========================================================================
        # TEST 9: Duplicate event -> does not create an uncontrolled alert loop
        # =========================================================================
        print("\n--- TEST 9: Alert Fatigue Deduplication ---")
        created_alert = db.query(AIAlert).filter(AIAlert.id == alert_id).first()
        assert created_alert is not None
        target_pid = created_alert.parent_id

        active_before = db.query(AIAlert).filter(
            AIAlert.parent_id == target_pid,
            AIAlert.alert_type == "ROUTINE_CHANGE",
            AIAlert.status == "ACTIVE"
        ).count()
        assert active_before >= 1

        # Trigger duplicate simulation
        sim_res2 = client.post("/api/ai/simulate-abnormal-routine", headers=f_headers, json={
            "scenario": "abnormal_day"
        })
        assert sim_res2.status_code == 200
        sim_data2 = sim_res2.json()
        assert sim_data2["alert_id"] == alert_id, "Expected reuse of existing active alert ID"

        active_after = db.query(AIAlert).filter(
            AIAlert.parent_id == target_pid,
            AIAlert.alert_type == "ROUTINE_CHANGE",
            AIAlert.status == "ACTIVE"
        ).count()
        assert active_after == active_before, f"Expected {active_before} active alerts after duplicate run, found {active_after}"
        print(f"  [OK] Alert deduplicated: Active alert count remained {active_after} (ID: {alert_id}). No notification loop created.")
        passed_count += 1

        # =========================================================================
        # TEST 10: Tamil mode -> parent receives understandable safety/AI messages
        # =========================================================================
        print("\n--- TEST 10: Tamil Mode Accessibility & Understandability ---")
        # 10a. Routine status in Tamil
        routine_res_ta = client.get("/api/ai/routine-status", headers=p_headers)
        assert routine_res_ta.status_code == 200
        ta_data = routine_res_ta.json()
        assert "reason_tamil" in ta_data
        assert len(ta_data["reason_tamil"]) > 0
        print(f"  [OK] Tamil routine reason: {ta_data['reason_tamil']}")

        # 10b. Family briefing in Tamil
        briefing = generate_family_briefing(
            parent_name="அம்மா",
            has_checked_in=True,
            feeling="happy",
            meds_taken=2,
            meds_total=2,
            recent_events_count=0
        )
        assert len(briefing["summary_text_tamil"]) > 0
        assert "அம்மா" in briefing["summary_text_tamil"]
        print(f"  [OK] Tamil briefing summary: {briefing['summary_text_tamil']}")

        # 10c. Alert title & message in Tamil
        alert_rec = db.query(AIAlert).filter(AIAlert.id == alert_id).first()
        assert alert_rec.title_tamil is not None
        assert alert_rec.message_tamil is not None
        assert alert_rec.suggested_action_tamil is not None
        print(f"  [OK] Tamil alert title: {alert_rec.title_tamil}")
        print(f"  [OK] Tamil alert action: {alert_rec.suggested_action_tamil}")
        passed_count += 1

        # =========================================================================
        # TEST 11 (BONUS / P11 Core): AI Voice Routing Flow (5 Intents)
        # =========================================================================
        print("\n--- TEST 11: AI Voice Routing Pipeline (Intent -> Target Flow) ---")
        
        voice_cases = [
            ("I need my blood pressure medicine", "en", "MEDICATION_HELP", "MEDICATION_FLOW", "/app/parent/health"),
            ("I want to talk to my daughter", "en", "CALL_FAMILY", "COMMUNICATION_FLOW", "/app/parent"),
            ("I don't feel well today", "en", "HEALTH_CONCERN", "HEALTH_HELP_FLOW", "/app/parent/health"),
            ("Something happened at home near the door", "en", "HOME_INCIDENT", "SAFETY_FLOW", "/app/parent/safety"),
            ("Emergency, please save me!", "en", "EMERGENCY", "SOS_EMERGENCY_FLOW", "/app/parent/sos"),
            ("எனக்கு மாத்திரை மருந்து வேண்டும்", "ta", "MEDICATION_HELP", "MEDICATION_FLOW", "/app/parent/health"),
            ("உடம்பு சரியில்லை, உதவி தேவை", "ta", "HEALTH_CONCERN", "HEALTH_HELP_FLOW", "/app/parent/health")
        ]

        for text, lang, exp_intent, exp_flow, exp_route in voice_cases:
            res = client.post("/api/ai/voice-route", headers=p_headers, json={
                "spoken_text": text,
                "language": lang
            })
            assert res.status_code == 200, res.text
            d = res.json()
            assert d["intent"] == exp_intent, f"For '{text}', expected {exp_intent}, got {d['intent']}"
            assert d["target_flow"] == exp_flow, f"For '{text}', expected {exp_flow}, got {d['target_flow']}"
            assert d["target_route"] == exp_route, f"For '{text}', expected {exp_route}, got {d['target_route']}"
            assert len(d["explanation"]) > 0
            assert len(d["suggested_action"]) > 0
            print(f"  [OK] Voice Route '{text[:28]}...' -> Flow: {d['target_flow']} ({d['target_route']})")

        passed_count += 1

        print("\n" + "="*75)
        print(f">>> ALL COMBINED PHASE D TESTS PASSED ({passed_count}/{total_tests}) <<<")
        print("="*75)

    finally:
        db.close()

if __name__ == "__main__":
    run_combined_phase_d_suite()
