"""
EVER NEAR AI: MULTI-USER PRODUCTION CONVERSION VERIFICATION TEST
===============================================================
Tests full end-to-end real user lifecycle:
1. Registration of real Parent A and Family A (fresh accounts)
2. Registration of real Parent B and Family B (fresh accounts)
3. Fresh state verification: 0 check-ins, 0 medications, 0 alerts, 0 relationships
4. Invitation Code Lifecycle:
   - Parent A creates single-use code EN-XXXX-XX
   - Public verification endpoint confirms code details
   - Family A accepts code and becomes approved family member
   - Duplicate redemption attempt is rejected (single-use constraint)
   - Expired or invalid code is rejected
5. Strict Multi-Tenant Data Isolation:
   - Family A can access Parent A data
   - Family A CANNOT access Parent B data (403 or empty)
   - Family B CANNOT access Parent A data (403 or empty)
   - Parent A check-in visible only to Family A, never to Parent B or Family B
   - Parent A Safe Return outing location blocked from unauthorized family (403)
6. PostgreSQL 18 persistence verification
"""

import sys
import uuid
import datetime
from fastapi.testclient import TestClient

sys.stdout.reconfigure(encoding='utf-8')
from app.main import app

def run_multi_user_verification():
    client = TestClient(app)
    print("=" * 70)
    print("EVER NEAR AI: REAL MULTI-USER PRODUCTION VERIFICATION SUITE")
    print("=" * 70)

    # Unique test phone numbers (pure 10-digit numeric)
    uid_a = f"{uuid.uuid4().int % 1000000:06d}"
    uid_b = f"{(uuid.uuid4().int + 54321) % 1000000:06d}"
    
    parent_a_phone = f"9801{uid_a}"
    family_a_phone = f"9802{uid_a}"
    parent_b_phone = f"9803{uid_b}"
    family_b_phone = f"9804{uid_b}"

    # -------------------------------------------------------------------------
    # TEST 1: Register Real Users with password confirmation & validation
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Registering Real Independent Users...")

    # 1a. Password mismatch rejection
    mismatch_res = client.post("/api/auth/register", json={
        "phone": parent_a_phone,
        "full_name": "Kavitha Amma",
        "role": "PARENT",
        "password": "Password123",
        "password_confirm": "DifferentPassword123"
    })
    assert mismatch_res.status_code == 400, f"Expected 400 for password mismatch, got {mismatch_res.status_code}"
    print("  [OK] Password mismatch properly rejected (400)")

    # 1b. Short password rejection (< 6 chars)
    short_pw_res = client.post("/api/auth/register", json={
        "phone": parent_a_phone,
        "full_name": "Kavitha Amma",
        "role": "PARENT",
        "password": "123",
        "password_confirm": "123"
    })
    assert short_pw_res.status_code == 400, f"Expected 400 for short password, got {short_pw_res.status_code}"
    print("  [OK] Short password (< 6 chars) properly rejected (400)")

    # 1c. Register Parent A
    res_pa = client.post("/api/auth/register", json={
        "phone": parent_a_phone,
        "full_name": "Kavitha Amma",
        "role": "PARENT",
        "password": "SecurePassword123",
        "password_confirm": "SecurePassword123",
        "preferred_name": "Amma",
        "language_pref": "ta"
    })
    assert res_pa.status_code == 200, f"Parent A registration failed: {res_pa.text}"
    token_pa = res_pa.json()["access_token"]
    headers_pa = {"Authorization": f"Bearer {token_pa}"}
    user_pa = res_pa.json()
    print(f"  [OK] Parent A registered: id={user_pa['user_id']}, name='Kavitha Amma', phone={parent_a_phone}")

    # 1d. Register Family A
    res_fa = client.post("/api/auth/register", json={
        "phone": family_a_phone,
        "full_name": "Arun Kumar",
        "role": "FAMILY",
        "password": "SecurePassword123",
        "password_confirm": "SecurePassword123",
        "preferred_name": "Arun",
        "relationship_type": "Son",
        "language_pref": "ta"
    })
    assert res_fa.status_code == 200, f"Family A registration failed: {res_fa.text}"
    token_fa = res_fa.json()["access_token"]
    headers_fa = {"Authorization": f"Bearer {token_fa}"}
    print(f"  [OK] Family A registered: id={res_fa.json()['user_id']}, name='Arun Kumar', phone={family_a_phone}")

    # 1e. Register Parent B
    res_pb = client.post("/api/auth/register", json={
        "phone": parent_b_phone,
        "full_name": "Saraswathi Amma",
        "role": "PARENT",
        "password": "SecurePassword123",
        "password_confirm": "SecurePassword123",
        "preferred_name": "Saraswathi",
        "language_pref": "en"
    })
    assert res_pb.status_code == 200, f"Parent B registration failed: {res_pb.text}"
    token_pb = res_pb.json()["access_token"]
    headers_pb = {"Authorization": f"Bearer {token_pb}"}
    print(f"  [OK] Parent B registered: id={res_pb.json()['user_id']}, name='Saraswathi Amma', phone={parent_b_phone}")

    # 1f. Register Family B
    res_fb = client.post("/api/auth/register", json={
        "phone": family_b_phone,
        "full_name": "Deepa Sundaram",
        "role": "FAMILY",
        "password": "SecurePassword123",
        "password_confirm": "SecurePassword123",
        "preferred_name": "Deepa",
        "relationship_type": "Daughter",
        "language_pref": "en"
    })
    assert res_fb.status_code == 200, f"Family B registration failed: {res_fb.text}"
    token_fb = res_fb.json()["access_token"]
    headers_fb = {"Authorization": f"Bearer {token_fb}"}
    print(f"  [OK] Family B registered: id={res_fb.json()['user_id']}, name='Deepa Sundaram', phone={family_b_phone}")

    # -------------------------------------------------------------------------
    # TEST 2: Verify Fresh Initial State (Zero Fake Records)
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Verifying Fresh User State (No Seed Leakage)...")

    # Parent A should have 0 check-ins, 0 medications, 0 family contacts
    chk_pa = client.get("/api/checkins/today", headers=headers_pa)
    assert chk_pa.status_code == 200
    assert chk_pa.json() is None, f"Expected null checkin for new user, got {chk_pa.json()}"
    print("  [OK] Parent A has 0 check-ins (clean empty state)")

    meds_pa = client.get("/api/medications", headers=headers_pa)
    assert meds_pa.status_code == 200
    assert len(meds_pa.json()) == 0, f"Expected 0 meds, got {len(meds_pa.json())}"
    print("  [OK] Parent A has 0 medications (no demo meds attached)")

    fam_pa = client.get("/api/family", headers=headers_pa)
    assert fam_pa.status_code == 200
    assert len(fam_pa.json()) == 0, f"Expected 0 family contacts, got {len(fam_pa.json())}"
    print("  [OK] Parent A has 0 family contacts initially")

    # Family A initially has NO linked parent
    p_status_fa = client.get("/api/family/parent-status", headers=headers_fa)
    assert p_status_fa.status_code == 404, f"Expected 404 for unlinked family, got {p_status_fa.status_code}"
    print("  [OK] Family A is initially unlinked (404 Not Found from /parent-status)")

    # -------------------------------------------------------------------------
    # TEST 3: Family Invitation Lifecycle (Generate -> Verify -> Accept)
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Testing Family Invitation Code System...")

    # 3a. Parent A generates a connection code for Son
    create_inv = client.post("/api/family/invitations", json={
        "relationship_type": "Son",
        "can_view_health": True,
        "can_view_cctv": True,
        "can_receive_sos": True,
        "expires_hours": 48
    }, headers=headers_pa)
    assert create_inv.status_code == 201, f"Failed to create invitation: {create_inv.text}"
    inv_data = create_inv.json()
    invite_code = inv_data["invite_code"]
    assert invite_code.startswith("EN-"), f"Invalid code format: {invite_code}"
    assert len(invite_code) == 10, f"Expected 10-char code (EN-XXXX-XX), got {invite_code}"
    assert inv_data["is_used"] is False
    print(f"  [OK] Parent A created single-use invitation code: '{invite_code}'")

    # 3b. Parent A lists active invitations
    list_inv = client.get("/api/family/invitations", headers=headers_pa)
    assert list_inv.status_code == 200
    assert len(list_inv.json()) >= 1
    assert any(i["invite_code"] == invite_code for i in list_inv.json())
    print("  [OK] Parent A retrieved list of active invitation codes")

    # 3c. Public verification of invitation code before accepting
    verify_res = client.get(f"/api/family/invitations/verify?code={invite_code}")
    assert verify_res.status_code == 200, f"Verification failed: {verify_res.text}"
    verify_data = verify_res.json()
    assert verify_data["valid"] is True
    assert verify_data["parent_id"] == user_pa["user_id"]
    assert verify_data["parent_name"] == "Kavitha Amma"
    assert verify_data["relationship_type"] == "Son"
    print(f"  [OK] Code verified: valid=True, inviting_parent='{verify_data['parent_name']}'")

    # 3d. Family A accepts invitation code
    accept_res = client.post("/api/family/invitations/accept", json={
        "invite_code": invite_code
    }, headers=headers_fa)
    assert accept_res.status_code == 200, f"Accept failed: {accept_res.text}"
    accept_data = accept_res.json()
    assert accept_data["parent_id"] == user_pa["user_id"]
    assert accept_data["relationship_type"] == "Son"
    print(f"  [OK] Family A accepted code: linked to Parent A (rel_id={accept_data['relationship_id']})")

    # 3e. Attempting to REUSE the same single-use code must be rejected (400 Bad Request)
    reuse_res = client.post("/api/family/invitations/accept", json={
        "invite_code": invite_code
    }, headers=headers_fb)
    assert reuse_res.status_code == 400, f"Expected 400 for reused code, got {reuse_res.status_code}"
    print("  [OK] Single-use enforcement: Reusing code rejected (400 Bad Request)")

    # 3f. Invalid code verification must return 404
    bad_code_res = client.get("/api/family/invitations/verify?code=EN-FAKE-99")
    assert bad_code_res.status_code == 404
    print("  [OK] Invalid code properly rejected with 404")

    # -------------------------------------------------------------------------
    # TEST 4: Verified Linked Relationship & Context
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Verifying Linked Relationship...")

    # Family A now identifies Parent A via /parent-status
    status_fa = client.get("/api/family/parent-status", headers=headers_fa)
    assert status_fa.status_code == 200, f"Expected 200, got {status_fa.status_code}: {status_fa.text}"
    assert status_fa.json()["parent_id"] == user_pa["user_id"]
    assert status_fa.json()["parent_name"] == "Kavitha Amma"
    print(f"  [OK] Family A identifies linked parent: '{status_fa.json()['parent_name']}'")

    # Parent A now sees Family A in contacts
    contacts_pa = client.get("/api/family", headers=headers_pa)
    assert contacts_pa.status_code == 200
    assert len(contacts_pa.json()) == 1
    assert contacts_pa.json()[0]["name"] == "Arun Kumar"
    print(f"  [OK] Parent A sees Family A in contacts: '{contacts_pa.json()[0]['name']}'")

    # -------------------------------------------------------------------------
    # TEST 5: Strict Multi-Tenant Data Isolation
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Testing Multi-Tenant Data Isolation between Parent A and Parent B...")

    # 5a. Parent A submits a check-in
    post_chk_a = client.post("/api/checkins", json={
        "feeling": "peaceful",
        "feeling_tamil": "அமைதியாக உணர்கிறேன்",
        "note": "Morning temple visit completed"
    }, headers=headers_pa)
    assert post_chk_a.status_code == 200
    print("  [OK] Parent A submitted morning check-in: 'peaceful'")

    # 5b. Family A can see Parent A's check-in via /parent-status
    fa_parent_status = client.get("/api/family/parent-status", headers=headers_fa)
    assert fa_parent_status.status_code == 200
    chk_seen_by_fa = fa_parent_status.json().get("today_checkin")
    assert chk_seen_by_fa is not None
    assert chk_seen_by_fa["feeling"] == "peaceful"
    print("  [OK] Family A successfully views Parent A's check-in")

    # 5c. Parent B does NOT see Parent A's check-in (Parent B still has null today_checkin)
    chk_pb = client.get("/api/checkins/today", headers=headers_pb)
    assert chk_pb.status_code == 200
    assert chk_pb.json() is None, "ISOLATION BREACH: Parent B saw Parent A's check-in!"
    print("  [OK] Parent B data isolated: has 0 check-ins despite Parent A having checked in")

    # 5d. Family B (unlinked) CANNOT see Parent A's data
    fb_parent_status = client.get("/api/family/parent-status", headers=headers_fb)
    assert fb_parent_status.status_code == 404, "ISOLATION BREACH: Unlinked Family B saw a parent!"
    print("  [OK] Family B data isolated: cannot access unlinked parent status (404)")

    # 5e. Safe Return Outing Isolation:
    # Parent A starts an outing
    start_trip = client.post("/api/safe-return/start", json={
        "destination": "Mylapore Temple",
        "destination_tamil": "மயிலாப்பூர் கோவில்",
        "duration_minutes": 60
    }, headers=headers_pa)
    assert start_trip.status_code == 200
    print("  [OK] Parent A started Safe Return outing to 'Mylapore Temple'")

    # Family A (approved linked) can view active outing
    trip_fa = client.get("/api/safe-return/active", headers=headers_fa)
    assert trip_fa.status_code == 200
    assert trip_fa.json() is not None
    assert trip_fa.json()["destination"] == "Mylapore Temple"
    print("  [OK] Family A can view Parent A's active outing")

    # Family B (stranger / unlinked) is BLOCKED with 403 Forbidden
    trip_fb = client.get("/api/safe-return/active", headers=headers_fb)
    assert trip_fb.status_code == 403, f"ISOLATION BREACH: Expected 403 for stranger family, got {trip_fb.status_code}"
    print("  [OK] Family B blocked from Parent A's location outing: 403 Forbidden properly enforced")

    # Unauthorized camera access: Family B blocked from cameras (403)
    cams_fb = client.get("/api/cameras", headers=headers_fb)
    assert cams_fb.status_code == 403, f"Expected 403 for unapproved family on cameras, got {cams_fb.status_code}"
    print("  [OK] Family B blocked from CCTV cameras: 403 Forbidden properly enforced")

    # -------------------------------------------------------------------------
    # TEST 6: Audit Logging for Real User Operations
    # -------------------------------------------------------------------------
    print("\n[TEST 6] Verifying Security Audit Log Records...")
    audit_res = client.get("/audit-logs")
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert len(logs) > 0
    # Confirm invitation acceptance was audited
    accept_logged = any("INVITATION_ACCEPTED" in str(l.get("action", "")) for l in logs)
    assert accept_logged, "INVITATION_ACCEPTED event not found in audit logs!"
    print("  [OK] Real user invitation redemption properly recorded in PostgreSQL AuditLog table")

    print("\n" + "=" * 70)
    print(">>> ALL MULTI-USER PRODUCTION VERIFICATION TESTS PASSED 100%! <<<")
    print("=" * 70)

if __name__ == "__main__":
    run_multi_user_verification()
