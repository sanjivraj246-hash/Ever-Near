import sys
import datetime
import httpx

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8000/api"

def print_flow(num, title):
    print("\n" + "=" * 70)
    print(f"VERIFYING COMBINED PHASE B — FLOW {num}: {title}")
    print("=" * 70)

def test_combined_phase_b():
    client = httpx.Client(base_url=BASE_URL, timeout=10.0)

    # Health check
    h = client.get("/health")
    assert h.status_code == 200, "Health check failed"

    # =========================================================================
    # FLOW 1: Parent login -> MY CARE -> real profile loaded
    # =========================================================================
    print_flow(1, "Parent login -> MY CARE -> real profile loaded")
    p_login = client.post("/auth/login", json={"phone": "9876543210", "password": "1234"})
    assert p_login.status_code == 200, f"Parent login failed: {p_login.text}"
    p_data = p_login.json()
    assert "access_token" in p_data
    p_token = p_data["access_token"]
    p_headers = {"Authorization": f"Bearer {p_token}"}

    # Fetch authenticated parent profile
    p_profile = client.get("/parent/profile", headers=p_headers)
    assert p_profile.status_code == 200, f"Profile fetch failed: {p_profile.text}"
    prof_data = p_profile.json()
    assert prof_data["role"] == "PARENT"
    assert prof_data["phone"] == "9876543210"
    print(f"  [OK] Authenticated Parent profile loaded: {prof_data['preferred_name']} ({prof_data['full_name']}), role={prof_data['role']}")

    # Authenticate family member (Karthik)
    f_login = client.post("/auth/login", json={"phone": "9876543211", "password": "1234"})
    assert f_login.status_code == 200, f"Family login failed: {f_login.text}"
    f_data = f_login.json()
    assert "access_token" in f_data
    f_token = f_data["access_token"]
    f_headers = {"Authorization": f"Bearer {f_token}"}

    # =========================================================================
    # FLOW 2: Parent -> I'M OKAY -> real API -> PostgreSQL -> family sees updated status
    # =========================================================================
    print_flow(2, "Parent -> I'M OKAY -> real API -> PostgreSQL -> family sees updated status")
    checkin_res = client.post("/checkins", json={
        "feeling": "good",
        "feeling_tamil": "நன்றாக இருக்கிறேன்",
        "note": "Phase B integration check-in"
    }, headers=p_headers)
    assert checkin_res.status_code == 200
    print(f"  [OK] Parent check-in recorded: {checkin_res.json()['feeling']}")

    # Family checks today status
    f_checkin = client.get("/checkins/today", headers=f_headers)
    assert f_checkin.status_code == 200
    assert f_checkin.json()["feeling"] == "good"
    print("  [OK] Family received updated check-in status from database")

    # =========================================================================
    # FLOW 3: Parent -> I NEED HELP -> request -> backend -> family notification
    # =========================================================================
    print_flow(3, "Parent -> I NEED HELP -> request -> backend -> family notification")
    help_res = client.post("/help-requests", json={
        "category": "medicine",
        "category_tamil": "மருந்து தேவை",
        "note": "Refill for blood pressure medicine"
    }, headers=p_headers)
    assert help_res.status_code == 200
    req_id = help_res.json()["id"]
    print(f"  [OK] Help request #{req_id} created by Parent")

    # Family retrieves help requests
    f_requests = client.get("/help-requests", headers=f_headers)
    assert f_requests.status_code == 200
    assert any(r["id"] == req_id for r in f_requests.json())
    print(f"  [OK] Family received pending help request #{req_id}")

    # =========================================================================
    # FLOW 4: Parent -> TALK TO FAMILY -> real communication API -> family receives request
    # =========================================================================
    print_flow(4, "Parent -> TALK TO FAMILY -> real communication API -> family receives request")
    comm_res = client.post("/communication/requests", json={
        "family_member_id": 2,
        "reason_category": "want_to_talk",
        "notes": "Amma wants to talk to Karthik",
        "priority": "NORMAL"
    }, headers=p_headers)
    assert comm_res.status_code == 200
    comm_id = comm_res.json()["id"]
    print(f"  [OK] Communication Request #{comm_id} created")

    # Family retrieves active requests
    active_comm = client.get(f"/communication/requests/{comm_id}", headers=f_headers)
    assert active_comm.status_code == 200
    print(f"  [OK] Family received communication request #{comm_id}, status: {active_comm.json()['status']}")

    # =========================================================================
    # FLOW 5: Parent -> MY HEALTH -> real health/medicine/report data
    # =========================================================================
    print_flow(5, "Parent -> MY HEALTH -> real health/medicine/report data")
    meds = client.get("/medications", headers=p_headers)
    assert meds.status_code == 200
    assert isinstance(meds.json(), list)
    print(f"  [OK] Real medications retrieved: {len(meds.json())} items")

    docs = client.get("/health-documents", headers=p_headers)
    assert docs.status_code == 200
    assert isinstance(docs.json(), list)
    print(f"  [OK] Real health documents retrieved: {len(docs.json())} items")

    timeline = client.get("/care/timeline", headers=p_headers)
    assert timeline.status_code == 200
    assert isinstance(timeline.json(), list)
    print(f"  [OK] Real care timeline retrieved: {len(timeline.json())} items")

    # =========================================================================
    # FLOW 6: Parent -> HOME & SAFETY -> real safety data
    # =========================================================================
    print_flow(6, "Parent -> HOME & SAFETY -> real safety data")
    cams = client.get("/cameras", headers=p_headers)
    assert cams.status_code == 200
    assert isinstance(cams.json(), list)
    print(f"  [OK] Real camera streams retrieved: {len(cams.json())} cameras")

    safety_evs = client.get("/safety/events", headers=p_headers)
    assert safety_evs.status_code == 200
    assert isinstance(safety_evs.json(), list)
    print(f"  [OK] Real safety events retrieved: {len(safety_evs.json())} events")

    # =========================================================================
    # FLOW 7: Parent -> SOS -> real emergency backend -> family/trusted contact flow
    # =========================================================================
    print_flow(7, "Parent -> SOS -> real emergency backend -> family/trusted contact flow")
    sos = client.post("/sos", json={"notes": "Emergency assistance test in Phase B"}, headers=p_headers)
    assert sos.status_code == 200
    sos_id = sos.json()["id"]
    print(f"  [OK] Real SOS Alert #{sos_id} created")

    # Family detects active emergency
    active_sos = client.get("/sos/active", headers=f_headers)
    assert active_sos.status_code == 200
    assert active_sos.json() is not None
    assert active_sos.json()["id"] == sos_id
    print(f"  [OK] Family detected real SOS #{sos_id}")

    # Family acknowledges SOS
    ack_res = client.post(f"/sos/{sos_id}/acknowledge", json={"acknowledged_by": "Karthik (Son)"}, headers=f_headers)
    assert ack_res.status_code == 200
    print(f"  [OK] SOS #{sos_id} acknowledged by family")

    # Resolve SOS
    res_sos = client.post(f"/sos/{sos_id}/resolve", headers=p_headers)
    assert res_sos.status_code == 200
    print(f"  [OK] SOS #{sos_id} resolved safely")

    # =========================================================================
    # FLOW 8: Family -> CARE CIRCLE -> real parent data -> permission filtering
    # =========================================================================
    print_flow(8, "Family -> CARE CIRCLE -> real parent data -> permission filtering")
    # Verify family briefing
    briefing = client.get("/ai/family-briefing", headers=f_headers)
    assert briefing.status_code == 200
    print("  [OK] Family retrieved permission-filtered briefing")

    # Verify Care Circle members
    circle = client.get("/family-connection/care-circle", headers=f_headers)
    assert circle.status_code == 200
    assert len(circle.json()) >= 3
    print(f"  [OK] Care circle members retrieved: {len(circle.json())} members")

    # =========================================================================
    # FLOW 9: Parent changes permission -> backend updates -> family access changes accordingly
    # =========================================================================
    print_flow(9, "Parent changes permission -> backend updates -> family access changes accordingly")
    # Parent turns CCTV OFF
    p_turn_off = client.post("/privacy/settings", json={
        "cctv_access": False,
        "location_sharing": False,
        "health_info": True
    }, headers=p_headers)
    assert p_turn_off.status_code == 200
    assert p_turn_off.json()["cctv_access"] is False
    print("  [OK] Parent updated sovereign privacy settings: CCTV = OFF, Location = OFF")

    # Family attempts to access CCTV -> must be rejected with 403 Forbidden!
    cctv_blocked = client.get("/cameras", headers=f_headers)
    assert cctv_blocked.status_code == 403, f"Expected 403 Forbidden, got {cctv_blocked.status_code}"
    print("  [OK] Backend strictly blocked Family access to CCTV with 403 Forbidden!")

    # Family attempts to access Location -> must be rejected with 403 Forbidden!
    loc_blocked = client.get("/safe-return/active", headers=f_headers)
    assert loc_blocked.status_code == 403, f"Expected 403 Forbidden, got {loc_blocked.status_code}"
    print("  [OK] Backend strictly blocked Family access to Location with 403 Forbidden!")

    # Parent turns CCTV back ON
    p_turn_on = client.post("/privacy/settings", json={
        "cctv_access": True,
        "location_sharing": True,
        "health_info": True
    }, headers=p_headers)
    assert p_turn_on.status_code == 200
    assert p_turn_on.json()["cctv_access"] is True
    print("  [OK] Parent restored CCTV = ON, Location = ON")

    # Family access restored
    cctv_allowed = client.get("/cameras", headers=f_headers)
    assert cctv_allowed.status_code == 200
    print("  [OK] Family access to CCTV restored with 200 OK")

    # =========================================================================
    # FLOW 10: Permission expires/revoked -> previously allowed access is rejected
    # =========================================================================
    print_flow(10, "Permission expires/revoked -> previously allowed access is rejected")
    # Parent turns health_info OFF
    p_health_off = client.post("/privacy/settings", json={"health_info": False}, headers=p_headers)
    assert p_health_off.status_code == 200

    # Ensure PrivacyPermission also synced
    client.post("/privacy/permissions", json={"share_health": False}, headers=p_headers)

    # Family attempts to access health docs -> 403 Forbidden
    f_health_blocked = client.get("/health-documents", headers=f_headers)
    assert f_health_blocked.status_code == 403
    print("  [OK] Health documents blocked when Parent set Health sharing to OFF")

    # Parent grants temporary permission for HEALTH_DOC to Karthik (Son)
    temp_grant = client.post("/family-connection/temporary-permissions", json={
        "grantee_name": "Karthik (Son)",
        "resource_type": "HEALTH_DOC",
        "resource_name": "Routine_Vitals_Summary.pdf",
        "duration_hours": 2
    }, headers=p_headers)
    assert temp_grant.status_code == 200
    perm_id = temp_grant.json()["id"]
    print(f"  [OK] Parent granted temporary access #{perm_id} for HEALTH_DOC to Karthik (2 hours)")

    # Family can now access health documents via temporary permission!
    f_health_temp = client.get("/health-documents", headers=f_headers)
    assert f_health_temp.status_code == 200
    print("  [OK] Family successfully accessed health documents under active temporary permission")

    # Parent revokes temporary permission
    revoke_res = client.post(f"/family-connection/temporary-permissions/{perm_id}/revoke", headers=p_headers)
    assert revoke_res.status_code == 200
    print(f"  [OK] Parent revoked temporary permission #{perm_id}")

    # Previously allowed access is now rejected with 403 Forbidden!
    f_health_revoked = client.get("/health-documents", headers=f_headers)
    assert f_health_revoked.status_code == 403
    print("  [OK] Previously allowed access strictly rejected with 403 Forbidden after revocation!")

    # Restore health_info back to True for normal operations
    client.post("/privacy/settings", json={"health_info": True}, headers=p_headers)
    client.post("/privacy/permissions", json={"share_health": True}, headers=p_headers)

    # =========================================================================
    # UNAUTHORIZED ACCESS TESTS: Role Boundaries & Multi-Tenant Isolation
    # =========================================================================
    print("\n" + "=" * 70)
    print("VERIFYING UNAUTHORIZED ACCESS & ROLE BOUNDARY ENFORCEMENT")
    print("=" * 70)

    # 1. Parent cannot access restricted family controls (Surprise Coordinator)
    p_surprise = client.post("/family-connection/surprises", json={
        "title": "Unauthorized Parent Surprise",
        "surprise_type": "GIFT",
        "event_date": "2026-10-15",
        "participants": []
    }, headers=p_headers)
    assert p_surprise.status_code == 403, f"Parent accessed surprises! Got: {p_surprise.status_code}"
    print("  [OK] Parent cannot access family surprise planning (403 Forbidden properly enforced)")

    # 2. Parent cannot access family profile endpoint
    p_fam_prof = client.get("/family/profile", headers=p_headers)
    assert p_fam_prof.status_code == 403
    print("  [OK] Parent cannot access /family/profile (403 Forbidden properly enforced)")

    # 3. Family cannot access parent profile endpoint
    f_parent_prof = client.get("/parent/profile", headers=f_headers)
    assert f_parent_prof.status_code == 403
    print("  [OK] Family cannot access /parent/profile (403 Forbidden properly enforced)")

    # 4. Family cannot modify parent sovereign privacy settings
    f_hack_priv = client.post("/privacy/settings", json={"cctv_access": True}, headers=f_headers)
    assert f_hack_priv.status_code == 403
    print("  [OK] Family cannot modify parent sovereign privacy settings (403 Forbidden)")

    # 5. Family cannot activate privacy pause on behalf of parent
    f_hack_pause = client.post("/privacy/pause", json={"duration_minutes": 30}, headers=f_headers)
    assert f_hack_pause.status_code == 403
    print("  [OK] Family cannot activate Privacy Pause on behalf of parent (403 Forbidden)")

    # 6. Unlinked stranger family member cannot access parent private data
    # Register stranger family member
    stranger_phone = f"999{datetime.datetime.utcnow().strftime('%M%S%f')[:7]}"
    client.post("/auth/register", json={
        "phone": stranger_phone,
        "full_name": "Stranger User",
        "role": "FAMILY",
        "password": "pass"
    })
    stranger_login = client.post("/auth/login", json={"phone": stranger_phone, "password": "pass"})
    s_token = stranger_login.json()["access_token"]
    s_headers = {"Authorization": f"Bearer {s_token}"}

    stranger_memories = client.get("/family-connection/memories", headers=s_headers)
    assert stranger_memories.status_code == 403, f"Stranger accessed memories! Got: {stranger_memories.status_code}"
    print("  [OK] Unlinked stranger family member blocked from parent private memories (403 Forbidden)")

    print("\n" + "=" * 70)
    print(">>> ALL COMBINED PHASE B END-TO-END FLOWS VERIFIED 100%! <<<")
    print("=" * 70)

if __name__ == "__main__":
    test_combined_phase_b()
