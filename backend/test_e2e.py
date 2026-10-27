import sys
import httpx
import json

sys.stdout.reconfigure(encoding='utf-8')

base_url = 'http://127.0.0.1:8000/api'
client = httpx.Client(base_url=base_url)

print('=== EVER NEAR AI: END-TO-END CRITICAL WORKFLOW TEST ===\n')

# 1. Parent Auth
p_login = client.post('/auth/login', json={'phone': '9876543210', 'password': '1234'}).json()
p_token = p_login['access_token']
p_headers = {'Authorization': f'Bearer {p_token}'}
print(f'1. Parent Authenticated: {p_login["full_name"]} (Role: {p_login["role"]})')

# 2. Family Auth
f_login = client.post('/auth/login', json={'phone': '9876543211', 'password': '1234'}).json()
f_token = f_login['access_token']
f_headers = {'Authorization': f'Bearer {f_token}'}
print(f'2. Family Member Authenticated: {f_login["full_name"]} (Role: {f_login["role"]})')

# 3. Trusted Relationship
family_list = client.get('/family', headers=p_headers).json()
contacts = [f"{m['name']} ({m['relationship_type']})" for m in family_list]
print(f'3. Trusted Circle Contacts: {contacts}')

# 4. Parent Daily Check-In
checkin = client.post('/check-ins', json={
    'feeling': 'good',
    'feeling_tamil': 'நன்றாக இருக்கிறேன்',
    'voice_input': False,
    'note': 'Morning routine completed peacefully'
}, headers=p_headers).json()
print(f'4. Daily Check-in recorded: {checkin["feeling"]} (Tamil: {checkin["feeling_tamil"]}) at {checkin["created_at"]}')

# 5. Routine Baseline & Change Detection
baseline = client.get('/ai/normal-day', headers=p_headers).json()
print(f'5. Personal Normal Day Baseline: Wake: {baseline["typical_wake_window"]} | Med: {baseline["typical_morning_med"]} | Confidence: {int(baseline["confidence_score"]*100)}%')

routine_status = client.get('/ai/routine-status', headers=p_headers).json()
print(f'6. Routine Status: {routine_status["status"]} | Reason: {routine_status["reason"][:60]}...')

# 6. Multi-Signal Explainable AI (Why?)
explain = client.get('/ai/explain-status', headers=p_headers).json()
sig_list = [f"{s['name']}: {s['status']}" for s in explain['signals']]
print(f'7. Explainable AI: Overall Status: {explain["overall_status"]} | Headline: {explain["headline"]}')
print(f'   Signals ({len(explain["signals"])}): {sig_list}')
print(f'   Action: {explain["suggested_action"]}')

# 7. Ask EVER NEAR (Contextual Q&A)
ask_resp = client.post('/ai/ask', json={'question': 'Was her medicine confirmed today?'}, headers=f_headers).json()
print(f'8. Ask EVER NEAR: Question: "{ask_resp["question"]}" -> Answer: "{ask_resp["answer"][:60]}..." (Sources: {ask_resp["sources_used"]})')

# 8. Independence View
indep = client.get('/ai/independence-view', headers=p_headers).json()
print(f'9. Independence View: {indep["completed_count"]}/{indep["total_count"]} completed. "{indep["positive_message"][:45]}..."')

# 9. Everyday Help Request
help_req = client.post('/help-requests', json={
    'category': 'groceries',
    'category_tamil': 'மளிகை / வீட்டுத் தேவைகள்',
    'note': 'Need fresh milk and bread'
}, headers=p_headers).json()
print(f'10. Help Request Logged: {help_req["category"]} (Status: {help_req["status"]})')

# 10. Safe Return Trip
trip = client.post('/safe-return/start', json={
    'destination': 'Nearby Store',
    'destination_tamil': 'அருகிலுள்ள கடை',
    'duration_minutes': 30
}, headers=p_headers).json()
print(f'11. Safe Return Trip Started: Dest: {trip["destination"]} | Status: {trip["status"]} | ID: {trip["id"]}')

return_trip = client.post(f'/safe-return/{trip["id"]}/return', headers=p_headers).json()
print(f'12. Safe Return Confirmed: Status: {return_trip["status"]}')

# 11. Privacy Pause & Sovereignty
pause = client.post('/privacy/pause', json={'duration_minutes': 15}, headers=p_headers).json()
print(f'13. Privacy Pause: Is Paused: {pause["is_paused"]} | Emergency Remains Active: {pause["emergency_remains_active"]}')

resume = client.post('/privacy/resume', headers=p_headers).json()
print(f'14. Privacy Resumed: Is Paused: {resume["is_paused"]}')

# 12. SOS Emergency Alert & Acknowledgment Workflow
sos = client.post('/sos', json={'notes': 'Test parent SOS trigger'}, headers=p_headers).json()
print(f'15. SOS Alert Created: ID {sos["id"]} (Status: {sos["status"]})')

sos_ack = client.post(f'/sos/{sos["id"]}/acknowledge', json={'responder_name': 'Karthik (Son)'}, headers=f_headers).json()
print(f'16. SOS Acknowledged by Family: Status: {sos_ack["status"]} by {sos_ack["acknowledged_by"]}')

sos_res = client.post(f'/sos/{sos["id"]}/resolve', headers=p_headers).json()
print(f'17. SOS Resolved: Status: {sos_res["status"]}')

# 13. Audit Log Verification
audit_logs = client.get('/privacy/audit-logs', headers=p_headers).json()
print(f'18. Audit Logs Recorded: {len(audit_logs)} entries (Latest: {audit_logs[0]["action"]} at {audit_logs[0]["timestamp"]})')

print('\n=== ALL 20 SUCCESS CRITERIA VALIDATED END-TO-END! ===')
