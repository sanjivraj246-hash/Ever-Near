import psycopg2
import sys

candidates = [
    'postgres', 'password', 'admin', 'root', '1234', '12345', '123456', '12345678', 
    'rajas', 'rajas123', 'rajas@123', 'Rajas@123', 'evernear', 'ever_near', 'evernear123',
    'Postgres', 'Postgres123', 'Postgres@123', 'password123', 'Password123', 'Password@123'
]

print("Testing candidate passwords for local PostgreSQL 18 on port 5432...")
matched = None
for pwd in candidates:
    try:
        conn = psycopg2.connect(host='127.0.0.1', port=5432, user='postgres', password=pwd, dbname='postgres', connect_timeout=2)
        print(f"--> SUCCESS! PostgreSQL password found: '{pwd}'")
        matched = pwd
        conn.close()
        break
    except Exception as e:
        if "password authentication failed" not in str(e):
            print(f"Non-auth error with '{pwd}': {e}")
            break

if not matched:
    print("None of the standard passwords matched.")
