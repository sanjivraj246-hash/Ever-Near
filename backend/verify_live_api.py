import urllib.request
import json

def verify_live():
    # 1. Health
    req = urllib.request.urlopen("http://127.0.0.1:8000/health")
    data = json.loads(req.read().decode('utf-8'))
    print("1. LIVE SERVER HEALTH:", data)
    assert data["status"] == "ok"

    # 2. Login as Parent
    login_req = urllib.request.Request(
        "http://127.0.0.1:8000/api/auth/login",
        data=json.dumps({"phone": "9876543210", "password": "password123"}).encode('utf-8'),
        headers={"Content-Type": "application/json"}
    )
    try:
        login_res = urllib.request.urlopen(login_req)
        login_data = json.loads(login_res.read().decode('utf-8'))
        token = login_data["access_token"]
        print("2. LIVE PARENT AUTH TOKEN ACQUIRED")
    except Exception as e:
        # Fallback to test user password
        login_req = urllib.request.Request(
            "http://127.0.0.1:8000/api/auth/login",
            data=json.dumps({"phone": "9876543210", "password": "1234"}).encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )
        login_res = urllib.request.urlopen(login_req)
        login_data = json.loads(login_res.read().decode('utf-8'))
        token = login_data["access_token"]
        print("2. LIVE PARENT AUTH TOKEN ACQUIRED (via 1234)")

    # 3. Live Voice Route Check
    vr_req = urllib.request.Request(
        "http://127.0.0.1:8000/api/ai/voice-route",
        data=json.dumps({"spoken_text": "I need my medicine", "language": "en"}).encode('utf-8'),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    vr_res = urllib.request.urlopen(vr_req)
    vr_data = json.loads(vr_res.read().decode('utf-8'))
    print("3. LIVE AI VOICE ROUTING:", vr_data["intent"], "->", vr_data["target_flow"], vr_data["target_route"])
    assert vr_data["target_flow"] == "MEDICATION_FLOW"

    # 4. Live Cameras Check (with source transparency)
    cam_req = urllib.request.Request(
        "http://127.0.0.1:8000/api/cameras",
        headers={"Authorization": f"Bearer {token}"}
    )
    cam_res = urllib.request.urlopen(cam_req)
    cam_data = json.loads(cam_res.read().decode('utf-8'))
    print("4. LIVE CAMERAS:", len(cam_data), "camera(s)")
    if len(cam_data) > 0:
        print("   Camera 1:", cam_data[0]["name"], "| is_simulation:", cam_data[0].get("is_simulation"), "| source_type:", cam_data[0].get("source_type"))

    print("\n>>> LIVE VERIFICATION SUCCEEDED 100% <<<")

if __name__ == "__main__":
    verify_live()
