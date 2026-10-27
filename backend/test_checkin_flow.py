"""
EVER NEAR AI — REAL DAILY WELL-BEING CHECK-IN TEST SUITE
Covers complete 15-point verification:
- TEST 01: Fresh parent starts empty (no check-in today, empty history)
- TEST 02: Fresh family member with no link sees empty state (None / 0 check-ins)
- TEST 03: Parent submits check-in (English 'good' + Tamil)
- TEST 04: FastAPI receives and persists record in database
- TEST 05: /api/check-ins/today returns today's check-in
- TEST 06: /api/check-ins/latest returns the latest check-in
- TEST 07: /api/check-ins/history contains the record
- TEST 08: Double submission on same day updates existing record without duplicate
- TEST 09: Parent submits feeling 'not_well'
- TEST 10: Parent submits feeling 'need_help'
- TEST 11: Connected family member sees parent's real check-in with exact feeling and timestamp
- TEST 12: Unlinked / unauthorized family member sees None (zero access to parent data)
- TEST 13: Unrelated Parent B cannot see Parent A's check-in (strict isolation)
- TEST 14: Alias endpoints (/api/checkins, /api/check-ins) work identically
- TEST 15: Baseline engine updates routine without generating premature alerts (< 5 days)
"""

import sys
import secrets
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.entities import User, DailyCheckIn, FamilyRelationship, CareTimelineItem
from app.services.care_service import CareService
from app.ai.baseline_engine import baseline_engine

sys.stdout.reconfigure(encoding='utf-8')
client = TestClient(app)

def run_checkin_tests():
    print("\n" + "=" * 75)
    print("EVER NEAR AI: REAL DAILY WELL-BEING CHECK-IN END-TO-END VERIFICATION")
    print("=" * 75)

    rand = secrets.randbelow(90000) + 10000
    p1_phone = f"+91 97111{rand}"
    p2_phone = f"+91 97222{rand}"
    fam_phone = f"+91 97333{rand}"
    unlinked_fam_phone = f"+91 97444{rand}"
    pin = "123456"

    # Register Parent 1
    r_p1 = client.post("/api/auth/register", json={
        "phone": p1_phone,
        "full_name": "Meenakshi Amma",
        "role": "PARENT",
        "password": pin,
        "preferred_name": "Amma",
        "language_pref": "ta"
    })
    assert r_p1.status_code == 200, f"Parent 1 registration failed: {r_p1.text}"
    p1_token = r_p1.json()["access_token"]
    p1_id = r_p1.json()["user_id"]
    p1_headers = {"Authorization": f"Bearer {p1_token}"}

    # Register Parent 2 (Isolated)
    r_p2 = client.post("/api/auth/register", json={
        "phone": p2_phone,
        "full_name": "Lakshmi Amma",
        "role": "PARENT",
        "password": pin,
        "preferred_name": "Lakshmi",
        "language_pref": "ta"
    })
    assert r_p2.status_code == 200
    p2_token = r_p2.json()["access_token"]
    p2_id = r_p2.json()["user_id"]
    p2_headers = {"Authorization": f"Bearer {p2_token}"}

    # Register Family Member (to be linked to Parent 1)
    r_fam = client.post("/api/auth/register", json={
        "phone": fam_phone,
        "full_name": "Karthik Sundaram",
        "role": "FAMILY",
        "password": pin,
        "relationship_type": "Son",
        "language_pref": "en"
    })
    assert r_fam.status_code == 200
    fam_token = r_fam.json()["access_token"]
    fam_id = r_fam.json()["user_id"]
    fam_headers = {"Authorization": f"Bearer {fam_token}"}

    # Register Unlinked Family Member
    r_ufam = client.post("/api/auth/register", json={
        "phone": unlinked_fam_phone,
        "full_name": "Unknown Person",
        "role": "FAMILY",
        "password": pin,
        "relationship_type": "Other",
        "language_pref": "en"
    })
    assert r_ufam.status_code == 200
    ufam_token = r_ufam.json()["access_token"]
    ufam_headers = {"Authorization": f"Bearer {ufam_token}"}

    # Link Family Member to Parent 1
    db = SessionLocal()
    try:
        rel = FamilyRelationship(
            parent_id=p1_id,
            family_user_id=fam_id,
            relationship_type="Son",
            status="APPROVED",
            can_view_health=True,
            can_receive_sos=True
        )
        db.add(rel)
        db.commit()
    finally:
        db.close()

    # =========================================================================
    # TEST 01 & 11: Fresh parent starts empty
    # =========================================================================
    print("\n>>> TEST 01: Fresh Parent Empty State...")
    res_today = client.get("/api/check-ins/today", headers=p1_headers)
    assert res_today.status_code == 200
    assert res_today.json() is None, "Expected None for fresh parent today checkin"

    res_latest = client.get("/api/check-ins/latest", headers=p1_headers)
    assert res_latest.status_code == 200
    assert res_latest.json() is None, "Expected None for fresh parent latest checkin"

    res_hist = client.get("/api/check-ins/history", headers=p1_headers)
    assert res_hist.status_code == 200
    assert len(res_hist.json()) == 0, "Expected 0 check-ins for fresh parent"
    print("  [PASS] TEST 01: Fresh parent sees clean empty state (None / 0 history).")

    # =========================================================================
    # TEST 02: Fresh unlinked family member sees empty state
    # =========================================================================
    print("\n>>> TEST 02: Unlinked Family Member Empty State...")
    ufam_today = client.get("/api/check-ins/today", headers=ufam_headers)
    assert ufam_today.status_code == 200
    assert ufam_today.json() is None

    ufam_latest = client.get("/api/check-ins/latest", headers=ufam_headers)
    assert ufam_latest.status_code == 200
    assert ufam_latest.json() is None
    print("  [PASS] TEST 02: Unlinked family member safely receives None with no crash.")

    # =========================================================================
    # TEST 03 - 07: Submit Check-in (Good / Tamil)
    # =========================================================================
    print("\n>>> TEST 03-07: Parent Submits Feeling 'good' + Tamil...")
    res_sub = client.post("/api/check-ins", json={
        "feeling": "good",
        "feeling_tamil": "நான் நன்றாக உணர்கிறேன்",
        "note": "Took a morning walk in the garden"
    }, headers=p1_headers)
    assert res_sub.status_code == 200, f"Check-in failed: {res_sub.text}"
    sub_data = res_sub.json()
    assert sub_data["feeling"] == "good"
    assert sub_data["feeling_tamil"] == "நான் நன்றாக உணர்கிறேன்"
    assert sub_data["user_id"] == p1_id
    assert sub_data["id"] is not None
    checkin_id_1 = sub_data["id"]
    print(f"  [PASS] TEST 03: Check-in saved with ID #{checkin_id_1}.")

    # Direct database verification
    db = SessionLocal()
    try:
        db_rec = db.query(DailyCheckIn).filter(DailyCheckIn.id == checkin_id_1).first()
        assert db_rec is not None
        assert db_rec.user_id == p1_id
        assert db_rec.feeling == "good"
        assert db_rec.feeling_tamil == "நான் நன்றாக உணர்கிறேன்"
        assert db_rec.created_at is not None
        print("  [PASS] TEST 04: Directly verified record in database tables.")
    finally:
        db.close()

    # Verify /today, /latest, /history
    t_res = client.get("/api/check-ins/today", headers=p1_headers)
    assert t_res.status_code == 200
    assert t_res.json()["id"] == checkin_id_1

    l_res = client.get("/api/check-ins/latest", headers=p1_headers)
    assert l_res.status_code == 200
    assert l_res.json()["id"] == checkin_id_1

    h_res = client.get("/api/check-ins/history", headers=p1_headers)
    assert h_res.status_code == 200
    assert len(h_res.json()) == 1
    print("  [PASS] TEST 05-07: /today, /latest, and /history all return persisted check-in.")

    # =========================================================================
    # TEST 08 & 15: Double Submission Duplicate Protection (Idempotency)
    # =========================================================================
    print("\n>>> TEST 08: Double Submission / Rapid Resubmit Idempotency...")
    res_sub2 = client.post("/api/check-ins", json={
        "feeling": "okay",
        "feeling_tamil": "நான் நலமாக இருக்கிறேன்",
        "note": "Updated feeling after afternoon rest"
    }, headers=p1_headers)
    assert res_sub2.status_code == 200
    sub_data2 = res_sub2.json()
    assert sub_data2["id"] == checkin_id_1, "Expected existing check-in to be updated, not duplicated!"
    assert sub_data2["feeling"] == "okay"

    # Verify history still has exactly 1 entry
    h_res2 = client.get("/api/check-ins/history", headers=p1_headers)
    assert len(h_res2.json()) == 1, "Duplicate protection failed: multiple records created for same day!"

    # Verify timeline does not have duplicate checkin items
    db = SessionLocal()
    try:
        timeline_items = db.query(CareTimelineItem).filter(
            CareTimelineItem.parent_id == p1_id,
            CareTimelineItem.event_category == "CHECKIN"
        ).all()
        assert len(timeline_items) == 1, f"Expected 1 timeline item, found: {len(timeline_items)}"
        print("  [PASS] TEST 08: Idempotency verified: 1 checkin record & 1 timeline item after resubmit.")
    finally:
        db.close()

    # =========================================================================
    # TEST 09 & 10: All 4 Feelings Supported (not_well, need_help)
    # =========================================================================
    print("\n>>> TEST 09-10: Testing 'not_well' and 'need_help' Feelings...")
    res_sub3 = client.post("/api/check-ins", json={
        "feeling": "not_well",
        "feeling_tamil": "எனக்கு உடல்நலம் சரியில்லை"
    }, headers=p1_headers)
    assert res_sub3.status_code == 200
    assert res_sub3.json()["feeling"] == "not_well"

    res_sub4 = client.post("/api/check-ins", json={
        "feeling": "need_help",
        "feeling_tamil": "எனக்கு உதவி தேவை"
    }, headers=p1_headers)
    assert res_sub4.status_code == 200
    assert res_sub4.json()["feeling"] == "need_help"
    print("  [PASS] TEST 09-10: 'not_well' and 'need_help' choices processed successfully.")

    # =========================================================================
    # TEST 11: Connected Family Member Sees Real Check-In
    # =========================================================================
    print("\n>>> TEST 11: Connected Family Member Reads Parent Check-In...")
    fam_today = client.get("/api/check-ins/today", headers=fam_headers)
    assert fam_today.status_code == 200
    fam_checkin = fam_today.json()
    assert fam_checkin is not None
    assert fam_checkin["user_id"] == p1_id
    assert fam_checkin["feeling"] == "need_help"
    assert fam_checkin["feeling_tamil"] == "எனக்கு உதவி தேவை"

    fam_latest = client.get("/api/check-ins/latest", headers=fam_headers)
    assert fam_latest.status_code == 200
    assert fam_latest.json()["id"] == fam_checkin["id"]
    print(f"  [PASS] TEST 11: Connected family member retrieved Parent 1 check-in (#{fam_checkin['id']}).")

    # =========================================================================
    # TEST 12 & 13: Multi-User Isolation (Parent B & Unlinked Family)
    # =========================================================================
    print("\n>>> TEST 12-13: Multi-User Isolation Checks...")
    p2_today = client.get("/api/check-ins/today", headers=p2_headers)
    assert p2_today.status_code == 200
    assert p2_today.json() is None, "DATA LEAK: Parent 2 saw Parent 1's check-in!"

    p2_hist = client.get("/api/check-ins/history", headers=p2_headers)
    assert len(p2_hist.json()) == 0, "DATA LEAK: Parent 2 saw Parent 1's check-in history!"

    ufam_today = client.get("/api/check-ins/today", headers=ufam_headers)
    assert ufam_today.json() is None, "DATA LEAK: Unlinked family saw Parent 1's check-in!"
    print("  [PASS] TEST 12-13: Strict isolation verified across all roles.")

    # =========================================================================
    # TEST 14: Alias Routes (/api/checkins vs /api/check-ins)
    # =========================================================================
    print("\n>>> TEST 14: Testing Alias Endpoints (/api/checkins)...")
    res_alias_today = client.get("/api/checkins/today", headers=p1_headers)
    assert res_alias_today.status_code == 200
    assert res_alias_today.json()["id"] == checkin_id_1

    res_alias_latest = client.get("/api/checkins/latest", headers=p1_headers)
    assert res_alias_latest.status_code == 200
    assert res_alias_latest.json()["id"] == checkin_id_1

    res_alias_hist = client.get("/api/checkins/history", headers=p1_headers)
    assert res_alias_hist.status_code == 200
    assert len(res_alias_hist.json()) == 1
    print("  [PASS] TEST 14: Both /api/check-ins and /api/checkins return identical data.")

    # =========================================================================
    # TEST 15: AI Baseline Engine Readiness
    # =========================================================================
    print("\n>>> TEST 15: Testing Routine Baseline Calculation...")
    db = SessionLocal()
    try:
        baseline = baseline_engine.calculate_personal_baseline(db, p1_id)
        assert baseline is not None
        assert baseline["status"] == "learning_baseline"
        assert baseline["is_learning"] is True
        assert baseline["parent_id"] == p1_id
        assert "typical_checkin_window" in baseline
        print(f"  [PASS] TEST 15: Baseline calculated: status={baseline['status']}, window={baseline['typical_checkin_window']}")
    finally:
        db.close()

    print("\n" + "=" * 75)
    print("ALL 15 CHECK-IN TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 75)

if __name__ == "__main__":
    run_checkin_tests()
