import uuid
from fastapi.testclient import TestClient
from app.main import app

def run_tests():
    client = TestClient(app)

    rand_suffix = str(uuid.uuid4())[:6]
    parent_phone = f"9999{rand_suffix}"
    family_phone = f"8888{rand_suffix}"

    print("1. Testing Parent Registration...")
    reg_p = client.post("/api/auth/register", json={
        "phone": parent_phone,
        "full_name": "Meenakshi Amma",
        "role": "PARENT",
        "password": "password123",
        "preferred_name": "Amma",
        "language_pref": "ta"
    })
    assert reg_p.status_code == 200, f"Parent reg failed: {reg_p.text}"
    p_data = reg_p.json()
    assert p_data["role"] == "PARENT"
    assert "access_token" in p_data
    print(f"Parent registration OK: role={p_data['role']}, user_id={p_data['user_id']}")

    print("2. Testing Family Registration...")
    reg_f = client.post("/api/auth/register", json={
        "phone": family_phone,
        "full_name": "Suresh Kumar",
        "role": "FAMILY",
        "password": "password123",
        "preferred_name": "Suresh",
        "relationship_type": "Son",
        "language_pref": "en"
    })
    assert reg_f.status_code == 200, f"Family reg failed: {reg_f.text}"
    f_data = reg_f.json()
    assert f_data["role"] == "FAMILY"
    print(f"Family registration OK: role={f_data['role']}, user_id={f_data['user_id']}")

    print("3. Testing Login with correct credentials...")
    login_p = client.post("/api/auth/login", json={"phone": parent_phone, "password": "password123"})
    assert login_p.status_code == 200, f"Login failed: {login_p.text}"
    p_token = login_p.json()["access_token"]
    assert login_p.json()["role"] == "PARENT"

    print("4. Testing Login with wrong credentials (should fail with 401)...")
    login_fail = client.post("/api/auth/login", json={"phone": parent_phone, "password": "wrongpassword"})
    assert login_fail.status_code == 401, f"Expected 401 but got: {login_fail.status_code}"
    assert "Unable to sign in. Please check your details." in login_fail.json()["detail"]
    print(f"Login rejection OK: {login_fail.json()['detail']}")

    print("5. Testing /auth/me for Parent...")
    me_p = client.get("/api/auth/me", headers={"Authorization": f"Bearer {p_token}"})
    assert me_p.status_code == 200
    assert me_p.json()["preferred_name"] == "Amma"
    print(f"Parent profile OK: {me_p.json()['preferred_name']}, role={me_p.json()['role']}")

    print("6. Testing /auth/me for Family...")
    f_token = f_data["access_token"]
    me_f = client.get("/api/auth/me", headers={"Authorization": f"Bearer {f_token}"})
    assert me_f.status_code == 200
    assert me_f.json()["relationship_type"] == "Son"
    print(f"Family profile OK: {me_f.json()['preferred_name']}, relation={me_f.json()['relationship_type']}")

    print("7. Testing Seeded Accounts (Lakshmi Amma & Karthik)...")
    seeded_p = client.post("/api/auth/login", json={"phone": "9876543210", "password": "1234"})
    assert seeded_p.status_code == 200
    assert seeded_p.json()["role"] == "PARENT"

    seeded_f = client.post("/api/auth/login", json={"phone": "9876543211", "password": "1234"})
    assert seeded_f.status_code == 200
    assert seeded_f.json()["role"] == "FAMILY"

    print("\n>>> ALL AUTH TESTS PASSED PERFECTLY! <<<")

if __name__ == "__main__":
    run_tests()
