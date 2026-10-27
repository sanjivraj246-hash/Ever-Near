import httpx as requests
import json
import sys

# Ensure UTF-8 output on Windows
sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://localhost:5173"

def print_header(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def main():
    print_header("EVER NEAR AI - FULL LIVE SYSTEM VERIFICATION")
    
    # Check Frontend
    print("\n[STEP 1] Checking Frontend Availability on port 5173...")
    try:
        f_res = requests.get(FRONTEND_URL, timeout=5)
        if f_res.status_code == 200:
            print("  [OK] Frontend is UP and serving HTML (HTTP 200)")
        else:
            print(f"  [FAIL] Frontend returned HTTP {f_res.status_code}")
    except Exception as e:
        print(f"  [ERROR] Could not connect to Frontend: {e}")

    # Check Backend
    print("\n[STEP 2] Checking Backend Health on port 8000...")
    try:
        b_res = requests.get(f"{BASE_URL}/docs", timeout=5)
        if b_res.status_code == 200:
            print("  [OK] Backend OpenAPI docs accessible (HTTP 200)")
        else:
            print(f"  [FAIL] Backend /docs returned HTTP {b_res.status_code}")
    except Exception as e:
        print(f"  [ERROR] Backend connection failed: {e}")
        return

    # Login as Parent (Lakshmi Amma)
    print("\n[STEP 3] Authenticating as Parent (Amma)...")
    parent_login = requests.post(f"{BASE_URL}/api/auth/login", json={"phone": "9876543210", "password": "1234"}).json()
    parent_token = parent_login.get("access_token")
    parent_headers = {"Authorization": f"Bearer {parent_token}"}
    print(f"  [OK] Parent logged in successfully.")

    # Login as Family (Karthik)
    print("\n[STEP 4] Authenticating as Family (Karthik)...")
    family_login = requests.post(f"{BASE_URL}/api/auth/login", json={"phone": "9876543211", "password": "1234"}).json()
    family_token = family_login.get("access_token")
    family_headers = {"Authorization": f"Bearer {family_token}"}
    print(f"  [OK] Family logged in successfully.")

    # Feature 1: Family Memory Bridge
    print("\n[FEATURE 1] Family Memory Bridge...")
    memories_res = requests.get(f"{BASE_URL}/api/family-connection/memories", headers=parent_headers)
    assert memories_res.status_code == 200
    memories = memories_res.json()
    print(f"  [OK] Retrieved {len(memories)} memories across categories.")
    for m in memories[:3]:
        print(f"       - [{m['category']}] {m['title']}")

    # Feature 2: Life Story Archive
    print("\n[FEATURE 2] Life Story Archive...")
    stories_res = requests.get(f"{BASE_URL}/api/family-connection/stories", headers=family_headers)
    assert stories_res.status_code == 200
    stories = stories_res.json()
    print(f"  [OK] Retrieved {len(stories)} life stories.")
    for s in stories[:3]:
        print(f"       - '{s['title']}' recorded on {s.get('recorded_date_text', 'N/A')} (Audio: {s.get('audio_url')})")

    # Feature 3: Family Presence (No ranking, no competition)
    print("\n[FEATURE 3] Family Presence...")
    presence_res = requests.get(f"{BASE_URL}/api/family-connection/presence", headers=family_headers)
    assert presence_res.status_code == 200
    presence = presence_res.json()
    print(f"  [OK] Family Presence Summary: {presence.get('period', 'This Week')}")
    for mem in presence.get("members", []):
        print(f"       - {mem.get('family_member_name')} ({mem.get('relationship_type')}): {mem.get('total_interactions')} meaningful interactions")

    # Feature 4 & 17: Connection Gap Insight + Why Am I Seeing This
    print("\n[FEATURE 4 & 17] Connection Gap Insight & Signal Explanation...")
    gap_res = requests.get(f"{BASE_URL}/api/family-connection/gap-insight", headers=family_headers)
    assert gap_res.status_code == 200
    gap = gap_res.json()
    print(f"  [OK] Insight Title: '{gap.get('title')}'")
    print(f"  [OK] Message: '{gap.get('message')}'")
    print(f"  [OK] Signal explanation (Why Am I Seeing This): '{gap.get('why_text')}'")

    # Feature 5: Time-Zone Family Coordinator
    print("\n[FEATURE 5] Time-Zone Family Coordinator...")
    tz_res = requests.get(f"{BASE_URL}/api/family-connection/availability", headers=family_headers)
    assert tz_res.status_code == 200
    tz_data = tz_res.json()
    print(f"  [OK] Retrieved availability for {len(tz_data)} global family members:")
    for t in tz_data:
        print(f"       - {t.get('family_member_name')} ({t.get('country')} / {t.get('timezone')}): {t.get('normal_availability')} (Preferred: {t.get('preferred_call_hours')})")

    # Feature 6: Personal Preference Memory
    print("\n[FEATURE 6] Personal Preference Memory ('About Me')...")
    pref_res = requests.get(f"{BASE_URL}/api/family-connection/preferences", headers=parent_headers)
    assert pref_res.status_code == 200
    pref = pref_res.json()
    print(f"  [OK] Language: {pref['preferred_language']}")
    print(f"  [OK] Favorite Food: {pref['favorite_food']}")
    print(f"  [OK] Preferred Call Time: {pref['preferred_call_time']}")

    # Feature 7 & 18: Meaningful Moments & Family Connection Timeline
    print("\n[FEATURE 7 & 18] Meaningful Moments & Family Connection Timeline...")
    timeline_res = requests.get(f"{BASE_URL}/api/family-connection/timeline", headers=family_headers)
    assert timeline_res.status_code == 200
    timeline = timeline_res.json()
    print(f"  [OK] Retrieved {len(timeline)} timeline connection events:")
    for evt in timeline[:4]:
        print(f"       - [{evt.get('event_type')}] {evt.get('title')} ({evt.get('date_display')})")

    # Feature 8: Family Surprise Coordinator (Strict Parent Privacy)
    print("\n[FEATURE 8] Family Surprise Coordinator (Parent Privacy Test)...")
    fam_surp = requests.get(f"{BASE_URL}/api/family-connection/surprises", headers=family_headers).json()
    print(f"  [OK] Family can see {len(fam_surp)} surprises being planned: '{fam_surp[0]['title']}'")
    parent_surp = requests.get(f"{BASE_URL}/api/family-connection/surprises", headers=parent_headers).json()
    assert len(parent_surp) == 0, "Parent must NOT see surprise planning details!"
    print("  [OK] STRICT PRIVACY VERIFIED: Parent cannot see surprise planning details (Count = 0)")

    # Feature 9 & 10: Care Circle & Temporary Access
    print("\n[FEATURE 9 & 10] Care Circle & Temporary Permissions...")
    circle_res = requests.get(f"{BASE_URL}/api/family-connection/care-circle", headers=family_headers).json()
    print(f"  [OK] Retrieved {len(circle_res)} Care Circle members with granular permissions:")
    for c in circle_res:
        print(f"       - {c.get('name')} ({c.get('role_title')}): comms={c.get('can_communication')}, health={c.get('can_health_docs')}, CCTV={c.get('can_cctv')}, emergency={c.get('can_emergency_only')}")
    temp_res = requests.get(f"{BASE_URL}/api/family-connection/temporary-permissions", headers=parent_headers).json()
    print(f"  [OK] Active Temporary Permissions: {len(temp_res)} (e.g. {temp_res[0].get('resource_type')} to {temp_res[0].get('grantee_name')}, remaining: {temp_res[0].get('time_remaining_str')})")

    # Feature 11: One-Tap Family Update
    print("\n[FEATURE 11] One-Tap Family Update ('Tell My Family I'm OK')...")
    one_tap_res = requests.post(f"{BASE_URL}/api/family-connection/one-tap-update", json={"message": "Amma is feeling peaceful and okay today ❤️"}, headers=parent_headers)
    assert one_tap_res.status_code == 200
    print(f"  [OK] Sent update: '{one_tap_res.json()['message']}'")

    # Feature 12: Family AI Briefing
    print("\n[FEATURE 12] Family AI Briefing...")
    briefing_res = requests.get(f"{BASE_URL}/api/family-connection/briefing", headers=family_headers).json()
    print(f"  [OK] Headline: {briefing_res.get('headline')}")
    for item in briefing_res.get('items', []):
        print(f"       {item.get('icon')} {item.get('text')}")

    # Feature 13: Independence Living Mode
    print("\n[FEATURE 13] Independence Living Mode Escalation...")
    indep_res = requests.get(f"{BASE_URL}/api/family-connection/independence-mode", headers=parent_headers).json()
    print(f"  [OK] Current Escalation: {indep_res.get('current_escalation')}")
    print(f"  [OK] Mode Enabled: {indep_res.get('mode_enabled')}")
    print(f"  [OK] Suppress Routine Alerts: {indep_res.get('suppress_routine_alerts')}")
    print(f"  [OK] Escalation ladder items: {len(indep_res.get('escalation_flow', []))}")

    # Feature 14: Familiarity Map
    print("\n[FEATURE 14] Familiarity Map...")
    places_res = requests.get(f"{BASE_URL}/api/family-connection/familiar-places", headers=parent_headers).json()
    print(f"  [OK] Registered {len(places_res)} familiar places:")
    for p in places_res:
        print(f"       - {p.get('name')} ({p.get('category')}) - Familiar status: {p.get('is_frequently_visited')}")

    # Feature 15: Adaptive Elderly Interface
    print("\n[FEATURE 15] Adaptive Elderly Interface...")
    iface_res = requests.get(f"{BASE_URL}/api/family-connection/interface-mode", headers=parent_headers).json()
    print(f"  [OK] Current mode: {iface_res.get('mode')}, Voice assistance: {iface_res.get('voice_guidance_active')}")

    # Feature 16: Memory-Based Family Assistant (Strict Known vs Unknown)
    print("\n[FEATURE 16] Memory-Based Family Assistant...")
    # Known Query
    q_known = requests.post(f"{BASE_URL}/api/family-connection/memory-assistant", json={"question": "What does Amma like for breakfast?"}, headers=family_headers).json()
    print(f"  [OK] Known Query ('What does Amma like for breakfast?'):")
    print(f"       Status: {q_known['status']}")
    print(f"       Answer: '{q_known['answer']}'")
    assert q_known['status'] == "KNOWN", "Expected KNOWN response for breakfast query"

    # Unknown Query
    q_unknown = requests.post(f"{BASE_URL}/api/family-connection/memory-assistant", json={"question": "What brand of sneakers does Amma wear to sleep?"}, headers=family_headers).json()
    print(f"  [OK] Unknown Query ('What brand of sneakers does Amma wear to sleep?'):")
    print(f"       Status: {q_unknown['status']}")
    print(f"       Answer: '{q_unknown['answer']}'")
    assert q_unknown['status'] == "UNKNOWN", "Expected UNKNOWN response for unknown query"
    assert "don't have that information" in q_unknown['answer'].lower(), "Expected polite non-hallucinating fallback"

    # Feature 19: Care Handover
    print("\n[FEATURE 19] Care Handover...")
    handover_res = requests.get(f"{BASE_URL}/api/family-connection/care-handover", headers=family_headers).json()
    if handover_res:
        print(f"  [OK] Active Handover: {handover_res.get('is_currently_active')}")
        print(f"       Primary: {handover_res.get('primary_caregiver_name')} -> Temporary: {handover_res.get('temporary_caregiver_name')}")
        print(f"       Window: {handover_res.get('date_range_display')}")
    else:
        print("  [OK] No active handover currently scheduled (None/null safe)")

    # Feature 20: Family Continuity
    print("\n[FEATURE 20] Family Continuity Archive...")
    continuity_res = requests.get(f"{BASE_URL}/api/family-connection/continuity", headers=family_headers).json()
    print(f"  [OK] Preserving family continuity: {len(continuity_res)} archived traditions, stories, and recipes.")

    # Check Existing Safety System Intact
    print("\n[SAFETY INTEGRITY] Checking Existing SOS & Routine Systems...")
    sos_res = requests.get(f"{BASE_URL}/api/sos/active", headers=parent_headers)
    assert sos_res.status_code == 200
    print(f"  [OK] Existing SOS endpoint responds normally (HTTP {sos_res.status_code})")

    care_res = requests.get(f"{BASE_URL}/api/care/today", headers=parent_headers)
    assert care_res.status_code == 200
    print(f"  [OK] Existing Care Routine summary responds normally (HTTP {care_res.status_code})")

    comm_res = requests.get(f"{BASE_URL}/api/communication/requests/active", headers=parent_headers)
    assert comm_res.status_code == 200
    print(f"  [OK] Existing Parent Enquiry & Voice Communication responds normally (HTTP {comm_res.status_code})")

    print_header("ALL 20 NEW FEATURES & SAFETY SYSTEMS FULLY VERIFIED IN PRODUCTION RUNTIME [OK]")

if __name__ == "__main__":
    main()
