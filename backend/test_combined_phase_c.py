import sys
import io
import datetime

# Ensure Windows terminal prints Tamil and Unicode safely
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from fastapi.testclient import TestClient
from app.main import app
from app.database.session import SessionLocal, engine, Base
from app.models.entities import (
    User, ParentProfile, FamilyProfile, FamilyRelationship,
    CommunicationRequest, CommunicationAttempt, CommunicationResponse,
    AutomatedResponseTemplate, ScheduledCallback, EscalationRule,
    CommunicationAuditLog, SOSAlert, AuditLog
)
from app.core.security import hash_password, create_access_token

def run_combined_phase_c_suite():
    print("\n" + "="*70)
    print(">>> EVER NEAR AI — COMBINED PHASE C (P8 + P9) TEST SUITE <<<")
    print("="*70)

    Base.metadata.create_all(bind=engine)
    client = TestClient(app)
    db = SessionLocal()

    try:
        # 0. Setup / Verify Users
        print("\n[Setup] Setting up Parent and Family users...")
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

        p_token = create_access_token(parent.id, "PARENT")
        f_token = create_access_token(family.id, "FAMILY")
        p_headers = {"Authorization": f"Bearer {p_token}"}
        f_headers = {"Authorization": f"Bearer {f_token}"}
        print("  [OK] Users and relationship ready.")

        # =========================================================================
        # FLOW 1: Parent -> Tamil -> TALK TO FAMILY -> family selected -> reason -> request sent -> family receives request
        # =========================================================================
        print("\n--- FLOW 1: Parent Tamil -> TALK TO FAMILY (குடும்பத்தினருடன் பேச) ---")
        # 1a. Tamil voice enquiry classification
        classify_res = client.post("/api/communication/voice-enquiry/classify", json={
            "spoken_text": "எனக்கு உடல் நலம் சரியில்லை, கார்த்திக் உடன் பேச வேண்டும்",
            "language": "ta"
        })
        assert classify_res.status_code == 200, classify_res.text
        classify_data = classify_res.json()
        assert classify_data["intent"] == "HEALTH_CONCERN"
        assert classify_data["priority"] == "IMPORTANT"
        print("  [OK] Tamil voice enquiry classified: HEALTH_CONCERN, priority=IMPORTANT")

        # 1b. Parent submits request in Tamil
        flow1_create = client.post("/api/communication/requests", headers=p_headers, json={
            "family_member_id": family.id,
            "family_member_name": "Karthik (Son)",
            "intent": "HEALTH_CONCERN",
            "reason_category": "not_well",
            "reason_text": "I don't feel well",
            "reason_tamil": "உடல் நலம் சரியில்லை",
            "priority": "IMPORTANT",
            "voice_input": True,
            "voice_transcript": "எனக்கு உடல் நலம் சரியில்லை"
        })
        assert flow1_create.status_code == 200, flow1_create.text
        flow1_data = flow1_create.json()
        flow1_id = flow1_data["id"]
        assert flow1_data["status"] == "NOTIFIED"
        assert flow1_data["reason_tamil"] == "உடல் நலம் சரியில்லை"
        assert flow1_data["ai_summary_tamil"] is not None
        print(f"  [OK] Request #{flow1_id} created with Tamil metadata.")

        # 1c. Family receives request in CARE CIRCLE
        f_reqs_res = client.get("/api/communication/requests", headers=f_headers)
        assert f_reqs_res.status_code == 200
        found = any(r["id"] == flow1_id for r in f_reqs_res.json())
        assert found, "Family did not receive request in CARE CIRCLE list"
        print(f"  [OK] Family received incoming request #{flow1_id} in CARE CIRCLE.")

        # =========================================================================
        # FLOW 2: Parent -> English -> TALK TO FAMILY -> request sent -> family responds -> parent receives status
        # =========================================================================
        print("\n--- FLOW 2: Parent English -> TALK TO FAMILY -> Family Responds ---")
        flow2_create = client.post("/api/communication/requests", headers=p_headers, json={
            "family_member_id": family.id,
            "family_member_name": "Karthik (Son)",
            "intent": "CALL_FAMILY",
            "reason_category": "want_to_talk",
            "reason_text": "I want to talk",
            "reason_tamil": "பேச வேண்டும்",
            "priority": "NORMAL"
        })
        assert flow2_create.status_code == 200
        flow2_id = flow2_create.json()["id"]

        # Family responds: CALL_NOW
        family_resp = client.post(f"/api/communication/requests/{flow2_id}/respond", headers=f_headers, json={
            "response_type": "CALL_NOW",
            "message": "Calling you right now Amma ❤️",
            "message_tamil": "இப்போது அழைக்கிறேன் அம்மா ❤️"
        })
        assert family_resp.status_code == 200
        resp_data = family_resp.json()
        assert resp_data["status"] == "RESPONDING"
        assert resp_data["automation_status"] == "STOPPED"
        print(f"  [OK] Family responded to Request #{flow2_id}: status=RESPONDING")

        # Parent retrieves active status and sees response
        parent_status = client.get(f"/api/communication/requests/{flow2_id}", headers=p_headers)
        assert parent_status.status_code == 200
        assert parent_status.json()["status"] == "RESPONDING"
        assert parent_status.json()["latest_response_message"] is not None
        print(f"  [OK] Parent received updated status: RESPONDING with message '{parent_status.json()['latest_response_message']}'.")

        # =========================================================================
        # FLOW 3: Parent -> communication reminder -> voice acknowledgement -> reminder stops
        # =========================================================================
        print("\n--- FLOW 3: Voice Acknowledgement Stops Communication Reminder ---")
        flow3_create = client.post("/api/communication/requests", headers=p_headers, json={
            "family_member_id": family.id,
            "intent": "CALL_FAMILY",
            "reason_category": "want_to_talk",
            "priority": "NORMAL"
        })
        flow3_id = flow3_create.json()["id"]
        assert flow3_create.json()["automation_status"] == "ACTIVE"

        # Parent says "நான் நலமாக இருக்கிறேன்" (Tamil acknowledgement)
        voice_ack_res = client.post("/api/communication/voice-response", headers=p_headers, json={
            "request_id": flow3_id,
            "spoken_text": "நான் நலமாக இருக்கிறேன்",
            "language": "ta"
        })
        assert voice_ack_res.status_code == 200
        ack_res_data = voice_ack_res.json()
        assert ack_res_data["classification"] == "ACKNOWLEDGED"
        assert ack_res_data["should_stop_reminder"] is True

        # Verify communication request automation is now STOPPED
        chk_req = client.get(f"/api/communication/requests/{flow3_id}", headers=p_headers).json()
        assert chk_req["automation_status"] == "STOPPED"
        assert chk_req["status"] == "ACKNOWLEDGED"
        print("  [OK] Voice acknowledgement ('நான் நலமாக இருக்கிறேன்') stopped communication reminder.")

        # Test English acknowledgement: "Okay, I'm here"
        flow3b_create = client.post("/api/communication/requests", headers=p_headers, json={
            "family_member_id": family.id,
            "intent": "CALL_FAMILY",
            "reason_category": "want_to_talk",
            "priority": "NORMAL"
        })
        flow3b_id = flow3b_create.json()["id"]
        voice_ack_en = client.post("/api/communication/voice-response", headers=p_headers, json={
            "request_id": flow3b_id,
            "spoken_text": "Okay, I'm here",
            "language": "en"
        })
        assert voice_ack_en.json()["classification"] == "ACKNOWLEDGED"
        assert voice_ack_en.json()["should_stop_reminder"] is True
        chk_req_en = client.get(f"/api/communication/requests/{flow3b_id}", headers=p_headers).json()
        assert chk_req_en["automation_status"] == "STOPPED"
        print("  [OK] Voice acknowledgement ('Okay, I'm here') stopped communication reminder.")

        # =========================================================================
        # FLOW 4: CRITICAL SAFETY RULE — SOS Active + Normal Voice Ack -> SOS Remains Active!
        # =========================================================================
        print("\n--- FLOW 4: CRITICAL SAFETY INVARIANT — Normal Ack Must NEVER Cancel SOS ---")
        # 4a. Trigger SOS
        sos_res = client.post("/api/sos", headers=p_headers, json={
            "notes": "Emergency SOS triggered by Lakshmi Amma"
        })
        assert sos_res.status_code == 200
        active_sos_id = sos_res.json()["id"]
        assert sos_res.json()["status"] == "ACTIVE"
        print(f"  [OK] SOS Alert #{active_sos_id} triggered, status=ACTIVE")

        # 4b. Parent provides normal voice acknowledgement: "Okay, I'm here" / "நான் நலமாக இருக்கிறேன்"
        v_resp = client.post("/api/communication/voice-response", headers=p_headers, json={
            "spoken_text": "Okay, I'm here",
            "language": "en"
        })
        assert v_resp.status_code == 200
        assert v_resp.json()["classification"] == "ACKNOWLEDGED"

        # 4c. Verify SOS is STILL ACTIVE
        sos_in_db = db.query(SOSAlert).filter(SOSAlert.id == active_sos_id).first()
        assert sos_in_db.status == "ACTIVE", f"SAFETY VIOLATION! SOS was changed to {sos_in_db.status}"

        # Test with Tamil "நான் நலமாக இருக்கிறேன்"
        v_resp_ta = client.post("/api/communication/voice-response", headers=p_headers, json={
            "spoken_text": "நான் நலமாக இருக்கிறேன்",
            "language": "ta"
        })
        assert v_resp_ta.status_code == 200
        sos_in_db_again = db.query(SOSAlert).filter(SOSAlert.id == active_sos_id).first()
        assert sos_in_db_again.status == "ACTIVE", f"SAFETY VIOLATION! SOS was changed by Tamil voice ack!"
        print(f"  [PASS] SAFETY INVARIANT VERIFIED: Active SOS Alert #{active_sos_id} remains ACTIVE despite voice acknowledgements!")

        # =========================================================================
        # FLOW 5: Parent -> SOS -> Emergency Active -> Explicit SOS Cancellation -> SOS Ends
        # =========================================================================
        print("\n--- FLOW 5: Explicit SOS Cancellation Ends SOS ---")
        resolve_res = client.post(f"/api/sos/{active_sos_id}/resolve", headers=p_headers)
        assert resolve_res.status_code == 200
        db.expire_all()
        sos_resolved = db.query(SOSAlert).filter(SOSAlert.id == active_sos_id).first()
        assert sos_resolved.status == "RESOLVED"
        print(f"  [OK] SOS Alert #{active_sos_id} explicitly resolved: status=RESOLVED")

        # =========================================================================
        # FLOW 6: Family -> CARE CIRCLE -> Incoming Request -> Call Later -> Parent Status
        # =========================================================================
        print("\n--- FLOW 6: Family Care Circle Responses (Call Later Callback) ---")
        flow6_create = client.post("/api/communication/requests", headers=p_headers, json={
            "family_member_id": family.id,
            "intent": "CALL_FAMILY",
            "reason_category": "want_to_talk",
            "priority": "NORMAL"
        })
        flow6_id = flow6_create.json()["id"]

        # Family schedules callback for 30 minutes
        sched_res = client.post(f"/api/communication/requests/{flow6_id}/schedule-callback", headers=f_headers, json={
            "minutes": 30
        })
        assert sched_res.status_code == 200
        cb_info = sched_res.json()
        assert cb_info["reminder_minutes"] == 30
        assert cb_info["status"] == "PENDING"

        # Parent sees CALLBACK_SCHEDULED status
        flow6_chk = client.get(f"/api/communication/requests/{flow6_id}", headers=p_headers).json()
        assert flow6_chk["status"] == "CALLBACK_SCHEDULED"
        assert flow6_chk["automation_status"] == "STOPPED"
        print(f"  [OK] Callback scheduled: Request #{flow6_id} updated to CALLBACK_SCHEDULED for 30 mins.")

        # =========================================================================
        # FLOW 7: Language Consistency & State Preservation (English ↔ Tamil)
        # =========================================================================
        print("\n--- FLOW 7: Bilingual Content Verification & State Preservation ---")
        # Classify various reason intents in both English and Tamil
        test_phrases = [
            ("medicine", "மாத்திரை எடுக்க உதவி வேணும்", "ta", "MEDICATION_HELP"),
            ("doctor", "மருத்துவமனைக்கு போக வேண்டும்", "ta", "DOCTOR_HELP"),
            ("home_incident", "Something happened at home, please check", "en", "HOME_INCIDENT"),
            ("emergency", "காப்பாத்துங்க உடனே வாங்க", "ta", "EMERGENCY"),
        ]
        for cat_key, phrase, l, exp_intent in test_phrases:
            res = client.post("/api/communication/voice-enquiry/classify", json={
                "spoken_text": phrase,
                "language": l
            })
            assert res.status_code == 200
            data = res.json()
            assert data["intent"] == exp_intent, f"Mismatch for '{phrase}': expected {exp_intent}, got {data['intent']}"
            print(f"  [OK] '{phrase[:25]}...' -> intent={data['intent']}, priority={data['priority']}")

        # Verify templates exist in both English and Tamil
        tmpl_res = client.get("/api/communication/templates", headers=f_headers)
        assert tmpl_res.status_code == 200
        templates = tmpl_res.json()
        for t in templates:
            assert t["text"] is not None and len(t["text"]) > 0
            assert t["text_tamil"] is not None and len(t["text_tamil"]) > 0
        print(f"  [OK] All {len(templates)} response templates contain both English and Tamil text.")

        # =========================================================================
        # SECURITY & AUTHORIZATION TESTS
        # =========================================================================
        print("\n--- SECURITY: Authentication & Authorization Boundaries ---")
        # Unauthenticated request fails
        unauth = client.get("/api/communication/requests")
        assert unauth.status_code == 401, f"Expected 401, got {unauth.status_code}"
        print("  [OK] Unauthenticated requests rejected with 401.")

        # Non-permitted outsider cannot access parent communication
        outsider = db.query(User).filter(User.phone == "9999988888").first()
        if not outsider:
            outsider = User(
                phone="9999988888",
                full_name="Random Outsider",
                role="FAMILY",
                password_hash=hash_password("1234"),
                is_active=True
            )
            db.add(outsider)
            db.commit()
            db.refresh(outsider)
        out_token = create_access_token(outsider.id, "FAMILY")
        out_headers = {"Authorization": f"Bearer {out_token}"}

        # Check outsider attempts to view requests for Lakshmi Amma
        # (Outsider has no approved relationship with Lakshmi Amma)
        out_reqs = client.get("/api/communication/requests", headers=out_headers)
        assert out_reqs.status_code == 200
        # Outsider must not see Lakshmi Amma's requests
        outsider_can_see_amma = any(r["parent_id"] == parent.id for r in out_reqs.json())
        assert not outsider_can_see_amma, "Security breach: outsider saw parent requests!"
        print("  [OK] Outsider without approved relationship cannot access parent communication.")

        print("\n" + "="*70)
        print(">>> ALL COMBINED PHASE C (P8 + P9) TESTS PASSED SUCCESSFULLY! <<<")
        print("="*70 + "\n")

    finally:
        db.close()

if __name__ == "__main__":
    run_combined_phase_c_suite()
