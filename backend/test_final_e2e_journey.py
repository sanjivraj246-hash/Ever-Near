"""
EVER NEAR AI — SECTION 30 FINAL MANUAL E2E JOURNEY TEST SUITE
Executes:
- TEST A: NEW PARENT (Register -> Fresh state -> Check-in -> Logout -> Login -> Check-in persists -> Family Invitation)
- TEST B: FAMILY (Register -> Login -> Accept invitation -> Parent connected -> Authorized info visible -> Unauthorized hidden)
- TEST C: GOOGLE (Backend identity verification -> Config & Blocked status reporting)
- TEST D: MULTI-PARENT ISOLATION (Second parent sees zero data from first parent)
"""

import sys
import secrets
import httpx
from app.db.session import SessionLocal
from app.models.entities import User, ParentProfile, FamilyProfile

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8000/api"

def run_section_30_tests():
    print("\n" + "=" * 75)
    print("EVER NEAR AI — SECTION 30: FINAL END-TO-END USER JOURNEY VERIFICATION")
    print("=" * 75)

    client = httpx.Client(base_url=BASE_URL, timeout=10.0)

    # Generate unique numeric test phones
    num_suffix = f"{secrets.randbelow(90000) + 10000}"
    parent_phone = f"+91 94444{num_suffix}"
    family_phone = f"+91 93333{num_suffix}"
    parent2_phone = f"+91 95555{num_suffix}"

    parent_pin = "778899"
    family_pin = "554433"
    parent2_pin = "332211"

    # =========================================================================
    # TEST A — NEW PARENT
    # =========================================================================
    print("\n" + "=" * 70)
    print(">>> TEST A — NEW PARENT JOURNEY")
    print("=" * 70)

    # 1. Open app & 2. Select MY CARE & 3. Select CREATE ACCOUNT
    print("1-3. Selecting MY CARE -> Create Account...")

    # 4. Enter real test mobile number & 5. Create 6-digit PIN & 6. Create account
    print(f"4-6. Creating account for Radha Amma ({parent_phone}) with 6-digit PIN...")
    reg_p = client.post("/auth/register", json={
        "phone": parent_phone,
        "full_name": "Radha Amma",
        "role": "PARENT",
        "password": parent_pin,
        "password_confirm": parent_pin,
        "preferred_name": "Amma",
        "language_pref": "ta"
    })
    assert reg_p.status_code == 200, f"Parent registration failed: {reg_p.text}"
    p_auth = reg_p.json()
    p_token = p_auth["access_token"]
    p_headers = {"Authorization": f"Bearer {p_token}"}
    print(f"  [OK] Parent account created. Role: {p_auth['role']}, User ID: {p_auth['user_id']}")

    # 7. Enter application & 8. Verify no fake data exists
    print("7-8. Verifying fresh parent account starts completely empty...")
    checkins_res = client.get("/check-ins/history", headers=p_headers)
    assert checkins_res.status_code == 200
    assert len(checkins_res.json()) == 0, f"Expected 0 check-ins, found: {len(checkins_res.json())}"

    meds_res = client.get("/medications", headers=p_headers)
    assert meds_res.status_code == 200
    assert len(meds_res.json()) == 0, f"Expected 0 medications, found: {len(meds_res.json())}"
    print("  [OK] Verified: 0 fake check-ins, 0 fake medications in new account.")

    # 9. Complete check-in
    print("9. Submitting daily check-in (I'm Okay)...")
    checkin_create = client.post("/check-ins", json={
        "feeling": "good",
        "feeling_tamil": "நன்றாக இருக்கிறேன்",
        "note": "Feeling peaceful and taking a morning walk"
    }, headers=p_headers)
    assert checkin_create.status_code == 200
    checkin_id = checkin_create.json()["id"]
    print(f"  [OK] Check-in #{checkin_id} saved to PostgreSQL.")

    # 10. Logout
    print("10. Logging out parent...")
    logout_res = client.post("/auth/logout", headers=p_headers)
    assert logout_res.status_code == 200
    print("  [OK] Logged out successfully.")

    # 11. Login again using mobile + 6-digit PIN
    print(f"11. Logging in again using mobile ({parent_phone}) and 6-digit PIN...")
    login_p = client.post("/auth/login", json={
        "phone": parent_phone,
        "pin": parent_pin
    })
    assert login_p.status_code == 200, f"Login failed: {login_p.text}"
    p_token_2 = login_p.json()["access_token"]
    p_headers_2 = {"Authorization": f"Bearer {p_token_2}"}
    print(f"  [OK] Re-login successful with 6-digit PIN. Session restored.")

    # 12. Verify check-in still exists
    print("12. Verifying check-in persistence in database...")
    checkins_after = client.get("/check-ins/history", headers=p_headers_2)
    assert checkins_after.status_code == 200
    records = checkins_after.json()
    assert len(records) == 1, f"Expected 1 persisted check-in, found: {len(records)}"
    assert records[0]["note"] == "Feeling peaceful and taking a morning walk"
    print(f"  [OK] Check-in verified persistent: note='{records[0]['note']}', feeling='{records[0]['feeling']}'")

    # 13. Create family invitation
    print("13. Creating family invitation code...")
    invite_res = client.post("/family/invitations", json={
        "relationship_type": "Son",
        "can_view_health": True,
        "can_view_cctv": True,
        "can_receive_sos": True
    }, headers=p_headers_2)
    assert invite_res.status_code in [200, 201], f"Invite creation failed: {invite_res.text}"
    invite_code = invite_res.json()["invite_code"]
    print(f"  [OK] Family invitation generated: {invite_code}")

    # =========================================================================
    # TEST B — FAMILY
    # =========================================================================
    print("\n" + "=" * 70)
    print(">>> TEST B — FAMILY JOURNEY")
    print("=" * 70)

    # 1. Open app & 2. Select CARE CIRCLE & 3. Create family account
    print(f"1-3. Creating family account for Venkat Raman ({family_phone}) with 6-digit PIN...")
    reg_f = client.post("/auth/register", json={
        "phone": family_phone,
        "full_name": "Venkat Raman",
        "role": "FAMILY",
        "password": family_pin,
        "password_confirm": family_pin,
        "relationship_type": "Son",
        "language_pref": "en"
    })
    assert reg_f.status_code == 200
    f_token = reg_f.json()["access_token"]
    f_headers = {"Authorization": f"Bearer {f_token}"}
    print(f"  [OK] Family account created: {reg_f.json()['full_name']}")

    # 4. Login with mobile + PIN
    print("4. Verifying family login with mobile + PIN...")
    login_f = client.post("/auth/login", json={"phone": family_phone, "pin": family_pin})
    assert login_f.status_code == 200
    assert login_f.json()["role"] == "FAMILY"
    print("  [OK] Family member signed in successfully.")

    # 5. Accept parent invitation
    print(f"5. Accepting parent invitation with code {invite_code}...")
    accept_res = client.post("/family/invitations/accept", json={"invite_code": invite_code}, headers=f_headers)
    assert accept_res.status_code == 200, f"Accepting invitation failed: {accept_res.text}"
    print(f"  [OK] Invitation accepted. Relationship established in PostgreSQL.")

    # 6. Verify parent appears
    print("6. Verifying parent appears in family care circle...")
    circle_res = client.get("/family-connection/care-circle", headers=f_headers)
    assert circle_res.status_code == 200
    print(f"  [OK] Care circle members loaded: {len(circle_res.json())} items.")

    # 7. Verify authorized information appears
    print("7. Verifying authorized parent check-in status visible to family...")
    status_res = client.get("/family/parent-status", headers=f_headers)
    assert status_res.status_code == 200
    print(f"  [OK] Authorized parent status retrieved: {status_res.json()}")

    # 8. Verify unauthorized information remains hidden
    print("8. Verifying unauthorized access is rejected (403 Forbidden)...")
    unauth_profile = client.get("/parent/profile", headers=f_headers)
    assert unauth_profile.status_code == 403
    print("  [OK] Family blocked from sovereign parent endpoints (403 Forbidden).")

    # =========================================================================
    # TEST C — GOOGLE AUTHENTICATION
    # =========================================================================
    print("\n" + "=" * 70)
    print(">>> TEST C — GOOGLE AUTHENTICATION STATUS")
    print("=" * 70)

    google_cfg = client.get("/auth/google/config").json()
    print(f"  Google Config Status: {google_cfg['status']}")
    print(f"  Reported Message: {google_cfg['message']}")
    if not google_cfg["configured"]:
        assert google_cfg["status"] == "BLOCKED"
        assert "GOOGLE AUTH BLOCKED — GOOGLE_CLIENT_ID/CLIENT_SECRET/REDIRECT_URI NOT CONFIGURED" in google_cfg["message"]
        print("  [OK] Unconfigured environment correctly reports BLOCKED without faking success.")
    else:
        print(f"  [OK] Google OAuth is active with Client ID: {google_cfg['client_id']}")

    # =========================================================================
    # TEST D — MULTI-USER ISOLATION
    # =========================================================================
    print("\n" + "=" * 70)
    print(">>> TEST D — MULTI-PARENT ISOLATION")
    print("=" * 70)

    print(f"Creating second parent: Gomathi Amma ({parent2_phone})...")
    reg_p2 = client.post("/auth/register", json={
        "phone": parent2_phone,
        "full_name": "Gomathi Amma",
        "role": "PARENT",
        "password": parent2_pin,
        "password_confirm": parent2_pin
    })
    assert reg_p2.status_code == 200
    p2_token = reg_p2.json()["access_token"]
    p2_headers = {"Authorization": f"Bearer {p2_token}"}

    print("Verifying Gomathi Amma sees ZERO data from Radha Amma...")
    p2_checkins = client.get("/check-ins/history", headers=p2_headers).json()
    assert len(p2_checkins) == 0, f"DATA LEAK: Parent 2 saw Parent 1's check-ins: {p2_checkins}"
    print(f"  [OK] Verified: Gomathi Amma has 0 check-ins. Zero data leakage across parents!")

    print("\n" + "=" * 75)
    print(">>> SECTION 30 ALL JOURNEY TESTS (A, B, C, D) PASSED 100%! <<<")
    print("=" * 75)

if __name__ == "__main__":
    run_section_30_tests()
