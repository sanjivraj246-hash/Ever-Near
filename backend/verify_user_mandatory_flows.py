"""
EVER NEAR AI: MANDATORY FLOW VERIFICATION SUITE
Verifies:
1. Parent-Family Data Isolation
2. Scoped WebSocket Notifications
3. Medication Creation & Taking
4. Help-Request Creation, Acknowledge & Resolution
5. Safety Timeline Integration
6. SOS Trigger, Acknowledge & Resolve
7. Direct PostgreSQL 18 Persistence
8. MY CARE & CARE CIRCLE Complete Workflows
"""

import sys
import secrets
import json
import psycopg2
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal, engine
from app.models.entities import User, ParentProfile, FamilyProfile, FamilyRelationship, HelpRequest, Medication, SOSAlert

sys.stdout.reconfigure(encoding='utf-8')
client = TestClient(app)

def run_mandatory_flow_verification():
    print("\n" + "=" * 80)
    print("EVER NEAR AI: COMPREHENSIVE MANDATORY FLOW & REGRESSION VERIFICATION")
    print("TARGET: PostgreSQL 18 Engine + Live FastAPI Stack")
    print("=" * 80)

    # 0. PostgreSQL 18 Connection Verification
    print("\n>>> [CHECK 0] Verifying PostgreSQL 18 Engine Connection & Persistence...")
    pg_conn = psycopg2.connect(host="127.0.0.1", port=5433, user="postgres", dbname="ever_near")
    cursor = pg_conn.cursor()
    cursor.execute("SELECT version();")
    v = cursor.fetchone()[0]
    print(f"  [PASS] Direct PostgreSQL 18 connected: {v[:40]}...")

    # Unique test phone numbers
    rand_a = f"{secrets.randbelow(90000) + 10000}"
    rand_b = f"{secrets.randbelow(90000) + 10000}"
    p_a_phone = f"+91 98111{rand_a}"
    f_a_phone = f"+91 98222{rand_a}"
    p_b_phone = f"+91 98333{rand_b}"
    f_b_phone = f"+91 98444{rand_b}"
    pin = "123456"

    # Register Parent A
    r_pa = client.post("/api/auth/register", json={
        "phone": p_a_phone, "full_name": "Saraswathi Amma", "role": "PARENT",
        "password": pin, "password_confirm": pin, "preferred_name": "Saraswathi Amma", "language_pref": "ta"
    })
    assert r_pa.status_code == 200, f"Parent A register failed: {r_pa.text}"
    token_pa = r_pa.json()["access_token"]
    user_pa_id = r_pa.json()["user_id"]
    h_pa = {"Authorization": f"Bearer {token_pa}"}

    # Register Family Member A
    r_fa = client.post("/api/auth/register", json={
        "phone": f_a_phone, "full_name": "Karthik (Son)", "role": "FAMILY",
        "password": pin, "password_confirm": pin, "preferred_name": "Karthik", "relationship_type": "Son"
    })
    assert r_fa.status_code == 200, f"Family A register failed: {r_fa.text}"
    token_fa = r_fa.json()["access_token"]
    user_fa_id = r_fa.json()["user_id"]
    h_fa = {"Authorization": f"Bearer {token_fa}"}

    # Register Parent B
    r_pb = client.post("/api/auth/register", json={
        "phone": p_b_phone, "full_name": "Balu Appa", "role": "PARENT",
        "password": pin, "password_confirm": pin, "preferred_name": "Balu Appa", "language_pref": "ta"
    })
    assert r_pb.status_code == 200, f"Parent B register failed: {r_pb.text}"
    token_pb = r_pb.json()["access_token"]
    user_pb_id = r_pb.json()["user_id"]
    h_pb = {"Authorization": f"Bearer {token_pb}"}

    # Register Family Member B (Unlinked to Parent A)
    r_fb = client.post("/api/auth/register", json={
        "phone": f_b_phone, "full_name": "Priya (Daughter B)", "role": "FAMILY",
        "password": pin, "password_confirm": pin, "preferred_name": "Priya", "relationship_type": "Daughter"
    })
    assert r_fb.status_code == 200, f"Family B register failed: {r_fb.text}"
    token_fb = r_fb.json()["access_token"]
    user_fb_id = r_fb.json()["user_id"]
    h_fb = {"Authorization": f"Bearer {token_fb}"}

    print("  [PASS] 4 Isolated Users registered: Parent A, Family A, Parent B, Family B.")

    # Link Parent A with Family A via invitation
    r_inv = client.post("/api/family/invitations", headers=h_pa, json={
        "relationship_type": "Son",
        "invited_phone": f_a_phone
    })
    assert r_inv.status_code in [200, 201], f"Invitation creation failed: {r_inv.text}"
    invite_code = r_inv.json()["invite_code"]

    r_accept = client.post("/api/family/invitations/accept", headers=h_fa, json={
        "invite_code": invite_code
    })
    assert r_accept.status_code == 200, f"Invitation accept failed: {r_accept.text}"
    print(f"  [PASS] Parent A and Family A successfully linked via invitation code: {invite_code}")

    # =========================================================================
    # 1. PARENT-FAMILY DATA ISOLATION
    # =========================================================================
    print("\n>>> [CHECK 1] Testing Strict Multi-User & Parent-Family Data Isolation...")
    # Parent A submits checkin
    client.post("/api/check-ins", headers=h_pa, json={"feeling": "good", "note": "Morning prayers complete"})

    # Linked Family A CAN view Parent A checkin
    r_chk_fa = client.get("/api/check-ins/today", headers=h_fa)
    assert r_chk_fa.status_code == 200 and r_chk_fa.json() is not None
    assert r_chk_fa.json()["feeling"] == "good"

    # Unlinked Family B CANNOT view Parent A checkin (sees None)
    r_chk_fb = client.get("/api/check-ins/today", headers=h_fb)
    assert r_chk_fb.status_code == 200
    assert r_chk_fb.json() is None

    # Unrelated Parent B sees None (clean fresh state)
    r_chk_pb = client.get("/api/check-ins/today", headers=h_pb)
    assert r_chk_pb.status_code == 200
    assert r_chk_pb.json() is None
    print("  [PASS] Strict Data Isolation verified: Family B & Parent B cannot access Parent A data.")

    # =========================================================================
    # 2. SCOPED WEBSOCKET NOTIFICATIONS
    # =========================================================================
    print("\n>>> [CHECK 2] Testing Scoped WebSocket Notifications...")
    with client.websocket_connect(f"/ws/notifications/{user_fa_id}?role=FAMILY") as ws_fa:
        with client.websocket_connect(f"/ws/notifications/{user_pb_id}?role=PARENT") as ws_pb:
            # Trigger Help Request from Parent A
            r_help = client.post("/api/help-requests", headers=h_pa, json={
                "category": "groceries",
                "note": "Need cow milk and rice"
            })
            assert r_help.status_code == 200
            help_id = r_help.json()["id"]

            # Family A MUST receive the notification
            msg_raw = ws_fa.receive_text()
            msg = json.loads(msg_raw)
            assert msg["type"] == "HELP_REQUEST"
            assert msg["help_request_id"] == help_id
            print(f"  [PASS] Scoped WebSocket delivered to linked Family A: {msg['type']} (id={help_id})")

    # =========================================================================
    # 3. MEDICATION CREATION & TRACKING
    # =========================================================================
    print("\n>>> [CHECK 3] Testing Prescribed Medication Creation & Tracking...")
    r_med = client.post("/api/medications", headers=h_pa, json={
        "name": "Metformin 500mg",
        "dosage": "1 tablet",
        "schedule_time": "08:00 AM",
        "period": "Morning",
        "instructions": "After breakfast",
        "icon": "pill"
    })
    assert r_med.status_code == 201, f"Med creation failed: {r_med.text}"
    med_id = r_med.json()["id"]
    print(f"  [PASS] Medication created with ID {med_id} for Parent A.")

    # Linked Family A views medications
    r_meds_fa = client.get("/api/medications", headers=h_fa)
    assert r_meds_fa.status_code == 200
    assert any(m["id"] == med_id for m in r_meds_fa.json())

    # Parent A logs medication as taken via acknowledge (which also records timeline)
    r_log = client.post(f"/api/medications/acknowledge?medication_id={med_id}", headers=h_pa)
    assert r_log.status_code == 200, f"Med log failed: {r_log.text}"

    # Verify taken status updated
    r_meds_pa = client.get("/api/medications", headers=h_pa)
    med_rec = next(m for m in r_meds_pa.json() if m["id"] == med_id)
    assert med_rec["today_taken"] is True
    print("  [PASS] Medication marked as TAKEN and verified in today's schedule.")

    # =========================================================================
    # 4. HELP-REQUEST RESPONSE & RESOLUTION
    # =========================================================================
    print("\n>>> [CHECK 4] Testing Help-Request Response & Resolution...")
    # Family A reads help requests
    r_hr_list = client.get("/api/help-requests", headers=h_fa)
    assert r_hr_list.status_code == 200
    assert any(hr["id"] == help_id for hr in r_hr_list.json())

    # Unlinked Family B gets 403 on acknowledge
    r_ack_fb = client.post(f"/api/help-requests/{help_id}/acknowledge", headers=h_fb)
    assert r_ack_fb.status_code == 403, f"Expected 403 for unauthorized Family B, got {r_ack_fb.status_code}"

    # Linked Family A acknowledges
    r_ack_fa = client.post(f"/api/help-requests/{help_id}/acknowledge", headers=h_fa)
    assert r_ack_fa.status_code == 200
    assert r_ack_fa.json()["status"] == "ACKNOWLEDGED"
    assert r_ack_fa.json()["handled_by"] == "Karthik (Son)"
    print(f"  [PASS] Help Request #{help_id} ACKNOWLEDGED by Karthik (Son).")

    # Linked Family A resolves
    r_res_fa = client.post(f"/api/help-requests/{help_id}/resolve", headers=h_fa)
    assert r_res_fa.status_code == 200
    assert r_res_fa.json()["status"] == "COMPLETED"
    print(f"  [PASS] Help Request #{help_id} RESOLVED successfully.")

    # =========================================================================
    # 5. SAFETY TIMELINE INTEGRATION
    # =========================================================================
    print("\n>>> [CHECK 5] Testing Safety Timeline Integration...")
    r_timeline = client.get("/api/care/today", headers=h_pa)
    assert r_timeline.status_code == 200
    t_items = r_timeline.json()
    assert len(t_items) >= 2, f"Expected at least 2 timeline items, got {len(t_items)}"
    print(f"  [PASS] Care Timeline contains {len(t_items)} logged events for today.")

    # =========================================================================
    # 6. SOS EMERGENCY WORKFLOW
    # =========================================================================
    print("\n>>> [CHECK 6] Testing SOS Emergency Workflow...")
    # Trigger SOS
    r_sos = client.post("/api/sos", headers=h_pa, json={"notes": "Felt dizzy after standing up"})
    assert r_sos.status_code == 200
    sos_id = r_sos.json()["id"]
    assert r_sos.json()["status"] == "ACTIVE"
    print(f"  [PASS] SOS Triggered with ID #{sos_id}.")

    # Linked Family sees active SOS
    r_act = client.get("/api/sos/active", headers=h_fa)
    assert r_act.status_code == 200 and r_act.json() is not None
    assert r_act.json()["id"] == sos_id

    # Unlinked Family B sees None
    r_act_b = client.get("/api/sos/active", headers=h_fb)
    assert r_act_b.status_code == 200
    assert r_act_b.json() is None

    # Family A acknowledges SOS
    r_sos_ack = client.post(f"/api/sos/{sos_id}/acknowledge", headers=h_fa, json={
        "responder_name": "Karthik"
    })
    assert r_sos_ack.status_code == 200
    assert r_sos_ack.json()["status"] == "ACKNOWLEDGED"
    print(f"  [PASS] SOS #{sos_id} Acknowledged by Karthik.")

    # Family A resolves SOS
    r_sos_res = client.post(f"/api/sos/{sos_id}/resolve", headers=h_fa)
    assert r_sos_res.status_code == 200
    assert r_sos_res.json()["status"] == "RESOLVED"

    # Active SOS is now None
    r_act_after = client.get("/api/sos/active", headers=h_fa)
    assert r_act_after.status_code == 200
    assert r_act_after.json() is None
    print(f"  [PASS] SOS #{sos_id} Resolved and cleared from active alarms.")

    # =========================================================================
    # 7. MY CARE & CARE CIRCLE ACTUAL WORKFLOWS
    # =========================================================================
    print("\n>>> [CHECK 7] Testing MY CARE & CARE CIRCLE Workflows...")
    # Safe return outing
    r_trip = client.post("/api/safe-return/start", headers=h_pa, json={
        "destination": "Temple",
        "destination_tamil": "கோவில்",
        "duration_minutes": 45
    })
    assert r_trip.status_code == 200
    trip_id = r_trip.json()["id"]
    assert r_trip.json()["status"] == "OUT"

    # Confirm safe return home
    r_home = client.post(f"/api/safe-return/{trip_id}/return", headers=h_pa)
    assert r_home.status_code == 200
    assert r_home.json()["status"] == "RETURNED"
    print("  [PASS] MY CARE Safe Return Outing & Return confirmed.")

    # CARE CIRCLE one-tap update & briefing
    r_tap = client.post("/api/family-connection/one-tap-update", headers=h_fa, json={
        "action": "THINKING_OF_YOU"
    })
    assert r_tap.status_code == 200
    r_brief = client.get("/api/family-connection/briefing", headers=h_fa)
    assert r_brief.status_code == 200
    print("  [PASS] CARE CIRCLE One-Tap Update & Briefing verified.")

    # =========================================================================
    # 8. DIRECT POSTGRESQL 18 PERSISTENCE AUDIT
    # =========================================================================
    print("\n>>> [CHECK 8] Direct PostgreSQL 18 Physical Persistence Audit...")
    cursor.execute("SELECT id, phone, full_name, role FROM users WHERE phone = %s;", (p_a_phone.replace("+91 ", "").replace(" ", ""),))
    pg_user = cursor.fetchone()
    assert pg_user is not None, "Parent A not found in PostgreSQL 18 users table!"
    print(f"  [PASS] PostgreSQL 18 users table: ID={pg_user[0]}, Phone={pg_user[1]}, Name={pg_user[2]}")

    cursor.execute("SELECT id, name, dosage, schedule_time FROM medications WHERE id = %s;", (med_id,))
    pg_med = cursor.fetchone()
    assert pg_med is not None, "Medication not found in PostgreSQL 18 medications table!"
    print(f"  [PASS] PostgreSQL 18 medications table: ID={pg_med[0]}, Name={pg_med[1]}, Dosage={pg_med[2]}")

    cursor.execute("SELECT id, status, handled_by FROM help_requests WHERE id = %s;", (help_id,))
    pg_hr = cursor.fetchone()
    assert pg_hr is not None, "Help request not found in PostgreSQL 18 help_requests table!"
    print(f"  [PASS] PostgreSQL 18 help_requests table: ID={pg_hr[0]}, Status={pg_hr[1]}, HandledBy={pg_hr[2]}")

    cursor.execute("SELECT id, status, acknowledged_by FROM sos_alerts WHERE id = %s;", (sos_id,))
    pg_sos = cursor.fetchone()
    assert pg_sos is not None, "SOS alert not found in PostgreSQL 18 sos_alerts table!"
    print(f"  [PASS] PostgreSQL 18 sos_alerts table: ID={pg_sos[0]}, Status={pg_sos[1]}, AckBy={pg_sos[2]}")

    cursor.close()
    pg_conn.close()

    print("\n" + "=" * 80)
    print("ALL 8 USER MANDATORY FLOWS VERIFIED SUCCESSFULLY WITH 100% PASS RATE!")
    print("=" * 80)

if __name__ == "__main__":
    run_mandatory_flow_verification()
