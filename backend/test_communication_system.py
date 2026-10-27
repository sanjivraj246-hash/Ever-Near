import sys
import datetime
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.entities import (
    User, ParentProfile, FamilyProfile, FamilyRelationship,
    CommunicationRequest, CommunicationAttempt, CommunicationResponse,
    AutomatedResponseTemplate, ScheduledCallback, EscalationRule,
    CommunicationAuditLog, SOSAlert
)
from app.core.security import hash_password, create_access_token

def test_communication_suite():
    print("\n" + "="*60)
    print(">>> TESTING INTELLIGENT PARENT ENQUIRY & CALL ATTENTION SYSTEM <<<")
    print("="*60)

    from app.db.session import engine, Base
    Base.metadata.create_all(bind=engine)

    client = TestClient(app)
    db = SessionLocal()

    try:
        # 1. Setup / Verify Parent & Family Users
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

        # Link parent and family
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

        parent_token = create_access_token(parent.id, "PARENT")
        family_token = create_access_token(family.id, "FAMILY")
        p_headers = {"Authorization": f"Bearer {parent_token}"}
        f_headers = {"Authorization": f"Bearer {family_token}"}

        print("\n[1/12] Testing Voice Enquiry Intent Classification...")
        # Test Tamil health concern
        res = client.post("/api/communication/voice-enquiry/classify", json={
            "spoken_text": "Enakku konjam udambu sari illa, en ponna pesanum",
            "language": "ta"
        })
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["intent"] == "HEALTH_CONCERN"
        assert data["priority"] == "IMPORTANT"
        assert "not a medical diagnosis" in data["safe_summary"].lower() or "health concern" in data["safe_summary"].lower()
        print("  [OK] Tamil Health Concern: classified HEALTH_CONCERN (no medical diagnosis)")

        # Test English call request
        res = client.post("/api/communication/voice-enquiry/classify", json={
            "spoken_text": "I want to talk to my daughter please",
            "language": "en"
        })
        assert res.status_code == 200, res.text
        assert res.json()["intent"] == "CALL_FAMILY"
        print("  [OK] English Call Request: classified CALL_FAMILY")

        print("\n[2/12] Testing Create Communication Request (Parent -> Family)...")
        res = client.post("/api/communication/requests", headers=p_headers, json={
            "family_member_id": family.id,
            "family_member_name": "Karthik (Son)",
            "intent": "CALL_FAMILY",
            "reason_category": "want_to_talk",
            "reason_text": "I want to talk with you",
            "reason_tamil": "உங்களுடன் பேச வேண்டும்",
            "priority": "NORMAL"
        })
        assert res.status_code == 200, res.text
        req_data = res.json()
        req_id = req_data["id"]
        assert req_data["status"] == "NOTIFIED"
        assert req_data["automation_status"] == "ACTIVE"
        print(f"  [OK] Request #{req_id} created, status=NOTIFIED, automation_status=ACTIVE")

        print("\n[3/12] Testing Active Request Retrieval...")
        res = client.get("/api/communication/requests/active", headers=p_headers)
        assert res.status_code == 200, res.text
        assert res.json()["id"] == req_id
        print("  [OK] Active request retrieved by parent")

        print("\n[4/12] Testing Important Call Attention Mode...")
        # Create important request
        res = client.post("/api/communication/requests", headers=p_headers, json={
            "family_member_id": family.id,
            "intent": "HEALTH_CONCERN",
            "reason_category": "not_well",
            "reason_text": "I don't feel well",
            "reason_tamil": "உடல் நலம் சரியில்லை",
            "priority": "IMPORTANT"
        })
        assert res.status_code == 200
        imp_data = res.json()
        imp_id = imp_data["id"]
        assert imp_data["priority"] == "IMPORTANT"
        print(f"  [OK] Important request #{imp_id} created with priority=IMPORTANT")

        print("\n[5/12] Testing Parent Voice Response: 'Okay, I'm here' (Stops Automation)...")
        res = client.post("/api/communication/voice-response", headers=p_headers, json={
            "request_id": imp_id,
            "spoken_text": "Okay, I'm here",
            "language": "en"
        })
        assert res.status_code == 200, res.text
        vr_data = res.json()
        assert vr_data["classification"] == "ACKNOWLEDGED"
        assert vr_data["should_stop_reminder"] == True
        assert vr_data["automation_action"] == "STOP"
        
        # Verify in DB that automation is STOPPED
        chk = client.get(f"/api/communication/requests/{imp_id}", headers=p_headers).json()
        assert chk["automation_status"] == "STOPPED"
        assert chk["parent_response"] == "acknowledged"
        print("  [OK] Parent voice acknowledgement detected: automation_status=STOPPED")

        print("\n[6/12] Testing Parent Voice Response: 'Please call me'...")
        # Create another request
        res = client.post("/api/communication/requests", headers=p_headers, json={
            "family_member_id": family.id,
            "intent": "CALL_FAMILY",
            "reason_category": "call_me"
        })
        call_req_id = res.json()["id"]

        res = client.post("/api/communication/voice-response", headers=p_headers, json={
            "request_id": call_req_id,
            "spoken_text": "Please call me now",
            "language": "en"
        })
        assert res.status_code == 200
        vr = res.json()
        assert vr["classification"] == "REQUEST_CALL"
        chk = client.get(f"/api/communication/requests/{call_req_id}", headers=p_headers).json()
        assert chk["status"] == "CALL_REQUESTED"
        assert chk["automation_status"] == "STOPPED"
        print("  [OK] 'Please call me' handled: status=CALL_REQUESTED, automation=STOPPED")

        print("\n[7/12] Testing Parent Voice Response: 'I need help' (NEEDS_HELP)...")
        res = client.post("/api/communication/voice-response", headers=p_headers, json={
            "request_id": call_req_id,
            "spoken_text": "Enakku udhavi thevai, please come",
            "language": "ta"
        })
        assert res.status_code == 200
        vr_help = res.json()
        assert vr_help["classification"] == "NEEDS_HELP"
        assert vr_help["automation_action"] == "ESCALATE"
        print("  [OK] 'I need help' handled: classification=NEEDS_HELP, escalation action triggered")

        print("\n[8/12] CRITICAL SAFETY CHECK: Voice Response Must NOT Cancel Active SOS...")
        # Create active SOS alert
        sos = SOSAlert(parent_id=parent.parent_profile.id if parent.parent_profile else 1, status="ACTIVE", notes="Active SOS in progress")
        db.add(sos)
        db.commit()
        db.refresh(sos)
        sos_id = sos.id

        # Parent says "I'm okay"
        client.post("/api/communication/voice-response", headers=p_headers, json={
            "spoken_text": "I'm okay, all right",
            "language": "en"
        })

        # Verify SOS is STILL ACTIVE
        sos_check = db.query(SOSAlert).filter(SOSAlert.id == sos_id).first()
        assert sos_check.status == "ACTIVE", f"CRITICAL FAILURE: SOS was cancelled by voice response! Status is {sos_check.status}"
        print(f"  [OK] SOS Alert #{sos_id} remains ACTIVE despite parent saying 'I\\'m okay' (Safety Rule Enforced!)")

        print("\n[9/12] Testing Family Acknowledge & Response (Call Now, Templates)...")
        res = client.post(f"/api/communication/requests/{req_id}/acknowledge", headers=f_headers)
        assert res.status_code == 200
        assert res.json()["status"] == "ACKNOWLEDGED"
        print(f"  [OK] Family acknowledged request #{req_id}")

        res = client.post(f"/api/communication/requests/{req_id}/respond", headers=f_headers, json={
            "response_type": "TEMPLATE_MSG",
            "template_key": "BUSY",
            "message": "I'm in a meeting right now. I will call you shortly Amma ❤️",
            "message_tamil": "நான் இப்போது கூட்டத்தில் உள்ளேன். விரைவில் அழைக்கிறேன் அம்மா ❤️"
        })
        assert res.status_code == 200
        assert res.json()["status"] == "RESPONDING"
        print("  [OK] Family sent template response to parent")

        print("\n[10/12] Testing Call Later Scheduled Callback...")
        res = client.post(f"/api/communication/requests/{req_id}/schedule-callback", headers=f_headers, json={
            "minutes": 30
        })
        assert res.status_code == 200
        cb_data = res.json()
        assert cb_data["reminder_minutes"] == 30
        assert cb_data["status"] == "PENDING"
        print("  [OK] Callback scheduled for 30 minutes later")

        print("\n[11/12] Testing Repeated Communication Attempts & Unusual Activity Detection...")
        # Simulate 2 more attempts to reach 3+ in 2 hours
        for i in range(2):
            client.post("/api/communication/requests", headers=p_headers, json={
                "family_member_id": family.id,
                "reason_category": "want_to_talk"
            })
        
        attempts_res = client.get("/api/communication/recent-attempts", headers=f_headers)
        assert attempts_res.status_code == 200
        att_data = attempts_res.json()
        assert att_data["unusual_activity_detected"] == True
        assert att_data["attempts_count_last_2h"] >= 3
        print(f"  [OK] Unusual Communication Activity Flagged: {att_data['attempts_count_last_2h']} attempts in past 2 hours")

        print("\n[12/12] Testing Audit Logs & Templates Endpoints...")
        templates_res = client.get("/api/communication/templates", headers=f_headers)
        assert templates_res.status_code == 200
        assert len(templates_res.json()) >= 4
        print(f"  [OK] Automated response templates retrieved: {len(templates_res.json())} templates available")

        audit_res = client.get("/api/communication/audit-logs", headers=f_headers)
        assert audit_res.status_code == 200
        assert len(audit_res.json()) > 0
        print(f"  [OK] Communication audit logs verified: {len(audit_res.json())} events recorded")

        print("\n" + "="*60)
        print(">>> ALL 12 COMMUNICATION SYSTEM TESTS PASSED SUCCESSFULLY! <<<")
        print("="*60 + "\n")

    finally:
        db.close()

if __name__ == "__main__":
    test_communication_suite()
