"""
EVER NEAR AI — Real Functional System Comprehensive Acceptance Test Suite
Tests all 22 steps and the complete 18-step Final Acceptance Flow.
"""
import sys
import os
import unittest
from fastapi.testclient import TestClient

# Ensure backend root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.db.session import SessionLocal, Base, engine
from app.database.seed import init_db
from app.models.entities import (
    User, DailyCheckIn, CareTimelineItem, AuditLog,
    AIAlert, AIAlertEvidence, PrivacySetting, CommunicationRequest
)

class TestRealFunctionalSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize DB and seed
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        init_db(db)
        db.close()
        cls.client = TestClient(app)

    def test_01_authentication_parent_and_family(self):
        """Step 1 & Acceptance Step 1: Real JWT authentication and role authorization"""
        # Parent login
        p_resp = self.client.post("/api/auth/login", json={"phone": "9876543210", "password": "1234"})
        self.assertEqual(p_resp.status_code, 200, f"Parent login failed: {p_resp.text}")
        p_data = p_resp.json()
        self.assertIn("access_token", p_data)
        self.assertEqual(p_data["role"], "PARENT")
        self.__class__.parent_token = p_data["access_token"]
        self.__class__.parent_headers = {"Authorization": f"Bearer {self.parent_token}"}

        # Family login
        f_resp = self.client.post("/api/auth/login", json={"phone": "9876543211", "password": "1234"})
        self.assertEqual(f_resp.status_code, 200, f"Family login failed: {f_resp.text}")
        f_data = f_resp.json()
        self.assertIn("access_token", f_data)
        self.assertEqual(f_data["role"], "FAMILY")
        self.__class__.family_token = f_data["access_token"]
        self.__class__.family_headers = {"Authorization": f"Bearer {self.family_token}"}

    def test_02_parent_checkin_and_baseline_calculation(self):
        """Step 3, 4 & Acceptance Steps 2, 3, 4: Real check-in persistence & Personal Care Baseline Engine"""
        checkin_payload = {
            "feeling": "peaceful",
            "feeling_tamil": "அமைதியாக",
            "note": "Took morning tea on veranda",
            "voice_input": False
        }
        resp = self.client.post("/api/checkins", json=checkin_payload, headers=self.parent_headers)
        self.assertEqual(resp.status_code, 200, f"Check-in failed: {resp.text}")
        data = resp.json()
        self.assertEqual(data["feeling"], "peaceful")

        # Verify DB persistence
        db = SessionLocal()
        ck = db.query(DailyCheckIn).filter(DailyCheckIn.user_id == 1).order_by(DailyCheckIn.created_at.desc()).first()
        self.assertIsNotNone(ck)
        self.assertEqual(ck.feeling, "peaceful")

        # Verify Care Timeline item created
        tl = db.query(CareTimelineItem).filter(CareTimelineItem.event_category == "CHECKIN").first()
        self.assertIsNotNone(tl)

        # Step 4: Baseline Engine query
        b_resp = self.client.get("/api/ai/baseline", headers=self.parent_headers)
        self.assertEqual(b_resp.status_code, 200, f"Baseline query failed: {b_resp.text}")
        b_data = b_resp.json()
        self.assertIn("typical_checkin_window", b_data)
        self.assertIn("routine_consistency_score", b_data)
        self.assertIn("expected_active_minutes", b_data)
        db.close()

    def test_03_medication_acknowledgement(self):
        """Step 2: POST /medications/acknowledge"""
        resp = self.client.post("/api/medications/acknowledge", headers=self.parent_headers)
        self.assertEqual(resp.status_code, 200, f"Medication acknowledge failed: {resp.text}")
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["action"], "TAKEN")

    def test_04_simulate_abnormal_routine_and_isolation_forest(self):
        """Step 5, 6, 8, 16 & Acceptance Steps 5, 6, 7, 8, 9: Isolation Forest Anomaly Detection & Context Engine"""
        sim_resp = self.client.post(
            "/api/ai/simulate-abnormal-routine",
            json={"scenario": "abnormal_day"},
            headers=self.family_headers
        )
        self.assertEqual(sim_resp.status_code, 200, f"Simulation failed: {sim_resp.text}")
        sim_data = sim_resp.json()
        self.assertTrue(sim_data["alert_created"])
        self.assertGreater(sim_data["change_score"], 0.50)
        self.assertIsNotNone(sim_data["alert_id"])
        self.__class__.generated_alert_id = sim_data["alert_id"]

        # Verify Isolation Forest scored the anomaly
        self.assertIn("anomaly_score", sim_data)

        # Verify DB records
        db = SessionLocal()
        alert = db.query(AIAlert).filter(AIAlert.id == self.generated_alert_id).first()
        self.assertIsNotNone(alert)
        self.assertEqual(alert.status, "ACTIVE")
        self.assertGreater(alert.change_score, 0.50)

        evidences = db.query(AIAlertEvidence).filter(AIAlertEvidence.alert_id == alert.id).all()
        self.assertGreaterEqual(len(evidences), 2, "Expected multiple supporting signals")
        db.close()

    def test_05_family_receives_alert_and_sees_why(self):
        """Step 7 & Acceptance Steps 10, 11, 12: Family receives alert and views 'Why am I seeing this?'"""
        # Family lists alerts
        alerts_resp = self.client.get("/api/ai/alerts", headers=self.family_headers)
        self.assertEqual(alerts_resp.status_code, 200)
        alerts = alerts_resp.json()
        self.assertGreaterEqual(len(alerts), 1)

        # Family views explanation
        exp_resp = self.client.get(f"/api/ai/alerts/{self.generated_alert_id}/explanation", headers=self.family_headers)
        self.assertEqual(exp_resp.status_code, 200, f"Explanation failed: {exp_resp.text}")
        exp = exp_resp.json()
        self.assertIn("detected_change", exp)
        self.assertIn("baseline_comparison", exp)
        self.assertIn("supporting_signals", exp)
        self.assertIn("change_score", exp)
        self.assertIn("anomaly_score", exp)
        self.assertIn("system_interpretation", exp)
        self.assertIn("suggested_action", exp)
        self.assertIn("disclaimer", exp)
        self.assertFalse("sick" in exp["system_interpretation"].lower(), "System must not diagnose diseases")

    def test_06_family_checkin_and_parent_response_loop(self):
        """Step 16 & Acceptance Steps 13, 14, 15, 16: Check In -> Parent Responds -> Resolved"""
        # Family clicks "Check In"
        checkin_resp = self.client.post(
            f"/api/ai/alerts/{self.generated_alert_id}/family-checkin",
            headers=self.family_headers
        )
        self.assertEqual(checkin_resp.status_code, 200)
        c_data = checkin_resp.json()
        self.assertEqual(c_data["status"], "CHECKED_IN")

        # Parent responds "I'm okay"
        resp_parent = self.client.post(
            f"/api/ai/alerts/{self.generated_alert_id}/parent-respond",
            headers=self.parent_headers
        )
        self.assertEqual(resp_parent.status_code, 200)
        r_data = resp_parent.json()
        self.assertEqual(r_data["status"], "RESOLVED")
        self.assertIsNotNone(r_data["resolved_at"])
        self.assertIn("I'm okay", r_data["parent_response_text"])

    def test_07_family_enquiry_workflow(self):
        """Step 9: Real Family Enquiry Workflow (Parent initiates -> Family responds)"""
        # Parent initiates Talk to Family
        enq_payload = {
            "family_member_name": "Karthik",
            "reason_category": "want_to_talk",
            "reason_text": "Want to talk about the garden",
            "priority": "NORMAL"
        }
        enq_resp = self.client.post("/api/family/enquiries", json=enq_payload, headers=self.parent_headers)
        self.assertEqual(enq_resp.status_code, 200, f"Create enquiry failed: {enq_resp.text}")
        enq_data = enq_resp.json()
        enquiry_id = enq_data["id"]
        self.assertEqual(enq_data["status"], "PENDING")

        # Family selects "I'm Responding"
        patch_payload = {
            "action": "RESPONDING",
            "message": "Karthik is responding."
        }
        patch_resp = self.client.patch(f"/api/family/enquiries/{enquiry_id}", json=patch_payload, headers=self.family_headers)
        self.assertEqual(patch_resp.status_code, 200, f"Patch enquiry failed: {patch_resp.text}")
        p_data = patch_resp.json()
        self.assertEqual(p_data["status"], "RESPONDING")
        self.assertIn("Karthik", p_data["responding_caregiver"])

    def test_08_sos_emergency_flow(self):
        """Step 10: Real SOS Emergency Workflow"""
        sos_payload = {"notes": "Parent pressed SOS confirmation button"}
        sos_resp = self.client.post("/api/sos", json=sos_payload, headers=self.parent_headers)
        self.assertEqual(sos_resp.status_code, 200, f"SOS trigger failed: {sos_resp.text}")
        s_data = sos_resp.json()
        self.assertEqual(s_data["status"], "ACTIVE")
        sos_id = s_data["id"]

        # Family acknowledges SOS
        ack_resp = self.client.post(f"/api/sos/{sos_id}/acknowledge", json={"responder_name": "Karthik"}, headers=self.family_headers)
        self.assertEqual(ack_resp.status_code, 200)
        self.assertEqual(ack_resp.json()["status"], "ACKNOWLEDGED")

    def test_09_backend_enforced_privacy_controls(self):
        """Step 13: Real backend-enforced Privacy Controls (CCTV: OFF blocks Family)"""
        # Ensure CCTV is OFF in privacy settings
        priv_update = {"cctv_access": False, "location_sharing": False}
        p_resp = self.client.post("/api/privacy/settings", json=priv_update, headers=self.parent_headers)
        self.assertEqual(p_resp.status_code, 200)
        self.assertFalse(p_resp.json()["cctv_access"])

        # Family attempts to access CCTV -> MUST BE FORBIDDEN (403)
        cam_resp = self.client.get("/api/cameras", headers=self.family_headers)
        self.assertEqual(cam_resp.status_code, 403, f"Expected 403 Forbidden for CCTV when privacy is OFF, got: {cam_resp.status_code}")
        self.assertIn("privacy", cam_resp.json()["detail"].lower())

    def test_10_care_timeline_and_audit_logs(self):
        """Step 11, 14 & Acceptance Steps 17, 18: Persisted Care Timeline and Audit Logs"""
        # Care Timeline
        tl_resp = self.client.get("/api/care/timeline", headers=self.family_headers)
        self.assertEqual(tl_resp.status_code, 200, f"Timeline failed: {tl_resp.text}")
        tl_data = tl_resp.json()
        self.assertGreaterEqual(len(tl_data), 4, "Expected persisted care timeline events")

        # Audit Logs
        audit_resp = self.client.get("/api/audit-logs", headers=self.family_headers)
        self.assertEqual(audit_resp.status_code, 200, f"Audit logs failed: {audit_resp.text}")
        audit_data = audit_resp.json()
        self.assertGreaterEqual(len(audit_data), 5, "Expected persisted audit log events")
        actions = [a["action"] for a in audit_data]
        self.assertTrue(any("AI_ANOMALY" in a for a in actions), "AI anomaly audit log missing")
        self.assertTrue(any("PRIVACY" in a for a in actions), "Privacy audit log missing")

if __name__ == "__main__":
    unittest.main()
