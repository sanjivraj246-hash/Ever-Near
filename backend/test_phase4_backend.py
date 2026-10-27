import sys
import uuid
from fastapi.testclient import TestClient

sys.stdout.reconfigure(encoding='utf-8')
from app.main import app

def run_phase4_verification():
    client = TestClient(app)

    print("=== PHASE 4: FASTAPI BACKEND FOUNDATION VERIFICATION ===")

    # 1. Health check
    print("\n1. Verifying Health Check...")
    h = client.get("/health")
    assert h.status_code == 200, f"Health check failed: {h.text}"
    assert h.json()["status"] == "ok"
    print("✓ /health passed:", h.json())

    # 2. Authentication Dependency (401 when unauthenticated)
    print("\n2. Verifying Unauthenticated Protection...")
    unauth_p = client.get("/api/parent/profile")
    assert unauth_p.status_code == 401, f"Expected 401 for unauth, got {unauth_p.status_code}"
    print("✓ Unauthenticated request rejected with 401:", unauth_p.json()["detail"])

    # 3. Register & Login Parent
    print("\n3. Testing Parent Auth & Profile...")
    suffix = str(uuid.uuid4())[:6]
    p_phone = f"9811{suffix}"
    reg_p = client.post("/api/auth/register", json={
        "phone": p_phone,
        "full_name": "Parvathi Amma",
        "role": "PARENT",
        "password": "SecurePassword123",
        "preferred_name": "Amma",
        "language_pref": "ta"
    })
    assert reg_p.status_code == 200, f"Parent registration failed: {reg_p.text}"
    p_token = reg_p.json()["access_token"]
    p_headers = {"Authorization": f"Bearer {p_token}"}
    p_id = reg_p.json()["user_id"]
    print(f"✓ Parent Registered (user_id={p_id}, role=PARENT)")

    # 4. Register & Login Family Member
    print("\n4. Testing Family Auth & Profile...")
    f_phone = f"9822{suffix}"
    reg_f = client.post("/api/auth/register", json={
        "phone": f_phone,
        "full_name": "Venkatesh",
        "role": "FAMILY",
        "password": "SecurePassword123",
        "preferred_name": "Venkat",
        "relationship_type": "Son",
        "language_pref": "en"
    })
    assert reg_f.status_code == 200, f"Family registration failed: {reg_f.text}"
    f_token = reg_f.json()["access_token"]
    f_headers = {"Authorization": f"Bearer {f_token}"}
    f_id = reg_f.json()["user_id"]
    print(f"✓ Family Member Registered (user_id={f_id}, role=FAMILY)")

    # 5. Role-Based Authorization
    print("\n5. Verifying Role-Based Authorization...")
    # Parent accessing /api/parent/profile -> 200 OK
    p_prof = client.get("/api/parent/profile", headers=p_headers)
    assert p_prof.status_code == 200, f"Parent profile failed: {p_prof.text}"
    assert p_prof.json()["role"] == "PARENT"
    print("✓ Parent accessing /api/parent/profile: 200 OK")

    # Family accessing /api/parent/profile -> 403 Forbidden
    f_on_p = client.get("/api/parent/profile", headers=f_headers)
    assert f_on_p.status_code == 403, f"Expected 403 for Family on Parent endpoint, got {f_on_p.status_code}"
    print("✓ Family accessing /api/parent/profile: 403 Forbidden properly enforced")

    # Family accessing /api/family/profile -> 200 OK
    f_prof = client.get("/api/family/profile", headers=f_headers)
    assert f_prof.status_code == 200, f"Family profile failed: {f_prof.text}"
    assert f_prof.json()["relationship_type"] == "Son"
    print("✓ Family accessing /api/family/profile: 200 OK")

    # 6. Identifying User, Role, and Parent/Family Relationship
    print("\n6. Verifying User, Role & Relationship Identification...")
    # Link family to parent
    inv = client.post("/api/family/invite", json={
        "phone": f_phone,
        "name": "Venkatesh",
        "relationship_type": "Son"
    }, headers=p_headers)
    assert inv.status_code == 200
    print("✓ Family linked to Parent")

    # Query context from parent view
    ctx_p = client.get("/api/parent/context", headers=p_headers)
    assert ctx_p.status_code == 200
    p_context = ctx_p.json()
    assert p_context["role"] == "PARENT"
    assert len(p_context["relationships"]) >= 1
    rel_names = [r["name"] for r in p_context["relationships"]]
    print(f"✓ Parent Context Identified: role={p_context['role']}, linked family members={rel_names}")

    # Query parent-status from family view
    p_status = client.get("/api/family/parent-status", headers=f_headers)
    assert p_status.status_code == 200
    print(f"✓ Family Identified Linked Parent: parent={p_status.json()['preferred_name']}")

    # 7. Checkins Endpoint (/api/checkins)
    print("\n7. Verifying /api/checkins...")
    c_post = client.post("/api/checkins", json={
        "feeling": "good",
        "feeling_tamil": "நன்றாக உணர்கிறேன்",
        "note": "Morning coffee finished peacefully"
    }, headers=p_headers)
    assert c_post.status_code == 200
    print(f"✓ Check-in Submitted: {c_post.json()['feeling']}")

    c_today = client.get("/api/checkins/today", headers=p_headers)
    assert c_today.status_code == 200
    assert c_today.json() is not None
    assert c_today.json()["feeling"] == "good"
    print("✓ /api/checkins/today returned today's checkin")

    # 8. Medications Endpoint (/api/medications)
    print("\n8. Verifying /api/medications...")
    meds = client.get("/api/medications", headers=p_headers)
    assert meds.status_code == 200
    med_list = meds.json()
    print(f"✓ /api/medications returned {len(med_list)} items")
    if med_list:
        first_id = med_list[0]["id"]
        log_res = client.post(f"/api/medications/{first_id}/log", json={"status": "TAKEN"}, headers=p_headers)
        assert log_res.status_code == 200
        print(f"✓ /api/medications/{first_id}/log recorded TAKEN")

    # 9. Alerts Endpoint (/api/alerts)
    print("\n9. Verifying /api/alerts...")
    alert_res = client.post("/api/alerts", json={"notes": "Test emergency trigger"}, headers=p_headers)
    assert alert_res.status_code == 200
    alert_id = alert_res.json()["id"]
    print(f"✓ /api/alerts created alert #{alert_id} (status: {alert_res.json()['status']})")

    active_alert = client.get("/api/alerts/active", headers=f_headers)
    assert active_alert.status_code == 200
    assert active_alert.json() is not None
    print(f"✓ /api/alerts/active detected alert #{active_alert.json()['id']}")

    ack_res = client.post(f"/api/alerts/{alert_id}/acknowledge", json={"responder_name": "Venkatesh (Son)"}, headers=f_headers)
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "ACKNOWLEDGED"
    print(f"✓ /api/alerts/{alert_id}/acknowledge marked ACKNOWLEDGED by {ack_res.json()['acknowledged_by']}")

    resolve_res = client.post(f"/api/alerts/{alert_id}/resolve", headers=p_headers)
    assert resolve_res.status_code == 200
    print("✓ /api/alerts marked RESOLVED")

    # 10. Request Validation (422 formatting without stack traces)
    print("\n10. Verifying Request Validation & Clean Error Formatting...")
    val_err = client.post("/api/auth/register", json={"invalid_field": "no data"})
    assert val_err.status_code == 422
    assert "detail" in val_err.json()
    assert "errors" in val_err.json()
    print(f"✓ 422 Validation Formatted cleanly: {val_err.json()['detail']}")

    print("\n=======================================================")
    print(">>> ALL PHASE 4 FASTAPI FOUNDATION TESTS PASSED 100%! <<<")
    print("=======================================================\n")

if __name__ == "__main__":
    run_phase4_verification()
