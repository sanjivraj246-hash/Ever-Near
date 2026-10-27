import sys
import httpx

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8000/api"

def test_full_user_journey():
    print("=" * 65)
    print("EVER NEAR AI — FULL LIVE HTTP USER JOURNEY SIMULATION")
    print("=" * 65)

    client = httpx.Client(base_url=BASE_URL, timeout=10.0)

    # 1. Health
    h = client.get("/health")
    assert h.status_code == 200, f"Health failed: {h.text}"
    print("\n1. Live Backend Health: OK (200)")

    # 2. Parent Login Flow
    print("\n2. Parent Login Flow (Lakshmi Amma)...")
    p_login = client.post("/auth/login", json={"phone": "9876543210", "password": "1234"})
    assert p_login.status_code == 200, f"Login failed: {p_login.text}"
    p_token = p_login.json()["access_token"]
    p_headers = {"Authorization": f"Bearer {p_token}"}
    p_me = client.get("/auth/me", headers=p_headers)
    assert p_me.status_code == 200
    assert p_me.json()["role"] == "PARENT"
    print(f"   ✓ Logged in as: {p_me.json()['full_name']} (Role: {p_me.json()['role']})")

    # 3. Parent Home Screen Loading & Check-in
    print("\n3. Parent Home Screen Data Load & Check-in...")
    today_check = client.get("/checkins/today", headers=p_headers)
    assert today_check.status_code == 200
    print(f"   ✓ Today's initial check-in status: {'Completed' if today_check.json() else 'None'}")

    sub_check = client.post("/checkins", json={
        "feeling": "good",
        "feeling_tamil": "நன்றாக உணர்கிறேன்",
        "note": "Morning routine completed peacefully"
    }, headers=p_headers)
    assert sub_check.status_code == 200
    print(f"   ✓ Submitted Feeling: '{sub_check.json()['feeling']}' (Tamil: {sub_check.json()['feeling_tamil']})")

    # 4. Parent Care Screen (Meds, Care Summary, Independence View)
    print("\n4. Parent Care Screen Data Flow...")
    meds = client.get("/medications", headers=p_headers)
    assert meds.status_code == 200
    med_list = meds.json()
    print(f"   ✓ Active Medications count: {len(med_list)}")

    care_sum = client.get("/care/today", headers=p_headers)
    assert care_sum.status_code == 200
    print(f"   ✓ Care Summary: Wellbeing='{care_sum.json()['wellbeing']}', Water='{care_sum.json()['water_liters']}', Activity='{care_sum.json()['activity_level']}'")

    indep = client.get("/ai/independence-view", headers=p_headers)
    assert indep.status_code == 200
    print(f"   ✓ Independence View: {indep.json()['completed_count']}/{indep.json()['total_count']} completed")

    # 5. Parent Family Screen
    print("\n5. Parent Family Screen Data Flow...")
    fam_contacts = client.get("/family", headers=p_headers)
    assert fam_contacts.status_code == 200
    print(f"   ✓ Connected Family Contacts ({len(fam_contacts.json())}): {[c['name'] for c in fam_contacts.json()[:2]]}")

    # 6. Parent Privacy Screen (Toggles, Pause)
    print("\n6. Parent Privacy Screen Data Flow...")
    priv_settings = client.get("/privacy/settings", headers=p_headers)
    assert priv_settings.status_code == 200
    print(f"   ✓ Initial Privacy: Health={priv_settings.json()['health_info']}, CCTV={priv_settings.json()['cctv_access']}, Location={priv_settings.json()['location_sharing']}")

    # Activate Privacy Pause for 30 minutes
    pause_res = client.post("/privacy/pause", json={"duration_minutes": 30}, headers=p_headers)
    assert pause_res.status_code == 200
    assert pause_res.json()["is_paused"] is True
    print(f"   ✓ Privacy Pause Activated for 30 mins (Emergency SOS remains active: {pause_res.json()['emergency_remains_active']})")

    # 7. Parent SOS Emergency Screen
    print("\n7. Parent Emergency SOS Flow...")
    sos_res = client.post("/sos", json={"notes": "Test emergency trigger from parent UI"}, headers=p_headers)
    assert sos_res.status_code == 200
    sos_id = sos_res.json()["id"]
    print(f"   ✓ Emergency Alert #{sos_id} created with status={sos_res.json()['status']}")

    # -------------------------------------------------------------------------
    # SWITCH TO FAMILY USER (Karthik)
    # -------------------------------------------------------------------------
    print("\n8. Switching to Family Member (Karthik)...")
    f_login = client.post("/auth/login", json={"phone": "9876543211", "password": "1234"})
    assert f_login.status_code == 200
    f_token = f_login.json()["access_token"]
    f_headers = {"Authorization": f"Bearer {f_token}"}
    f_me = client.get("/auth/me", headers=f_headers)
    assert f_me.status_code == 200
    assert f_me.json()["role"] == "FAMILY"
    print(f"   ✓ Logged in as: {f_me.json()['full_name']} (Role: {f_me.json()['role']})")

    # 9. Family Home Screen (Parent Status, Briefing, SOS Banner)
    print("\n9. Family Home Screen Data Flow...")
    p_status = client.get("/family/parent-status", headers=f_headers)
    assert p_status.status_code == 200
    print(f"   ✓ Family view of linked parent: {p_status.json()['preferred_name']} (Active Emergency: {p_status.json()['has_active_emergency']})")

    # Family detects active SOS
    active_sos = client.get("/sos/active", headers=f_headers)
    assert active_sos.status_code == 200
    assert active_sos.json() is not None
    print(f"   ✓ Family detected SOS #{active_sos.json()['id']}")

    # Family acknowledges SOS
    ack_sos = client.post(f"/sos/{sos_id}/acknowledge", json={"responder_name": "Karthik (Son)"}, headers=f_headers)
    assert ack_sos.status_code == 200
    assert ack_sos.json()["status"] == "ACKNOWLEDGED"
    print(f"   ✓ SOS #{sos_id} acknowledged by: {ack_sos.json()['acknowledged_by']}")

    # Resolve SOS
    res_sos = client.post(f"/sos/{sos_id}/resolve", headers=f_headers)
    assert res_sos.status_code == 200
    print(f"   ✓ SOS #{sos_id} marked RESOLVED")

    # 10. Privacy Shielding on Family Requests (Phase 18 Verification)
    print("\n10. Testing Backend Privacy Shielding (Privacy Pause Active)...")
    cam_blocked = client.get("/cameras", headers=f_headers)
    assert cam_blocked.status_code == 403, f"Expected 403 for cameras during privacy pause, got {cam_blocked.status_code}"
    print(f"   ✓ CCTV stream request correctly rejected with 403: {cam_blocked.json()['detail']}")

    # Parent resumes sharing
    resume_res = client.post("/privacy/resume", headers=p_headers)
    assert resume_res.status_code == 200
    assert resume_res.json()["is_paused"] is False
    print("   ✓ Parent resumed normal privacy sharing")

    # 11. Ask EVER NEAR Natural Language Q&A
    print("\n11. Testing 'Ask EVER NEAR' Natural Language Q&A...")
    ask_res = client.post("/ai/ask", json={"question": "Did Amma check in today?"}, headers=f_headers)
    assert ask_res.status_code == 200
    print(f"   ✓ Question: '{ask_res.json()['question']}'")
    print(f"   ✓ Answer (EN): {ask_res.json()['answer']}")
    print(f"   ✓ Answer (TA): {ask_res.json()['answer_tamil']}")
    print(f"   ✓ Sources Used: {ask_res.json()['sources_used']}")

    # 12. Care Timeline & Audit Log Verification
    print("\n12. Verifying Care Timeline & Audit Trails...")
    timeline = client.get("/care/timeline", headers=f_headers)
    assert timeline.status_code == 200
    print(f"   ✓ Care Timeline items recorded: {len(timeline.json())}")

    audits = client.get("/audit-logs", headers=f_headers)
    assert audits.status_code == 200
    print(f"   ✓ Audit Log entries recorded: {len(audits.json())}")

    print("\n" + "=" * 65)
    print(">>> COMPLETE USER JOURNEY VERIFICATION PASSED 100%! <<<")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    test_full_user_journey()
